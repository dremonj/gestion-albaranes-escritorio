import pytest

from gestion_albaranes import auth
from gestion_albaranes.errores import ErrorUsuario


def test_registrar_e_iniciar_sesion(conn):
    assert not auth.hay_usuarios(conn)
    nuevo = auth.registrar(conn, "dani", "Dani", "secreto1", "secreto1")
    assert auth.hay_usuarios(conn)
    sesion = auth.iniciar_sesion(conn, "dani", "secreto1")
    assert sesion == {"id": nuevo["id"], "usuario": "dani", "nombre": "Dani"}


def test_el_usuario_no_distingue_mayusculas(conn, usuario):
    assert auth.iniciar_sesion(conn, "DANI", "secreto1")["id"] == usuario["id"]
    with pytest.raises(ErrorUsuario, match="ya existe"):
        auth.registrar(conn, "Dani", "Otro", "secreto1")


def test_la_contrasena_no_se_guarda_en_claro(conn, usuario):
    fila = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario["id"],)).fetchone()
    assert b"secreto1" not in bytes(fila["hash"])
    assert len(fila["sal"]) == 16


def test_contrasena_incorrecta_o_usuario_inexistente(conn, usuario):
    with pytest.raises(ErrorUsuario, match="incorrectos"):
        auth.iniciar_sesion(conn, "dani", "mala")
    with pytest.raises(ErrorUsuario, match="incorrectos"):
        auth.iniciar_sesion(conn, "nadie", "secreto1")


@pytest.mark.parametrize(
    "usuario, nombre, clave, repetir, error",
    [
        ("ab", "A", "secreto1", "secreto1", "entre 3 y 30"),
        ("con espacio", "A", "secreto1", "secreto1", "entre 3 y 30"),
        ("valido", "", "secreto1", "secreto1", "nombre"),
        ("valido", "A", "corta", "corta", "al menos 6"),
        ("valido", "A", "secreto1", "secreto2", "no coinciden"),
    ],
)
def test_validaciones_de_registro(conn, usuario, nombre, clave, repetir, error):
    with pytest.raises(ErrorUsuario, match=error):
        auth.registrar(conn, usuario, nombre, clave, repetir)


def test_cambiar_contrasena(conn, usuario):
    with pytest.raises(ErrorUsuario, match="actual no es correcta"):
        auth.cambiar_contrasena(conn, usuario["id"], "mala", "nueva123", "nueva123")
    auth.cambiar_contrasena(conn, usuario["id"], "secreto1", "nueva123", "nueva123")
    with pytest.raises(ErrorUsuario):
        auth.iniciar_sesion(conn, "dani", "secreto1")
    assert auth.iniciar_sesion(conn, "dani", "nueva123")["usuario"] == "dani"
