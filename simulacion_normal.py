import os
import subprocess
import xml.etree.ElementTree as ET
import sumolib


# ==========================================
# CONFIGURACIÓN
# ==========================================

CONFIG = "sumo_bogota/osm.sumocfg"

DURACION = 4556
SEMILLA = 42
ESCALA_TRAFICO = "2"

SUMO_GUI = sumolib.checkBinary("sumo-gui")

ARCHIVO_VEHICULOS = "resultados_normal.xml"
ARCHIVO_RESUMEN = "resumen_normal.xml"


# ==========================================
# LIMPIAR RESULTADOS ANTERIORES
# ==========================================

def limpiar_archivos():

    for archivo in [ARCHIVO_VEHICULOS, ARCHIVO_RESUMEN]:

        if os.path.exists(archivo):
            os.remove(archivo)


# ==========================================
# ANALIZAR RESULTADOS DE VEHÍCULOS
# ==========================================

def analizar_vehiculos():

    if not os.path.exists(ARCHIVO_VEHICULOS):
        print("No se encontró el archivo de resultados de vehículos.")
        return

    arbol = ET.parse(ARCHIVO_VEHICULOS)
    raiz = arbol.getroot()

    vehiculos = raiz.findall("tripinfo")

    if not vehiculos:
        print("No hay vehículos que hayan completado su recorrido.")
        return

    cantidad = len(vehiculos)

    tiempo_espera = sum(
        float(v.get("waitingTime", 0))
        for v in vehiculos
    )

    duracion_total = sum(
        float(v.get("duration", 0))
        for v in vehiculos
    )

    tiempo_perdido = sum(
        float(v.get("timeLoss", 0))
        for v in vehiculos
    )

    distancia_total = sum(
        float(v.get("routeLength", 0))
        for v in vehiculos
    )

    espera_promedio = tiempo_espera / cantidad
    duracion_promedio = duracion_total / cantidad
    perdida_promedio = tiempo_perdido / cantidad

    velocidad_promedio = (
        distancia_total / duracion_total
        if duracion_total > 0
        else 0
    )

    print("\n" + "=" * 50)
    print("RESULTADOS DE TRÁFICO - SIMULACIÓN NORMAL")
    print("=" * 50)

    print(f"Vehículos que completaron su recorrido: {cantidad}")
    print(f"Tiempo promedio de espera: {espera_promedio:.2f} s")
    print(f"Duración promedio del recorrido: {duracion_promedio:.2f} s")
    print(f"Tiempo perdido promedio: {perdida_promedio:.2f} s")
    print(f"Velocidad promedio estimada: {velocidad_promedio:.2f} m/s")
    print(f"Distancia total recorrida: {distancia_total:.2f} m")


# ==========================================
# ANALIZAR RESUMEN DE SUMO
# ==========================================

def analizar_resumen():

    if not os.path.exists(ARCHIVO_RESUMEN):
        print("\nNo se encontró el resumen de SUMO.")
        return

    arbol = ET.parse(ARCHIVO_RESUMEN)
    raiz = arbol.getroot()

    pasos = raiz.findall("step")

    if not pasos:
        print("\nEl resumen no contiene pasos de simulación.")
        return

    ultimo = pasos[-1]

    print("\nESTADÍSTICAS GENERALES DE SUMO")

    for atributo in [
        "time",
        "loaded",
        "inserted",
        "running",
        "waiting",
        "ended",
        "arrived",
        "collisions",
        "teleports"
    ]:

        valor = ultimo.get(atributo)

        if valor is not None:
            print(f"{atributo}: {valor}")


# ==========================================
# EJECUTAR SIMULACIÓN ORIGINAL
# ==========================================

def ejecutar_simulacion():

    print("=" * 50)
    print("SIMULACIÓN NORMAL - SUMO ORIGINAL")
    print("=" * 50)

    limpiar_archivos()

    comando = [
        SUMO_GUI,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(SEMILLA),
        "--scale", ESCALA_TRAFICO,
        "--tripinfo-output", ARCHIVO_VEHICULOS,
        "--summary-output", ARCHIVO_RESUMEN,
        "--start",
        "--delay", "50"
    ]

    print("Abriendo SUMO-GUI...")
    print("Controlador original de los semáforos.")
    print(f"Semilla: {SEMILLA}")
    print(f"Escala de tráfico: {ESCALA_TRAFICO}")

    resultado = subprocess.run(comando)

    print("\nSimulación normal finalizada.")
    print(f"Código de salida: {resultado.returncode}")

    if resultado.returncode == 0:

        analizar_vehiculos()
        analizar_resumen()

    else:

        print("La simulación terminó con un error.")
        print("Revisa los mensajes de SUMO.")


# ==========================================
# EJECUTAR
# ==========================================

if __name__ == "__main__":

    ejecutar_simulacion()

