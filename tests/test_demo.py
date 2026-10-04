from gestion_albaranes import auth, demo
from gestion_albaranes.logica import Gestion


def test_se_crea_la_cuenta_de_prueba_con_datos_si_no_hay_cuentas(conn):
    assert demo.asegurar_cuenta_demo(conn) is True
    usuario = auth.iniciar_sesion(conn, demo.USUARIO, demo.CONTRASENA)
    g = Gestion(conn, usuario["id"])
    assert len(g.albaranes()) == 3 and len(g.productos()) == 6 and len(g.clientes()) == 3


def test_no_se_vuelve_a_crear(conn):
    demo.asegurar_cuenta_demo(conn)
    assert demo.asegurar_cuenta_demo(conn) is False
    assert conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 1


def test_no_se_crea_si_ya_hay_otras_cuentas(conn, usuario):
    assert demo.asegurar_cuenta_demo(conn) is False
    assert not demo.existe(conn)


def test_registrar_con_datos_de_ejemplo(conn):
    nuevo = auth.registrar(conn, "dani", "Dani", "secreto1", "secreto1")
    Gestion(conn, nuevo["id"]).cargar_datos_demo()
    assert len(Gestion(conn, nuevo["id"]).albaranes()) == 3
