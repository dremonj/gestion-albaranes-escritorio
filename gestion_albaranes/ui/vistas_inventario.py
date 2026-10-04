"""Pantallas de inventario: listado de productos y ficha con movimientos."""

import customtkinter as ctk

from ..errores import ErrorUsuario
from ..logica import cant, dec, euros, fecha_hora_es, r2
from .comun import AZUL, ROJO, ROJO_FONDO, SUAVE, TEXTO, Tabla, ayuda, boton, confirmar, error, fuente, panel, subtitulo, titulo
from .dialogos import DialogoAjuste, DialogoProducto


def mensaje_eliminado(resultado, que):
    if resultado == "archivado":
        return f"{que} aparece en albaranes: se ha archivado en lugar de borrarlo"
    return f"{que} eliminado"


class VistaInventario(ctk.CTkFrame):
    COLUMNAS = [("ref", "Ref.", 110, "w"), ("nombre", "Producto", 320, "w"), ("precio", "Precio", 100, "e"),
                ("iva", "IVA", 60, "center"), ("stock", "Stock", 120, "e"), ("minimo", "Mínimo", 90, "e")]

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        filtro = app.filtros.setdefault("inventario", {"texto": "", "bajos": False})

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x")
        titulo(cab, "Inventario").pack(side="left")
        boton(cab, "＋ Nuevo producto", self.nuevo, "primario").pack(side="right")

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(16, 10))
        self.buscar = ctk.CTkEntry(barra, placeholder_text="🔍 Buscar por referencia o nombre…", width=320, height=34, font=fuente(13))
        if filtro["texto"]:
            self.buscar.insert(0, filtro["texto"])
        self.buscar.bind("<KeyRelease>", lambda _e: self.refrescar())
        self.buscar.pack(side="left")
        self.bajos = ctk.CTkCheckBox(barra, text="Solo stock bajo", font=fuente(13), command=self.refrescar)
        if filtro["bajos"]:
            self.bajos.select()
        self.bajos.pack(side="left", padx=16)

        self.tabla = Tabla(self, self.COLUMNAS, alto=16, al_abrir=lambda i: app.ir("producto", producto_id=i))
        self.tabla.pack(fill="both", expand=True)

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(acciones, text="Producto seleccionado:", font=fuente(12, True), text_color=SUAVE).pack(side="left", padx=(0, 8))
        boton(acciones, "−1", lambda: self.rapido(-1), width=44).pack(side="left", padx=2)
        boton(acciones, "+1", lambda: self.rapido(1), width=44).pack(side="left", padx=2)
        boton(acciones, "± Ajustar unidades…", self.ajustar, "primario").pack(side="left", padx=6)
        boton(acciones, "📝 Editar", self.editar).pack(side="left", padx=2)
        boton(acciones, "📋 Ficha y movimientos", self.ficha).pack(side="left", padx=6)
        boton(acciones, "🗑 Eliminar", self.eliminar, "peligro").pack(side="right")
        self.refrescar()

    def refrescar(self):
        filtro = self.app.filtros["inventario"]
        filtro["texto"], filtro["bajos"] = self.buscar.get(), bool(self.bajos.get())
        filas = []
        for p in self.app.g.productos(filtro["texto"], filtro["bajos"]):
            stock = f"{'⚠ ' if p['bajo'] else ''}{cant(p['stock'])} {p['unidad']}"
            filas.append((p["id"], (p["referencia"], p["nombre"], euros(p["precio"]), f"{p['iva']} %", stock, cant(p["stock_minimo"])),
                          ["rojo"] if p["bajo"] else []))
        self.tabla.cargar(filas, "No hay productos que coincidan.")

    def _seleccion(self):
        pid = self.tabla.seleccion()
        if pid is None:
            self.app.avisar("Selecciona primero un producto de la lista", "error")
        return pid

    def nuevo(self):
        DialogoProducto(self, self.app.g, al_terminar=self._guardado("Producto creado"))

    def _guardado(self, mensaje):
        def hecho(pid):
            self.app.avisar(mensaje)
            self.refrescar()
            self.tabla.seleccionar(pid)
        return hecho

    def editar(self):
        if (pid := self._seleccion()) is not None:
            DialogoProducto(self, self.app.g, pid, al_terminar=self._guardado("Producto actualizado"))

    def ajustar(self):
        if (pid := self._seleccion()) is not None:
            p = self.app.g.producto(pid)
            DialogoAjuste(self, self.app.g, pid, al_terminar=lambda nuevo: (
                self.app.avisar(f"Stock de {p['nombre']}: {cant(nuevo)} {p['unidad']}"), self.refrescar()))

    def rapido(self, delta):
        if (pid := self._seleccion()) is None:
            return
        try:
            self.app.g.ajustar_stock(pid, "entrada" if delta > 0 else "salida", 1, f"Ajuste rápido {'+1' if delta > 0 else '−1'}")
        except ErrorUsuario as e:
            self.app.avisar(str(e), "error")
            return
        self.refrescar()

    def ficha(self):
        if (pid := self._seleccion()) is not None:
            self.app.ir("producto", producto_id=pid)

    def eliminar(self):
        if (pid := self._seleccion()) is None:
            return
        p = self.app.g.producto(pid)
        if confirmar(self, "Eliminar producto", f"¿Eliminar «{p['nombre']}»?"):
            self.app.avisar(mensaje_eliminado(self.app.g.eliminar_producto(pid), "El producto"))
            self.refrescar()


class VistaProducto(ctk.CTkScrollableFrame):
    def __init__(self, master, app, producto_id):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.producto_id = producto_id
        p = app.g.producto(producto_id)

        ctk.CTkButton(self, text="← Inventario", command=lambda: app.ir("inventario"), fg_color="transparent", hover_color="#e6ebf1",
                      text_color=AZUL, font=fuente(13), width=10, anchor="w").pack(anchor="w")
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", pady=(0, 14))
        titulo(cab, p["nombre"]).pack(side="left")
        boton(cab, "🗑 Eliminar", self.eliminar, "peligro").pack(side="right")
        boton(cab, "📝 Editar", lambda: DialogoProducto(self, app.g, producto_id, al_terminar=lambda _r: self._recargar("Producto actualizado"))).pack(side="right", padx=8)
        boton(cab, "± Ajustar unidades", lambda: DialogoAjuste(self, app.g, producto_id, al_terminar=lambda _r: self._recargar("Stock actualizado")),
              "primario").pack(side="right")

        if not p["activo"]:
            ctk.CTkLabel(self, text="  Producto archivado: aparece en albaranes antiguos, pero no se puede elegir en albaranes nuevos.  ",
                         fg_color="#fff8e1", text_color="#6b4e00", corner_radius=8, font=fuente(12), height=36).pack(fill="x", pady=(0, 12))

        tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        tarjetas.pack(fill="x", pady=(0, 14))
        tarjetas.grid_columnconfigure((0, 1, 2), weight=1, uniform="t")
        valor_stock = r2(dec(p["precio"]) * max(dec(p["stock"]), 0))
        datos = [
            (f"{cant(p['stock'])} {p['unidad']}", "en stock", f"Mínimo: {cant(p['stock_minimo'])}", p["bajo"]),
            (euros(p["precio"]), "precio sin IVA", f"IVA {p['iva']} %", False),
            (euros(valor_stock), "valor del stock", "precio × unidades", False),
        ]
        for i, (grande, texto, pequeno, alerta) in enumerate(datos):
            t = panel(tarjetas, fg_color=ROJO_FONDO if alerta else None)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            ctk.CTkLabel(t, text=grande, font=fuente(24, True), text_color=ROJO if alerta else TEXTO).pack(anchor="w", padx=18, pady=(14, 0))
            ctk.CTkLabel(t, text=texto, font=fuente(13), text_color=TEXTO).pack(anchor="w", padx=18)
            ctk.CTkLabel(t, text=pequeno, font=fuente(12), text_color=SUAVE).pack(anchor="w", padx=18, pady=(0, 14))

        info = panel(self)
        info.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(info, text=f"Referencia: {p['referencia']}", font=fuente(13, True), text_color=TEXTO).pack(anchor="w", padx=18, pady=(14, 2))
        ayuda(info, p["descripcion"] or "Sin descripción.", wraplength=800).pack(anchor="w", padx=18, pady=(0, 14))

        subtitulo(self, "Movimientos de stock").pack(anchor="w", pady=(0, 6))
        movs = app.g.movimientos(producto_id)
        tabla = Tabla(self, [("fecha", "Fecha", 140, "w"), ("motivo", "Motivo", 380, "w"), ("cambio", "Cambio", 100, "e"),
                             ("despues", "Stock después", 120, "e")], alto=min(max(len(movs), 3), 15))
        tabla.cargar([
            (m["id"], (fecha_hora_es(m["fecha"]), m["motivo"], f"{'+' if m['cantidad'] > 0 else ''}{cant(m['cantidad'])}", cant(m["stock_resultante"])),
             ["rojo" if m["cantidad"] < 0 else "verde"])
            for m in movs
        ], "Sin movimientos.")
        tabla.pack(fill="x")
        ayuda(self, "Las salidas por albarán se registran al emitirlo; las anulaciones devuelven las unidades.").pack(anchor="w", pady=(6, 0))

    def _recargar(self, mensaje):
        self.app.avisar(mensaje)
        self.app.ir("producto", producto_id=self.producto_id)

    def eliminar(self):
        p = self.app.g.producto(self.producto_id)
        if confirmar(self, "Eliminar producto", f"¿Eliminar «{p['nombre']}»?"):
            try:
                resultado = self.app.g.eliminar_producto(self.producto_id)
            except ErrorUsuario as e:
                error(self, str(e))
                return
            self.app.avisar(mensaje_eliminado(resultado, "El producto"))
            self.app.ir("inventario")
