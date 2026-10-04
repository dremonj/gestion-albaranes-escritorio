"""Base de datos SQLite: ubicación, esquema y copias de seguridad."""

import json
import os
import shutil
import sqlite3
from pathlib import Path

from .errores import ErrorUsuario

VERSION_ESQUEMA = 1

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY,
    usuario     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nombre      TEXT NOT NULL,
    hash        BLOB NOT NULL,
    sal         BLOB NOT NULL,
    iteraciones INTEGER NOT NULL,
    creado      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS empresa (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre     TEXT NOT NULL DEFAULT '',
    nif        TEXT NOT NULL DEFAULT '',
    direccion  TEXT NOT NULL DEFAULT '',
    cp         TEXT NOT NULL DEFAULT '',
    ciudad     TEXT NOT NULL DEFAULT '',
    provincia  TEXT NOT NULL DEFAULT '',
    telefono   TEXT NOT NULL DEFAULT '',
    email      TEXT NOT NULL DEFAULT '',
    prefijo    TEXT NOT NULL DEFAULT 'ALB'
);

CREATE TABLE IF NOT EXISTS clientes (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre     TEXT NOT NULL,
    nif        TEXT NOT NULL DEFAULT '',
    direccion  TEXT NOT NULL DEFAULT '',
    cp         TEXT NOT NULL DEFAULT '',
    ciudad     TEXT NOT NULL DEFAULT '',
    provincia  TEXT NOT NULL DEFAULT '',
    telefono   TEXT NOT NULL DEFAULT '',
    email      TEXT NOT NULL DEFAULT '',
    notas      TEXT NOT NULL DEFAULT '',
    activo     INTEGER NOT NULL DEFAULT 1,
    creado     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS productos (
    id           INTEGER PRIMARY KEY,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    referencia   TEXT NOT NULL,
    nombre       TEXT NOT NULL,
    descripcion  TEXT NOT NULL DEFAULT '',
    unidad       TEXT NOT NULL DEFAULT 'ud',
    precio       REAL NOT NULL DEFAULT 0,
    iva          INTEGER NOT NULL DEFAULT 21,
    stock        REAL NOT NULL DEFAULT 0,
    stock_minimo REAL NOT NULL DEFAULT 0,
    activo       INTEGER NOT NULL DEFAULT 1,
    creado       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (usuario_id, referencia)
);

CREATE TABLE IF NOT EXISTS albaranes (
    id               INTEGER PRIMARY KEY,
    usuario_id       INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    numero           TEXT,
    estado           TEXT NOT NULL DEFAULT 'borrador',
    fecha            TEXT NOT NULL,
    cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
    cliente_json     TEXT,
    empresa_json     TEXT,
    valorado         INTEGER NOT NULL DEFAULT 1,
    observaciones    TEXT NOT NULL DEFAULT '',
    fecha_entrega    TEXT,
    receptor         TEXT NOT NULL DEFAULT '',
    motivo_anulacion TEXT NOT NULL DEFAULT '',
    creado           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    actualizado      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS lineas (
    id          INTEGER PRIMARY KEY,
    albaran_id  INTEGER NOT NULL REFERENCES albaranes(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    producto_id INTEGER REFERENCES productos(id),
    referencia  TEXT NOT NULL DEFAULT '',
    descripcion TEXT NOT NULL,
    unidad      TEXT NOT NULL DEFAULT 'ud',
    cantidad    REAL NOT NULL,
    precio      REAL NOT NULL,
    descuento   REAL NOT NULL DEFAULT 0,
    iva         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS movimientos (
    id               INTEGER PRIMARY KEY,
    usuario_id       INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    producto_id      INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    fecha            TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    cantidad         REAL NOT NULL,
    stock_resultante REAL NOT NULL,
    motivo           TEXT NOT NULL,
    albaran_id       INTEGER REFERENCES albaranes(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS historial (
    id         INTEGER PRIMARY KEY,
    albaran_id INTEGER NOT NULL REFERENCES albaranes(id) ON DELETE CASCADE,
    fecha      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    texto      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contadores (
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    clave      TEXT NOT NULL,
    valor      INTEGER NOT NULL,
    PRIMARY KEY (usuario_id, clave)
);

CREATE INDEX IF NOT EXISTS ix_clientes_usuario ON clientes(usuario_id);
CREATE INDEX IF NOT EXISTS ix_productos_usuario ON productos(usuario_id);
CREATE INDEX IF NOT EXISTS ix_albaranes_usuario ON albaranes(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS ix_lineas_albaran ON lineas(albaran_id);
CREATE INDEX IF NOT EXISTS ix_movimientos_producto ON movimientos(producto_id);
"""


def carpeta_datos() -> Path:
    """Carpeta donde se guardan los datos (se puede cambiar con la variable ALBARANES_DATOS)."""
    personalizada = os.environ.get("ALBARANES_DATOS")
    if personalizada:
        carpeta = Path(personalizada)
    else:
        carpeta = Path(os.environ.get("APPDATA") or Path.home()) / "GestionAlbaranes"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_bd() -> Path:
    return carpeta_datos() / "albaranes.db"


def conectar(ruta=None) -> sqlite3.Connection:
    """Abre la base de datos (":memory:" para pruebas) y crea las tablas si faltan."""
    conn = sqlite3.connect(str(ruta if ruta is not None else ruta_bd()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(ESQUEMA)
    conn.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")
    conn.commit()
    return conn


def guardar_copia(conn: sqlite3.Connection, destino) -> None:
    """Copia de seguridad completa (todas las cuentas) en el archivo indicado."""
    destino = Path(destino)
    if destino.exists():
        destino.unlink()
    copia = sqlite3.connect(str(destino))
    try:
        conn.backup(copia)
    finally:
        copia.close()


def restaurar_copia(origen, destino=None) -> None:
    """Sustituye la base de datos por una copia. La conexión actual debe estar cerrada."""
    origen = Path(origen)
    try:
        prueba = sqlite3.connect(f"file:{origen.as_posix()}?mode=ro", uri=True)
        tablas = {r[0] for r in prueba.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        prueba.close()
    except sqlite3.DatabaseError:
        raise ErrorUsuario("El archivo no es una copia de seguridad válida.") from None
    if not {"usuarios", "albaranes", "productos"} <= tablas:
        raise ErrorUsuario("El archivo no es una copia de seguridad de esta aplicación.")
    shutil.copyfile(origen, destino or ruta_bd())


# ---------- Preferencias de la aplicación (último usuario, etc.) ----------


def _ruta_config() -> Path:
    return carpeta_datos() / "config.json"


def leer_config() -> dict:
    try:
        return json.loads(_ruta_config().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_config(**valores) -> None:
    config = leer_config()
    config.update(valores)
    try:
        _ruta_config().write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
