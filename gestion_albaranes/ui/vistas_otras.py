"""Pantallas de inicio, clientes, ajustes (empresa y cuenta) y «Acerca de»."""

from tkinter import filedialog

import customtkinter as ctk

from .. import APP_NOMBRE, VERSION, auth, db
from ..errores import ErrorUsuario
from ..logica import cant, euros, hoy
from .comun import (AZUL, BORDE, ROJO, ROJO_FONDO, SUAVE, TEXTO, Formulario, Tabla, ayuda, boton, confirmar, error,
                    etiqueta_estado, fuente, panel, subtitulo, titulo)
from .dialogos import DialogoCliente
from .vistas_albaranes import COLUMNAS_ALBARANES, filas_albaranes
from .vistas_inventario import mensaje_eliminado

# ---------- Inicio ----------


class VistaInicio(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        r = app.g.resumen()

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x")
        titulo(cab, f"Hola, {app.usuario['nombre']} 👋").pack(side="left")
        boton(cab, "＋ Nuevo albarán", lambda: app.ir("editor"), "primario").pack(side="right")

        if not app.g.empresa()["nombre"]:
            aviso = ctk.CTkFrame(self, fg_color="#fff8e1", border_width=1, border_color="#ffe08a", corner_radius=10)
            aviso.pack(fill="x", pady=(14, 0))
            ctk.CTkLabel(aviso, text="Aún no has puesto los datos de tu empresa. Aparecen en la cabecera de los albaranes.",
                         font=fuente(13), text_color="#6b4e00").pack(side="left", padx=16, pady=12)
            boton(aviso, "Configurarlos ahora →", lambda: app.ir("ajustes")).pack(side="right", padx=12)

        tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        tarjetas.pack(fill="x", pady=16)
        tarjetas.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="t")
        bajos = r["bajo_minimo"]
        datos = [
            (r["albaranes_mes"], "Albaranes este mes", euros(r["importe_mes"]), lambda: self._ir_albaranes("Todos"), False),
            (r["pendientes"], "Pendientes de entrega", "emitidos sin entregar", lambda: self._ir_albaranes("Pendientes"), False),
            (r["borradores"], "Borradores", "sin emitir", lambda: self._ir_albaranes("Borradores"), False),
            (len(bajos), "Productos con poco stock", "por debajo del mínimo", self._ir_bajos, bool(bajos)),
        ]
        for i, (numero, texto, pequeno, accion, alerta) in enumerate(datos):
            t = panel(tarjetas, fg_color=ROJO_FONDO if alerta else None, border_color="#f5c2c2" if alerta else BORDE)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            for w in (
                ctk.CTkLabel(t, text=str(numero), font=fuente(30, True), text_color=ROJO if alerta else TEXTO),
                ctk.CTkLabel(t, text=texto, font=fuente(13), text_color=TEXTO),
                ctk.CTkLabel(t, text=pequeno, font=fuente(12), text_color=SUAVE),
            ):
                w.pack(anchor="w", padx=18, pady=(0, 0))
                w.bind("<Button-1>", lambda _e, a=accion: a())
                w.configure(cursor="hand2")
            t.winfo_children()[0].pack_configure(pady=(14, 0))
            t.winfo_children()[-1].pack_configure(pady=(0, 14))
            t.bind("<Button-1>", lambda _e, a=accion: a())
            t.configure(cursor="hand2")

        columnas = ctk.CTkFrame(self, fg_color="transparent")
        columnas.pack(fill="both", expand=True)
        columnas.grid_columnconfigure(0, weight=3)
        columnas.grid_columnconfigure(1, weight=2)
        izq = ctk.CTkFrame(columnas, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        subtitulo(izq, "Últimos albaranes").pack(anchor="w", pady=(0, 6))
        ultimos = Tabla(izq, COLUMNAS_ALBARANES, alto=8, al_abrir=lambda i: app.ir("detalle", albaran_id=i))
        ultimos.cargar(filas_albaranes(r["ultimos"]), "Todavía no hay albaranes. ¡Crea el primero!")
        ultimos.pack(fill="both", expand=True)

        der = ctk.CTkFrame(columnas, fg_color="transparent")
        der.grid(row=0, column=1, sticky="nsew")
        subtitulo(der, "Stock bajo mínimos").pack(anchor="w", pady=(0, 6))
        tabla_bajos = Tabla(der, [("producto", "Producto", 220, "w"), ("stock", "Stock", 90, "e"), ("minimo", "Mínimo", 70, "e")],
                            alto=8, al_abrir=lambda i: app.ir("producto", producto_id=i))
        tabla_bajos.cargar([(p["id"], (p["nombre"], f"{cant(p['stock'])} {p['unidad']}", cant(p["stock_minimo"])), ["rojo"]) for p in bajos],
                           "✅ Todo por encima del mínimo")
        tabla_bajos.pack(fill="both", expand=True)
        ayuda(self, "Consejo: haz doble clic en cualquier fila para abrirla.").pack(anchor="w", pady=(10, 0))

    def _ir_albaranes(self, filtro):
        self.app.filtros["albaranes"] = {"estado": filtro, "texto": ""}
        self.app.ir("albaranes")

    def _ir_bajos(self):
        self.app.filtros["inventario"] = {"texto": "", "bajos": True}
        self.app.ir("inventario")


# ---------- Clientes ----------


class VistaClientes(ctk.CTkFrame):
    COLUMNAS = [("nombre", "Nombre", 280, "w"), ("nif", "NIF", 110, "w"), ("ciudad", "Ciudad", 140, "w"),
                ("telefono", "Teléfono", 120, "w"), ("email", "Email", 200, "w"), ("albaranes", "Albaranes", 90, "e")]

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x")
        titulo(cab, "Clientes").pack(side="left")
        boton(cab, "＋ Nuevo cliente", self.nuevo, "primario").pack(side="right")

        self.buscar = ctk.CTkEntry(self, placeholder_text="🔍 Buscar por nombre, NIF, ciudad o teléfono…", width=360, height=34, font=fuente(13))
        self.buscar.bind("<KeyRelease>", lambda _e: self.refrescar())
        self.buscar.pack(anchor="w", pady=(16, 10))

        self.tabla = Tabla(self, self.COLUMNAS, alto=16, al_abrir=self.editar)
        self.tabla.pack(fill="both", expand=True)
        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(acciones, text="Cliente seleccionado:", font=fuente(12, True), text_color=SUAVE).pack(side="left", padx=(0, 8))
        boton(acciones, "＋ Nuevo albarán para él", self.albaran, "primario").pack(side="left", padx=2)
        boton(acciones, "📝 Editar", lambda: self.editar(self._seleccion())).pack(side="left", padx=6)
        boton(acciones, "🗑 Eliminar", self.eliminar, "peligro").pack(side="right")
        self.refrescar()

    def refrescar(self):
        filas = [(c["id"], (c["nombre"], c["nif"], c["ciudad"], c["telefono"], c["email"], c["num_albaranes"]), [])
                 for c in self.app.g.clientes(self.buscar.get())]
        self.tabla.cargar(filas, "No hay clientes que coincidan.")

    def _seleccion(self):
        cid = self.tabla.seleccion()
        if cid is None:
            self.app.avisar("Selecciona primero un cliente de la lista", "error")
        return cid

    def _guardado(self, mensaje):
        def hecho(cid):
            self.app.avisar(mensaje)
            self.refrescar()
            self.tabla.seleccionar(cid)
        return hecho

    def nuevo(self):
        DialogoCliente(self, self.app.g, al_terminar=self._guardado("Cliente creado"))

    def editar(self, cid):
        if cid is not None:
            DialogoCliente(self, self.app.g, cid, al_terminar=self._guardado("Cliente actualizado"))

    def albaran(self):
        if (cid := self._seleccion()) is not None:
            self.app.ir("editor", cliente_id=cid)

    def eliminar(self):
        if (cid := self._seleccion()) is None:
            return
        c = self.app.g.cliente(cid)
        if confirmar(self, "Eliminar cliente", f"¿Eliminar a «{c['nombre']}»?"):
            self.app.avisar(mensaje_eliminado(self.app.g.eliminar_cliente(cid), "El cliente"))
            self.refrescar()


# ---------- Ajustes: empresa, cuenta y datos ----------


class VistaAjustes(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        titulo(self, "Mi empresa y cuenta").pack(anchor="w", pady=(0, 14))

        # Empresa
        caja = panel(self)
        caja.pack(fill="x", pady=(0, 14))
        subtitulo(caja, "Datos de tu empresa").pack(anchor="w", padx=18, pady=(16, 0))
        ayuda(caja, "Aparecen en la cabecera de los albaranes. Los albaranes ya emitidos conservan los datos que había al emitirlos.").pack(anchor="w", padx=18)
        rejilla = ctk.CTkFrame(caja, fg_color="transparent")
        rejilla.pack(fill="x", padx=12, pady=(6, 0))
        e = app.g.empresa()
        f = self.form_empresa = Formulario(rejilla, columnas=3)
        f.texto("nombre", "Nombre o razón social", e["nombre"], ancho=2)
        f.texto("nif", "NIF / CIF", e["nif"])
        f.texto("direccion", "Dirección", e["direccion"], ancho=3)
        f.texto("cp", "Código postal", e["cp"])
        f.texto("ciudad", "Ciudad", e["ciudad"])
        f.texto("provincia", "Provincia", e["provincia"])
        f.texto("telefono", "Teléfono", e["telefono"])
        f.texto("email", "Email", e["email"])
        f.texto("prefijo", "Prefijo de numeración", e["prefijo"])
        pie = ctk.CTkFrame(caja, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(4, 16))
        ayuda(pie, f"Los números se generan así: {e['prefijo']}-{hoy()[:4]}-0001, y empiezan de nuevo cada año.").pack(side="left")
        boton(pie, "💾 Guardar datos", self.guardar_empresa, "primario").pack(side="right")

        # Cuenta
        caja = panel(self)
        caja.pack(fill="x", pady=(0, 14))
        subtitulo(caja, "Tu cuenta").pack(anchor="w", padx=18, pady=(16, 0))
        ayuda(caja, f"Has iniciado sesión como «{app.usuario['usuario']}» ({app.usuario['nombre']}).").pack(anchor="w", padx=18)
        rejilla = ctk.CTkFrame(caja, fg_color="transparent")
        rejilla.pack(fill="x", padx=12, pady=(6, 0))
        f = self.form_clave = Formulario(rejilla, columnas=3)
        f.texto("actual", "Contraseña actual", show="•")
        f.texto("nueva", "Nueva contraseña", show="•")
        f.texto("repetir", "Repite la nueva", show="•")
        boton(caja, "🔑 Cambiar contraseña", self.cambiar_clave).pack(anchor="e", padx=18, pady=(4, 16))

        # Copias de seguridad
        caja = panel(self)
        caja.pack(fill="x", pady=(0, 14))
        subtitulo(caja, "Copia de seguridad").pack(anchor="w", padx=18, pady=(16, 0))
        ayuda(caja, f"Todos los datos (de todas las cuentas de este ordenador) están en:\n{db.ruta_bd()}\n"
                    "Guarda una copia de vez en cuando en un pendrive o en la nube.", wraplength=900).pack(anchor="w", padx=18)
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(8, 16))
        boton(fila, "⬇ Guardar copia…", self.guardar_copia).pack(side="left")
        boton(fila, "⬆ Restaurar copia…", self.restaurar_copia).pack(side="left", padx=8)

        # Datos de prueba
        caja = panel(self, border_color="#f0c4c4")
        caja.pack(fill="x")
        subtitulo(caja, "Zona de pruebas").pack(anchor="w", padx=18, pady=(16, 0))
        ayuda(caja, "Solo afecta a tu cuenta.").pack(anchor="w", padx=18)
        fila = ctk.CTkFrame(caja, fg_color="transparent")
        fila.pack(fill="x", padx=18, pady=(8, 16))
        boton(fila, "Cargar datos de ejemplo", self.cargar_demo).pack(side="left")
        boton(fila, "Borrar todos mis datos", self.borrar_todo, "peligro").pack(side="left", padx=8)

    def guardar_empresa(self):
        try:
            self.app.g.guardar_empresa(self.form_empresa.valores())
        except ErrorUsuario as e:
            error(self, str(e))
            return
        self.app.avisar("Datos de la empresa guardados")
        self.app.ir("ajustes")

    def cambiar_clave(self):
        v = self.form_clave.valores()
        try:
            auth.cambiar_contrasena(self.app.conn, self.app.usuario["id"], v["actual"], v["nueva"], v["repetir"])
        except ErrorUsuario as e:
            error(self, str(e))
            return
        for campo in self.form_clave.campos.values():
            campo.delete(0, "end")
        self.app.avisar("Contraseña cambiada")

    def guardar_copia(self):
        ruta = filedialog.asksaveasfilename(parent=self, title="Guardar copia de seguridad", defaultextension=".db",
                                            initialfile=f"albaranes-copia-{hoy()}.db", filetypes=[("Copia de seguridad", "*.db")])
        if ruta:
            db.guardar_copia(self.app.conn, ruta)
            self.app.avisar("Copia de seguridad guardada")

    def restaurar_copia(self):
        ruta = filedialog.askopenfilename(parent=self, title="Restaurar copia de seguridad", filetypes=[("Copia de seguridad", "*.db")])
        if ruta and confirmar(self, "Restaurar copia", "Se sustituirán TODOS los datos de este ordenador (todas las cuentas) "
                                                         "por los de la copia, y tendrás que volver a iniciar sesión. ¿Continuar?"):
            self.app.restaurar_copia(ruta)

    def cargar_demo(self):
        if not self.app.g.esta_vacia() and not confirmar(self, "Datos de ejemplo", "Se añadirán clientes, productos y albaranes de ejemplo a los que ya tienes. ¿Continuar?"):
            return
        try:
            self.app.g.cargar_datos_demo()
        except ErrorUsuario as e:
            error(self, f"No se han podido cargar todos los datos de ejemplo: {e}")
        self.app.avisar("Datos de ejemplo cargados")
        self.app.ir("inicio")

    def borrar_todo(self):
        if confirmar(self, "Borrar mis datos", "Se borrarán TODOS tus albaranes, clientes y productos. Los datos de tu empresa y tu cuenta se conservan. "
                                               "No se puede deshacer. ¿Seguro?"):
            self.app.g.borrar_todo()
            self.app.avisar("Datos borrados")
            self.app.ir("inicio")


# ---------- Acerca de ----------


class VistaAcerca(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        titulo(self, "Acerca de").pack(anchor="w", pady=(0, 14))
        caja = panel(self)
        caja.pack(fill="x")

        def parrafo(texto, **kw):
            ctk.CTkLabel(caja, text=texto, font=fuente(13), text_color=TEXTO, anchor="w", justify="left", wraplength=820, **kw).pack(anchor="w", padx=22, pady=(0, 8))

        def encabezado(texto):
            subtitulo(caja, texto).pack(anchor="w", padx=22, pady=(14, 4))

        ctk.CTkLabel(caja, text=f"📦 {APP_NOMBRE}", font=fuente(22, True), text_color=TEXTO).pack(anchor="w", padx=22, pady=(20, 0))
        ctk.CTkLabel(caja, text=f"Versión {VERSION}", font=fuente(12), text_color=SUAVE).pack(anchor="w", padx=22, pady=(0, 8))
        parrafo("Aplicación de escritorio para crear y gestionar albaranes de entrega, con control de inventario y clientes. "
                "Cada persona tiene su propia cuenta y solo ve sus datos. Funciona sin conexión a Internet.")

        encabezado("¿Qué es un albarán?")
        parrafo("Un albarán es el documento que acompaña a la mercancía cuando se entrega a un cliente. Sirve para dejar constancia "
                "de qué se entrega, cuánto, a quién y cuándo. El cliente lo firma al recibirlo («recibí conforme»). No es una factura: "
                "normalmente, a final de mes, se agrupan los albaranes de un cliente y se emite la factura.")
        parrafo("Debe incluir: datos de quien entrega y de quien recibe, número y fecha, la lista de productos con sus cantidades "
                "y, si se desea, sus precios (albarán valorado), y un espacio para la firma.")

        encabezado("Cómo funciona")
        pasos = [
            ("borrador", "Creas el albarán y puedes modificarlo libremente. No cambia el stock."),
            ("emitido", "Al emitirlo recibe un número correlativo (p. ej. ALB-2026-0001) y se descuentan las unidades del inventario. Ya no se puede modificar."),
            ("entregado", "Cuando el cliente recibe la mercancía, lo marcas como entregado indicando quién la recibió."),
            ("anulado", "Si hubo un error, se anula: las unidades vuelven al inventario y el número no se reutiliza."),
        ]
        for estado, texto in pasos:
            fila = ctk.CTkFrame(caja, fg_color="transparent")
            fila.pack(fill="x", padx=22, pady=3)
            etiqueta_estado(fila, estado).pack(side="left")
            ctk.CTkLabel(fila, text=texto, font=fuente(13), text_color=TEXTO, anchor="w", justify="left", wraplength=640).pack(side="left", padx=12)

        encabezado("Tus datos y tu cuenta")
        parrafo("Todo se guarda en este ordenador, en una base de datos SQLite. Las contraseñas no se guardan: se guarda una huella "
                "cifrada (PBKDF2-SHA256) que permite comprobarlas. Haz copias de seguridad desde «Mi empresa y cuenta».")
        ctk.CTkLabel(caja, text=str(db.ruta_bd()), font=fuente(12), text_color=AZUL).pack(anchor="w", padx=22, pady=(0, 8))

        encabezado("Tecnología")
        parrafo("Python 3 · CustomTkinter (interfaz) · SQLite (datos) · ReportLab (PDF).")
        ctk.CTkFrame(caja, height=10, fg_color="transparent").pack()

