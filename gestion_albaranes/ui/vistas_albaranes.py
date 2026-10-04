"""Pantallas de albaranes: listado, editor (nuevo / borrador) y detalle."""

import os
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .. import db
from ..errores import ErrorUsuario
from ..logica import (ANULADO, BORRADOR, EMITIDO, ENTREGADO, NOMBRE_ESTADO, TIPOS_IVA, calcular_linea, calcular_totales,
                      cant, dec, euros, fecha_es, fecha_hora_es, hoy)
from ..pdf import generar_pdf
from .comun import (AZUL, BLANCO, BORDE, ROJO, SUAVE, TEXTO, Tabla, ayuda, boton, confirmar, error, etiqueta_estado,
                    fuente, panel, subtitulo, titulo)
from .dialogos import DialogoAnular, DialogoCliente, DialogoEntrega

ETIQUETA_ESTADO_TABLA = {BORRADOR: "suave", ANULADO: "rojo", ENTREGADO: "verde"}


def filas_albaranes(albaranes):
    return [
        (a["id"], (a["numero"] or "Borrador", fecha_es(a["fecha"]), a["cliente_nombre"], NOMBRE_ESTADO[a["estado"]], euros(a["total"])),
         [ETIQUETA_ESTADO_TABLA[a["estado"]]] if a["estado"] in ETIQUETA_ESTADO_TABLA else [])
        for a in albaranes
    ]


COLUMNAS_ALBARANES = [("numero", "Número", 140, "w"), ("fecha", "Fecha", 100, "center"), ("cliente", "Cliente", 300, "w"),
                      ("estado", "Estado", 160, "center"), ("total", "Total", 120, "e")]


# ---------- Listado ----------


class VistaAlbaranes(ctk.CTkFrame):
    FILTROS = {"Todos": None, "Borradores": BORRADOR, "Pendientes": EMITIDO, "Entregados": ENTREGADO, "Anulados": ANULADO}

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        filtro = app.filtros.setdefault("albaranes", {"estado": "Todos", "texto": ""})

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x")
        titulo(cab, "Albaranes").pack(side="left")
        boton(cab, "＋ Nuevo albarán", lambda: app.ir("editor"), "primario").pack(side="right")

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(16, 10))
        self.estado = ctk.CTkSegmentedButton(barra, values=list(self.FILTROS), command=lambda _v: self.refrescar(),
                                             font=fuente(13), height=34, selected_color=AZUL)
        self.estado.set(filtro["estado"])
        self.estado.pack(side="left")
        self.buscar = ctk.CTkEntry(barra, placeholder_text="🔍 Buscar por número o cliente…", width=300, height=34, font=fuente(13))
        if filtro["texto"]:
            self.buscar.insert(0, filtro["texto"])
        self.buscar.bind("<KeyRelease>", lambda _e: self.refrescar())
        self.buscar.pack(side="right")

        self.tabla = Tabla(self, COLUMNAS_ALBARANES, alto=18, al_abrir=lambda i: app.ir("detalle", albaran_id=i))
        self.tabla.pack(fill="both", expand=True)
        ayuda(self, "Haz doble clic en un albarán (o pulsa Intro) para abrirlo.").pack(anchor="w", pady=(8, 0))
        self.refrescar()

    def refrescar(self):
        filtro = self.app.filtros["albaranes"]
        filtro["estado"], filtro["texto"] = self.estado.get(), self.buscar.get()
        lista = self.app.g.albaranes(self.FILTROS[filtro["estado"]], filtro["texto"])
        self.tabla.cargar(filas_albaranes(lista), "No hay albaranes que coincidan.")


# ---------- Editor ----------

PRODUCTO_LIBRE = "— Concepto libre —"
ANCHOS = [250, 0, 86, 40, 96, 70, 82, 100, 36]  # 0 = columna que se estira (descripción)


def _configurar_columnas(marco):
    for i, ancho in enumerate(ANCHOS):
        marco.grid_columnconfigure(i, minsize=ancho, weight=1 if ancho == 0 else 0)


class FilaLinea(ctk.CTkFrame):
    def __init__(self, master, editor, linea):
        super().__init__(master, fg_color="transparent")
        self.editor = editor
        _configurar_columnas(self)
        self.producto_id = linea.get("producto_id")
        self.unidad = linea.get("unidad", "ud")

        opciones = [PRODUCTO_LIBRE] + list(editor.productos_por_texto)
        self.producto = ctk.CTkComboBox(self, values=opciones, state="readonly", command=self._elegir_producto, height=32, width=ANCHOS[0] - 6,
                                        font=fuente(12), dropdown_font=fuente(12))
        texto_producto = editor.texto_producto(self.producto_id) if self.producto_id else PRODUCTO_LIBRE
        if texto_producto not in opciones:  # producto archivado: se muestra igualmente
            self.producto.configure(values=opciones + [texto_producto])
        self.producto.set(texto_producto)
        self.producto.grid(row=0, column=0, sticky="ew", padx=3, pady=(4, 0))

        self.descripcion = self._entrada(1, linea.get("descripcion", ""))
        self.cantidad = self._entrada(2, cant(linea.get("cantidad", 1)), "e")
        self.lbl_unidad = ctk.CTkLabel(self, text=self.unidad, font=fuente(12), text_color=SUAVE, anchor="w")
        self.lbl_unidad.grid(row=0, column=3, sticky="w", padx=2)
        self.precio = self._entrada(4, cant(linea.get("precio", 0)), "e")
        self.descuento = self._entrada(5, cant(linea.get("descuento", 0)), "e")
        self.iva = ctk.CTkOptionMenu(self, values=[f"{t} %" for t in TIPOS_IVA], height=32, font=fuente(12), width=ANCHOS[6] - 6,
                                     fg_color=BLANCO, button_color="#e6ebf1", button_hover_color="#d5dde7", text_color=TEXTO,
                                     command=lambda _v: editor.recalcular())
        self.iva.set(f"{int(linea.get('iva', 21))} %")
        self.iva.grid(row=0, column=6, sticky="ew", padx=3, pady=(4, 0))
        self.importe = ctk.CTkLabel(self, text="", font=fuente(13, True), anchor="e", text_color=TEXTO)
        self.importe.grid(row=0, column=7, sticky="e", padx=6)
        ctk.CTkButton(self, text="✕", width=30, height=30, fg_color="transparent", hover_color="#fde2e2", text_color=ROJO,
                      font=fuente(13, True), command=lambda: editor.quitar_linea(self)).grid(row=0, column=8, padx=2)
        self.info = ctk.CTkLabel(self, text="", font=fuente(11), text_color=SUAVE, anchor="w", height=16)
        self.info.grid(row=1, column=0, columnspan=3, sticky="w", padx=6)

    def _entrada(self, columna, valor, alineacion="w"):
        # Ancho fijo igual al de la columna para que las filas queden alineadas con la cabecera.
        e = ctk.CTkEntry(self, height=32, width=ANCHOS[columna] - 6 if ANCHOS[columna] else 120, font=fuente(12),
                         justify="right" if alineacion == "e" else "left")
        e.insert(0, str(valor))
        e.grid(row=0, column=columna, sticky="ew", padx=3, pady=(4, 0))
        e.bind("<KeyRelease>", lambda _e: self.editor.recalcular())
        return e

    def _poner(self, entrada, valor):
        entrada.delete(0, "end")
        entrada.insert(0, valor)

    def _elegir_producto(self, texto):
        self.producto_id = self.editor.productos_por_texto.get(texto)
        if self.producto_id:
            p = self.editor.app.g.producto(self.producto_id)
            self._poner(self.descripcion, p["nombre"])
            self._poner(self.precio, cant(p["precio"]))
            self.iva.set(f"{p['iva']} %")
            self.unidad = p["unidad"]
            self.cantidad.focus_set()
            self.cantidad.select_range(0, "end")
        else:
            self.unidad = "ud"
            self.descripcion.focus_set()
        self.lbl_unidad.configure(text=self.unidad)
        self.editor.recalcular()

    def datos(self) -> dict:
        return {
            "producto_id": self.producto_id, "descripcion": self.descripcion.get(), "cantidad": self.cantidad.get(),
            "precio": self.precio.get(), "descuento": self.descuento.get() or "0", "iva": int(self.iva.get().split()[0]),
            "unidad": self.unidad,
        }

    def actualizar(self):
        d = self.datos()
        self.importe.configure(text=euros(calcular_linea(d)["base"]))
        if not self.producto_id:
            self.info.configure(text="")
            return
        p = self.editor.app.g.producto(self.producto_id)
        falta = (dec(d["cantidad"]) or 0) > dec(p["stock"])
        self.info.configure(text=f"Stock: {cant(p['stock'])} {p['unidad']}" + ("  ⚠ insuficiente" if falta else ""),
                            text_color=ROJO if falta else SUAVE)


class VistaEditor(ctk.CTkFrame):
    """Crear un albarán nuevo o modificar un borrador."""

    def __init__(self, master, app, albaran_id=None, cliente_id=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        g = app.g
        self.albaran_id = albaran_id
        self.modificado = False
        self.filas: list[FilaLinea] = []
        self.productos_por_texto = {self.texto_producto_de(p): p["id"] for p in g.productos()}

        datos = {"cliente_id": cliente_id, "fecha": hoy(), "valorado": True, "observaciones": "", "lineas": [{}]}
        if albaran_id:
            a = g.albaran(albaran_id)
            if a["estado"] != BORRADOR:
                raise ErrorUsuario("Este albarán ya está emitido y no se puede modificar. Si hay un error, anúlalo y duplícalo.")
            datos = a

        # Cabecera
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x")
        titulo(cab, "Editar borrador" if albaran_id else "Nuevo albarán").pack(side="left")

        datos_panel = panel(self)
        datos_panel.pack(fill="x", pady=(14, 10))
        datos_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(datos_panel, text="Cliente *", font=fuente(12, True), text_color=SUAVE).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(datos_panel, text="Fecha (dd/mm/aaaa)", font=fuente(12, True), text_color=SUAVE).grid(row=0, column=2, sticky="w", padx=16, pady=(12, 0))
        self.cliente = ctk.CTkComboBox(datos_panel, values=[], state="readonly", height=36, font=fuente(13),
                                       dropdown_font=fuente(13), command=lambda _v: self._marcar())
        self.cliente.grid(row=1, column=0, sticky="ew", padx=(16, 6), pady=(2, 8))
        boton(datos_panel, "＋ Nuevo cliente", self._nuevo_cliente).grid(row=1, column=1, padx=6, pady=(2, 8))
        self.fecha = ctk.CTkEntry(datos_panel, width=150, height=36, font=fuente(13))
        self.fecha.insert(0, fecha_es(datos["fecha"]))
        self.fecha.bind("<KeyRelease>", lambda _e: self._marcar())
        self.fecha.grid(row=1, column=2, padx=16, pady=(2, 8))
        self.valorado = ctk.CTkCheckBox(datos_panel, text="Mostrar precios en el albarán (albarán valorado)", font=fuente(13),
                                        command=self._marcar)
        if datos["valorado"]:
            self.valorado.select()
        self.valorado.grid(row=2, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 14))
        self._cargar_clientes(datos["cliente_id"])

        # Líneas
        lineas_panel = panel(self)
        lineas_panel.pack(fill="both", expand=True)
        cabecera = ctk.CTkFrame(lineas_panel, fg_color="#f8fafc", corner_radius=8)
        cabecera.pack(fill="x", padx=10, pady=(10, 0))
        _configurar_columnas(cabecera)
        for i, texto in enumerate(["PRODUCTO", "DESCRIPCIÓN", "CANTIDAD", "", "PRECIO €", "DTO %", "IVA", "IMPORTE", ""]):
            ctk.CTkLabel(cabecera, text=texto, font=fuente(11, True), text_color=SUAVE, width=max(ANCHOS[i] - 16, 10),
                         anchor="e" if i in (2, 4, 5, 7) else "w").grid(row=0, column=i, sticky="ew", padx=8, pady=6)
        # Margen derecho para que la cabecera quede alineada con las filas (que tienen barra de desplazamiento).
        cabecera.grid_columnconfigure(9, minsize=18)
        self.contenedor = ctk.CTkScrollableFrame(lineas_panel, fg_color="transparent")
        self.contenedor.pack(fill="both", expand=True, padx=4)
        for linea in datos["lineas"]:
            self.anadir_linea(linea, enfocar=False)
        boton(lineas_panel, "＋ Añadir línea", self.anadir_linea).pack(anchor="w", padx=12, pady=(4, 12))

        # Pie: observaciones, totales y botones
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", pady=(10, 0))
        pie.grid_columnconfigure(0, weight=1)
        obs = ctk.CTkFrame(pie, fg_color="transparent")
        obs.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ctk.CTkLabel(obs, text="Observaciones", font=fuente(12, True), text_color=SUAVE).pack(anchor="w")
        self.observaciones = ctk.CTkTextbox(obs, height=80, font=fuente(13), border_width=2, border_color="#c8d1dc", fg_color=BLANCO)
        self.observaciones.insert("1.0", datos["observaciones"] or "")
        self.observaciones.bind("<KeyRelease>", lambda _e: self._marcar())
        self.observaciones.pack(fill="both", expand=True)
        self.totales = panel(pie, fg_color="#fafbfc", width=330)
        self.totales.grid(row=0, column=1, sticky="ne")

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", pady=(10, 0))
        self.mensaje = ctk.CTkLabel(acciones, text="", text_color=ROJO, font=fuente(12, True), anchor="w", justify="left", wraplength=600)
        self.mensaje.pack(side="left", fill="x", expand=True)
        boton(acciones, "✔ Guardar y emitir", lambda: self.guardar(emitir=True), "primario").pack(side="right")
        boton(acciones, "💾 Guardar borrador", self.guardar).pack(side="right", padx=8)
        boton(acciones, "Cancelar", self.cancelar).pack(side="right")
        ayuda(self, "Al emitir, el albarán recibe un número y se descuentan las unidades del inventario. Un borrador no afecta al stock.").pack(anchor="w", pady=(6, 0))

        self.recalcular()
        self.modificado = False

    # --- utilidades ---

    @staticmethod
    def texto_producto_de(p):
        return f"{p['referencia']} · {p['nombre']}"

    def texto_producto(self, producto_id):
        for texto, pid in self.productos_por_texto.items():
            if pid == producto_id:
                return texto
        p = self.app.g.producto(producto_id)
        self.productos_por_texto[self.texto_producto_de(p) + " (archivado)"] = p["id"]
        return self.texto_producto_de(p) + " (archivado)"

    def _cargar_clientes(self, seleccionado=None):
        clientes = self.app.g.clientes()
        if seleccionado and all(c["id"] != seleccionado for c in clientes):
            clientes.append(self.app.g.cliente(seleccionado))
        self.clientes_por_texto = {}
        for c in clientes:
            texto = c["nombre"] + (f" · {c['nif']}" if c["nif"] else "")
            if texto in self.clientes_por_texto:
                texto += f" (#{c['id']})"
            self.clientes_por_texto[texto] = c["id"]
        valores = list(self.clientes_por_texto) or ["(no hay clientes: crea uno)"]
        self.cliente.configure(values=valores)
        texto = next((t for t, i in self.clientes_por_texto.items() if i == seleccionado), "")
        self.cliente.set(texto or "— Selecciona un cliente —")

    def _nuevo_cliente(self):
        def creado(cliente_id):
            self._cargar_clientes(cliente_id)
            self._marcar()
            self.app.avisar("Cliente creado")

        DialogoCliente(self, self.app.g, al_terminar=creado)

    def _marcar(self):
        self.modificado = True

    def anadir_linea(self, linea=None, enfocar=True):
        fila = FilaLinea(self.contenedor, self, linea or {})
        fila.pack(fill="x", pady=1)
        self.filas.append(fila)
        if enfocar:
            self._marcar()
            self.after(50, fila.producto.focus_set)
            self.after(80, lambda: self.contenedor._parent_canvas.yview_moveto(1.0))
        self.recalcular()

    def quitar_linea(self, fila):
        self.filas.remove(fila)
        fila.destroy()
        if not self.filas:
            self.anadir_linea(enfocar=False)
        self._marcar()
        self.recalcular()

    def recalcular(self):
        if not hasattr(self, "totales"):  # aún se está construyendo la pantalla
            return
        self._marcar()
        for fila in self.filas:
            fila.actualizar()
        t = calcular_totales([f.datos() for f in self.filas])
        for w in self.totales.winfo_children():
            w.destroy()
        filas = [("Base imponible", euros(t["base"]), False)]
        filas += [(f"IVA {d['iva']} % (sobre {euros(d['base'])})", euros(d["cuota"]), False) for d in t["desglose"]]
        for i, (texto, valor, _) in enumerate(filas):
            ctk.CTkLabel(self.totales, text=texto, font=fuente(12), text_color=SUAVE).grid(row=i, column=0, sticky="w", padx=(16, 24), pady=(10 if i == 0 else 2, 2))
            ctk.CTkLabel(self.totales, text=valor, font=fuente(13, i == 0), text_color=TEXTO).grid(row=i, column=1, sticky="e", padx=16)
        n = len(filas)
        ctk.CTkFrame(self.totales, height=2, fg_color=TEXTO).grid(row=n, column=0, columnspan=2, sticky="ew", padx=16, pady=4)
        ctk.CTkLabel(self.totales, text="Total", font=fuente(16), text_color=TEXTO).grid(row=n + 1, column=0, sticky="w", padx=16, pady=(0, 12))
        ctk.CTkLabel(self.totales, text=euros(t["total"]), font=fuente(18, True), text_color=TEXTO).grid(row=n + 1, column=1, sticky="e", padx=16, pady=(0, 12))

    # --- acciones ---

    def datos(self) -> dict:
        return {
            "id": self.albaran_id,
            "cliente_id": self.clientes_por_texto.get(self.cliente.get()),
            "fecha": self.fecha.get(),
            "valorado": bool(self.valorado.get()),
            "observaciones": self.observaciones.get("1.0", "end-1c"),
            "lineas": [f.datos() for f in self.filas],
        }

    def guardar(self, emitir=False):
        self.mensaje.configure(text="")
        try:
            self.albaran_id = self.app.g.guardar_borrador(self.datos())
        except ErrorUsuario as e:
            self.mensaje.configure(text=str(e))
            return
        self.modificado = False
        if not emitir:
            self.app.avisar("Borrador guardado")
            self.app.ir("detalle", albaran_id=self.albaran_id)
            return
        try:
            numero = self.app.g.emitir(self.albaran_id)
        except ErrorUsuario as e:
            self.mensaje.configure(text=f"Se ha guardado como borrador, pero no se ha podido emitir. {e}")
            return
        self.app.avisar(f"Albarán {numero} emitido")
        self.app.ir("detalle", albaran_id=self.albaran_id)

    def cancelar(self):
        if self.albaran_id:
            self.app.ir("detalle", albaran_id=self.albaran_id)
        else:
            self.app.ir("albaranes")

    def puede_salir(self) -> bool:
        return not self.modificado or confirmar(self, "Cambios sin guardar", "Hay cambios sin guardar en el albarán. ¿Salir sin guardarlos?")


# ---------- Detalle ----------


class VistaDetalle(ctk.CTkScrollableFrame):
    def __init__(self, master, app, albaran_id):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.albaran_id = albaran_id
        a = self.a = app.g.albaran(albaran_id)

        volver = ctk.CTkButton(self, text="← Albaranes", command=lambda: app.ir("albaranes"), fg_color="transparent",
                               hover_color="#e6ebf1", text_color=AZUL, font=fuente(13), width=10, anchor="w")
        volver.pack(anchor="w")
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", pady=(0, 12))
        titulo(cab, a["numero"] or "Borrador").pack(side="left")
        etiqueta_estado(cab, a["estado"]).pack(side="left", padx=12)

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", pady=(0, 12))
        if a["estado"] == BORRADOR:
            boton(acciones, "✔ Emitir", self.emitir, "primario").pack(side="left", padx=(0, 6))
            boton(acciones, "📝 Editar", lambda: app.ir("editor", albaran_id=albaran_id)).pack(side="left", padx=6)
            boton(acciones, "🗑 Eliminar", self.eliminar, "peligro").pack(side="left", padx=6)
        if a["estado"] == EMITIDO:
            boton(acciones, "📬 Marcar como entregado", self.entregar, "primario").pack(side="left", padx=(0, 6))
        if a["estado"] in (EMITIDO, ENTREGADO):
            boton(acciones, "⛔ Anular", self.anular, "peligro").pack(side="left", padx=6)
        boton(acciones, "⧉ Duplicar", self.duplicar).pack(side="left", padx=6)
        boton(acciones, "💾 Guardar PDF…", self.guardar_pdf).pack(side="right", padx=(6, 0))
        boton(acciones, "🖨 Ver / imprimir PDF", self.ver_pdf, "primario" if a["estado"] != BORRADOR else "normal").pack(side="right")

        self._documento()
        self._historial()

    def _documento(self):
        a = self.a
        doc = panel(self, corner_radius=4)
        doc.pack(fill="x", pady=(0, 14))
        if a["estado"] in (BORRADOR, ANULADO):
            ctk.CTkLabel(doc, text=f"  {a['estado'].upper()}  —  {'no se descuenta stock hasta emitirlo' if a['estado'] == BORRADOR else 'sin validez; las unidades se devolvieron al inventario'}",
                         fg_color="#fde2e2" if a["estado"] == ANULADO else "#eceff3", text_color=ROJO if a["estado"] == ANULADO else SUAVE,
                         font=fuente(12, True), corner_radius=6).pack(fill="x", padx=24, pady=(18, 0))

        sup = ctk.CTkFrame(doc, fg_color="transparent")
        sup.pack(fill="x", padx=28, pady=(20, 10))
        sup.grid_columnconfigure((0, 1), weight=1)
        emp = a["empresa"]
        ctk.CTkLabel(sup, text=emp.get("nombre") or "Tu empresa (configúrala en «Mi empresa y cuenta»)", font=fuente(18, True),
                     text_color=TEXTO, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(sup, text=self._bloque(emp), font=fuente(12), text_color=SUAVE, anchor="w", justify="left").grid(row=1, column=0, sticky="nw")
        ctk.CTkLabel(sup, text="ALBARÁN DE ENTREGA", font=fuente(17, True), text_color=TEXTO, anchor="e").grid(row=0, column=1, sticky="e")
        info = [("Nº", a["numero"] or "Pendiente de emitir"), ("Fecha", fecha_es(a["fecha"]))]
        if a["fecha_entrega"]:
            info.append(("Entregado", fecha_es(a["fecha_entrega"])))
        if a["receptor"]:
            info.append(("Recibido por", a["receptor"]))
        ctk.CTkLabel(sup, text="\n".join(f"{k}:  {v}" for k, v in info), font=fuente(13, True), text_color=TEXTO,
                     anchor="e", justify="right").grid(row=1, column=1, sticky="ne")

        ctk.CTkFrame(doc, height=2, fg_color=TEXTO).pack(fill="x", padx=28)
        cli = a["cliente"]
        caja = ctk.CTkFrame(doc, fg_color="transparent", border_width=1, border_color=BORDE, corner_radius=6)
        caja.pack(anchor="e", padx=28, pady=14)
        ctk.CTkLabel(caja, text="CLIENTE / DESTINATARIO", font=fuente(10, True), text_color=SUAVE, anchor="w").pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(caja, text=cli["nombre"], font=fuente(14, True), text_color=TEXTO, anchor="w").pack(anchor="w", padx=14)
        ctk.CTkLabel(caja, text=self._bloque(cli), font=fuente(12), text_color=SUAVE, anchor="w", justify="left",
                     width=320).pack(anchor="w", padx=14, pady=(0, 10))

        valorado = bool(a["valorado"])
        columnas = [("ref", "Ref.", 90, "w"), ("desc", "Descripción", 320, "w"), ("cant", "Cantidad", 90, "e"), ("ud", "Ud.", 60, "w")]
        if valorado:
            columnas += [("precio", "Precio", 90, "e"), ("dto", "Dto.", 60, "e"), ("iva", "IVA", 60, "e"), ("importe", "Importe", 100, "e")]
        tabla = Tabla(doc, columnas, alto=max(2, len(a["lineas"])))
        filas = []
        for l in a["lineas"]:
            valores = [l["referencia"], l["descripcion"], cant(l["cantidad"]), l["unidad"]]
            if valorado:
                valores += [euros(l["precio"]), f"{cant(l['descuento'])} %" if l["descuento"] else "", f"{l['iva']} %", euros(calcular_linea(l)["base"])]
            filas.append((l["id"], valores, []))
        tabla.cargar(filas)
        tabla.pack(fill="x", padx=28)

        pie = ctk.CTkFrame(doc, fg_color="transparent")
        pie.pack(fill="x", padx=28, pady=(12, 22))
        izquierda = ctk.CTkFrame(pie, fg_color="transparent")
        izquierda.pack(side="left", fill="both", expand=True, anchor="n")
        if a["observaciones"]:
            subtitulo(izquierda, "Observaciones").pack(anchor="w")
            ctk.CTkLabel(izquierda, text=a["observaciones"], font=fuente(12), text_color=TEXTO, anchor="w", justify="left",
                         wraplength=480).pack(anchor="w")
        ayuda(izquierda, f"Total de unidades: {cant(a['totales']['unidades'])}").pack(anchor="w", pady=(6, 0))
        if a["motivo_anulacion"]:
            ctk.CTkLabel(izquierda, text=f"Motivo de anulación: {a['motivo_anulacion']}", font=fuente(12, True), text_color=ROJO).pack(anchor="w")
        if valorado:
            t = a["totales"]
            caja_t = ctk.CTkFrame(pie, fg_color="#fafbfc", border_width=1, border_color=BORDE, corner_radius=8)
            caja_t.pack(side="right", anchor="n")
            filas_t = [("Base imponible", euros(t["base"]))] + [(f"IVA {d['iva']} % (sobre {euros(d['base'])})", euros(d["cuota"])) for d in t["desglose"]]
            for i, (k, v) in enumerate(filas_t):
                ctk.CTkLabel(caja_t, text=k, font=fuente(12), text_color=SUAVE).grid(row=i, column=0, sticky="w", padx=(16, 24), pady=(10 if i == 0 else 1, 1))
                ctk.CTkLabel(caja_t, text=v, font=fuente(13), text_color=TEXTO).grid(row=i, column=1, sticky="e", padx=16)
            n = len(filas_t)
            ctk.CTkFrame(caja_t, height=2, fg_color=TEXTO).grid(row=n, column=0, columnspan=2, sticky="ew", padx=16, pady=4)
            ctk.CTkLabel(caja_t, text="Total", font=fuente(16), text_color=TEXTO).grid(row=n + 1, column=0, sticky="w", padx=16, pady=(0, 10))
            ctk.CTkLabel(caja_t, text=euros(t["total"]), font=fuente(18, True), text_color=TEXTO).grid(row=n + 1, column=1, sticky="e", padx=16, pady=(0, 10))

    @staticmethod
    def _bloque(datos):
        lineas = []
        if datos.get("nif"):
            lineas.append(f"NIF: {datos['nif']}")
        if datos.get("direccion"):
            lineas.append(datos["direccion"])
        poblacion = " ".join(x for x in (datos.get("cp"), datos.get("ciudad")) if x)
        if poblacion or datos.get("provincia"):
            lineas.append(", ".join(x for x in (poblacion, datos.get("provincia")) if x))
        if datos.get("telefono"):
            lineas.append(f"Tel.: {datos['telefono']}")
        if datos.get("email"):
            lineas.append(datos["email"])
        return "\n".join(lineas)

    def _historial(self):
        caja = panel(self)
        caja.pack(fill="x")
        subtitulo(caja, "Historial").pack(anchor="w", padx=18, pady=(14, 4))
        for h in self.a["historial"]:
            ctk.CTkLabel(caja, text=f"{fecha_hora_es(h['fecha'])}   ·   {h['texto']}", font=fuente(12), text_color=TEXTO,
                         anchor="w").pack(anchor="w", padx=18)
        ctk.CTkFrame(caja, height=10, fg_color="transparent").pack()

    # --- acciones ---

    def _recargar(self, mensaje=None):
        if mensaje:
            self.app.avisar(mensaje)
        self.app.ir("detalle", albaran_id=self.albaran_id)

    def emitir(self):
        try:
            numero = self.app.g.emitir(self.albaran_id)
        except ErrorUsuario as e:
            error(self, str(e))
            return
        self._recargar(f"Albarán {numero} emitido")

    def eliminar(self):
        if confirmar(self, "Eliminar borrador", "¿Eliminar este borrador? No se puede deshacer."):
            self.app.g.eliminar_borrador(self.albaran_id)
            self.app.avisar("Borrador eliminado")
            self.app.ir("albaranes")

    def entregar(self):
        DialogoEntrega(self, self.app.g, self.albaran_id, self.a["numero"], al_terminar=lambda _r: self._recargar("Albarán marcado como entregado"))

    def anular(self):
        DialogoAnular(self, self.app.g, self.albaran_id, self.a["numero"], al_terminar=lambda _r: self._recargar("Albarán anulado y stock devuelto"))

    def duplicar(self):
        try:
            nuevo = self.app.g.duplicar(self.albaran_id)
        except ErrorUsuario as e:
            error(self, str(e))
            return
        self.app.avisar("Se ha creado un borrador copiado. Revísalo y guárdalo.")
        self.app.ir("editor", albaran_id=nuevo)

    def _nombre_pdf(self):
        return f"{self.a['numero'] or 'borrador-' + str(self.albaran_id)}.pdf"

    def ver_pdf(self):
        carpeta = db.carpeta_datos() / "pdf"
        carpeta.mkdir(exist_ok=True)
        destino = carpeta / self._nombre_pdf()
        try:
            generar_pdf(self.app.g.albaran(self.albaran_id), destino)
        except PermissionError:
            error(self, "No se puede generar el PDF porque está abierto en otro programa. Ciérralo e inténtalo de nuevo.")
            return
        abrir_archivo(destino)

    def guardar_pdf(self):
        ruta = filedialog.asksaveasfilename(parent=self, title="Guardar albarán en PDF", defaultextension=".pdf",
                                            initialfile=self._nombre_pdf(), filetypes=[("PDF", "*.pdf")])
        if not ruta:
            return
        try:
            generar_pdf(self.app.g.albaran(self.albaran_id), ruta)
        except PermissionError:
            error(self, "No se puede guardar: el archivo está abierto en otro programa.")
            return
        self.app.avisar(f"PDF guardado: {Path(ruta).name}")
        abrir_archivo(ruta)


def abrir_archivo(ruta):
    try:
        os.startfile(str(ruta))  # Windows: abre con el programa predeterminado
    except AttributeError:
        import subprocess
        import sys

        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(ruta)])

