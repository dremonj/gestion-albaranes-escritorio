"""Cuenta de prueba que se crea automáticamente la primera vez que se abre la aplicación."""

from . import auth
from .logica import Gestion

USUARIO = "demo"
CONTRASENA = "demo1234"
NOMBRE = "Usuario de prueba"


def existe(conn) -> bool:
    return conn.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (USUARIO,)).fetchone() is not None


def asegurar_cuenta_demo(conn) -> bool:
    """Si todavía no hay ninguna cuenta, crea la de prueba con datos de ejemplo. Devuelve True si la ha creado."""
    if auth.hay_usuarios(conn):
        return False
    usuario = auth.registrar(conn, USUARIO, NOMBRE, CONTRASENA, CONTRASENA)
    Gestion(conn, usuario["id"]).cargar_datos_demo()
    return True
