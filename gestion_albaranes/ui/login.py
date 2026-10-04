"""Pantalla de inicio de sesión y creación de cuenta."""

import customtkinter as ctk

from .. import APP_NOMBRE, auth, db
from ..errores import ErrorUsuario
from ..logica import Gestion
from .comun import AZUL, FONDO, ROJO, SUAVE, TEXTO, boton, fuente, panel


class PantallaLogin(ctk.CTkFrame):
    def __init__(self, master, conn, al_entrar):
        super().__init__(master, fg_color=FONDO, corner_radius=0)
        self.conn = conn
        self.al_entrar = al_entrar
        self.modo = "entrar" if auth.hay_usuarios(conn) else "crear"

        tarjeta = panel(self, width=440)
        tarjeta.place(relx=0.5, rely=0.47, anchor="center")
        ctk.CTkLabel(tarjeta, text="📦", font=fuente(44)).pack(pady=(28, 0))
        ctk.CTkLabel(tarjeta, text=APP_NOMBRE, font=fuente(24, True), text_color=TEXTO).pack()
        self.subtitulo = ctk.CTkLabel(tarjeta, text="", font=fuente(13), text_color=SUAVE)
        self.subtitulo.pack(pady=(2, 14))

        self.selector = ctk.CTkSegmentedButton(tarjeta, values=["Iniciar sesión", "Crear cuenta"], command=self._cambiar_modo,
                                               font=fuente(13), height=34, selected_color=AZUL)
        self.selector.pack(fill="x", padx=36)

        self.formulario = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self.formulario.pack(fill="x", padx=36, pady=(12, 0))
        self.entradas: dict[str, ctk.CTkEntry] = {}
        for clave, texto, oculto in [
            ("nombre", "Tu nombre", False),
            ("usuario", "Usuario", False),
            ("contrasena", "Contraseña", True),
            ("repetir", "Repite la contraseña", True),
        ]:
            entrada = ctk.CTkEntry(self.formulario, placeholder_text=texto, height=40, font=fuente(14), show="•" if oculto else "")
            entrada.bind("<Return>", lambda _e: self._enviar())
            self.entradas[clave] = entrada

        self.ver = ctk.CTkCheckBox(self.formulario, text="Mostrar contraseña", font=fuente(12), command=self._mostrar_contrasena,
                                   checkbox_width=18, checkbox_height=18)
        self.demo = ctk.CTkCheckBox(self.formulario, text="Rellenar con datos de ejemplo para probar", font=fuente(12),
                                    checkbox_width=18, checkbox_height=18)

        self.error = ctk.CTkLabel(tarjeta, text="", text_color=ROJO, font=fuente(12, True), wraplength=360, justify="center")
        self.error.pack(padx=36, pady=(6, 0))
        self.boton = boton(tarjeta, "", self._enviar, "primario", height=42, font=fuente(15, True))
        self.boton.pack(fill="x", padx=36, pady=(4, 30))

        ctk.CTkLabel(self, text="Tus datos se guardan solo en este ordenador.", font=fuente(11), text_color=SUAVE).place(
            relx=0.5, rely=0.97, anchor="s")

        self.selector.set("Iniciar sesión" if self.modo == "entrar" else "Crear cuenta")
        self._pintar()

    def _cambiar_modo(self, valor):
        self.modo = "entrar" if valor == "Iniciar sesión" else "crear"
        self.error.configure(text="")
        self._pintar()

    def _pintar(self):
        for w in self.formulario.winfo_children():
            w.pack_forget()
        crear = self.modo == "crear"
        claves = ["nombre", "usuario", "contrasena", "repetir"] if crear else ["usuario", "contrasena"]
        for clave in claves:
            self.entradas[clave].pack(fill="x", pady=5)
        self.ver.pack(anchor="w", pady=(4, 2))
        if crear:
            self.demo.pack(anchor="w", pady=(2, 0))
            if not auth.hay_usuarios(self.conn):
                self.demo.select()
        self.subtitulo.configure(text="Crea tu cuenta para empezar" if crear else "Inicia sesión con tu cuenta")
        self.boton.configure(text="Crear cuenta y entrar" if crear else "Entrar")

        if not crear:
            ultimo = db.leer_config().get("ultimo_usuario", "")
            if ultimo and not self.entradas["usuario"].get():
                self.entradas["usuario"].insert(0, ultimo)
        primero = self.entradas["nombre" if crear else ("contrasena" if self.entradas["usuario"].get() else "usuario")]
        self.after(50, primero.focus_set)

    def _mostrar_contrasena(self):
        mostrar = "" if self.ver.get() else "•"
        self.entradas["contrasena"].configure(show=mostrar)
        self.entradas["repetir"].configure(show=mostrar)

    def _enviar(self):
        valores = {k: e.get() for k, e in self.entradas.items()}
        self.boton.configure(state="disabled")
        self.update_idletasks()
        try:
            if self.modo == "crear":
                usuario = auth.registrar(self.conn, valores["usuario"], valores["nombre"], valores["contrasena"], valores["repetir"])
                if self.demo.get():
                    Gestion(self.conn, usuario["id"]).cargar_datos_demo()
            else:
                usuario = auth.iniciar_sesion(self.conn, valores["usuario"], valores["contrasena"])
        except ErrorUsuario as e:
            self.error.configure(text=str(e))
            self.entradas["contrasena"].delete(0, "end")
            self.entradas["repetir"].delete(0, "end")
            self.boton.configure(state="normal")
            return
        db.guardar_config(ultimo_usuario=usuario["usuario"])
        self.al_entrar(usuario)
