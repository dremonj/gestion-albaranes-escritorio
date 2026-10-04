"""Generación del albarán en PDF (formato A4) con ReportLab."""

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .logica import ANULADO, BORRADOR, calcular_linea, cant, euros, fecha_es

GRIS = colors.HexColor("#555555")
GRIS_CLARO = colors.HexColor("#f0f0f0")
LINEA = colors.HexColor("#cccccc")

_base = getSampleStyleSheet()["Normal"]
NORMAL = ParagraphStyle("normal", parent=_base, fontName="Helvetica", fontSize=9, leading=12)
PEQUENO = ParagraphStyle("pequeno", parent=NORMAL, fontSize=8, leading=10, textColor=GRIS)
NEGRITA = ParagraphStyle("negrita", parent=NORMAL, fontName="Helvetica-Bold")
EMPRESA = ParagraphStyle("empresa", parent=NORMAL, fontName="Helvetica-Bold", fontSize=14, leading=18)
TITULO = ParagraphStyle("titulo", parent=NORMAL, fontName="Helvetica-Bold", fontSize=15, leading=19, alignment=TA_RIGHT)
DERECHA = ParagraphStyle("derecha", parent=NORMAL, alignment=TA_RIGHT)
CENTRO = ParagraphStyle("centro", parent=PEQUENO, alignment=TA_CENTER)


def _p(texto, estilo=NORMAL):
    return Paragraph(escape(str(texto or "")).replace("\n", "<br/>"), estilo)


def _direccion(datos: dict) -> list[str]:
    poblacion = " ".join(x for x in (datos.get("cp"), datos.get("ciudad")) if x)
    return [x for x in (datos.get("direccion"), poblacion, datos.get("provincia")) if x]


def generar_pdf(albaran: dict, destino) -> None:
    """Crea el PDF del albarán (tal y como lo devuelve Gestion.albaran) en la ruta `destino`."""
    emp, cli, tot = albaran["empresa"], albaran["cliente"], albaran["totales"]
    valorado = bool(albaran["valorado"])
    ancho = A4[0] - 30 * mm
    marca = {BORRADOR: "BORRADOR", ANULADO: "ANULADO"}.get(albaran["estado"], "")

    def fondo(canvas, doc):
        canvas.saveState()
        if marca:
            canvas.setFont("Helvetica-Bold", 90)
            canvas.setFillColor(colors.Color(0.78, 0.16, 0.16, alpha=0.10))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, marca)
            canvas.restoreState()
            canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(destino), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"Albarán {albaran['numero'] or 'borrador'}", author=emp.get("nombre") or "",
    )
    historia = []

    # Cabecera: empresa a la izquierda, título y datos del documento a la derecha.
    bloque_empresa = [_p(emp.get("nombre") or "Tu empresa (configúrala en «Mi empresa»)", EMPRESA)]
    if emp.get("nif"):
        bloque_empresa.append(_p(f"NIF: {emp['nif']}"))
    bloque_empresa += [_p(x) for x in _direccion(emp)]
    if emp.get("telefono"):
        bloque_empresa.append(_p(f"Tel.: {emp['telefono']}"))
    if emp.get("email"):
        bloque_empresa.append(_p(emp["email"]))

    datos_doc = [["Nº", albaran["numero"] or "Pendiente de emitir"], ["Fecha", fecha_es(albaran["fecha"])]]
    if albaran.get("fecha_entrega"):
        datos_doc.append(["Entregado", fecha_es(albaran["fecha_entrega"])])
    tabla_doc = Table([[_p(k, PEQUENO), _p(v, NEGRITA)] for k, v in datos_doc], colWidths=[22 * mm, 45 * mm])
    tabla_doc.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    cabecera = Table([[bloque_empresa, [_p("ALBARÁN DE ENTREGA", TITULO), Spacer(1, 4), tabla_doc]]],
                     colWidths=[ancho - 72 * mm, 72 * mm])
    cabecera.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    historia += [cabecera, Spacer(1, 10)]

    # Cliente
    bloque_cliente = [_p("CLIENTE / DESTINATARIO", PEQUENO), _p(cli.get("nombre"), NEGRITA)]
    if cli.get("nif"):
        bloque_cliente.append(_p(f"NIF: {cli['nif']}"))
    bloque_cliente += [_p(x) for x in _direccion(cli)]
    if cli.get("telefono"):
        bloque_cliente.append(_p(f"Tel.: {cli['telefono']}"))
    caja = Table([["", bloque_cliente]], colWidths=[ancho * 0.42, ancho * 0.58])
    caja.setStyle(TableStyle([("BOX", (1, 0), (1, 0), 0.8, LINEA), ("LEFTPADDING", (1, 0), (1, 0), 8),
                              ("TOPPADDING", (1, 0), (1, 0), 6), ("BOTTOMPADDING", (1, 0), (1, 0), 8)]))
    historia += [caja, Spacer(1, 14)]

    # Líneas
    if valorado:
        cabeceras = ["Ref.", "Descripción", "Cantidad", "Ud.", "Precio", "Dto.", "IVA", "Importe"]
        anchos = [20, None, 18, 12, 21, 13, 12, 24]
    else:
        cabeceras = ["Ref.", "Descripción", "Cantidad", "Ud."]
        anchos = [25, None, 25, 18]
    fijo = sum(a for a in anchos if a) * mm
    anchos = [a * mm if a else ancho - fijo for a in anchos]
    negrita_derecha = ParagraphStyle("nd", parent=NEGRITA, alignment=TA_RIGHT)
    numericas = {"Cantidad", "Precio", "Dto.", "IVA", "Importe"}
    filas = [[_p(c, negrita_derecha if c in numericas else NEGRITA) for c in cabeceras]]
    for l in albaran["lineas"]:
        fila = [_p(l["referencia"], PEQUENO), _p(l["descripcion"]), _p(cant(l["cantidad"]), DERECHA), _p(l["unidad"])]
        if valorado:
            fila += [
                _p(euros(l["precio"]), DERECHA),
                _p(f"{cant(l['descuento'])} %" if l["descuento"] else "", DERECHA),
                _p(f"{l['iva']} %", DERECHA),
                _p(euros(calcular_linea(l)["base"]), DERECHA),
            ]
        filas.append(fila)
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CLARO),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    historia += [tabla, Spacer(1, 12)]

    # Observaciones y totales
    izquierda = []
    if albaran.get("observaciones"):
        izquierda += [_p("Observaciones", NEGRITA), _p(albaran["observaciones"]), Spacer(1, 4)]
    izquierda.append(_p(f"Total de unidades: {cant(tot['unidades'])}", PEQUENO))
    derecha = ""
    if valorado:
        filas_tot = [[_p("Base imponible"), _p(euros(tot["base"]), DERECHA)]]
        filas_tot += [[_p(f"IVA {d['iva']} % sobre {euros(d['base'])}", PEQUENO), _p(euros(d["cuota"]), DERECHA)] for d in tot["desglose"]]
        filas_tot.append([_p("TOTAL", NEGRITA), _p(euros(tot["total"]), ParagraphStyle("t", parent=DERECHA, fontName="Helvetica-Bold", fontSize=11))])
        derecha = Table(filas_tot, colWidths=[48 * mm, 30 * mm])
        derecha.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, LINEA), ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.black)]))
    pie = Table([[izquierda, derecha]], colWidths=[ancho - 80 * mm, 80 * mm])
    pie.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    historia += [pie, Spacer(1, 26)]

    # Firmas
    recibido = [_p("Recibí conforme (nombre, DNI y firma)", PEQUENO)]
    if albaran.get("receptor"):
        recibido += [Spacer(1, 30), _p(albaran["receptor"], NEGRITA)]
    firmas = Table([[[_p("Entregado por", PEQUENO)], "", recibido]], colWidths=[(ancho - 12 * mm) / 2, 12 * mm, (ancho - 12 * mm) / 2],
                   rowHeights=[30 * mm])
    firmas.setStyle(TableStyle([("BOX", (0, 0), (0, 0), 0.8, LINEA), ("BOX", (2, 0), (2, 0), 0.8, LINEA), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    historia += [firmas, Spacer(1, 14), _p("Este documento acredita la entrega de la mercancía. No es una factura.", CENTRO)]
    if albaran["estado"] == ANULADO and albaran.get("motivo_anulacion"):
        historia.append(_p(f"Albarán anulado. Motivo: {albaran['motivo_anulacion']}", CENTRO))

    doc.build(historia, onFirstPage=fondo, onLaterPages=fondo)
