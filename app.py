from flask import Flask, render_template, request
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import io
import base64
from reportlab.platypus import Image
from PIL import Image, ExifTags

# 🔥 PEGÁS LA FUNCIÓN ACÁ
def corregir_orientacion(ruta):
    image = Image.open(ruta)

    try:
        exif = image._getexif()

        if exif is not None:
            orientation = None
            for tag, name in ExifTags.TAGS.items():
                if name == 'Orientation':
                    orientation = tag
                    break

            if orientation and orientation in exif:
                if exif[orientation] == 3:
                    image = image.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    image = image.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    image = image.rotate(90, expand=True)

    except:
        pass

    image.save(ruta)



def formatear_moneda(valor):
    return "$ {:,.2f}".format(float(valor)).replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------- BASE ----------------

# Cargar grilla
df = pd.read_excel("grilla.xlsx")
df = df[
    (df["Monto"] >= 100000) & 
    (df["Monto"] <= 600000) & 
    (df["Monto"] % 50000 == 0)
]

tabla_6 = dict(zip(df["Monto"], df["Cuotas6"]))
tabla_12 = dict(zip(df["Monto"], df["Cuotas12"]))
tabla_18 = dict(zip(df["Monto"], df["Cuotas18"]))
tabla_24 = dict(zip(df["Monto"], df["Cuotas24"]))

app = Flask(__name__)

# ---------------- UTIL ----------------

def formatear(numero):
    return "{:,.2f}".format(numero).replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------- LOGICA NUEVA ----------------

def calcular_membresia(entidad, reparticion, monto):

    # 🔹 AAMAS
    if entidad == "aamas":

        if reparticion in ["policia", "spb", "ips"]:
            cuota_social = 7975
            medico = 11825
            farmacia = 10750
            membresia = 8810

        elif reparticion == "educacion":
            cuota_social = 6972
            medico = 9950
            farmacia = 9317
            membresia = 6000

        else:
            cuota_social = 0
            medico = 0
            farmacia = 0
            membresia = 0

    # 🔹 QUANTUM
    elif entidad == "quantum":

        # Quantum solo usa educación pero igual cubrimos todo
        cuota_social = 9594
        medico = 8172
        farmacia = 7343
        membresia = 6000

    else:
        cuota_social = 0
        medico = 0
        farmacia = 0
        membresia = 0

    return cuota_social, medico, farmacia, membresia


def calcular_cuota(monto, cuotas):

    monto = float(monto)

    if cuotas == 6:
        return tabla_6.get(monto, 0)
    elif cuotas == 12:
        return tabla_12.get(monto, 0)
    elif cuotas == 18:
        return tabla_18.get(monto, 0)
    elif cuotas == 24:
        return tabla_24.get(monto, 0)
    else:
        return 0


def calcular_total(entidad, reparticion, monto, valor_cuota,
                   cuota_social, medico, farmacia, membresia):

    # ---------------- AAMAS ----------------
    if entidad == "aamas":

        if monto <= 400000:
            total = valor_cuota + cuota_social + medico + membresia
        else:
            total = valor_cuota + cuota_social + medico + farmacia + membresia

    # ---------------- QUANTUM ----------------
    elif entidad == "quantum":

        total = valor_cuota + cuota_social + medico + farmacia + membresia

    return total


links_datero = {
    # AAMAS
    ("aamas", "policia"): "https://drive.google.com/file/d/12UzO8MQajtYY1z1XoI7ZRUJzASPXQE-S/view?usp=drive_link",
    ("aamas", "spb"): "https://drive.google.com/file/d/12UzO8MQajtYY1z1XoI7ZRUJzASPXQE-S/view?usp=drive_link",
    ("aamas", "ips"): "https://drive.google.com/file/d/1Lm829VsapuzVrTd3v3H7RZ1riXxjEAGM/view?usp=drive_link",
    ("aamas", "educacion"): "https://drive.google.com/file/d/11L99L9Z_gd-JHLdn-2GvQBc2xLaI5a01/view?usp=drive_link",

    # QUANTUM
    ("quantum", "educacion"): "https://drive.google.com/file/d/1lJD7_qeYlJndC0SbAx6fXN58fIKM0uGS/view?usp=drive_link"
}



# ---------------- RUTAS ----------------

@app.route("/")
def inicio():
    return render_template("index.html", montos=tabla_12.keys())


@app.route("/calcular", methods=["POST"])
def calcular():

    entidad = request.form["entidad"]
    reparticion = request.form["reparticion"]
    monto = float(request.form["monto"])
    cuotas = int(request.form["cuotas"])

    # Calcular valores
    cuota_social, medico, farmacia, membresia = calcular_membresia(entidad, reparticion, float(monto))
    valor_cuota = calcular_cuota(monto, cuotas)

    # 🔥 FIX VISUAL + LOGICA
    if entidad == "aamas" and monto <= 400000:
        farmacia = 0

    cuota_total = calcular_total(
        entidad, reparticion, monto, valor_cuota,
        cuota_social, medico, farmacia, membresia
        
    )

    link = links_datero.get((entidad, reparticion), "#")
    link_formulario = f"https://sistema-consultas-8hfc.onrender.com/formulario?ent={entidad}&rep={reparticion}&monto={monto}&cuotas={cuotas}"


    return render_template(
        "resultado.html",
        entidad=entidad,
        reparticion=reparticion,
        monto=formatear(monto),
        cuotas=cuotas,
        valor_cuota=formatear(valor_cuota),
        cuota_social=formatear(cuota_social),
        medico=formatear(medico),
        farmacia=formatear(farmacia),
        membresia=formatear(membresia),
        cuota_total=cuota_total,
        link=link,
        link_formulario=link_formulario
    )


@app.route("/formulario")
def formulario():
    entidad = request.args.get("ent")
    reparticion = request.args.get("rep")
    monto = request.args.get("monto")
    cuotas = request.args.get("cuotas")

    return render_template(
        "formulario.html",
        entidad=entidad,
        reparticion=reparticion,
        monto=monto,
        cuotas=cuotas
    )

    return render_template("formulario.html", entidad=entidad, reparticion=reparticion)

@app.route("/identidad", methods=["POST"])
def identidad():
    datos = request.form.to_dict()
    return render_template("identidad.html", **datos)

@app.route("/guardar_formulario", methods=["POST"])
def guardar_formulario():

    # ---------------- DATOS ----------------
    entidad = request.form["entidad"]
    reparticion = request.form["reparticion"].upper()
    
    monto = float(request.form["monto"])
    cuotas = int(request.form["cuotas"])

    valor_cuota = calcular_cuota(monto, cuotas)

    # 🔥 AGREGADO (CLAVE)
    cuota_social, medico, farmacia, membresia = calcular_membresia(entidad, reparticion.lower(), monto)

    if entidad == "aamas" and monto <= 400000:
        farmacia = 0

    nombre = request.form["nombre"].upper()
    dni = request.form["dni"].upper()
    cuit = request.form["cuit"].upper()
    telefono = request.form.get("telefono", "").upper()
    fecha = request.form["fecha_nacimiento"].upper()
    nacionalidad = request.form["nacionalidad"].upper()
    provincia = request.form["provincia"].upper()
    localidad = request.form["localidad"].upper()
    domicilio = request.form["domicilio"].upper()
    email = request.form["email"].upper()
    cbu = request.form["cbu"].upper()
    dni_frente = request.files["dni_frente"]
    dni_dorso = request.files["dni_dorso"]
    selfie = request.files["selfie"]

    import os
    import time

    os.makedirs("static/fotos", exist_ok=True)

    timestamp = int(time.time())

    ruta_frente = f"static/fotos/frente_{timestamp}.jpg"
    ruta_dorso = f"static/fotos/dorso_{timestamp}.jpg"
    ruta_selfie = f"static/fotos/selfie_{timestamp}.jpg"

    dni_frente.save(ruta_frente)
    dni_dorso.save(ruta_dorso)
    selfie.save(ruta_selfie)

    corregir_orientacion(ruta_frente)
    corregir_orientacion(ruta_dorso)
    corregir_orientacion(ruta_selfie)



    ref1_nombre = request.form["ref1_nombre"].upper()
    ref1_tel = request.form["ref1_tel"].upper()
    ref1_relacion = request.form["ref1_relacion"].upper()

    ref2_nombre = request.form["ref2_nombre"].upper()
    ref2_tel = request.form["ref2_tel"].upper()
    ref2_relacion = request.form["ref2_relacion"].upper()
    

    # ---------------- PDF ----------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=15)


    styles = getSampleStyleSheet()
    elements = []

    # 🎨 COLOR SEGÚN ENTIDAD
    if entidad == "aamas":
        color_header = colors.HexColor("#0A3D91")
    else:
        color_header = colors.HexColor("#000000")

    # 🧱 HEADER
    header = Table([[f"DATERO ONLINE - {entidad.upper()}"]], colWidths=[500])
    header.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,-1), color_header),
    ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
    ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ("FONTSIZE", (0,0), (-1,-1), 16),
    ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ("TOPPADDING", (0,0), (-1,-1), 12),
]))
    elements.append(header)
    elements.append(Spacer(1, 10))

    # 🔹 ESTILO TABLAS
    estilo_tabla = TableStyle([
    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
    ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F2F2F2")),
    ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
    ("FONTSIZE", (0,0), (-1,-1), 8),
    ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
])

    # 🔹 TITULOS SECCIONES
    def titulo_seccion(texto):
        elements.append(Paragraph(f"<b>{texto}</b>", styles["Heading3"]))
        elements.append(Spacer(1, 10))

    # ---------------- DATOS PERSONALES ----------------
    titulo_seccion("DATOS PERSONALES")

    data_personal = [
        ["Apellido y Nombre", nombre],
        ["DNI", dni],
        ["CUIT", cuit],
        ["Teléfono", telefono],
        ["Fecha Nacimiento", fecha],
        ["Nacionalidad", nacionalidad],
        ["Provincia", provincia],
        ["Localidad", localidad],
        ["Domicilio", domicilio],
        ["Email", email],
        ["CBU", cbu],
        ["Repartición", reparticion],
]

    tabla1 = Table(data_personal, colWidths=[180, 300])
    tabla1.setStyle(estilo_tabla)
    elements.append(tabla1)
    elements.append(Spacer(1, 10))

    # ---------------- DATOS DEL PRÉSTAMO ----------------
    titulo_seccion("DATOS DEL PRÉSTAMO")

    data_prestamo = [
        ["Monto", formatear_moneda(monto)],
        ["Cantidad de cuotas", cuotas],
        ["Valor de cuota", formatear_moneda(valor_cuota)],
]

    tabla2 = Table(data_prestamo, colWidths=[180, 300])
    tabla2.setStyle(estilo_tabla)
    elements.append(tabla2)
    elements.append(Spacer(1, 10))

    # ---------------- SERVICIOS ----------------
    titulo_seccion("SERVICIOS")

    data_servicios = [
        ["Cuota Social", formatear_moneda(cuota_social)],
        ["Coseguro Médico", formatear_moneda(medico)],
        ["Coseguro Farmacia", formatear_moneda(farmacia)],
        ["Membresía", formatear_moneda(membresia)],
]

    tabla3 = Table(data_servicios, colWidths=[180, 300])
    tabla3.setStyle(estilo_tabla)
    elements.append(tabla3)
    elements.append(Spacer(1, 10))

    # ---------------- REFERENCIAS ----------------
    titulo_seccion("REFERENCIAS")

    data_refs = [
        ["Nombre", "Teléfono", "Relación"],
        [ref1_nombre, ref1_tel, ref1_relacion],
        [ref2_nombre, ref2_tel, ref2_relacion],
]

    tabla4 = Table(
    data_refs,
    colWidths=[170, 120, 110],
    rowHeights=14  # 🔥 ESTO ES CLAVE
    )

    tabla4.setStyle(TableStyle([
    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAEAEA")),
    ("ALIGN", (0,0), (-1,-1), "CENTER"),

    # 🔥 ACHICAR TEXTO
    ("FONTSIZE", (0,0), (-1,-1), 7),
    ("FONTNAME", (0,0), (-1,-1), "Helvetica"),

    # 🔥 ACHICAR ESPACIOS INTERNOS
    ("TOPPADDING", (0,0), (-1,-1), 2),
    ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ("LEFTPADDING", (0,0), (-1,-1), 4),
    ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    elements.append(tabla4)


    return render_template(
    "firma.html",
    entidad=entidad,
    reparticion=reparticion,
    monto=monto,
    monto_fmt=formatear_moneda(monto),
    cuotas=cuotas,
    valor_cuota=valor_cuota,
    valor_cuota_fmt=formatear_moneda(valor_cuota),
    cuota_social=cuota_social,
    cuota_social_fmt=formatear_moneda(cuota_social),
    medico=medico,
    medico_fmt=formatear_moneda(medico),
    farmacia=farmacia,
    farmacia_fmt=formatear_moneda(farmacia),
    membresia=membresia,
    membresia_fmt=formatear_moneda(membresia),

    # 🔥 DATOS PERSONALES
    nombre=nombre,
    dni=dni,
    cuit=cuit,
    telefono=telefono,
    fecha=fecha,
    nacionalidad=nacionalidad,
    provincia=provincia,
    localidad=localidad,
    domicilio=domicilio,
    email=email,
    cbu=cbu,
    ruta_frente=ruta_frente,
    ruta_dorso=ruta_dorso,
    ruta_selfie=ruta_selfie,

    # 🔥 REFERENCIAS
    ref1_nombre=ref1_nombre,
    ref1_tel=ref1_tel,
    ref1_relacion=ref1_relacion,
    ref2_nombre=ref2_nombre,
    ref2_tel=ref2_tel,
    ref2_relacion=ref2_relacion,
)

@app.route("/generar_pdf_final", methods=["POST"])
def generar_pdf_final():

    entidad = request.form["entidad"]
    reparticion = request.form["reparticion"]

    monto = float(request.form["monto"])
    cuotas = int(request.form["cuotas"])
    valor_cuota = float(request.form["valor_cuota"])

    ruta_frente = request.form["ruta_frente"]
    ruta_dorso = request.form["ruta_dorso"]
    ruta_selfie = request.form["ruta_selfie"]

    cuota_social = float(request.form["cuota_social"])
    medico = float(request.form["medico"])
    farmacia = float(request.form["farmacia"])
    membresia = float(request.form["membresia"])

    nombre = request.form.get("nombre", "")
    dni = request.form.get("dni", "")
    cuit = request.form.get("cuit", "")
    telefono = request.form.get("telefono", "")
    fecha = request.form.get("fecha_nacimiento", "")
    nacionalidad = request.form.get("nacionalidad", "")
    provincia = request.form.get("provincia", "")
    localidad = request.form.get("localidad", "")
    domicilio = request.form.get("domicilio", "")
    email = request.form.get("email", "")
    cbu = request.form.get("cbu", "")

    ref1_nombre = request.form.get("ref1_nombre", "")
    ref1_tel = request.form.get("ref1_tel", "")
    ref1_relacion = request.form.get("ref1_relacion", "")

    ref2_nombre = request.form.get("ref2_nombre", "")
    ref2_tel = request.form.get("ref2_tel", "")
    ref2_relacion = request.form.get("ref2_relacion", "")

    firma = request.form["firma"]

    import base64, io
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER

    # 🔥 convertir firma
    firma_data = firma.split(",")[1]
    firma_bytes = base64.b64decode(firma_data)
    firma_buffer = io.BytesIO(firma_bytes)

    # ---------------- PDF ----------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=20)

    styles = getSampleStyleSheet()
    elements = []

    # 🎨 COLOR SEGÚN ENTIDAD
    if entidad == "aamas":
        color_header = colors.HexColor("#0A3D91")
    else:
        color_header = colors.HexColor("#000000")

    # 🧱 HEADER
    header = Table([[f"DATERO ONLINE - {entidad.upper()}"]], colWidths=[500])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), color_header),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING", (0,0), (-1,-1), 12),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 10))

    # 🔹 ESTILO TABLAS
    estilo_tabla = TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F2F2F2")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ])

    def titulo_seccion(texto):
        elements.append(Paragraph(f"<b>{texto}</b>", styles["Heading3"]))
        elements.append(Spacer(1, 10))

    # ---------------- DATOS PERSONALES ----------------
    titulo_seccion("DATOS PERSONALES")

    data_personal = [
        ["Apellido y Nombre", nombre],
        ["DNI", dni],
        ["CUIT", cuit],
        ["Teléfono", telefono],
        ["Fecha Nacimiento", fecha],
        ["Nacionalidad", nacionalidad],
        ["Provincia", provincia],
        ["Localidad", localidad],
        ["Domicilio", domicilio],
        ["Email", email],
        ["CBU", cbu],
        ["Repartición", reparticion],
    ]

    tabla1 = Table(data_personal, colWidths=[180, 300])
    tabla1.setStyle(estilo_tabla)
    elements.append(tabla1)
    elements.append(Spacer(1, 10))

    # ---------------- DATOS DEL PRÉSTAMO ----------------
    titulo_seccion("DATOS DEL PRÉSTAMO")

    data_prestamo = [
        ["Monto", formatear_moneda(monto)],
        ["Cantidad de cuotas", cuotas],
        ["Valor de cuota", formatear_moneda(valor_cuota)],
    ]

    tabla2 = Table(data_prestamo, colWidths=[180, 300])
    tabla2.setStyle(estilo_tabla)
    elements.append(tabla2)
    elements.append(Spacer(1, 10))

    # ---------------- SERVICIOS ----------------
    titulo_seccion("SERVICIOS")

    data_servicios = [
        ["Cuota Social", formatear_moneda(cuota_social)],
        ["Coseguro Médico", formatear_moneda(medico)],
        ["Coseguro Farmacia", formatear_moneda(farmacia)],
        ["Membresía", formatear_moneda(membresia)],
    ]

    tabla3 = Table(data_servicios, colWidths=[180, 300])
    tabla3.setStyle(estilo_tabla)
    elements.append(tabla3)
    elements.append(Spacer(1, 10))

    # ---------------- REFERENCIAS ----------------
    titulo_seccion("REFERENCIAS")

    data_refs = [
        ["Nombre", "Teléfono", "Relación"],
        [ref1_nombre, ref1_tel, ref1_relacion],
        [ref2_nombre, ref2_tel, ref2_relacion],
    ]

    tabla4 = Table(data_refs, colWidths=[180, 140, 130], rowHeights=18)
    tabla4.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAEAEA")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))

    elements.append(tabla4)
    elements.append(Spacer(1, 10))

    # ---------------- FIRMA PRO (CORREGIDA) ----------------
    elements.append(Spacer(1, 15))

    img = Image(firma_buffer, width=120, height=50)
    img.hAlign = 'CENTER'
    elements.append(img)

    elements.append(Spacer(1, 5))

    linea = Table([[""]], colWidths=[200])
    linea.setStyle(TableStyle([
        ("LINEABOVE", (0,0), (-1,-1), 1, colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER")
    ]))
    elements.append(linea)

    elements.append(Spacer(1, 5))

    style_centro = styles["Normal"]
    style_centro.alignment = TA_CENTER

    elements.append(Paragraph(f"<b>{nombre}</b>", style_centro))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph("FIRMA DEL CLIENTE", style_centro))

    # 🔥 ------------------------------------
    # 🔥 NUEVA HOJA CON DOCUMENTACIÓN
    # 🔥 ------------------------------------

    from reportlab.platypus import PageBreak

    elements.append(PageBreak())

    elements.append(Paragraph("DOCUMENTACIÓN DEL CLIENTE", styles["Title"]))
    elements.append(Spacer(1, 10))

    # DNI FRENTE
    elements.append(Paragraph("DNI FRENTE", styles["Heading3"]))
    elements.append(Spacer(1, 10))
    elements.append(Image(ruta_frente, width=220, height=140))
    elements.append(Spacer(1, 10))

    # DNI DORSO
    elements.append(Paragraph("DNI DORSO", styles["Heading3"]))
    elements.append(Spacer(1, 10))
    elements.append(Image(ruta_dorso, width=220, height=140))
    elements.append(Spacer(1, 10))

    # SELFIE
    elements.append(Paragraph("SELFIE CON DNI", styles["Heading3"]))
    elements.append(Spacer(1, 10))
    elements.append(Image(ruta_selfie, width=220, height=140))
    elements.append(Spacer(1, 15))

    # 🔥 FIRMA FINAL (segunda hoja)
    elements.append(Paragraph("FIRMA DEL CLIENTE", styles["Heading3"]))
    elements.append(Spacer(1, 10))

    img = Image(firma_buffer, width=120, height=50)
    img.hAlign = 'CENTER'
    elements.append(img)

    elements.append(Spacer(1, 5))

    linea = Table([[""]], colWidths=[200])
    linea.setStyle(TableStyle([
    ("LINEABOVE", (0,0), (-1,-1), 1, colors.black),
    ("ALIGN", (0,0), (-1,-1), "CENTER")
]))
    elements.append(linea)

    elements.append(Spacer(1, 5))

    style_centro = styles["Normal"]
    style_centro.alignment = TA_CENTER

    elements.append(Paragraph(f"<b>{nombre}</b>", style_centro))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph("FIRMA DEL CLIENTE", style_centro))

    # 🔹 FINAL
    doc.build(elements)
    buffer.seek(0)

    import time
    import os

    filename = f"datero_{int(time.time())}.pdf"

    os.makedirs("static", exist_ok=True)

    filepath = f"static/{filename}"

    with open(filepath, "wb") as f:
        f.write(buffer.getvalue())

    return render_template("descargar.html", archivo=filename)

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run()