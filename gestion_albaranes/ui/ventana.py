"""Ventana principal: alterna entre el inicio de sesión y la aplicación con su menú lateral."""

import sys
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import APP_NOMBRE, VERSION, db, demo
from ..errores import ErrorUsuario
from ..logica import Gestion
from .comun import FONDO, MENU, MENU_HOVER, AZUL, AZUL_OSC, Aviso, configurar_estilos, error, fuente
from .login import PantallaLogin
from .vistas_albaranes import VistaAlbaranes, VistaDetalle, VistaEditor
from .vistas_inventario import VistaInventario, VistaProducto
from .vistas_otras import VistaAcerca, VistaAjustes, VistaClientes, VistaInicio

VISTAS = {
    "inicio": VistaInicio,
    "albaranes": VistaAlbaranes,
    "editor": VistaEditor,
    "detalle": VistaDetalle,
    "inventario": VistaInventario,
    "producto": VistaProducto,
    "clientes": VistaClientes,
    "ajustes": VistaAjustes,
    "acerca": VistaAcerca,
}

MENU_ITEMS = [
    ("inicio", "🏠  Inicio"),
    ("albaranes", "🧾  Albaranes"),
    ("nuevo", "＋  Nuevo albarán"),
    ("inventario", "📦  Inventario"),
    ("clientes", "👥  Clientes"),
    ("ajustes", "⚙  Mi empresa y cuenta"),
    ("acerca", "ℹ  Acerca de"),
]

# Qué opción del menú se ilumina en cada pantalla.
SECCION_MENU = {"detalle": "albaranes", "producto": "inventario"}


def ruta_recurso(nombre: str) -> Path:
    """Ruta a un archivo de recursos, tanto ejecutando el código como desde el .exe de PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "recursos" / nombre


class Aplicacion(ctk.CTk):
    def __init__(self, conn=None):
        super().__init__()
        self.conn = conn or db.conectar()
        self.report_callback_exception = self._error_inesperado
        try:
            demo.asegurar_cuenta_demo(self.conn)
        except Exception:
            self._registrar_error(traceback.format_exc())
        configurar_estilos(self)
        self.title(APP_NOMBRE)
        self.geometry("1280x800")
        self.minsize(1100, 680)
        self.configure(fg_color=FONDO)
        icono = ruta_recurso("icono.ico")
        if icono.exists():
            try:
                self.iconbitmap(str(icono))
            except Exception:
                pass
        self.pantalla = None
        self.after(0, lambda: self.state("zoomed") if sys.platform == "win32" else None)
        self.mostrar_login()

    @staticmethod
    def _registrar_error(texto):
        try:
            with open(db.carpeta_datos() / "errores.log", "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} (versión {VERSION}) ---\n{texto}\n")
        except OSError:
            pass

    def _error_inesperado(self, tipo, valor, tb):
        """Cualquier fallo no previsto se guarda en errores.log y se avisa al usuario en vez de pasar en silencio."""
        self._registrar_error("".join(traceback.format_exception(tipo, valor, tb)))
        messagebox.showerror("Error inesperado", f"Ha ocurrido un error inesperado:\n\n{valor}\n\n"
                             f"Se ha guardado el detalle en:\n{db.carpeta_datos() / 'errores.log'}", parent=self)

    def _cambiar(self, pantalla):
        if self.pantalla is not None:
            self.pantalla.destroy()
        self.pantalla = pantalla
        pantalla.pack(fill="both", expand=True)

    def mostrar_login(self):
        self.title(APP_NOMBRE)
        self._cambiar(PantallaLogin(self, self.conn, self.entrar))

    def entrar(self, usuario):
        self.title(f"{APP_NOMBRE} — {usuario['nombre']}")
        self._cambiar(Principal(self, self.conn, usuario, self.mostrar_login))

    def restaurar_copia(self, ruta):
        self.conn.close()
        try:
            db.restaurar_copia(ruta)
        except ErrorUsuario as e:
            self.conn = db.conectar()
            error(self, str(e))
            return
        self.conn = db.conectar()
        self.mostrar_login()


class Principal(ctk.CTkFrame):
    """Menú lateral + zona de contenido. Las pantallas acceden aquí a los datos (self.g) y a la navegación (self.ir)."""

    def __init__(self, master, conn, usuario, al_salir):
        super().__init__(master, fg_color=FONDO, corner_radius=0)
        self.conn = conn
        self.usuario = usuario
        self.al_salir = al_salir
        self.g = Gestion(conn, usuario["id"])
        self.filtros = {}
        self.vista = None
        self.aviso = Aviso(self)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        menu = ctk.CTkFrame(self, fg_color=MENU, corner_radius=0, width=230)
        menu.grid(row=0, column=0, sticky="nsw")
        menu.grid_propagate(False)
        menu.pack_propagate(False)
        ctk.CTkLabel(menu, text="📦  Gestión de\n      Albaranes", font=fuente(17, True), text_color="#ffffff",
                     justify="left", anchor="w").pack(fill="x", padx=18, pady=(22, 20))
        self.botones = {}
        for clave, texto in MENU_ITEMS:
            destacado = clave == "nuevo"
            b = ctk.CTkButton(menu, text=texto, anchor="w" if not destacado else "center", height=40, corner_radius=8,
                              font=fuente(14, destacado), fg_color=AZUL if destacado else "transparent",
                              hover_color=AZUL_OSC if destacado else MENU_HOVER, text_color="#d9e2ec" if not destacado else "#ffffff",
                              command=lambda c=clave: self.ir("editor") if c == "nuevo" else self.ir(c))
            b.pack(fill="x", padx=12, pady=(8 if destacado else 2, 8 if destacado else 2))
            self.botones[clave] = b

        cuenta = ctk.CTkFrame(menu, fg_color="transparent")
        cuenta.pack(side="bottom", fill="x", padx=12, pady=16)
        ctk.CTkLabel(cuenta, text=f"👤 {usuario['nombre']}", font=fuente(13, True), text_color="#ffffff", anchor="w").pack(fill="x", padx=6)
        ctk.CTkLabel(cuenta, text=f"@{usuario['usuario']}", font=fuente(12), text_color="#9fb3c8", anchor="w").pack(fill="x", padx=6)
        ctk.CTkButton(cuenta, text="⏻  Cerrar sesión", command=self.cerrar_sesion, fg_color="transparent", border_width=1,
                      border_color="#486581", hover_color=MENU_HOVER, text_color="#d9e2ec", height=34, font=fuente(13)).pack(fill="x", pady=(10, 0))

        self.contenido = ctk.CTkFrame(self, fg_color=FONDO, corner_radius=0)
        self.contenido.grid(row=0, column=1, sticky="nsew")
        self.ir("inicio")

    def ir(self, seccion, **parametros):
        if self.vista is not None and hasattr(self.vista, "puede_salir") and not self.vista.puede_salir():
            return
        try:
            nueva = VISTAS[seccion](self.contenido, self, **parametros)
        except ErrorUsuario as e:
            error(self, str(e))
            return
        if self.vista is not None:
            self.vista.destroy()
        self.vista = nueva
        nueva.pack(fill="both", expand=True, padx=28, pady=22)
        activa = "nuevo" if seccion == "editor" and not parametros.get("albaran_id") else SECCION_MENU.get(seccion, seccion)
        if seccion == "editor" and parametros.get("albaran_id"):
            activa = "albaranes"
        for clave, b in self.botones.items():
            if clave == "nuevo":
                continue
            b.configure(fg_color=MENU_HOVER if clave == activa else "transparent", text_color="#ffffff" if clave == activa else "#d9e2ec")

    def avisar(self, texto, tipo="ok"):
        self.aviso.mostrar(texto, tipo)

    def cerrar_sesion(self):
        if self.vista is not None and hasattr(self.vista, "puede_salir") and not self.vista.puede_salir():
            return
        self.al_salir()
