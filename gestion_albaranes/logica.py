"""Reglas de negocio: clientes, inventario y albaranes.

Todo pasa por la clase Gestion, que trabaja siempre con los datos de UN usuario:
cada consulta filtra por usuario_id, así nadie puede ver ni tocar datos de otra cuenta.
"""

import json
import sqlite3
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .errores import ErrorUsuario

BORRADOR, EMITIDO, ENTREGADO, ANULADO = "borrador", "emitido", "entregado", "anulado"
NOMBRE_ESTADO = {
    BORRADOR: "Borrador",
    EMITIDO: "Pendiente de entrega",
    ENTREGADO: "Entregado",
    ANULADO: "Anulado",
}
TIPOS_IVA = (21, 10, 4, 0)
UNIDADES = ("ud", "kg", "g", "l", "m", "m²", "caja", "palé", "h")
CAMPOS_EMPRESA = ("nombre", "nif", "direccion", "cp", "ciudad", "provincia", "telefono", "email", "prefijo")
CAMPOS_CLIENTE = ("nombre", "nif", "direccion", "cp", "ciudad", "provincia", "telefono", "email", "notas")

# ---------- Números, importes y fechas ----------


def dec(valor, defecto=None):
    """Convierte a Decimal aceptando coma decimal ("1,5"). Devuelve `defecto` si no es un número."""
    if isinstance(valor, Decimal):
        return valor
    if valor is None:
        return defecto
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return defecto
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return defecto
    return numero if numero.is_finite() else defecto


def r2(x) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def r3(x) -> Decimal:
    return Decimal(x).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _formato_es(numero: Decimal, decimales: int, minimo: int) -> str:
    texto = f"{numero:,.{decimales}f}"
    entero, _, fraccion = texto.partition(".")
    fraccion = fraccion.rstrip("0").ljust(minimo, "0")
    entero = entero.replace(",", ".")
    return f"{entero},{fraccion}" if fraccion else entero


def euros(x) -> str:
    return _formato_es(r2(dec(x, Decimal(0))), 2, 2) + " €"


def cant(x) -> str:
    """Cantidad con hasta 3 decimales y sin ceros sobrantes: 1,5 · 12 · 0,125."""
    return _formato_es(r3(dec(x, Decimal(0))), 3, 0)


def hoy() -> str:
    return date.today().isoformat()


def fecha_es(iso) -> str:
    if not iso:
        return ""
    a, m, d = str(iso)[:10].split("-")
    return f"{d}/{m}/{a}"


def fecha_hora_es(texto) -> str:
    if not texto:
        return ""
    return f"{fecha_es(texto[:10])} {texto[11:16]}"


def leer_fecha(texto) -> str:
    """Admite dd/mm/aaaa (también con guiones) o aaaa-mm-dd y devuelve aaaa-mm-dd."""
    texto = (texto or "").strip()
    if not texto:
        return hoy()
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            pass
    raise ErrorUsuario(f"La fecha «{texto}» no es válida. Usa el formato dd/mm/aaaa.")


# ---------- Cálculos ----------


def calcular_linea(linea: dict) -> dict:
    cantidad = dec(linea.get("cantidad"), Decimal(0))
    precio = dec(linea.get("precio"), Decimal(0))
    descuento = dec(linea.get("descuento"), Decimal(0))
    bruto = r2(cantidad * precio)
    importe_descuento = r2(bruto * descuento / 100)
    return {"bruto": bruto, "descuento": importe_descuento, "base": bruto - importe_descuento, "iva": int(dec(linea.get("iva"), Decimal(0)))}


def calcular_totales(lineas) -> dict:
    """Totales con desglose por tipo de IVA (la cuota se calcula sobre la base de cada tipo)."""
    bases: dict[int, Decimal] = {}
    unidades = Decimal(0)
    for linea in lineas:
        c = calcular_linea(linea)
        bases[c["iva"]] = bases.get(c["iva"], Decimal(0)) + c["base"]
        unidades += dec(linea.get("cantidad"), Decimal(0))
    desglose = [{"iva": iva, "base": base, "cuota": r2(base * iva / 100)} for iva, base in sorted(bases.items(), reverse=True)]
    base = sum((d["base"] for d in desglose), Decimal(0))
    cuota = sum((d["cuota"] for d in desglose), Decimal(0))
    return {"base": base, "cuota": cuota, "total": base + cuota, "desglose": desglose, "unidades": r3(unidades)}


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- Gestión de los datos de un usuario ----------


class Gestion:
    def __init__(self, conn: sqlite3.Connection, usuario_id: int):
        self.conn = conn
        self.uid = usuario_id

    def _uno(self, sql, *params):
        fila = self.conn.execute(sql, params).fetchone()
        return dict(fila) if fila else None

    def _todos(self, sql, *params):
        return [dict(f) for f in self.conn.execute(sql, params)]

    # ----- Empresa -----

    def empresa(self) -> dict:
        datos = self._uno("SELECT * FROM empresa WHERE usuario_id = ?", self.uid)
        if datos is None:
            with self.conn:
                self.conn.execute("INSERT INTO empresa (usuario_id) VALUES (?)", (self.uid,))
            datos = self._uno("SELECT * FROM empresa WHERE usuario_id = ?", self.uid)
        return datos

    def guardar_empresa(self, datos: dict) -> None:
        valores = {c: _texto(datos.get(c)) for c in CAMPOS_EMPRESA}
        valores["nif"] = valores["nif"].upper()
        valores["prefijo"] = (valores["prefijo"] or "ALB").upper()[:6]
        if not valores["prefijo"].replace("-", "").isalnum():
            raise ErrorUsuario("El prefijo solo puede tener letras y números.")
        self.empresa()
        with self.conn:
            self.conn.execute(
                f"UPDATE empresa SET {', '.join(f'{c} = ?' for c in CAMPOS_EMPRESA)} WHERE usuario_id = ?",
                (*valores.values(), self.uid),
            )

    # ----- Clientes -----

    def clientes(self, texto: str = "", incluir_archivados: bool = False) -> list[dict]:
        filas = self._todos(
            """SELECT c.*, (SELECT COUNT(*) FROM albaranes a WHERE a.cliente_id = c.id) AS num_albaranes
               FROM clientes c WHERE c.usuario_id = ? ORDER BY c.nombre COLLATE NOCASE""",
            self.uid,
        )
        t = texto.strip().lower()
        return [
            c for c in filas
            if (incluir_archivados or c["activo"])
            and (not t or any(t in (c[k] or "").lower() for k in ("nombre", "nif", "ciudad", "telefono")))
        ]

    def cliente(self, cliente_id: int) -> dict:
        c = self._uno("SELECT * FROM clientes WHERE id = ? AND usuario_id = ?", cliente_id, self.uid)
        if c is None:
            raise ErrorUsuario("Cliente no encontrado.")
        return c

    def guardar_cliente(self, datos: dict) -> int:
        valores = {c: _texto(datos.get(c)) for c in CAMPOS_CLIENTE}
        if not valores["nombre"]:
            raise ErrorUsuario("El nombre del cliente es obligatorio.")
        valores["nif"] = valores["nif"].upper()
        with self.conn:
            if datos.get("id"):
                self.cliente(datos["id"])
                self.conn.execute(
                    f"UPDATE clientes SET {', '.join(f'{c} = ?' for c in CAMPOS_CLIENTE)} WHERE id = ? AND usuario_id = ?",
                    (*valores.values(), datos["id"], self.uid),
                )
                return datos["id"]
            cur = self.conn.execute(
                f"INSERT INTO clientes (usuario_id, {', '.join(CAMPOS_CLIENTE)}) VALUES (?{', ?' * len(CAMPOS_CLIENTE)})",
                (self.uid, *valores.values()),
            )
            return cur.lastrowid

    def eliminar_cliente(self, cliente_id: int) -> str:
        """Borra el cliente o, si tiene albaranes, lo archiva. Devuelve 'eliminado' o 'archivado'."""
        self.cliente(cliente_id)
        with self.conn:
            if self.conn.execute("SELECT 1 FROM albaranes WHERE cliente_id = ?", (cliente_id,)).fetchone():
                self.conn.execute("UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,))
                return "archivado"
            self.conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
            return "eliminado"

    # ----- Productos e inventario -----

    def productos(self, texto: str = "", solo_bajos: bool = False, incluir_archivados: bool = False) -> list[dict]:
        filas = self._todos("SELECT * FROM productos WHERE usuario_id = ? ORDER BY nombre COLLATE NOCASE", self.uid)
        t = texto.strip().lower()
        resultado = []
        for p in filas:
            p["bajo"] = p["stock"] <= p["stock_minimo"]
            if not (incluir_archivados or p["activo"]):
                continue
            if solo_bajos and not p["bajo"]:
                continue
            if t and not any(t in (p[k] or "").lower() for k in ("referencia", "nombre", "descripcion")):
                continue
            resultado.append(p)
        return resultado

    def producto(self, producto_id: int) -> dict:
        p = self._uno("SELECT * FROM productos WHERE id = ? AND usuario_id = ?", producto_id, self.uid)
        if p is None:
            raise ErrorUsuario("Producto no encontrado.")
        p["bajo"] = p["stock"] <= p["stock_minimo"]
        return p

    def productos_bajo_minimo(self) -> list[dict]:
        return self.productos(solo_bajos=True)

    def _movimiento(self, producto: dict, delta: Decimal, motivo: str, albaran_id=None) -> Decimal:
        nuevo = r3(dec(producto["stock"]) + delta)
        self.conn.execute("UPDATE productos SET stock = ? WHERE id = ?", (float(nuevo), producto["id"]))
        self.conn.execute(
            "INSERT INTO movimientos (usuario_id, producto_id, fecha, cantidad, stock_resultante, motivo, albaran_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.uid, producto["id"], _ahora(), float(r3(delta)), float(nuevo), motivo, albaran_id),
        )
        producto["stock"] = float(nuevo)
        return nuevo

    def guardar_producto(self, datos: dict) -> int:
        nombre = _texto(datos.get("nombre"))
        referencia = _texto(datos.get("referencia")).upper()
        if not referencia:
            raise ErrorUsuario("La referencia del producto es obligatoria.")
        if not nombre:
            raise ErrorUsuario("El nombre del producto es obligatorio.")
        precio = dec(datos.get("precio"))
        if precio is None or precio < 0:
            raise ErrorUsuario("El precio debe ser un número mayor o igual que 0.")
        iva = dec(datos.get("iva"), Decimal(21))
        if iva not in TIPOS_IVA:
            raise ErrorUsuario("Tipo de IVA no válido.")
        minimo = dec(datos.get("stock_minimo"), Decimal(0))
        if minimo is None or minimo < 0:
            raise ErrorUsuario("El stock mínimo debe ser un número mayor o igual que 0.")
        repetido = self.conn.execute(
            "SELECT 1 FROM productos WHERE usuario_id = ? AND referencia = ? AND id != ?",
            (self.uid, referencia, datos.get("id") or 0),
        ).fetchone()
        if repetido:
            raise ErrorUsuario(f"Ya existe un producto con la referencia {referencia}.")
        valores = (referencia, nombre, _texto(datos.get("descripcion")), _texto(datos.get("unidad")) or "ud",
                   float(r2(precio)), int(iva), float(r3(minimo)))

        with self.conn:
            if datos.get("id"):
                # El stock no se cambia aquí: se usa ajustar_stock para que quede registrado.
                self.producto(datos["id"])
                self.conn.execute(
                    """UPDATE productos SET referencia = ?, nombre = ?, descripcion = ?, unidad = ?, precio = ?, iva = ?,
                       stock_minimo = ? WHERE id = ? AND usuario_id = ?""",
                    (*valores, datos["id"], self.uid),
                )
                return datos["id"]
            inicial = dec(datos.get("stock"), Decimal(0))
            if inicial is None or inicial < 0:
                raise ErrorUsuario("Las unidades iniciales deben ser un número mayor o igual que 0.")
            cur = self.conn.execute(
                """INSERT INTO productos (usuario_id, referencia, nombre, descripcion, unidad, precio, iva, stock_minimo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.uid, *valores),
            )
            if inicial > 0:
                self._movimiento({"id": cur.lastrowid, "stock": 0}, inicial, "Stock inicial")
            return cur.lastrowid

    def ajustar_stock(self, producto_id: int, modo: str, cantidad, motivo: str = "") -> Decimal:
        """Modifica las unidades. modo: 'entrada' (suma), 'salida' (resta) o 'fijar' (valor exacto)."""
        producto = self.producto(producto_id)
        valor = dec(cantidad)
        if valor is None or valor < 0:
            raise ErrorUsuario("Introduce una cantidad válida.")
        actual = dec(producto["stock"])
        deltas = {"entrada": valor, "salida": -valor, "fijar": valor - actual}
        if modo not in deltas:
            raise ErrorUsuario("Tipo de ajuste no válido.")
        delta = deltas[modo]
        if delta == 0:
            raise ErrorUsuario("El ajuste no cambia el stock.")
        if actual + delta < 0:
            raise ErrorUsuario(f"No hay suficiente stock: quedan {cant(actual)} {producto['unidad']}.")
        por_defecto = {"entrada": "Entrada de mercancía", "salida": "Salida manual", "fijar": "Recuento de inventario"}
        with self.conn:
            return self._movimiento(producto, delta, _texto(motivo) or por_defecto[modo])

    def movimientos(self, producto_id: int) -> list[dict]:
        self.producto(producto_id)
        return self._todos(
            """SELECT m.*, a.numero AS albaran_numero FROM movimientos m
               LEFT JOIN albaranes a ON a.id = m.albaran_id
               WHERE m.producto_id = ? AND m.usuario_id = ? ORDER BY m.id DESC""",
            producto_id, self.uid,
        )

    def eliminar_producto(self, producto_id: int) -> str:
        """Borra el producto o, si aparece en albaranes, lo archiva. Devuelve 'eliminado' o 'archivado'."""
        self.producto(producto_id)
        with self.conn:
            if self.conn.execute("SELECT 1 FROM lineas WHERE producto_id = ?", (producto_id,)).fetchone():
                self.conn.execute("UPDATE productos SET activo = 0 WHERE id = ?", (producto_id,))
                return "archivado"
            self.conn.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
            return "eliminado"

    # ----- Albaranes -----

    def _normalizar_lineas(self, lineas) -> list[dict]:
        if not lineas:
            raise ErrorUsuario("El albarán debe tener al menos una línea.")
        resultado = []
        for i, l in enumerate(lineas, start=1):
            cantidad = dec(l.get("cantidad"))
            if cantidad is None or cantidad <= 0:
                raise ErrorUsuario(f"Línea {i}: la cantidad debe ser mayor que 0.")
            precio = dec(l.get("precio"))
            if precio is None or precio < 0:
                raise ErrorUsuario(f"Línea {i}: el precio no es válido.")
            descuento = dec(l.get("descuento"), Decimal(0))
            if descuento is None or not 0 <= descuento <= 100:
                raise ErrorUsuario(f"Línea {i}: el descuento debe estar entre 0 y 100.")
            iva = dec(l.get("iva"), Decimal(21))
            if iva not in TIPOS_IVA:
                raise ErrorUsuario(f"Línea {i}: tipo de IVA no válido.")
            descripcion = _texto(l.get("descripcion"))
            referencia, unidad = _texto(l.get("referencia")), _texto(l.get("unidad")) or "ud"
            producto_id = l.get("producto_id") or None
            if producto_id:
                p = self.producto(producto_id)
                referencia, unidad = p["referencia"], p["unidad"]
                descripcion = descripcion or p["nombre"]
            if not descripcion:
                raise ErrorUsuario(f"Línea {i}: falta la descripción.")
            resultado.append({
                "producto_id": producto_id, "referencia": referencia, "descripcion": descripcion, "unidad": unidad,
                "cantidad": float(r3(cantidad)), "precio": float(r2(precio)), "descuento": float(r2(descuento)), "iva": int(iva),
            })
        return resultado

    def _albaran_propio(self, albaran_id: int) -> dict:
        a = self._uno("SELECT * FROM albaranes WHERE id = ? AND usuario_id = ?", albaran_id, self.uid)
        if a is None:
            raise ErrorUsuario("Albarán no encontrado.")
        return a

    def _historial(self, albaran_id: int, texto: str) -> None:
        self.conn.execute("INSERT INTO historial (albaran_id, fecha, texto) VALUES (?, ?, ?)", (albaran_id, _ahora(), texto))

    def lineas(self, albaran_id: int) -> list[dict]:
        return self._todos("SELECT * FROM lineas WHERE albaran_id = ? ORDER BY orden", albaran_id)

    def albaran(self, albaran_id: int) -> dict:
        """Albarán completo con líneas, totales, historial y datos de cliente y empresa."""
        a = self._albaran_propio(albaran_id)
        a["lineas"] = self.lineas(albaran_id)
        a["totales"] = calcular_totales(a["lineas"])
        a["historial"] = self._todos("SELECT * FROM historial WHERE albaran_id = ? ORDER BY id", albaran_id)
        # Al emitir se guarda una copia del cliente y de la empresa para que el documento no cambie después.
        a["cliente"] = json.loads(a["cliente_json"]) if a["cliente_json"] else self.cliente(a["cliente_id"])
        a["empresa"] = json.loads(a["empresa_json"]) if a["empresa_json"] else self.empresa()
        return a

    def albaranes(self, estado: str | None = None, texto: str = "") -> list[dict]:
        filas = self._todos(
            """SELECT a.*, c.nombre AS cliente_actual FROM albaranes a JOIN clientes c ON c.id = a.cliente_id
               WHERE a.usuario_id = ? ORDER BY a.fecha DESC, COALESCE(a.numero, 'zzz') DESC, a.id DESC""",
            self.uid,
        )
        t = texto.strip().lower()
        resultado = []
        for a in filas:
            a["cliente_nombre"] = json.loads(a["cliente_json"])["nombre"] if a["cliente_json"] else a["cliente_actual"]
            if estado and a["estado"] != estado:
                continue
            if t and t not in (a["numero"] or "").lower() and t not in a["cliente_nombre"].lower():
                continue
            a["total"] = calcular_totales(self.lineas(a["id"]))["total"]
            resultado.append(a)
        return resultado

    def guardar_borrador(self, datos: dict) -> int:
        """Crea un albarán en borrador o modifica uno que siga en borrador."""
        if not datos.get("cliente_id"):
            raise ErrorUsuario("Selecciona un cliente.")
        self.cliente(datos["cliente_id"])
        fecha = leer_fecha(datos.get("fecha"))
        lineas = self._normalizar_lineas(datos.get("lineas"))
        campos = (fecha, datos["cliente_id"], 1 if datos.get("valorado", True) else 0, _texto(datos.get("observaciones")), _ahora())
        with self.conn:
            if datos.get("id"):
                albaran_id = datos["id"]
                if self._albaran_propio(albaran_id)["estado"] != BORRADOR:
                    raise ErrorUsuario("Solo se pueden modificar albaranes en borrador.")
                self.conn.execute(
                    "UPDATE albaranes SET fecha = ?, cliente_id = ?, valorado = ?, observaciones = ?, actualizado = ? WHERE id = ?",
                    (*campos, albaran_id),
                )
                self.conn.execute("DELETE FROM lineas WHERE albaran_id = ?", (albaran_id,))
            else:
                cur = self.conn.execute(
                    "INSERT INTO albaranes (usuario_id, fecha, cliente_id, valorado, observaciones, actualizado, creado) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self.uid, *campos, _ahora()),
                )
                albaran_id = cur.lastrowid
                self._historial(albaran_id, "Creado como borrador")
            for orden, l in enumerate(lineas):
                self.conn.execute(
                    """INSERT INTO lineas (albaran_id, orden, producto_id, referencia, descripcion, unidad, cantidad, precio, descuento, iva)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (albaran_id, orden, l["producto_id"], l["referencia"], l["descripcion"], l["unidad"],
                     l["cantidad"], l["precio"], l["descuento"], l["iva"]),
                )
        return albaran_id

    def comprobar_stock(self, lineas) -> list[dict]:
        """Productos sin stock suficiente (sumando las líneas del mismo producto)."""
        pedido: dict[int, Decimal] = {}
        for l in lineas:
            if l.get("producto_id"):
                pedido[l["producto_id"]] = pedido.get(l["producto_id"], Decimal(0)) + dec(l.get("cantidad"), Decimal(0))
        faltan = []
        for producto_id, solicitado in pedido.items():
            p = self.producto(producto_id)
            if dec(p["stock"]) < solicitado:
                faltan.append({"producto": p, "solicitado": solicitado, "disponible": dec(p["stock"])})
        return faltan

    def _siguiente_numero(self, fecha: str) -> str:
        prefijo = self.empresa()["prefijo"] or "ALB"
        clave = f"{prefijo}-{fecha[:4]}"
        fila = self.conn.execute("SELECT valor FROM contadores WHERE usuario_id = ? AND clave = ?", (self.uid, clave)).fetchone()
        n = (fila["valor"] if fila else 0) + 1
        self.conn.execute(
            "INSERT INTO contadores (usuario_id, clave, valor) VALUES (?, ?, ?) ON CONFLICT (usuario_id, clave) DO UPDATE SET valor = excluded.valor",
            (self.uid, clave, n),
        )
        return f"{clave}-{n:04d}"

    def emitir(self, albaran_id: int) -> str:
        """Asigna número, guarda copia de cliente y empresa y descuenta el stock. Devuelve el número."""
        a = self._albaran_propio(albaran_id)
        if a["estado"] != BORRADOR:
            raise ErrorUsuario("Este albarán ya está emitido.")
        lineas = self.lineas(albaran_id)
        faltan = self.comprobar_stock(lineas)
        if faltan:
            detalle = ", ".join(f"{f['producto']['nombre']} (pides {cant(f['solicitado'])}, hay {cant(f['disponible'])})" for f in faltan)
            raise ErrorUsuario(f"Stock insuficiente: {detalle}.")
        cliente = self.cliente(a["cliente_id"])
        empresa = self.empresa()
        with self.conn:
            numero = self._siguiente_numero(a["fecha"])
            self.conn.execute(
                "UPDATE albaranes SET numero = ?, estado = ?, cliente_json = ?, empresa_json = ?, actualizado = ? WHERE id = ?",
                (numero, EMITIDO, json.dumps(cliente, ensure_ascii=False), json.dumps(empresa, ensure_ascii=False), _ahora(), albaran_id),
            )
            for l in lineas:
                if l["producto_id"]:
                    self._movimiento(self.producto(l["producto_id"]), -dec(l["cantidad"]), f"Salida por albarán {numero}", albaran_id)
            self._historial(albaran_id, f"Emitido con número {numero}")
        return numero

    def marcar_entregado(self, albaran_id: int, fecha_entrega=None, receptor: str = "") -> None:
        a = self._albaran_propio(albaran_id)
        if a["estado"] != EMITIDO:
            raise ErrorUsuario("Solo se pueden entregar albaranes emitidos.")
        fecha = leer_fecha(fecha_entrega)
        receptor = _texto(receptor)
        with self.conn:
            self.conn.execute(
                "UPDATE albaranes SET estado = ?, fecha_entrega = ?, receptor = ?, actualizado = ? WHERE id = ?",
                (ENTREGADO, fecha, receptor, _ahora(), albaran_id),
            )
            self._historial(albaran_id, f"Entregado{' a ' + receptor if receptor else ''} el {fecha_es(fecha)}")

    def anular(self, albaran_id: int, motivo: str = "") -> None:
        """Anula un albarán emitido o entregado y devuelve las unidades al inventario."""
        a = self._albaran_propio(albaran_id)
        if a["estado"] not in (EMITIDO, ENTREGADO):
            raise ErrorUsuario("Solo se pueden anular albaranes emitidos o entregados.")
        motivo = _texto(motivo)
        with self.conn:
            for l in self.lineas(albaran_id):
                if l["producto_id"]:
                    self._movimiento(self.producto(l["producto_id"]), dec(l["cantidad"]), f"Devolución por anulación de {a['numero']}", albaran_id)
            self.conn.execute(
                "UPDATE albaranes SET estado = ?, motivo_anulacion = ?, actualizado = ? WHERE id = ?",
                (ANULADO, motivo, _ahora(), albaran_id),
            )
            self._historial(albaran_id, f"Anulado{': ' + motivo if motivo else ''}")

    def eliminar_borrador(self, albaran_id: int) -> None:
        if self._albaran_propio(albaran_id)["estado"] != BORRADOR:
            raise ErrorUsuario("Solo se pueden eliminar borradores. Los albaranes emitidos se anulan.")
        with self.conn:
            self.conn.execute("DELETE FROM albaranes WHERE id = ?", (albaran_id,))

    def duplicar(self, albaran_id: int) -> int:
        a = self._albaran_propio(albaran_id)
        cliente = self.cliente(a["cliente_id"])
        if not cliente["activo"]:
            raise ErrorUsuario("No se puede duplicar: el cliente está archivado.")
        lineas = [l for l in self.lineas(albaran_id) if not l["producto_id"] or self.producto(l["producto_id"])["activo"]]
        if not lineas:
            raise ErrorUsuario("No se puede duplicar: los productos ya no están disponibles.")
        return self.guardar_borrador({
            "cliente_id": a["cliente_id"], "fecha": hoy(), "valorado": bool(a["valorado"]),
            "observaciones": a["observaciones"], "lineas": lineas,
        })

    # ----- Resumen para la pantalla de inicio -----

    def resumen(self) -> dict:
        mes = hoy()[:7]
        todos = self.albaranes()
        del_mes = [a for a in todos if a["fecha"].startswith(mes) and a["estado"] in (EMITIDO, ENTREGADO)]
        return {
            "albaranes_mes": len(del_mes),
            "importe_mes": sum((a["total"] for a in del_mes), Decimal(0)),
            "pendientes": sum(1 for a in todos if a["estado"] == EMITIDO),
            "borradores": sum(1 for a in todos if a["estado"] == BORRADOR),
            "bajo_minimo": self.productos_bajo_minimo(),
            "ultimos": sorted(todos, key=lambda a: a["actualizado"], reverse=True)[:8],
        }

    def esta_vacia(self) -> bool:
        return not any(
            self.conn.execute(f"SELECT 1 FROM {tabla} WHERE usuario_id = ? LIMIT 1", (self.uid,)).fetchone()
            for tabla in ("clientes", "productos", "albaranes")
        )

    def borrar_todo(self) -> None:
        """Borra clientes, productos y albaranes de esta cuenta (conserva la cuenta y los datos de empresa)."""
        with self.conn:
            for tabla in ("albaranes", "movimientos", "productos", "clientes", "contadores"):
                self.conn.execute(f"DELETE FROM {tabla} WHERE usuario_id = ?", (self.uid,))

    def cargar_datos_demo(self) -> None:
        """Rellena la cuenta con datos de ejemplo para probar la aplicación."""
        if not self.empresa()["nombre"]:
            self.guardar_empresa({
                "nombre": "Distribuciones Ejemplo S.L.", "nif": "B12345678", "direccion": "Calle Mayor, 12",
                "cp": "28001", "ciudad": "Madrid", "provincia": "Madrid", "telefono": "910 000 000",
                "email": "pedidos@ejemplo.es", "prefijo": self.empresa()["prefijo"],
            })
        c1 = self.guardar_cliente({"nombre": "Bar Restaurante La Plaza", "nif": "B87654321", "direccion": "Plaza de España, 3",
                                   "cp": "28008", "ciudad": "Madrid", "provincia": "Madrid", "telefono": "600 111 222",
                                   "email": "laplaza@ejemplo.es"})
        c2 = self.guardar_cliente({"nombre": "Supermercados Hermanos García", "nif": "B11223344",
                                   "direccion": "Av. de la Constitución, 45", "cp": "41001", "ciudad": "Sevilla",
                                   "provincia": "Sevilla", "telefono": "955 333 444"})
        self.guardar_cliente({"nombre": "Juan Pérez Martín", "nif": "12345678Z", "direccion": "C/ del Olmo, 7, 2ºB",
                              "cp": "46001", "ciudad": "Valencia", "provincia": "Valencia"})
        ejemplo = [
            ("AGU-150", "Agua mineral 1,5 L (pack 6)", "caja", "2.40", 10, 120, 20),
            ("ACE-5L", "Aceite de oliva virgen extra 5 L", "ud", "38.50", 4, 25, 5),
            ("CAF-1K", "Café en grano 1 kg", "kg", "16.90", 10, 40, 10),
            ("SER-50", "Servilletas 30x30 (paquete 50)", "ud", "1.75", 21, 300, 50),
            ("DET-5L", "Detergente lavavajillas 5 L", "ud", "12.30", 21, 4, 6),
            ("HAR-25", "Harina de trigo 25 kg", "ud", "14.00", 4, 18, 5),
        ]
        ids = [
            self.guardar_producto({"referencia": r, "nombre": n, "unidad": u, "precio": p, "iva": i, "stock": s, "stock_minimo": m})
            for r, n, u, p, i, s, m in ejemplo
        ]

        def linea(indice, cantidad, descuento=0):
            p = self.producto(ids[indice])
            return {"producto_id": p["id"], "descripcion": p["nombre"], "cantidad": cantidad,
                    "precio": p["precio"], "descuento": descuento, "iva": p["iva"]}

        a1 = self.guardar_borrador({"cliente_id": c1, "observaciones": "Entregar por la puerta trasera antes de las 10:00.",
                                    "lineas": [linea(0, 10), linea(2, 3), linea(3, 20, 5)]})
        self.emitir(a1)
        self.marcar_entregado(a1, hoy(), "María López")
        a2 = self.guardar_borrador({"cliente_id": c2, "lineas": [linea(1, 4), linea(5, 6)]})
        self.emitir(a2)
        self.guardar_borrador({"cliente_id": c1, "lineas": [linea(4, 2)]})
