"""Cuentas de usuario: registro, inicio de sesión y cambio de contraseña.

Las contraseñas nunca se guardan: se guarda un hash PBKDF2-SHA256 con sal aleatoria.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3

from .errores import ErrorUsuario

ITERACIONES = 600_000
LONGITUD_MINIMA = 6
_PATRON_USUARIO = re.compile(r"^[A-Za-z0-9._-]{3,30}$")
_SAL_FALSA = secrets.token_bytes(16)


def _hash(contrasena: str, sal: bytes, iteraciones: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)


def _validar_contrasena(contrasena: str, repetir: str | None) -> None:
    if len(contrasena) < LONGITUD_MINIMA:
        raise ErrorUsuario(f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres.")
    if repetir is not None and contrasena != repetir:
        raise ErrorUsuario("Las contraseñas no coinciden.")


def _publico(fila: sqlite3.Row) -> dict:
    return {"id": fila["id"], "usuario": fila["usuario"], "nombre": fila["nombre"]}


def hay_usuarios(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None


def registrar(conn: sqlite3.Connection, usuario: str, nombre: str, contrasena: str, repetir: str | None = None) -> dict:
    usuario = (usuario or "").strip()
    nombre = (nombre or "").strip()
    if not _PATRON_USUARIO.match(usuario):
        raise ErrorUsuario("El usuario debe tener entre 3 y 30 caracteres: letras, números, punto, guion o guion bajo (sin espacios).")
    if not nombre:
        raise ErrorUsuario("Escribe tu nombre.")
    _validar_contrasena(contrasena, repetir)
    if conn.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,)).fetchone():
        raise ErrorUsuario(f"El usuario «{usuario}» ya existe. Elige otro.")

    sal = secrets.token_bytes(16)
    with conn:
        cur = conn.execute(
            "INSERT INTO usuarios (usuario, nombre, hash, sal, iteraciones) VALUES (?, ?, ?, ?, ?)",
            (usuario, nombre, _hash(contrasena, sal, ITERACIONES), sal, ITERACIONES),
        )
        conn.execute("INSERT INTO empresa (usuario_id) VALUES (?)", (cur.lastrowid,))
    return {"id": cur.lastrowid, "usuario": usuario, "nombre": nombre}


def iniciar_sesion(conn: sqlite3.Connection, usuario: str, contrasena: str) -> dict:
    fila = conn.execute("SELECT * FROM usuarios WHERE usuario = ?", ((usuario or "").strip(),)).fetchone()
    if fila is None:
        # Se calcula un hash igualmente para que no se note por el tiempo si el usuario existe.
        _hash(contrasena or "", _SAL_FALSA, ITERACIONES)
        raise ErrorUsuario("Usuario o contraseña incorrectos.")
    calculado = _hash(contrasena or "", fila["sal"], fila["iteraciones"])
    if not hmac.compare_digest(calculado, fila["hash"]):
        raise ErrorUsuario("Usuario o contraseña incorrectos.")
    return _publico(fila)


def cambiar_contrasena(conn: sqlite3.Connection, usuario_id: int, actual: str, nueva: str, repetir: str | None = None) -> None:
    fila = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if fila is None:
        raise ErrorUsuario("La cuenta no existe.")
    if not hmac.compare_digest(_hash(actual or "", fila["sal"], fila["iteraciones"]), fila["hash"]):
        raise ErrorUsuario("La contraseña actual no es correcta.")
    _validar_contrasena(nueva, repetir)
    sal = secrets.token_bytes(16)
    with conn:
        conn.execute(
            "UPDATE usuarios SET hash = ?, sal = ?, iteraciones = ? WHERE id = ?",
            (_hash(nueva, sal, ITERACIONES), sal, ITERACIONES, usuario_id),
        )
