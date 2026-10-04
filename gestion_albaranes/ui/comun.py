"""Colores, tipografías y componentes reutilizables de la interfaz."""

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from ..errores import ErrorUsuario
from ..logica import NOMBRE_ESTADO

# ---------- Estilo ----------

AZUL = "#1f6feb"
AZUL_OSC = "#1a5fcc"
MENU = "#102a43"
MENU_HOVER = "#243b53"
FONDO = "#f4f6f9"
BLANCO = "#ffffff"
BORDE = "#dde3ea"
TEXTO = "#1f2933"
SUAVE = "#616e7c"
ROJO = "#c62828"
ROJO_FONDO = "#fff1f1"
VERDE = "#2e7d32"

COLOR_ESTADO = {
    "borrador": ("#eceff3", "#52606d"),
    "emitido": ("#fff3cd", "#8a5a00"),
    "entregado": ("#dcf5e3", "#1e6b34"),
    "anulado": ("#fde2e2", "#a61b1b"),
}

FUENTE = "Segoe UI"


def fuente(tamano=13, negrita=False):
    return ctk.CTkFont(family=FUENTE, size=tamano, weight="bold" if negrita else "normal")


def configurar_estilos(raiz) -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    escala = 1.0
    try:
        escala = raiz._get_window_scaling()
    except AttributeError:
        pass
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    estilo.configure("Treeview", font=(FUENTE, 10), rowheight=int(30 * escala), background=BLANCO,
                     fieldbackground=BLANCO, foreground=TEXTO, borderwidth=0)
    estilo.configure("Treeview.Heading", font=(FUENTE, 9, "bold"), background="#f8fafc", foreground=SUAVE,
                     relief="flat", padding=(6, 6))
    estilo.map("Treeview", background=[("selected", "#dbe8ff")], foreground=[("selected", TEXTO)])
    estilo.map("Treeview.Heading", background=[("active", "#eef2f7")])


# ---------- Botones ----------


def boton(master, texto, comando, tipo="normal", **kw):
    """tipo: 'primario', 'normal' o 'peligro'."""
    estilos = {
        "primario": dict(fg_color=AZUL, hover_color=AZUL_OSC, text_color=BLANCO, border_width=0),
        "normal": dict(fg_color=BLANCO, hover_color="#eef2f7", text_color=TEXTO, border_width=1, border_color=BORDE),
        "peligro": dict(fg_color=BLANCO, hover_color=ROJO_FONDO, text_color=ROJO, border_width=1, border_color="#f0c4c4"),
    }
    opciones = dict(height=34, corner_radius=8, font=fuente(13, tipo == "primario"))
    opciones.update(estilos[tipo])
    opciones.update(kw)
    return ctk.CTkButton(master, text=texto, command=comando, **opciones)


def etiqueta_estado(master, estado):
    fondo, texto = COLOR_ESTADO.get(estado, ("#eee", "#333"))
    return ctk.CTkLabel(master, text=f"  {NOMBRE_ESTADO.get(estado, estado)}  ", fg_color=fondo, text_color=texto,
                        corner_radius=10, font=fuente(12, True), height=24)


def panel(master, **kw):
    opciones = dict(fg_color=BLANCO, corner_radius=10, border_width=1, border_color=BORDE)
    opciones.update({k: v for k, v in kw.items() if v is not None})
    return ctk.CTkFrame(master, **opciones)


def titulo(master, texto):
    return ctk.CTkLabel(master, text=texto, font=fuente(24, True), text_color=TEXTO, anchor="w")


def subtitulo(master, texto):
    return ctk.CTkLabel(master, text=texto, font=fuente(16, True), text_color=TEXTO, anchor="w")


def ayuda(master, texto, **kw):
    return ctk.CTkLabel(master, text=texto, font=fuente(12), text_color=SUAVE, anchor="w", justify="left", **kw)


# ---------- Mensajes ----------


def confirmar(padre, titulo_, mensaje) -> bool:
    return messagebox.askyesno(titulo_, mensaje, parent=padre)


def error(padre, mensaje) -> None:
    messagebox.showerror("No se ha podido completar", mensaje, parent=padre)


# ---------- Tabla ----------


class Tabla(ctk.CTkFrame):
    """Tabla (ttk.Treeview) con barra de desplazamiento.

    columnas: lista de (clave, título, ancho, alineación) donde alineación es 'w', 'e' o 'center'.
    """

    def __init__(self, master, columnas, alto=12, al_abrir=None, **kw):
        super().__init__(master, fg_color=BLANCO, corner_radius=10, border_width=1, border_color=BORDE, **kw)
        self.al_abrir = al_abrir
        claves = [c[0] for c in columnas]
        self.arbol = ttk.Treeview(self, columns=claves, show="headings", height=alto, selectmode="browse")
        for clave, cabecera, ancho, alineacion in columnas:
            self.arbol.heading(clave, text=cabecera, anchor=alineacion)
            # Solo se estiran las columnas de texto anchas (nombre, descripción…).
            self.arbol.column(clave, width=ancho, minwidth=40, anchor=alineacion, stretch=alineacion == "w" and ancho >= 200)
        # height pequeño: por defecto la barra mide 200 px y estiraría las tablas cortas.
        barra = ctk.CTkScrollbar(self, command=self.arbol.yview, height=20)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        barra.grid(row=0, column=1, sticky="ns", pady=6)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.arbol.tag_configure("rojo", foreground=ROJO)
        self.arbol.tag_configure("verde", foreground=VERDE)
        self.arbol.tag_configure("suave", foreground=SUAVE)
        self.arbol.tag_configure("par", background="#fafbfc")
        self.arbol.bind("<Double-1>", self._abrir)
        self.arbol.bind("<Return>", self._abrir)

    def _abrir(self, _evento=None):
        if self.al_abrir and self.seleccion() is not None:
            self.al_abrir(self.seleccion())

    def cargar(self, filas, vacio="No hay datos que mostrar."):
        """filas: lista de (id, valores, etiquetas)."""
        anterior = self.seleccion()
        self.arbol.delete(*self.arbol.get_children())
        if not filas:
            columnas = self.arbol["columns"]
            valores = [""] * len(columnas)
            valores[min(1, len(columnas) - 1)] = vacio
            self.arbol.insert("", "end", iid="__vacio__", values=valores, tags=("suave",))
            return
        for i, (iid, valores, etiquetas) in enumerate(filas):
            self.arbol.insert("", "end", iid=str(iid), values=valores, tags=tuple(etiquetas) + (("par",) if i % 2 else ()))
        if anterior is not None and self.arbol.exists(str(anterior)):
            self.arbol.selection_set(str(anterior))
            self.arbol.see(str(anterior))

    def seleccion(self):
        sel = self.arbol.selection()
        if not sel or sel[0] == "__vacio__":
            return None
        return int(sel[0])

    def seleccionar(self, iid):
        if self.arbol.exists(str(iid)):
            self.arbol.selection_set(str(iid))
            self.arbol.focus(str(iid))
            self.arbol.see(str(iid))


# ---------- Formularios ----------


class Formulario:
    """Ayuda a crear campos etiquetados en una rejilla y a leer sus valores."""

    def __init__(self, master, columnas=2):
        self.master = master
        self.columnas = columnas
        self.campos: dict[str, object] = {}
        self.fila = 0
        self.col = 0
        for c in range(columnas):
            master.grid_columnconfigure(c, weight=1, uniform="form")

    def _colocar(self, widget_etiqueta, widget, ancho):
        if self.col + ancho > self.columnas:
            self.fila += 2
            self.col = 0
        widget_etiqueta.grid(row=self.fila, column=self.col, columnspan=ancho, sticky="w", padx=6, pady=(6, 0))
        widget.grid(row=self.fila + 1, column=self.col, columnspan=ancho, sticky="ew", padx=6, pady=(2, 4))
        self.col += ancho
        if self.col >= self.columnas:
            self.fila += 2
            self.col = 0

    def _etiqueta(self, texto):
        return ctk.CTkLabel(self.master, text=texto, font=fuente(12, True), text_color=SUAVE, anchor="w")

    def texto(self, clave, etiqueta, valor="", ancho=1, **kw):
        entrada = ctk.CTkEntry(self.master, height=34, font=fuente(13), **kw)
        if valor not in (None, ""):
            entrada.insert(0, str(valor))
        self._colocar(self._etiqueta(etiqueta), entrada, ancho)
        self.campos[clave] = entrada
        return entrada

    def opciones(self, clave, etiqueta, valores, valor=None, ancho=1):
        menu = ctk.CTkOptionMenu(self.master, values=list(valores), height=34, font=fuente(13), fg_color=BLANCO,
                                 button_color="#e6ebf1", button_hover_color="#d5dde7", text_color=TEXTO,
                                 dropdown_font=fuente(13))
        if valor is not None:
            menu.set(str(valor))
        self._colocar(self._etiqueta(etiqueta), menu, ancho)
        self.campos[clave] = menu
        return menu

    def area(self, clave, etiqueta, valor="", ancho=None, alto=70):
        caja = ctk.CTkTextbox(self.master, height=alto, font=fuente(13), border_width=2, border_color="#c8d1dc", fg_color=BLANCO)
        if valor:
            caja.insert("1.0", valor)
        self._colocar(self._etiqueta(etiqueta), caja, ancho or self.columnas)
        self.campos[clave] = caja
        return caja

    def nota(self, texto, ancho=None):
        if self.col:
            self.fila += 2
            self.col = 0
        ayuda(self.master, texto, wraplength=560).grid(row=self.fila, column=0, columnspan=ancho or self.columnas, sticky="w", padx=6, pady=4)
        self.fila += 2

    def valores(self) -> dict:
        datos = {}
        for clave, w in self.campos.items():
            datos[clave] = w.get("1.0", "end-1c") if isinstance(w, ctk.CTkTextbox) else w.get()
        return datos


class Dialogo(ctk.CTkToplevel):
    """Ventana modal con un formulario, mensaje de error y botones Cancelar / Aceptar.

    Las subclases rellenan self.cuerpo en construir() y hacen el trabajo en aceptar(),
    que debe lanzar ErrorUsuario si algo no es válido.
    """

    def __init__(self, padre, titulo_, texto_aceptar="Guardar", ancho=620, al_terminar=None):
        super().__init__(padre)
        self.withdraw()
        self.title(titulo_)
        self.configure(fg_color=BLANCO)
        self.resizable(False, False)
        self.transient(padre.winfo_toplevel())
        self.al_terminar = al_terminar
        self.resultado = None

        ctk.CTkLabel(self, text=titulo_, font=fuente(18, True), text_color=TEXTO, anchor="w").pack(fill="x", padx=22, pady=(18, 6))
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent", width=ancho)
        self.cuerpo.pack(fill="both", expand=True, padx=16)
        self.construir()
        self.mensaje = ctk.CTkLabel(self, text="", text_color=ROJO, font=fuente(12, True), anchor="w", justify="left", wraplength=ancho - 40)
        self.mensaje.pack(fill="x", padx=22)
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=22, pady=(4, 18))
        boton(pie, texto_aceptar, self._aceptar, "primario").pack(side="right")
        boton(pie, "Cancelar", self.destroy).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self._aceptar() if not isinstance(e.widget, tk.Text) else None)
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(10, self._mostrar)

    def _mostrar(self):
        self.update_idletasks()
        padre = self.master.winfo_toplevel()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_width()) // 2
        y = padre.winfo_rooty() + max(40, (padre.winfo_height() - self.winfo_height()) // 3)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.lift()
        self.grab_set()
        self.focus_force()
        foco = self.primer_foco()
        if foco is not None:
            foco.focus_set()

    def primer_foco(self):
        return None

    def construir(self):
        raise NotImplementedError

    def aceptar(self):
        raise NotImplementedError

    def _aceptar(self):
        try:
            self.resultado = self.aceptar()
        except ErrorUsuario as e:
            self.mensaje.configure(text=str(e))
            return
        self.grab_release()
        self.destroy()
        if self.al_terminar:
            self.al_terminar(self.resultado)


class Aviso:
    """Mensaje breve en la esquina inferior derecha que desaparece solo."""

    def __init__(self, ventana):
        self.ventana = ventana
        self.etiqueta = None
        self.tarea = None

    def mostrar(self, texto, tipo="ok"):
        if self.etiqueta is not None:
            self.etiqueta.destroy()
            self.ventana.after_cancel(self.tarea)
        color = {"ok": "#1f2933", "error": ROJO}[tipo]
        self.etiqueta = ctk.CTkLabel(self.ventana, text=f"  {'✔' if tipo == 'ok' else '⚠'}  {texto}  ", fg_color=color,
                                     text_color=BLANCO, corner_radius=8, font=fuente(13), height=40, wraplength=420)
        self.etiqueta.place(relx=1.0, rely=1.0, x=-20, y=-20, anchor="se")
        self.tarea = self.ventana.after(3800, self._ocultar)

    def _ocultar(self):
        if self.etiqueta is not None:
            self.etiqueta.destroy()
            self.etiqueta = None
