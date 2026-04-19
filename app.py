from flask import Flask, render_template, request
import pandas as pd

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

    # ---------------- AAMAS ----------------
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

    # ---------------- QUANTUM ----------------
    elif entidad == "quantum":

        cuota_social = 9594
        medico = 8172
        farmacia = 7343
        membresia = 6000

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
        link=link
    )


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)