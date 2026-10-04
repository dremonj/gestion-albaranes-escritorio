from decimal import Decimal

import pytest

from gestion_albaranes import auth
from gestion_albaranes.errores import ErrorUsuario
from gestion_albaranes.logica import Gestion, calcular_totales, cant, dec, euros, leer_fecha

from .conftest import linea


# ---------- Cálculos y formatos ----------


def test_totales_con_descuento_y_desglose_de_iva():
    t = calcular_totales([
        {"cantidad": 3, "precio": 10, "descuento": 10, "iva": 21},  # 27,00
        {"cantidad": 2, "precio": 5, "descuento": 0, "iva": 21},  # 10,00
        {"cantidad": 4, "precio": 2.5, "descuento": 0, "iva": 4},  # 10,00
    ])
    assert t["base"] == Decimal("47.00")
    assert [(d["iva"], d["base"], d["cuota"]) for d in t["desglose"]] == [(21, Decimal("37.00"), Decimal("7.77")), (4, Decimal("10.00"), Decimal("0.40"))]
    assert t["total"] == Decimal("55.17")
    assert t["unidades"] == Decimal("9")


def test_numeros_con_coma_y_formato_espanol():
    assert dec("1,5") == Decimal("1.5")
    assert dec("1.234,56") == Decimal("1234.56")
    assert dec("abc") is None
    assert euros(Decimal("1234.5")) == "1.234,50 €"
    assert cant(2.5) == "2,5"
    assert cant(12) == "12"


def test_fechas():
    assert leer_fecha("04/10/2026") == "2026-10-04"
    assert leer_fecha("2026-10-04") == "2026-10-04"
    with pytest.raises(ErrorUsuario, match="no es válida"):
        leer_fecha("31/02/2026")


# ---------- Clientes y productos ----------


def test_referencia_y_nif_en_mayusculas_y_sin_repetir(g, datos):
    assert g.producto(datos["p1"])["referencia"] == "P-1"
    assert g.cliente(datos["cliente"])["nif"] == "B123"
    with pytest.raises(ErrorUsuario, match="Ya existe"):
        g.guardar_producto({"referencia": "p-1", "nombre": "Otro", "precio": 1})


def test_stock_inicial_registrado_como_movimiento(g, datos):
    movs = g.movimientos(datos["p1"])
    assert len(movs) == 1 and movs[0]["cantidad"] == 50 and movs[0]["motivo"] == "Stock inicial"


def test_editar_producto_no_cambia_stock(g, datos):
    g.guardar_producto({"id": datos["p1"], "referencia": "P-1", "nombre": "Renombrado", "precio": 12, "iva": 21, "stock": 999})
    p = g.producto(datos["p1"])
    assert p["nombre"] == "Renombrado" and p["stock"] == 50


def test_ajustar_unidades(g, datos):
    pid = datos["p1"]
    assert g.ajustar_stock(pid, "entrada", 5) == Decimal("55")
    assert g.ajustar_stock(pid, "salida", "2,5") == Decimal("52.5")
    assert g.ajustar_stock(pid, "fijar", 40, "Recuento") == Decimal("40")
    assert g.movimientos(pid)[0]["cantidad"] == -12.5
    with pytest.raises(ErrorUsuario, match="No hay suficiente stock"):
        g.ajustar_stock(pid, "salida", 41)
    with pytest.raises(ErrorUsuario, match="no cambia"):
        g.ajustar_stock(pid, "fijar", 40)


def test_productos_bajo_minimo(g, datos):
    assert g.productos_bajo_minimo() == []
    g.ajustar_stock(datos["p1"], "fijar", 5)
    assert [p["id"] for p in g.productos_bajo_minimo()] == [datos["p1"]]


def test_archivar_en_vez_de_borrar_si_hay_albaranes(g, datos):
    g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 1)]})
    assert g.eliminar_producto(datos["p1"]) == "archivado"
    assert g.eliminar_producto(datos["p2"]) == "eliminado"
    assert g.eliminar_cliente(datos["cliente"]) == "archivado"
    assert g.clientes() == [] and len(g.clientes(incluir_archivados=True)) == 1


# ---------- Albaranes ----------


def test_borrador_no_cambia_stock_ni_tiene_numero(g, datos):
    aid = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 5)]})
    a = g.albaran(aid)
    assert a["estado"] == "borrador" and a["numero"] is None
    assert g.producto(datos["p1"])["stock"] == 50


def test_validaciones_del_albaran(g, datos):
    c, p = datos["cliente"], datos["p1"]
    with pytest.raises(ErrorUsuario, match="cliente"):
        g.guardar_borrador({"lineas": [linea(g, p, 1)]})
    with pytest.raises(ErrorUsuario, match="al menos una línea"):
        g.guardar_borrador({"cliente_id": c, "lineas": []})
    with pytest.raises(ErrorUsuario, match="mayor que 0"):
        g.guardar_borrador({"cliente_id": c, "lineas": [linea(g, p, 0)]})
    with pytest.raises(ErrorUsuario, match="descuento"):
        g.guardar_borrador({"cliente_id": c, "lineas": [linea(g, p, 1, descuento=120)]})


def test_emitir_numera_y_descuenta_stock(g, datos):
    c, p1, p2 = datos["cliente"], datos["p1"], datos["p2"]
    a1 = g.guardar_borrador({"cliente_id": c, "fecha": "01/03/2026", "lineas": [linea(g, p1, 5), linea(g, p2, 2)]})
    assert g.emitir(a1) == "ALB-2026-0001"
    assert g.producto(p1)["stock"] == 45 and g.producto(p2)["stock"] == 8
    a2 = g.guardar_borrador({"cliente_id": c, "fecha": "02/03/2026", "lineas": [linea(g, p1, 1)]})
    assert g.emitir(a2) == "ALB-2026-0002"
    with pytest.raises(ErrorUsuario, match="ya está emitido"):
        g.emitir(a2)
    with pytest.raises(ErrorUsuario, match="borrador"):
        g.guardar_borrador({"id": a2, "cliente_id": c, "lineas": [linea(g, p1, 1)]})


def test_el_albaran_emitido_conserva_datos_del_cliente(g, datos):
    aid = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 1)]})
    g.emitir(aid)
    g.guardar_cliente({"id": datos["cliente"], "nombre": "Nombre cambiado"})
    assert g.albaran(aid)["cliente"]["nombre"] == "Cliente de prueba"


def test_numeracion_por_anio_y_prefijo(g, datos):
    g.guardar_empresa({"prefijo": "ped"})
    a = g.guardar_borrador({"cliente_id": datos["cliente"], "fecha": "31/12/2026", "lineas": [linea(g, datos["p1"], 1)]})
    b = g.guardar_borrador({"cliente_id": datos["cliente"], "fecha": "02/01/2027", "lineas": [linea(g, datos["p1"], 1)]})
    assert g.emitir(a) == "PED-2026-0001"
    assert g.emitir(b) == "PED-2027-0001"


def test_no_se_emite_sin_stock_y_no_cambia_nada(g, datos):
    aid = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p2"], 6), linea(g, datos["p2"], 6)]})
    with pytest.raises(ErrorUsuario, match="Stock insuficiente"):
        g.emitir(aid)
    assert g.albaran(aid)["estado"] == "borrador"
    assert g.producto(datos["p2"])["stock"] == 10


def test_concepto_libre_no_afecta_al_stock(g, datos):
    aid = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [{"descripcion": "Portes", "cantidad": 1, "precio": 15, "iva": 21}]})
    g.emitir(aid)
    assert g.albaran(aid)["totales"]["total"] == Decimal("18.15")


def test_entregar_y_anular_devuelve_stock(g, datos):
    aid = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 7)]})
    with pytest.raises(ErrorUsuario, match="emitidos"):
        g.marcar_entregado(aid)
    g.emitir(aid)
    g.marcar_entregado(aid, "05/05/2026", "Ana")
    a = g.albaran(aid)
    assert a["estado"] == "entregado" and a["receptor"] == "Ana" and a["fecha_entrega"] == "2026-05-05"
    assert g.producto(datos["p1"])["stock"] == 43
    g.anular(aid, "Error")
    assert g.albaran(aid)["estado"] == "anulado"
    assert g.producto(datos["p1"])["stock"] == 50
    with pytest.raises(ErrorUsuario, match="Solo se pueden anular"):
        g.anular(aid)


def test_solo_se_eliminan_borradores(g, datos):
    a = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 1)]})
    b = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 1)]})
    g.emitir(b)
    g.eliminar_borrador(a)
    assert len(g.albaranes()) == 1
    with pytest.raises(ErrorUsuario, match="Solo se pueden eliminar borradores"):
        g.eliminar_borrador(b)


def test_duplicar(g, datos):
    a = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 3)]})
    g.emitir(a)
    copia = g.albaran(g.duplicar(a))
    assert copia["estado"] == "borrador" and copia["lineas"][0]["cantidad"] == 3


def test_filtros_del_listado(g, datos):
    a = g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 1)]})
    g.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [linea(g, datos["p1"], 1)]})
    numero = g.emitir(a)
    assert len(g.albaranes(estado="borrador")) == 1
    assert [x["numero"] for x in g.albaranes(texto=numero[-4:])] == [numero]
    assert len(g.albaranes(texto="cliente de")) == 2


# ---------- Separación entre cuentas ----------


def test_cada_usuario_solo_ve_sus_datos(conn, g, datos):
    otro = Gestion(conn, auth.registrar(conn, "amigo", "Amigo", "secreto2")["id"])
    assert otro.clientes() == [] and otro.productos() == [] and otro.albaranes() == []
    with pytest.raises(ErrorUsuario, match="no encontrado"):
        otro.producto(datos["p1"])
    with pytest.raises(ErrorUsuario, match="no encontrado"):
        otro.ajustar_stock(datos["p1"], "entrada", 5)
    with pytest.raises(ErrorUsuario, match="no encontrado"):
        otro.guardar_borrador({"cliente_id": datos["cliente"], "lineas": [{"descripcion": "x", "cantidad": 1, "precio": 1}]})
    # Ambos pueden usar la misma referencia de producto y tienen su propia numeración.
    otro.guardar_producto({"referencia": "P-1", "nombre": "Del amigo", "precio": 1})
    cid = otro.guardar_cliente({"nombre": "Cliente del amigo"})
    aid = otro.guardar_borrador({"cliente_id": cid, "fecha": "01/01/2026", "lineas": [{"descripcion": "x", "cantidad": 1, "precio": 1}]})
    assert otro.emitir(aid) == "ALB-2026-0001"
    assert len(g.productos()) == 2


def test_datos_de_ejemplo_y_borrar_todo(g):
    assert g.esta_vacia()
    g.cargar_datos_demo()
    assert [a["estado"] for a in sorted(g.albaranes(), key=lambda a: a["id"])] == ["entregado", "emitido", "borrador"]
    assert len(g.productos()) == 6 and len(g.clientes()) == 3
    assert all(p["stock"] >= 0 for p in g.productos())
    g.borrar_todo()
    assert g.esta_vacia()
    assert g.empresa()["nombre"] == "Distribuciones Ejemplo S.L."
