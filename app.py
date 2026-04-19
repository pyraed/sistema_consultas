from flask import Flask, render_template, request
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import io


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
            # 🔥 fallback (clave para que no rompa)
            cuota_social = 0
            medico = 0
            farmacia = 0
            membresia = 0

    # 🔹 QUANTUM
    elif entidad == "quantum":

        cuota_social = 9594
        medico = 8172
        farmacia = 7343
        membresia = 6000

    else:
        # 🔥 fallback general
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
    reparticion = request.form["reparticion"].upper()
    monto = float(request.form["monto"])
    cuotas = int(request.form["cuotas"])

    # Calcular valores
    cuota_social, medico, farmacia, membresia = calcular_membresia(entidad, reparticion, monto)
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

    if link == "#":
        return "No hay datero configurado para esta combinación"


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

@app.route("/guardar_formulario", methods=["POST"])
def guardar_formulario():

    # ---------------- DATOS ----------------
    entidad = request.form["entidad"]
    reparticion = request.form["reparticion"]
    
    monto = float(request.form["monto"])
    cuotas = int(request.form["cuotas"])
    

    # 🔥 CALCULO REAL
    cuota_social, medico, farmacia, membresia = calcular_membresia(entidad, reparticion, monto)
    valor_cuota = calcular_cuota(monto, cuotas)

    # 🔥 LOGICA
    if entidad == "aamas" and monto <= 400000:
        farmacia = 0


    nombre = request.form["nombre"].upper()
    dni = request.form["dni"].upper()
    cuit = request.form["cuit"].upper()
    fecha = request.form["fecha_nacimiento"].upper()
    nacionalidad = request.form["nacionalidad"].upper()
    provincia = request.form["provincia"].upper()
    localidad = request.form["localidad"].upper()
    domicilio = request.form["domicilio"].upper()
    email = request.form["email"].upper()
    cbu = request.form["cbu"].upper()

    ref1_nombre = request.form["ref1_nombre"].upper()
    ref1_tel = request.form["ref1_tel"].upper()
    ref1_relacion = request.form["ref1_relacion"].upper()

    ref2_nombre = request.form["ref2_nombre"].upper()
    ref2_tel = request.form["ref2_tel"].upper()
    ref2_relacion = request.form["ref2_relacion"].upper()

    # ---------------- PDF ----------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()
    elements = []

    # 🔥 TITULO
    titulo = f"Datero Online - {entidad.upper()}"
    elements.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
    elements.append(Spacer(1, 15))

    # 🔹 DATOS PERSONALES
    elements.append(Paragraph("<b>Datos Personales</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))

    data_personal = [
        ["Apellido y Nombre", nombre],
        ["DNI", dni],
        ["CUIT", cuit],
        ["Fecha Nacimiento", fecha],
        ["Nacionalidad", nacionalidad],
        ["Provincia", provincia],
        ["Localidad", localidad],
        ["Domicilio", domicilio],
        ["Email", email],
        ["CBU", cbu],
        ["Repartición", reparticion],
    ]

    table1 = Table(data_personal, colWidths=[180, 300])
    table1.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.lightgrey)
    ]))

    elements.append(table1)
    elements.append(Spacer(1, 20))

    # 🔹 SERVICIOS (NUEVO)
    elements.append(Paragraph("<b>Servicios</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))

    data_servicios = [
        ["Cuota Social", formatear_moneda(cuota_social)],
        ["Coseguro Médico", formatear_moneda(medico)],
        ["Coseguro Farmacia", formatear_moneda(farmacia)],
        ["Membresía", formatear_moneda(membresia)],
]

    tabla_servicios = Table(data_servicios, colWidths=[200, 280])
    tabla_servicios.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.lightgrey)
    ]))

    elements.append(tabla_servicios)
    elements.append(Spacer(1, 20))

    # 🔹 DATOS DEL PRÉSTAMO (NUEVO)
    elements.append(Paragraph("<b>Datos del Préstamo</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))

    data_prestamo = [
        ["Monto", formatear_moneda(monto)],
        ["Cantidad de cuotas", cuotas],
        ["Valor de cuota", formatear_moneda(valor_cuota)],
]

    tabla_prestamo = Table(data_prestamo, colWidths=[200, 280])
    tabla_prestamo.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.lightgrey)
    ]))

    elements.append(tabla_prestamo)
    elements.append(Spacer(1, 20))

    # 🔹 REFERENCIAS
    elements.append(Paragraph("<b>Referencias</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))

    data_refs = [
        ["Nombre", "Teléfono", "Relación"],
        [ref1_nombre, ref1_tel, ref1_relacion],
        [ref2_nombre, ref2_tel, ref2_relacion],
    ]

    table2 = Table(data_refs, colWidths=[200, 150, 130])
    table2.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)
    ]))

    elements.append(table2)

    # Construir PDF
    doc.build(elements)

    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="datero.pdf", mimetype="application/pdf")


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)