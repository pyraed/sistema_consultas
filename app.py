"""
app.py — Sistema de Gestión Mutual
AAMAS / QUANTUM
"""

import os
import io
import time
import base64
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session

import pandas as pd
from PIL import Image, ExifTags
from PyPDF2 import PdfReader, PdfWriter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, Image as RLImage, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader


# ══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-cambiar-en-produccion")

COLOR_AAMAS       = colors.HexColor("#1E3A8A")
COLOR_QUANTUM     = colors.HexColor("#18181b")
COLOR_HEADER_TEXT = colors.white
COLOR_ROW_ALT     = colors.HexColor("#F8FAFC")
COLOR_LABEL       = colors.HexColor("#F1F5F9")
COLOR_BORDER      = colors.HexColor("#CBD5E1")


# ══════════════════════════════════════════════════════════
#  USUARIOS
# ══════════════════════════════════════════════════════════

USUARIOS = {
    "aamas":   "mutualaamas2026",
    "quantum": "mutualquantum2026",
    "admin":   "mutuales2026",
}


# ══════════════════════════════════════════════════════════
#  LOGIN REQUIRED
# ══════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════
#  CARGA DE GRILLA
# ══════════════════════════════════════════════════════════

df = pd.read_excel("grilla.xlsx")
df = df[
    (df["Monto"] >= 100_000) &
    (df["Monto"] <= 600_000) &
    (df["Monto"] % 50_000 == 0)
]

TABLAS = {
    6:  dict(zip(df["Monto"], df["Cuotas6"])),
    9:  dict(zip(df["Monto"], df["Cuotas9"])),
    12: dict(zip(df["Monto"], df["Cuotas12"])),
    18: dict(zip(df["Monto"], df["Cuotas18"])),
    24: dict(zip(df["Monto"], df["Cuotas24"])),
}


# ══════════════════════════════════════════════════════════
#  LINKS Y CONTRATOS
# ══════════════════════════════════════════════════════════

LINKS_DATERO = {
    ("aamas",   "policia"):   "https://drive.google.com/file/d/12UzO8MQajtYY1z1XoI7ZRUJzASPXQE-S/view?usp=drive_link",
    ("aamas",   "spb"):       "https://drive.google.com/file/d/12UzO8MQajtYY1z1XoI7ZRUJzASPXQE-S/view?usp=drive_link",
    ("aamas",   "ips"):       "https://drive.google.com/file/d/1Lm829VsapuzVrTd3v3H7RZ1riXxjEAGM/view?usp=drive_link",
    ("aamas",   "educacion"): "https://drive.google.com/file/d/11L99L9Z_gd-JHLdn-2GvQBc2xLaI5a01/view?usp=drive_link",
    ("quantum", "educacion"): "https://drive.google.com/file/d/1lJD7_qeYlJndC0SbAx6fXN58fIKM0uGS/view?usp=drive_link",
}

CONTRATOS = {
    ("aamas",   "policia"):   "static/contratos/datero_policia_spb_aamas.pdf",
    ("aamas",   "spb"):       "static/contratos/datero_policia_spb_aamas.pdf",
    ("aamas",   "educacion"): "static/contratos/datero_educacion_aamas.pdf",
    ("aamas",   "ips"):       "static/contratos/datero_ips_aamas.pdf",
    ("quantum", "educacion"): "static/contratos/datero_educacion_quantum.pdf",
}

BASE_URL = "https://www.sistemagestionaamas.com.ar"


# ══════════════════════════════════════════════════════════
#  POSICIONES DE FIRMA
# ══════════════════════════════════════════════════════════

POSICIONES_FIRMA_BASE = {
    0:  (30,  80),   1:  (30,  80),   2:  (80,  90),
    3:  (80,  50),   4:  (10,  70),   5:  (20,  200),
    6:  (50,  150),  7:  (550, 220),  8:  (10,  230),
    9:  (220, 90),   10: (80,  130),  11: (30,  350),
    12: (110, 280),  13: (120, 430),
}

POSICIONES_POLICIA_SPB = {12: (370, 410), 14: (110, 460), 15: (20, 10)}
POSICIONES_QUANTUM     = {0: (50, 100), 3: (100, 80),  5: (20, 230)}

PAGINAS_SIN_FIRMA = {1, 9, 13}


# ══════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════

def fmt(valor) -> str:
    return "$ {:,.2f}".format(float(valor)).replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_fecha(fecha_str: str) -> str:
    """Convierte fecha de YYYY-MM-DD a DD/MM/YYYY. Si ya está en otro formato la devuelve igual."""
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return fecha_str


def color_entidad(entidad: str) -> colors.Color:
    return COLOR_AAMAS if entidad.lower() == "aamas" else COLOR_QUANTUM


def _corregir_exif(image: Image.Image) -> Image.Image:
    try:
        exif = image._getexif()
        if exif is None:
            return image
        orientation_tag = next(
            (tag for tag, name in ExifTags.TAGS.items() if name == "Orientation"), None
        )
        if orientation_tag and orientation_tag in exif:
            rotaciones = {3: 180, 6: 270, 8: 90}
            grados = rotaciones.get(exif[orientation_tag])
            if grados:
                image = image.rotate(grados, expand=True)
    except Exception:
        pass
    return image


def corregir_orientacion(ruta: str):
    img = Image.open(ruta)
    img = _corregir_exif(img)
    img.save(ruta)


def corregir_orientacion_y_recortar(ruta: str, recorte_w=0.9, recorte_h=0.7):
    img = Image.open(ruta)
    img = _corregir_exif(img)
    w, h = img.size
    nw, nh = int(w * recorte_w), int(h * recorte_h)
    left = (w - nw) // 2
    top  = (h - nh) // 2
    img  = img.crop((left, top, left + nw, top + nh))
    img.save(ruta)


# ══════════════════════════════════════════════════════════
#  LÓGICA DE NEGOCIO
# ══════════════════════════════════════════════════════════

def calcular_membresia(entidad: str, reparticion: str, monto: float) -> tuple:
    ent, rep = entidad.lower(), reparticion.lower()
    if ent == "aamas":
        if rep in ("policia", "spb", "ips"):
            return 7_975, 11_825, 10_750, 8_810
        elif rep == "educacion":
            return 6_972, 9_950, 9_317, 6_000
        return 0, 0, 0, 0
    elif ent == "quantum":
        return 9_594, 8_172, 7_343, 6_000
    return 0, 0, 0, 0


def calcular_cuota(monto: float, cuotas: int) -> float:
    return TABLAS.get(cuotas, {}).get(float(monto), 0)


def calcular_total(entidad, monto, valor_cuota,
                   cuota_social, medico, farmacia, membresia) -> float:
    ent = entidad.lower()
    if ent == "aamas":
        base = valor_cuota + cuota_social + medico + membresia
        return base + farmacia if monto > 400_000 else base
    elif ent == "quantum":
        return valor_cuota + cuota_social + medico + farmacia + membresia
    return valor_cuota


def aplicar_farmacia(entidad: str, monto: float, farmacia: float) -> float:
    if entidad.lower() == "aamas" and monto <= 400_000:
        return 0
    return farmacia


def get_contrato_path(entidad: str, reparticion: str) -> str:
    key = (entidad.lower(), reparticion.lower())
    return CONTRATOS.get(key, "static/contratos/datero_educacion_aamas.pdf")


def get_posiciones_firma(entidad: str, reparticion: str) -> dict:
    pos = dict(POSICIONES_FIRMA_BASE)
    ent, rep = entidad.lower(), reparticion.lower()
    if ent == "aamas" and rep in ("policia", "spb"):
        pos.update(POSICIONES_POLICIA_SPB)
    elif ent == "quantum":
        pos.update(POSICIONES_QUANTUM)
    return pos


# ══════════════════════════════════════════════════════════
#  HELPERS PDF
# ══════════════════════════════════════════════════════════

def _estilos_pdf(entidad: str):
    base = getSampleStyleSheet()
    color_h = color_entidad(entidad)

    base.add(ParagraphStyle(
        name="Centro",
        parent=base["Normal"],
        alignment=TA_CENTER,
        fontSize=8,
    ))
    base.add(ParagraphStyle(
        name="SeccionTitulo",
        parent=base["Normal"],
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=color_h,
        spaceAfter=4,
        spaceBefore=8,
    ))

    estilo_tabla = TableStyle([
        ("GRID",           (0, 0), (-1, -1), 0.4, COLOR_BORDER),
        ("BACKGROUND",     (0, 0), (0, -1),  COLOR_LABEL),
        ("FONTNAME",       (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME",       (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, COLOR_ROW_ALT]),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ])

    estilo_refs = TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.4, COLOR_BORDER),
        ("BACKGROUND",    (0, 0), (-1, 0),  COLOR_LABEL),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])

    return base, estilo_tabla, estilo_refs


def _pdf_header(entidad: str, elements: list, styles):
    label = "AAMAS" if entidad.lower() == "aamas" else "QUANTUM"
    header = Table([[f"DATERO ONLINE  ·  {label}"]], colWidths=[535])
    header.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), color_entidad(entidad)),
        ("TEXTCOLOR",     (0, 0), (-1, -1), COLOR_HEADER_TEXT),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 12))


def _pdf_seccion(titulo: str, elements: list, styles):
    elements.append(Paragraph(titulo, styles["SeccionTitulo"]))
    elements.append(Spacer(1, 4))


def _pdf_tabla(data, col_widths, estilo, elements):
    t = Table(data, colWidths=col_widths)
    t.setStyle(estilo)
    elements.append(t)
    elements.append(Spacer(1, 10))


def _pdf_firma(firma_buffer: io.BytesIO, nombre: str, fecha_firma: str,
               hora_firma: str, elements: list, styles):
    """Bloque de firma con fecha y hora."""
    firma_buffer.seek(0)
    img = RLImage(firma_buffer, width=130, height=55)
    img.hAlign = "CENTER"
    elements.append(img)

    linea = Table([[""]], colWidths=[220])
    linea.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.8, colors.HexColor("#334155")),
        ("ALIGN",     (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(linea)
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"<b>{nombre}</b>", styles["Centro"]))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("FIRMA DEL SOLICITANTE", styles["Centro"]))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(
        f"Fecha de firma: {fecha_firma}  —  {hora_firma} hs",
        styles["Centro"]
    ))


def _pdf_imagen_doc(ruta, titulo, elements, styles, max_w=260, max_h=155):
    elements.append(Paragraph(titulo, styles["SeccionTitulo"]))
    elements.append(Spacer(1, 6))
    img = RLImage(ruta)
    img._restrictSize(max_w, max_h)
    img.hAlign = "CENTER"
    elements.append(img)
    elements.append(Spacer(1, 12))


# ══════════════════════════════════════════════════════════
#  GENERACIÓN DEL PDF DATERO
# ══════════════════════════════════════════════════════════

def generar_pdf_datero(datos: dict, firma_buffer: io.BytesIO) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=30, leftMargin=30,
        topMargin=30,   bottomMargin=20
    )
    styles, estilo_tabla, estilo_refs = _estilos_pdf(datos["entidad"])
    elements = []

    _pdf_header(datos["entidad"], elements, styles)

    _pdf_seccion("DATOS PERSONALES", elements, styles)
    _pdf_tabla([
        ["Apellido y Nombre", datos["nombre"]],
        ["DNI",               datos["dni"]],
        ["CUIT",              datos["cuit"]],
        ["Teléfono",          datos["telefono"]],
        ["Fecha Nacimiento",  datos["fecha"]],   # ← ya viene formateada DD/MM/YYYY
        ["Nacionalidad",      datos["nacionalidad"]],
        ["Provincia",         datos["provincia"]],
        ["Localidad",         datos["localidad"]],
        ["Domicilio",         datos["domicilio"]],
        ["Email",             datos["email"]],
        ["CBU",               datos["cbu"]],
        ["Repartición",       datos["reparticion"]],
    ], [185, 310], estilo_tabla, elements)

    if datos.get("alt") == "1":
        _pdf_seccion("SERVICIOS / MEMBRESÍA", elements, styles)
        _pdf_tabla([
            ["Cuota Social",    fmt(datos["cuota_social"])],
            ["Coseguro Médico", fmt(datos["medico"])],
        ], [185, 310], estilo_tabla, elements)
    else:
        _pdf_seccion("SERVICIOS", elements, styles)
        _pdf_tabla([
            ["Cuota Social",      fmt(datos["cuota_social"])],
            ["Coseguro Médico",   fmt(datos["medico"])],
            ["Coseguro Farmacia", fmt(datos["farmacia"])],
            ["Membresía",         fmt(datos["membresia"])],
        ], [185, 310], estilo_tabla, elements)

        _pdf_seccion("DATOS DEL PRÉSTAMO", elements, styles)
        _pdf_tabla([
            ["Monto",              fmt(datos["monto"])],
            ["Cantidad de cuotas", datos["cuotas"]],
            ["Valor de cuota",     fmt(datos["valor_cuota"])],
        ], [185, 310], estilo_tabla, elements)

    _pdf_seccion("REFERENCIAS PERSONALES", elements, styles)
    _pdf_tabla([
        ["Nombre",             "Teléfono",          "Relación"],
        [datos["ref1_nombre"], datos["ref1_tel"],    datos["ref1_relacion"]],
        [datos["ref2_nombre"], datos["ref2_tel"],    datos["ref2_relacion"]],
    ], [220, 155, 120], estilo_refs, elements)

    elements.append(Spacer(1, 18))
    _pdf_firma(firma_buffer, datos["nombre"],
               datos["fecha_firma"], datos["hora_firma"],
               elements, styles)

    elements.append(PageBreak())

    doc_header = Table([["DOCUMENTACIÓN DEL SOLICITANTE"]], colWidths=[535])
    doc_header.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), color_entidad(datos["entidad"])),
        ("TEXTCOLOR",     (0, 0), (-1, -1), COLOR_HEADER_TEXT),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 13),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    elements.append(doc_header)
    elements.append(Spacer(1, 14))

    _pdf_imagen_doc(datos["ruta_frente"], "DNI — FRENTE",   elements, styles, 220, 120)
    _pdf_imagen_doc(datos["ruta_dorso"],  "DNI — DORSO",    elements, styles, 220, 120)
    _pdf_imagen_doc(datos["ruta_selfie"], "SELFIE CON DNI", elements, styles, 180, 130)

    elements.append(Spacer(1, 8))
    _pdf_seccion("FIRMA DEL SOLICITANTE", elements, styles)
    elements.append(Spacer(1, 6))
    _pdf_firma(firma_buffer, datos["nombre"],
               datos["fecha_firma"], datos["hora_firma"],
               elements, styles)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════
#  TEXTO SOBRE CONTRATO — separado por entidad
# ══════════════════════════════════════════════════════════

def _texto_contrato(c, i: int, rep: str, entidad: str, datos: dict, cuota_prestamo: float):
    rep = rep.lower()
    ent = entidad.lower()
    c.setFont("Helvetica", 10)

    if ent == "aamas":

        if rep == "educacion" and i in (12, 13):
            c.drawString(200, 645, datos["nombre"])
            c.drawString(200, 630, datos["dni"])
            c.drawString(200, 615, datos["email"])
            c.drawString(400, 600, datos["telefono"])

            if i == 12:
                c.drawString(120, 255, datos["nombre"])
                c.drawString(200, 670, f"La Plata, {datos['fecha_firma']}") #Arriba
                c.drawString(138, 228, f"La Plata, {datos['fecha_firma']}") #Cliente
                c.drawString(365, 228, f"La Plata, {datos['fecha_firma']}") #Presidente
                c.drawString(200, 687, "Asociación de Apoyo a las Mujeres Argentinas Solas")
                c.drawString(90, 243, datos["dni"])
                c.drawString(350, 255, "Presidente")
                c.drawString(320, 243, "20202020")

                for y_pos, codigo, label, valor in [
                    (506, "30018", "Cuota Social",      datos["cuota_social"]),
                    (480, "32018", "Coseguro Médico",   datos["medico"]),
                    (450, "33018", "Coseguro Farmacia", datos["farmacia"]),
                    (423, "31018", "Membresia",    datos["membresia"]),
                    (395, "60018", "Cuota Préstamo",    cuota_prestamo),
                    
                ]:
                    c.drawString(70,  y_pos, codigo)
                    c.drawString(200, y_pos, label)
                    c.drawString(400, y_pos, fmt(float(valor)))

            if i == 13:
                c.drawString(200, 687, "Asociación de Apoyo a las Mujeres Argentinas Solas")
                c.drawString(90, 390, datos["dni"])
                c.drawString(120, 405, datos["nombre"])
                c.drawString(350, 405, "Presidente")
                c.drawString(320, 390, "20202020")
                c.drawString(200, 670, f"La Plata, {datos['fecha_firma']}") #Arriba
                c.drawString(135, 376, f"La Plata, {datos['fecha_firma']}") #Cliente
                c.drawString(365, 376, f"La Plata, {datos['fecha_firma']}") #Presidente

        elif rep in ("policia", "spb"):
            if i == 12:
                c.drawString(210, 505, datos["nombre"])
                c.drawString(400, 670, f"La Plata, {datos['fecha_firma']}") #Arriba
                c.drawString(460, 410, datos["nombre"]) #ACLARACION
                c.drawString(160, 485, datos["dni"])
                c.drawString(290, 470, datos["email"])
                c.drawString(400, 600, "Presidente")
                c.drawString(85, 585, "AAMAS")
                c.drawString(80, 547, "Co seguro medico, Co seguro Farmacia, Cuota social, Membresia, Cuota prestamo")



            if i == 13:
                c.drawString(320, 690, datos["nombre"])
                c.drawString(320, 670, datos["dni"])
                c.drawString(300, 650, fmt(datos["monto"]))
                c.drawString(320, 595, "% 100")

            if i == 14:
                c.drawString(330, 460, datos["nombre"])  
                c.drawString(210, 410, datos["dni"])  



        if i == 0:
            c.drawString(200, 620, datos["nombre"])
            c.drawString(259, 95,  datos["nombre"])
            c.drawString(130, 265, datos["nombre"])
            c.drawString(160, 595, datos["fecha"])
            c.drawString(150, 550, datos["domicilio"])
            c.drawString(380, 525, datos["localidad"])
            c.drawString(380, 595, datos["cuit"])
            c.drawString(80,  575, datos["email"])
            c.drawString(100, 505, datos["reparticion"])
            c.drawString(130, 460, datos["telefono"])
            c.drawString(250, 525, datos["dni"])
            c.drawString(495, 95,  datos["dni"])
            c.drawString(270, 265, datos["dni"])
            c.drawString(480, 640, f"La Plata, {datos['fecha_firma']}")

        if i == 1:
            c.drawString(200, 495, datos["nombre"])
            c.drawString(400, 495, datos["cuit"])
            c.drawString(430, 475, datos["telefono"])

        if i == 2:
            c.drawString(420, 100, datos["dni"])
            c.drawString(200, 100, datos["nombre"])

        if i == 3:
            c.drawString(420, 50, datos["dni"])
            c.drawString(200, 50, datos["nombre"])
            c.drawString(420, 520, f"La Plata, {datos['fecha_firma']}")

        if i == 4:
            c.drawString(400, 65,  datos["dni"])
            c.drawString(360, 610, datos["dni"])
            c.drawString(210, 65,  datos["nombre"])
            c.drawString(140, 630, datos["nombre"])
            c.drawString(100, 540, datos["localidad"])
            c.drawString(150, 565, datos["domicilio"])
            c.drawString(400, 540, datos["telefono"])
            c.drawString(400, 585, datos["fecha"])
            c.drawString(120, 585, datos["nacionalidad"])

        if i == 5:
            c.drawString(230, 220, datos["nombre"])
            c.drawString(450, 220, datos["dni"])
            c.drawString(420, 700, f"La Plata, {datos['fecha_firma']}")

        if i == 8:
            c.drawString(20, 190, datos["nombre"])
            c.drawString(30, 140, datos["cuit"])
            c.drawString(20, 90,  datos["email"])

        if i == 10:
            c.drawString(100, 90, datos["nombre"])
            c.drawString(140, 40, datos["dni"])

    elif ent == "quantum":

        if rep == "educacion" and i in (12, 13):
            c.drawString(200, 645, datos["nombre"])
            c.drawString(200, 630, datos["dni"])
            c.drawString(200, 615, datos["email"])
            c.drawString(400, 600, datos["telefono"])

            if i == 12:
                c.drawString(120, 255, datos["nombre"])
                c.drawString(200, 687, "Asociación Mutual Quantum de Profesionales y Técnicos")
                c.drawString(90, 243, datos["dni"])
                c.drawString(350, 255, "Presidente")
                c.drawString(320, 243, "20202020")
                c.drawString(200, 670, f"La Plata, {datos['fecha_firma']}") #Arriba
                c.drawString(138, 228, f"La Plata, {datos['fecha_firma']}") #Cliente
                c.drawString(365, 228, f"La Plata, {datos['fecha_firma']}") #Presidente

                for y_pos, codigo, label, valor in [
                    (506, "30142", "Cuota Social",      datos["cuota_social"]),
                    (480, "32142", "Coseguro Médico",   datos["medico"]),
                    (450, "33142", "Coseguro Farmacia", datos["farmacia"]),
                    (423, "31142", "Membresia",    datos["membresia"]),
                    (395, "60142", "Cuota Préstamo",    cuota_prestamo),
                    

                ]:
                    c.drawString(70,  y_pos, codigo)
                    c.drawString(200, y_pos, label)
                    c.drawString(400, y_pos, fmt(float(valor)))

            if i == 13:
                c.drawString(200, 687, "Asociación Mutual Quantum de Profesionales y Técnicos")
                c.drawString(90, 390, datos["dni"])
                c.drawString(120, 405, datos["nombre"])
                c.drawString(350, 405, "Presidente")
                c.drawString(320, 390, "20202020")
                c.drawString(200, 670, f"La Plata, {datos['fecha_firma']}") #Arriba
                c.drawString(135, 376, f"La Plata, {datos['fecha_firma']}") #Cliente
                c.drawString(365, 376, f"La Plata, {datos['fecha_firma']}") #Presidente

        if i == 0:
            c.drawString(200, 635, datos["nombre"])
            c.drawString(259, 105, datos["nombre"])
            c.drawString(130, 277, datos["nombre"])
            c.drawString(160, 613, datos["fecha"])
            c.drawString(150, 565, datos["domicilio"])
            c.drawString(380, 542, datos["localidad"])
            c.drawString(380, 613, datos["cuit"])
            c.drawString(80,  590, datos["email"])
            c.drawString(100, 520, datos["reparticion"])
            c.drawString(130, 475, datos["telefono"])
            c.drawString(250, 542, datos["dni"])
            c.drawString(495, 105, datos["dni"])
            c.drawString(270, 277, datos["dni"])
            c.drawString(470, 670, f"La Plata, {datos['fecha_firma']}")

        if i == 1:
            c.drawString(200, 535, datos["nombre"])
            c.drawString(400, 535, datos["cuit"])
            c.drawString(380, 515, datos["telefono"])

        if i == 2:
            c.drawString(420, 100, datos["dni"])
            c.drawString(200, 100, datos["nombre"])

        if i == 3:
            c.drawString(420, 95, datos["dni"])
            c.drawString(200, 95, datos["nombre"])
            c.drawString(420, 560, f"La Plata, {datos['fecha_firma']}")

        if i == 4:
            c.drawString(400, 65,  datos["dni"])
            c.drawString(360, 610, datos["dni"])
            c.drawString(210, 65,  datos["nombre"])
            c.drawString(140, 630, datos["nombre"])
            c.drawString(100, 540, datos["localidad"])
            c.drawString(150, 565, datos["domicilio"])
            c.drawString(400, 540, datos["telefono"])
            c.drawString(400, 585, datos["fecha"])
            c.drawString(120, 585, datos["nacionalidad"])

        if i == 5:
            c.drawString(230, 220, datos["nombre"])
            c.drawString(450, 220, datos["dni"])
            c.drawString(420, 700, f"La Plata, {datos['fecha_firma']}")

        if i == 8:
            c.drawString(20, 190, datos["nombre"])
            c.drawString(30, 140, datos["cuit"])
            c.drawString(20, 90,  datos["email"])

        if i == 10:
            c.drawString(100, 90, datos["nombre"])
            c.drawString(140, 40, datos["dni"])


def firmar_contrato(contrato_path: str, firma_buffer: io.BytesIO,
                    entidad: str, reparticion: str,
                    datos: dict, cuota_prestamo: float) -> PdfWriter:
    contrato = PdfReader(contrato_path)
    writer   = PdfWriter()
    pos_map  = get_posiciones_firma(entidad, reparticion)

    for i, page in enumerate(contrato.pages):

        packet = io.BytesIO()
        c = rl_canvas.Canvas(packet)

        _texto_contrato(c, i, reparticion, entidad, datos, cuota_prestamo)

        if i not in PAGINAS_SIN_FIRMA:
            x, y = pos_map.get(i, (220, 90))
            firma_buffer.seek(0)
            firma_img = ImageReader(firma_buffer)

            if i == 7:
                c.saveState()
                c.translate(x, y)
                c.rotate(90)
                c.drawImage(firma_img, -100, 20, width=140, height=60, mask="auto")
                c.restoreState()
            elif i == 11:
                c.saveState()
                c.translate(x, y)
                c.rotate(-90)
                c.drawImage(firma_img, -100, 20, width=140, height=60, mask="auto")
                c.restoreState()
            else:
                c.drawImage(firma_img, x, y, width=140, height=60, mask="auto")

        c.save()
        packet.seek(0)

        page.merge_page(PdfReader(packet).pages[0])
        writer.add_page(page)

    return writer


# ══════════════════════════════════════════════════════════
#  RUTAS — LOGIN / LOGOUT
# ══════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        usuario  = request.form.get("usuario", "").strip().lower()
        password = request.form.get("password", "").strip()
        if usuario in USUARIOS and USUARIOS[usuario] == password:
            session["usuario"] = usuario
            return redirect(url_for("inicio"))
        else:
            error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════
#  RUTAS FLASK — protegidas
# ══════════════════════════════════════════════════════════

@app.route("/")
@login_required
def inicio():
    return render_template("index.html", montos=TABLAS[12].keys())


@app.route("/calcular", methods=["POST"])
@login_required
def calcular():
    entidad     = request.form["entidad"]
    reparticion = request.form["reparticion"]
    monto       = float(request.form["monto"])
    cuotas      = int(request.form["cuotas"])

    cuota_social, medico, farmacia, membresia = calcular_membresia(entidad, reparticion, monto)
    farmacia    = aplicar_farmacia(entidad, monto, farmacia)
    valor_cuota = calcular_cuota(monto, cuotas)
    if request.form.get("alt", "0") == "1":
        valor_cuota = 19800
    cuota_total = calcular_total(entidad, monto, valor_cuota,
                                 cuota_social, medico, farmacia, membresia)

    link_formulario = (
        f"{BASE_URL}/formulario"
        f"?ent={entidad}&rep={reparticion}&monto={int(monto)}&cuotas={cuotas}"
    )

    return render_template(
        "resultado.html",
        entidad=entidad,
        reparticion=reparticion,
        monto=fmt(monto),
        cuotas=cuotas,
        valor_cuota=fmt(valor_cuota),
        cuota_social=fmt(cuota_social),
        medico=fmt(medico),
        farmacia=fmt(farmacia),
        membresia=fmt(membresia),
        cuota_total=cuota_total,
        link_formulario=link_formulario,
    )


@app.route("/formulario")
def formulario():
    return render_template(
        "formulario.html",
        entidad=request.args.get("ent"),
        reparticion=request.args.get("rep"),
        monto=request.args.get("monto"),
        cuotas=request.args.get("cuotas"),
        alt=request.args.get("alt", "0"),
    )


@app.route("/identidad", methods=["POST"])
def identidad():
    return render_template("identidad.html", **request.form.to_dict())


@app.route("/guardar_formulario", methods=["POST"])
def guardar_formulario():
    entidad     = request.form["entidad"].lower()
    reparticion = request.form["reparticion"].lower()
    monto       = float(request.form["monto"])
    cuotas      = int(request.form["cuotas"])

    valor_cuota = calcular_cuota(monto, cuotas)
    if request.form.get("alt", "0") == "1":
        valor_cuota = 19800
    cuota_social, medico, farmacia, membresia = calcular_membresia(entidad, reparticion, monto)
    farmacia = aplicar_farmacia(entidad, monto, farmacia)

    campos = [
        "nombre", "dni", "cuit", "telefono", "fecha_nacimiento",
        "nacionalidad", "provincia", "localidad", "domicilio", "email", "cbu",
        "ref1_nombre", "ref1_tel", "ref1_relacion",
        "ref2_nombre", "ref2_tel", "ref2_relacion",
    ]
    datos = {c: request.form.get(c, "").upper() for c in campos}

    os.makedirs("static/fotos", exist_ok=True)
    ts = int(time.time())
    rutas = {
        "frente": f"static/fotos/frente_{ts}.jpg",
        "dorso":  f"static/fotos/dorso_{ts}.jpg",
        "selfie": f"static/fotos/selfie_{ts}.jpg",
    }
    request.files["dni_frente"].save(rutas["frente"])
    request.files["dni_dorso"].save(rutas["dorso"])
    request.files["selfie"].save(rutas["selfie"])

    corregir_orientacion_y_recortar(rutas["frente"])
    corregir_orientacion_y_recortar(rutas["dorso"])
    corregir_orientacion(rutas["selfie"])

    return render_template(
        "firma.html",
        entidad=entidad,
        reparticion=reparticion.upper(),
        monto=monto,
        monto_fmt=fmt(monto),
        cuotas=cuotas,
        valor_cuota=valor_cuota,
        valor_cuota_fmt=fmt(valor_cuota),
        cuota_social=cuota_social,
        cuota_social_fmt=fmt(cuota_social),
        medico=medico,
        medico_fmt=fmt(medico),
        farmacia=farmacia,
        farmacia_fmt=fmt(farmacia),
        membresia=membresia,
        membresia_fmt=fmt(membresia),
        nombre=datos["nombre"],
        dni=datos["dni"],
        cuit=datos["cuit"],
        telefono=datos["telefono"],
        fecha=fmt_fecha(datos["fecha_nacimiento"]),
        nacionalidad=datos["nacionalidad"],
        provincia=datos["provincia"],
        localidad=datos["localidad"],
        domicilio=datos["domicilio"],
        email=datos["email"],
        cbu=datos["cbu"],
        ruta_frente=rutas["frente"],
        ruta_dorso=rutas["dorso"],
        ruta_selfie=rutas["selfie"],
        ref1_nombre=datos["ref1_nombre"],
        ref1_tel=datos["ref1_tel"],
        ref1_relacion=datos["ref1_relacion"],
        ref2_nombre=datos["ref2_nombre"],
        ref2_tel=datos["ref2_tel"],
        ref2_relacion=datos["ref2_relacion"],
        alt=request.form.get("alt", "0"),
    )


@app.route("/generar_pdf_final", methods=["POST"])
def generar_pdf_final():
    entidad      = request.form["entidad"].lower()
    reparticion  = request.form["reparticion"].lower()
    monto        = float(request.form["monto"])
    cuotas       = int(request.form["cuotas"])
    valor_cuota  = float(request.form["valor_cuota"])
    if request.form.get("alt", "0") == "1":
        valor_cuota = 19800
    cuota_social = float(request.form["cuota_social"])
    medico       = float(request.form["medico"])
    farmacia     = float(request.form["farmacia"])
    membresia    = float(request.form["membresia"])

    firma_bytes  = base64.b64decode(request.form["firma"].split(",")[1])
    firma_buffer = io.BytesIO(firma_bytes)

    from datetime import datetime, timedelta
    ahora       = datetime.now() - timedelta(hours=3)  # UTC-3 Argentina
    fecha_firma = ahora.strftime("%d/%m/%Y")
    hora_firma  = ahora.strftime("%H:%M")

    datos = {
        "entidad":       entidad,
        "reparticion":   reparticion.upper(),
        "monto":         monto,
        "cuotas":        cuotas,
        "valor_cuota":   valor_cuota,
        "cuota_social":  cuota_social,
        "medico":        medico,
        "farmacia":      farmacia,
        "membresia":     membresia,
        "nombre":        request.form.get("nombre", ""),
        "dni":           request.form.get("dni", ""),
        "cuit":          request.form.get("cuit", ""),
        "telefono":      request.form.get("telefono", ""),
        "fecha":         fmt_fecha(request.form.get("fecha_nacimiento", "")),
        "nacionalidad":  request.form.get("nacionalidad", ""),
        "provincia":     request.form.get("provincia", ""),
        "localidad":     request.form.get("localidad", ""),
        "domicilio":     request.form.get("domicilio", ""),
        "email":         request.form.get("email", ""),
        "cbu":           request.form.get("cbu", ""),
        "ref1_nombre":   request.form.get("ref1_nombre", ""),
        "ref1_tel":      request.form.get("ref1_tel", ""),
        "ref1_relacion": request.form.get("ref1_relacion", ""),
        "ref2_nombre":   request.form.get("ref2_nombre", ""),
        "ref2_tel":      request.form.get("ref2_tel", ""),
        "ref2_relacion": request.form.get("ref2_relacion", ""),
        "ruta_frente":   request.form["ruta_frente"],
        "ruta_dorso":    request.form["ruta_dorso"],
        "ruta_selfie":   request.form["ruta_selfie"],
        "alt":           request.form.get("alt", "0"),
        "fecha_firma":   fecha_firma,
        "hora_firma":    hora_firma,
    }

    cuota_prestamo = TABLAS.get(cuotas, {}).get(int(monto), 0)

    datero_buffer = generar_pdf_datero(datos, firma_buffer)

    writer_contrato = firmar_contrato(
        get_contrato_path(entidad, reparticion),
        firma_buffer, entidad, reparticion, datos, cuota_prestamo
    )

    final_writer = PdfWriter()

    for page in PdfReader(datero_buffer).pages:
        final_writer.add_page(page)

    contrato_output = io.BytesIO()
    writer_contrato.write(contrato_output)
    contrato_output.seek(0)

    for page in PdfReader(contrato_output).pages:
        final_writer.add_page(page)

    os.makedirs("static", exist_ok=True)
    filename = f"contrato_{entidad}_{int(time.time())}.pdf"
    with open(f"static/{filename}", "wb") as f:
        final_writer.write(f)

    return render_template("descargar.html", archivo=filename)


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)