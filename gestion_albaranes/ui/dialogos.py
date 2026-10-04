"""Ventanas emergentes para crear y editar datos."""

import customtkinter as ctk

from ..logica import TIPOS_IVA, UNIDADES, cant, dec, fecha_es, hoy
from .comun import AZUL, TEXTO, Dialogo, Formulario, ayuda, fuente


def _iva_texto(iva):
    return f"{iva} %"


def _iva_valor(texto):
    return int(str(texto).replace("%", "").strip())


class DialogoCliente(Dialogo):
    def __init__(self, padre, g, cliente_id=None, al_terminar=None):
        self.g = g
        self.cliente = g.cliente(cliente_id) if cliente_id else {}
        super().__init__(padre, "Editar cliente" if cliente_id else "Nuevo cliente", al_terminar=al_terminar)

    def construir(self):
        c = self.cliente
        f = self.form = Formulario(self.cuerpo, columnas=3)
        self.foco = f.texto("nombre", "Nombre o razón social *", c.get("nombre"), ancho=2)
        f.texto("nif", "NIF / CIF", c.get("nif"))
        f.texto("direccion", "Dirección", c.get("direccion"), ancho=3)
        f.texto("cp", "Código postal", c.get("cp"))
        f.texto("ciudad", "Ciudad", c.get("ciudad"))
        f.texto("provincia", "Provincia", c.get("provincia"))
        f.texto("telefono", "Teléfono", c.get("telefono"))
        f.texto("email", "Email", c.get("email"), ancho=2)
        f.area("notas", "Notas", c.get("notas", ""), alto=60)

    def primer_foco(self):
        return self.foco

    def aceptar(self):
        datos = self.form.valores()
        if self.cliente:
            datos["id"] = self.cliente["id"]
        return self.g.guardar_cliente(datos)


class DialogoProducto(Dialogo):
    def __init__(self, padre, g, producto_id=None, al_terminar=None):
        self.g = g
        self.producto = g.producto(producto_id) if producto_id else {}
        super().__init__(padre, "Editar producto" if producto_id else "Nuevo producto", al_terminar=al_terminar)

    def construir(self):
        p = self.producto
        f = self.form = Formulario(self.cuerpo, columnas=3)
        self.foco = f.texto("referencia", "Referencia *", p.get("referencia"), placeholder_text="Ej. CAF-1K")
        f.texto("nombre", "Nombre *", p.get("nombre"), ancho=2)
        f.area("descripcion", "Descripción (opcional)", p.get("descripcion", ""), alto=50)
        f.opciones("unidad", "Unidad de medida", UNIDADES, p.get("unidad", "ud"))
        f.texto("precio", "Precio sin IVA (€) *", cant(p["precio"]) if p else "")
        f.opciones("iva", "IVA", [_iva_texto(t) for t in TIPOS_IVA], _iva_texto(p.get("iva", 21)))
        if p:
            f.nota(f"Stock actual: {cant(p['stock'])} {p['unidad']}. Para cambiarlo usa «Ajustar unidades» (así queda registrado).")
        else:
            f.texto("stock", "Unidades iniciales en stock", "0")
        f.texto("stock_minimo", "Stock mínimo (aviso)", cant(p["stock_minimo"]) if p else "0")

    def primer_foco(self):
        return self.foco

    def aceptar(self):
        datos = self.form.valores()
        datos["iva"] = _iva_valor(datos["iva"])
        if self.producto:
            datos["id"] = self.producto["id"]
        return self.g.guardar_producto(datos)


class DialogoAjuste(Dialogo):
    """Modificar las unidades de un producto: entrada, salida o recuento exacto."""

    MODOS = {"➕ Entrada (sumar)": "entrada", "➖ Salida (restar)": "salida", "🟰 Fijar stock exacto": "fijar"}

    def __init__(self, padre, g, producto_id, al_terminar=None):
        self.g = g
        self.producto = g.producto(producto_id)
        super().__init__(padre, f"Ajustar unidades · {self.producto['nombre']}", texto_aceptar="Aplicar ajuste", al_terminar=al_terminar)

    def construir(self):
        p = self.producto
        ctk.CTkLabel(self.cuerpo, text=f"Stock actual: {cant(p['stock'])} {p['unidad']}", font=fuente(15, True),
                     text_color=TEXTO, anchor="w").pack(fill="x", padx=6, pady=(0, 8))
        self.modo = ctk.CTkSegmentedButton(self.cuerpo, values=list(self.MODOS), font=fuente(13), height=36,
                                           selected_color=AZUL, command=lambda _v: self._previsualizar())
        self.modo.set(next(iter(self.MODOS)))
        self.modo.pack(fill="x", padx=6, pady=(0, 6))
        rejilla = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        rejilla.pack(fill="x")
        f = self.form = Formulario(rejilla, columnas=2)
        self.cantidad = f.texto("cantidad", f"Cantidad ({p['unidad']})")
        f.texto("motivo", "Motivo (opcional)", placeholder_text="Ej. Compra a proveedor, rotura…")
        self.cantidad.bind("<KeyRelease>", lambda _e: self._previsualizar())
        self.vista_previa = ayuda(self.cuerpo, "")
        self.vista_previa.pack(fill="x", padx=6, pady=(4, 0))

    def primer_foco(self):
        return self.cantidad

    def _previsualizar(self):
        valor = dec(self.cantidad.get())
        if valor is None or valor < 0:
            self.vista_previa.configure(text="")
            return
        actual = dec(self.producto["stock"])
        modo = self.MODOS[self.modo.get()]
        nuevo = {"entrada": actual + valor, "salida": actual - valor, "fijar": valor}[modo]
        self.vista_previa.configure(text=f"El stock quedará en {cant(nuevo)} {self.producto['unidad']}.")

    def aceptar(self):
        datos = self.form.valores()
        return self.g.ajustar_stock(self.producto["id"], self.MODOS[self.modo.get()], datos["cantidad"], datos["motivo"])


class DialogoEntrega(Dialogo):
    def __init__(self, padre, g, albaran_id, numero, al_terminar=None):
        self.g, self.albaran_id = g, albaran_id
        super().__init__(padre, f"Entregar {numero}", texto_aceptar="Confirmar entrega", ancho=520, al_terminar=al_terminar)

    def construir(self):
        f = self.form = Formulario(self.cuerpo, columnas=2)
        f.texto("fecha", "Fecha de entrega (dd/mm/aaaa)", fecha_es(hoy()))
        self.foco = f.texto("receptor", "Recibido por (nombre)", placeholder_text="Persona que firma")

    def primer_foco(self):
        return self.foco

    def aceptar(self):
        datos = self.form.valores()
        self.g.marcar_entregado(self.albaran_id, datos["fecha"], datos["receptor"])


class DialogoAnular(Dialogo):
    def __init__(self, padre, g, albaran_id, numero, al_terminar=None):
        self.g, self.albaran_id = g, albaran_id
        super().__init__(padre, f"Anular {numero}", texto_aceptar="Anular albarán", ancho=520, al_terminar=al_terminar)

    def construir(self):
        ayuda(self.cuerpo, "Las unidades de este albarán volverán al inventario. El albarán se conserva\n"
                           "como anulado para no romper la numeración.").pack(fill="x", padx=6, pady=(0, 6))
        rejilla = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        rejilla.pack(fill="x")
        self.form = Formulario(rejilla, columnas=1)
        self.foco = self.form.texto("motivo", "Motivo de la anulación", placeholder_text="Ej. Error en las cantidades")

    def primer_foco(self):
        return self.foco

    def aceptar(self):
        self.g.anular(self.albaran_id, self.form.valores()["motivo"])

