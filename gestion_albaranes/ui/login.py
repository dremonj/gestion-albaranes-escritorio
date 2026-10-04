"""Pantalla de inicio de sesión y creación de cuenta."""

import customtkinter as ctk

from .. import APP_NOMBRE, auth, db, demo
from ..errores import ErrorUsuario
from ..logica import Gestion
from .comun import AZUL, FONDO, ROJO, SUAVE, TEXTO, boton, fuente, panel

# (clave, etiqueta, oculto, ayuda bajo el campo)
CAMPOS = {
    "nombre": ("Tu nombre", False, "Ej.: Dani"),
    "usuario": ("Usuario", False, "Sin espacios ni tildes. Ej.: dani"),
    "contrasena": ("Contraseña", True, "Mínimo 6 caracteres"),
    "repetir": ("Repite la contraseña", True, ""),
}


class PantallaLogin(ctk.CTkFrame):
    def __init__(self, master, conn, al_entrar):
        super().__init__(master, fg_color=FONDO, corner_radius=0)
        self.conn = conn
        self.al_entrar = al_entrar
        self.modo = "entrar" if auth.hay_usuarios(conn) else "crear"

        tarjeta = panel(self, width=460)
        tarjeta.place(relx=0.5, rely=0.47, anchor="center")
        ctk.CTkLabel(tarjeta, text="📦", font=fuente(40)).pack(pady=(24, 0))
        ctk.CTkLabel(tarjeta, text=APP_NOMBRE, font=fuente(24, True), text_color=TEXTO).pack()
        self.subtitulo = ctk.CTkLabel(tarjeta, text="", font=fuente(13), text_color=SUAVE)
        self.subtitulo.pack(pady=(2, 12))

        self.selector = ctk.CTkSegmentedButton(tarjeta, values=["Iniciar sesión", "Crear cuenta"], command=self._cambiar_modo,
                                               font=fuente(13), height=34, selected_color=AZUL)
        self.selector.pack(fill="x", padx=36)

        self.formulario = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self.formulario.pack(fill="x", padx=36, pady=(8, 0))
        self.bloques: dict[str, ctk.CTkFrame] = {}
        self.entradas: dict[str, ctk.CTkEntry] = {}
        self.pistas: list[ctk.CTkLabel] = []
        for clave, (etiqueta, oculto, ayuda) in CAMPOS.items():
            bloque = ctk.CTkFrame(self.formulario, fg_color="transparent")
            fila = ctk.CTkFrame(bloque, fg_color="transparent")
            fila.pack(fill="x")
            ctk.CTkLabel(fila, text=etiqueta, font=fuente(12, True), text_color=TEXTO, anchor="w").pack(side="left")
            if ayuda:
                pista = ctk.CTkLabel(fila, text=ayuda, font=fuente(11), text_color=SUAVE, anchor="e")
                pista.pack(side="right")
                self.pistas.append(pista)
            entrada = ctk.CTkEntry(bloque, height=38, font=fuente(14), show="•" if oculto else "")
            entrada.pack(fill="x", pady=(2, 0))
            entrada.bind("<Return>", lambda _e: self._enviar())
            self.bloques[clave] = bloque
            self.entradas[clave] = entrada

        self.ver = ctk.CTkCheckBox(self.formulario, text="Mostrar contraseña", font=fuente(12), command=self._mostrar_contrasena,
                                   checkbox_width=18, checkbox_height=18)
        self.datos_ejemplo = ctk.CTkCheckBox(self.formulario, text="Rellenar mi cuenta con datos de ejemplo", font=fuente(12),
                                             checkbox_width=18, checkbox_height=18)

        self.error = ctk.CTkLabel(tarjeta, text="", text_color=ROJO, font=fuente(12, True), wraplength=380, justify="center")
        self.error.pack(padx=36, pady=(6, 0))
        self.boton = boton(tarjeta, "", self._enviar, "primario", height=42, font=fuente(15, True))
        self.boton.pack(fill="x", padx=36, pady=(2, 8))

        # Acceso a la cuenta de prueba (se crea sola la primera vez que se abre la aplicación)
        self.caja_demo = ctk.CTkFrame(tarjeta, fg_color="#f0f6ff", corner_radius=8, border_width=1, border_color="#cfe0ff")
        ctk.CTkLabel(self.caja_demo, text="¿Solo quieres probarla?", font=fuente(12, True), text_color=TEXTO).pack(pady=(8, 0))
        ctk.CTkLabel(self.caja_demo, text=f"Usuario: {demo.USUARIO}     Contraseña: {demo.CONTRASENA}",
                     font=fuente(12), text_color=SUAVE).pack(padx=10)
        boton(self.caja_demo, "Entrar con la cuenta de prueba", self._entrar_demo, height=32).pack(pady=(4, 10))

        ctk.CTkLabel(self, text="Tus datos se guardan solo en este ordenador.", font=fuente(11), text_color=SUAVE).place(
            relx=0.5, rely=0.97, anchor="s")

        self.selector.set("Iniciar sesión" if self.modo == "entrar" else "Crear cuenta")
        self._pintar()
        # Cuando la ventana ya está visible, el cursor se coloca en el primer campo.
        self.after(400, self._enfocar)

    def _cambiar_modo(self, valor):
        self.modo = "entrar" if valor == "Iniciar sesión" else "crear"
        self.error.configure(text="")
        self._pintar()
        self._enfocar()

    def _pintar(self):
        for w in self.formulario.winfo_children():
            w.pack_forget()
        crear = self.modo == "crear"
        for clave in ["nombre", "usuario", "contrasena", "repetir"] if crear else ["usuario", "contrasena"]:
            self.bloques[clave].pack(fill="x", pady=4)
        for pista in self.pistas:  # las pistas solo hacen falta al crear la cuenta
            if crear:
                pista.pack(side="right")
            else:
                pista.pack_forget()
        self.ver.pack(anchor="w", pady=(6, 2))
        if crear:
            self.datos_ejemplo.pack(anchor="w", pady=(2, 0))
        self.subtitulo.configure(text="Crea tu cuenta" if crear else "Inicia sesión con tu cuenta")
        self.boton.configure(text="Crear cuenta y entrar" if crear else "Entrar")
        if not crear:
            ultimo = db.leer_config().get("ultimo_usuario", "")
            if ultimo and not self.entradas["usuario"].get():
                self.entradas["usuario"].insert(0, ultimo)
        if demo.existe(self.conn) and not crear:
            self.caja_demo.pack(fill="x", padx=36, pady=(4, 24))
        else:
            self.caja_demo.pack_forget()
            self.boton.pack_configure(pady=(2, 28))

    def _enfocar(self):
        crear = self.modo == "crear"
        if crear:
            vacio = next((k for k in ("nombre", "usuario", "contrasena", "repetir") if not self.entradas[k].get()), "nombre")
        else:
            vacio = "contrasena" if self.entradas["usuario"].get() else "usuario"
        try:
            self.winfo_toplevel().focus_force()
            self.entradas[vacio].focus_set()
        except Exception:
            pass

    def _mostrar_contrasena(self):
        mostrar = "" if self.ver.get() else "•"
        self.entradas["contrasena"].configure(show=mostrar)
        self.entradas["repetir"].configure(show=mostrar)

    def _entrar_demo(self):
        self.entradas["usuario"].delete(0, "end")
        self.entradas["usuario"].insert(0, demo.USUARIO)
        self.entradas["contrasena"].delete(0, "end")
        self.entradas["contrasena"].insert(0, demo.CONTRASENA)
        self._enviar()

    def _enviar(self):
        valores = {k: e.get() for k, e in self.entradas.items()}
        self.error.configure(text="")
        self.boton.configure(state="disabled")
        self.update_idletasks()
        try:
            if self.modo == "crear":
                usuario = auth.registrar(self.conn, valores["usuario"], valores["nombre"], valores["contrasena"], valores["repetir"])
                if self.datos_ejemplo.get():
                    Gestion(self.conn, usuario["id"]).cargar_datos_demo()
            else:
                usuario = auth.iniciar_sesion(self.conn, valores["usuario"], valores["contrasena"])
        except ErrorUsuario as e:
            self.error.configure(text=str(e))
            if self.modo == "entrar":
                self.entradas["contrasena"].delete(0, "end")
            self.boton.configure(state="normal")
            self._enfocar()
            return
        finally:
            if self.boton.winfo_exists():
                self.boton.configure(state="normal")
        db.guardar_config(ultimo_usuario=usuario["usuario"])
        self.al_entrar(usuario)
