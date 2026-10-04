import pytest

from gestion_albaranes import db
from gestion_albaranes.errores import ErrorUsuario
from gestion_albaranes.pdf import generar_pdf


@pytest.mark.parametrize("valorado", [True, False])
def test_genera_pdf(g, tmp_path, valorado):
    g.cargar_datos_demo()
    for a in g.albaranes():
        albaran = g.albaran(a["id"])
        albaran["valorado"] = valorado
        destino = tmp_path / f"{a['id']}.pdf"
        generar_pdf(albaran, destino)
        assert destino.read_bytes().startswith(b"%PDF")


def test_pdf_con_textos_raros(g, tmp_path):
    cid = g.guardar_cliente({"nombre": "<b>Cliente & Cía</b>", "direccion": "C/ Ñandú, 3"})
    aid = g.guardar_borrador({"cliente_id": cid, "observaciones": "Línea 1\nLínea 2 <script>",
                              "lineas": [{"descripcion": "Café «especial» & más", "cantidad": 1, "precio": 1}]})
    generar_pdf(g.albaran(aid), tmp_path / "raro.pdf")


def test_copia_de_seguridad_y_restaurar(conn, g, tmp_path):
    g.cargar_datos_demo()
    copia = tmp_path / "copia.db"
    db.guardar_copia(conn, copia)
    destino = tmp_path / "restaurada.db"
    db.restaurar_copia(copia, destino)
    restaurada = db.conectar(destino)
    assert restaurada.execute("SELECT COUNT(*) FROM albaranes").fetchone()[0] == 3
    restaurada.close()


def test_restaurar_rechaza_archivos_no_validos(tmp_path):
    malo = tmp_path / "malo.db"
    malo.write_text("esto no es una base de datos")
    with pytest.raises(ErrorUsuario):
        db.restaurar_copia(malo, tmp_path / "x.db")
