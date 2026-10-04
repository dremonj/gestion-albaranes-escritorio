import pytest

from gestion_albaranes import auth, db
from gestion_albaranes.logica import Gestion


@pytest.fixture(autouse=True)
def hash_rapido(monkeypatch):
    # En las pruebas no hace falta un hash lento; en la aplicación real se usan 600.000 iteraciones.
    monkeypatch.setattr(auth, "ITERACIONES", 1000)


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def usuario(conn):
    return auth.registrar(conn, "dani", "Dani", "secreto1", "secreto1")


@pytest.fixture
def g(conn, usuario):
    return Gestion(conn, usuario["id"])


@pytest.fixture
def datos(g):
    """Una cuenta con un cliente y dos productos."""
    cliente = g.guardar_cliente({"nombre": "Cliente de prueba", "nif": "b123"})
    p1 = g.guardar_producto({"referencia": "p-1", "nombre": "Producto 1", "precio": "10", "iva": 21, "stock": 50, "stock_minimo": 5})
    p2 = g.guardar_producto({"referencia": "P-2", "nombre": "Producto 2", "precio": "3,5", "iva": 10, "stock": 10})
    return {"cliente": cliente, "p1": p1, "p2": p2}


def linea(g, producto_id, cantidad, **extra):
    p = g.producto(producto_id)
    return {"producto_id": p["id"], "descripcion": p["nombre"], "cantidad": cantidad, "precio": p["precio"], "iva": p["iva"], **extra}
