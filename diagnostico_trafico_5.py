import os
import sys
import csv
import traci
import sumolib

# ============================================================
# CONFIGURACIÓN
# ============================================================

CONFIG = os.path.join("sumo_bogota", "osm.sumocfg")

DURACION = 4556
SEMILLA = 42
ESCALA_TRAFICO = "2"

ARCHIVO_CSV = "diagnostico_trafico_5.csv"

PASO_SIMULACION = 1

SEMAFOROS = {
    "262567760": {
        "A": ["1083001223#0_0", "1083001223#0_1"],
        "B": ["862794316#0_0", "862794316#0_1"]
    },
    "262567775": {
        "A": ["88757025#0_0", "88757025#0_1"],
        "B": ["1083001225#0_1", "1083001225#0_2"]
    },
    "262567777": {
        "A": ["1060493360#3_1", "1060493360#3_2"],
        "B": ["908369205#0_0", "908369205#0_1"]
    },
    "264377450": {
        "A": ["1083001233_0", "1083001233_1"],
        "B": ["1056806207#0_0", "1056806207#0_1"]
    },
    "265804326": {
        "A": ["88877450#2_0", "88877450#2_1"],
        "B": ["1083001234#0_0", "1083001234#0_1"]
    }
}


# ============================================================
# VALIDACIÓN DE LA RED
# ============================================================

def validar_red():
    print("\nVALIDANDO SEMÁFOROS Y CARRILES...\n")

    tls_disponibles = set(traci.trafficlight.getIDList())
    carriles_disponibles = set(traci.lane.getIDList())

    errores = []

    for tls_id, grupos in SEMAFOROS.items():

        if tls_id not in tls_disponibles:
            errores.append(f"Semáforo inexistente: {tls_id}")
            continue

        print(f"Semáforo {tls_id}: OK")

        for grupo, carriles in grupos.items():

            for carril in carriles:

                if carril not in carriles_disponibles:
                    errores.append(
                        f"Carril inexistente: {carril} ({tls_id}, grupo {grupo})"
                    )
                else:
                    print(f"  Grupo {grupo}: {carril} OK")

    if errores:
        print("\nSE ENCONTRARON ERRORES:")

        for error in errores:
            print(" -", error)

        return False

    print("\nTodos los elementos configurados existen.")
    return True


# ============================================================
# MEDICIÓN DE TRÁFICO
# ============================================================

def medir_grupo(carriles):

    cola = 0
    vehiculos = 0
    detenidos = 0
    velocidad_total = 0

    vehiculos_unicos = set()

    for carril in carriles:

        cola += traci.lane.getLastStepHaltingNumber(carril)

        vehiculos_carril = traci.lane.getLastStepVehicleIDs(carril)

        vehiculos += len(vehiculos_carril)

        for vehiculo_id in vehiculos_carril:

            vehiculos_unicos.add(vehiculo_id)

            velocidad = traci.vehicle.getSpeed(vehiculo_id)

            velocidad_total += velocidad

            if velocidad < 0.1:
                detenidos += 1

    if vehiculos > 0:
        velocidad_media = velocidad_total / vehiculos
    else:
        velocidad_media = 0

    return {
        "cola": cola,
        "vehiculos": vehiculos,
        "detenidos": detenidos,
        "velocidad_media": velocidad_media,
        "ids": vehiculos_unicos
    }


# ============================================================
# EJECUCIÓN DEL DIAGNÓSTICO
# ============================================================

def main():

    SUMO = sumolib.checkBinary("sumo")

    comando = [
        SUMO,
        "-c", CONFIG,
        "--seed", str(SEMILLA),
        "--scale", ESCALA_TRAFICO,
        "--no-step-log", "true",
        "--duration-log.disable", "true"
    ]

    print("\nINICIANDO DIAGNÓSTICO DE LOS CINCO SEMÁFOROS")
    print("=" * 60)

    traci.start(comando)

    try:

        if not validar_red():
            return

        resultados = {}

        for tls_id in SEMAFOROS:

            resultados[tls_id] = {
                "A": {
                    "cola_total": 0,
                    "cola_maxima": 0,
                    "vehiculos_total": 0,
                    "detenidos_total": 0,
                    "vehiculo_segundos": 0,
                    "detenido_segundos": 0,
                    "velocidad_total": 0,
                    "mediciones": 0,
                    "vehiculos_unicos": set(),
                    "salidas_observadas": 0
                },
                "B": {
                    "cola_total": 0,
                    "cola_maxima": 0,
                    "vehiculos_total": 0,
                    "detenidos_total": 0,
                    "vehiculo_segundos": 0,
                    "detenido_segundos": 0,
                    "velocidad_total": 0,
                    "mediciones": 0,
                    "vehiculos_unicos": set(),
                    "salidas_observadas": 0
                }
            }

        tiempo = 0

        while tiempo < DURACION and traci.simulation.getMinExpectedNumber() > 0:

            traci.simulationStep()

            tiempo += PASO_SIMULACION

            for tls_id, grupos in SEMAFOROS.items():

                for grupo, carriles in grupos.items():

                    medicion = medir_grupo(carriles)

                    datos = resultados[tls_id][grupo]

                    cola = medicion["cola"]
                    vehiculos = medicion["vehiculos"]
                    detenidos = medicion["detenidos"]

                    datos["cola_total"] += cola
                    datos["cola_maxima"] = max(
                        datos["cola_maxima"], cola
                    )

                    datos["vehiculos_total"] += vehiculos
                    datos["detenidos_total"] += detenidos

                    datos["vehiculo_segundos"] += vehiculos * PASO_SIMULACION
                    datos["detenido_segundos"] += detenidos * PASO_SIMULACION

                    datos["velocidad_total"] += (
                        medicion["velocidad_media"] * vehiculos
                    )

                    datos["mediciones"] += 1

                    datos["vehiculos_unicos"].update(
                        medicion["ids"]
                    )

            if tiempo % 500 == 0:
                print(f"Tiempo simulado: {tiempo}/{DURACION} segundos")

        # ====================================================
        # GUARDAR RESULTADOS
        # ====================================================

        with open(
            ARCHIVO_CSV,
            "w",
            newline="",
            encoding="utf-8"
        ) as archivo:

            campos = [
                "semaforo",
                "grupo",
                "cola_promedio",
                "cola_maxima",
                "vehiculos_promedio",
                "detenidos_promedio",
                "velocidad_media",
                "vehiculo_segundos",
                "detenido_segundos",
                "vehiculos_unicos"
            ]

            escritor = csv.DictWriter(
                archivo,
                fieldnames=campos
            )

            escritor.writeheader()

            for tls_id, grupos in resultados.items():

                for grupo, datos in grupos.items():

                    mediciones = datos["mediciones"]

                    if mediciones == 0:
                        continue

                    escritor.writerow({
                        "semaforo": tls_id,
                        "grupo": grupo,
                        "cola_promedio": round(
                            datos["cola_total"] / mediciones, 3
                        ),
                        "cola_maxima": datos["cola_maxima"],
                        "vehiculos_promedio": round(
                            datos["vehiculos_total"] / mediciones, 3
                        ),
                        "detenidos_promedio": round(
                            datos["detenidos_total"] / mediciones, 3
                        ),
                        "velocidad_media": round(
                            datos["velocidad_total"] /
                            max(datos["vehiculos_total"], 1), 3
                        ),
                        "vehiculo_segundos": datos["vehiculo_segundos"],
                        "detenido_segundos": datos["detenido_segundos"],
                        "vehiculos_unicos": len(
                            datos["vehiculos_unicos"]
                        )
                    })

        # ====================================================
        # RESUMEN EN CONSOLA
        # ====================================================

        print("\n" + "=" * 60)
        print("RESULTADOS DEL DIAGNÓSTICO")
        print("=" * 60)

        for tls_id, grupos in resultados.items():

            print(f"\nSEMÁFORO: {tls_id}")

            for grupo, datos in grupos.items():

                mediciones = datos["mediciones"]

                if mediciones == 0:
                    continue

                print(f"\n  Grupo {grupo}")
                print(
                    "    Cola promedio:",
                    round(datos["cola_total"] / mediciones, 3)
                )
                print(
                    "    Cola máxima:",
                    datos["cola_maxima"]
                )
                print(
                    "    Vehículos promedio:",
                    round(datos["vehiculos_total"] / mediciones, 3)
                )
                print(
                    "    Vehículos detenidos promedio:",
                    round(datos["detenidos_total"] / mediciones, 3)
                )
                print(
                    "    Vehículos únicos observados:",
                    len(datos["vehiculos_unicos"])
                )
                print(
                    "    Vehículo-segundos:",
                    datos["vehiculo_segundos"]
                )
                print(
                    "    Segundos de vehículo detenido:",
                    datos["detenido_segundos"]
                )

        print("\n" + "=" * 60)
        print("DIAGNÓSTICO FINALIZADO")
        print(f"Archivo generado: {ARCHIVO_CSV}")
        print("=" * 60)

    finally:
        traci.close()


if __name__ == "__main__":
    main()
