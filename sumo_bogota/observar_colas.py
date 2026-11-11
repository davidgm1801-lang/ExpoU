import traci
import sumolib
import csv

CONFIG = "osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

TLS_ID = "262567760"
DURACION = 4556  # 10 minutos simulados

CARRILES = [
    "1083001223#0_0",
    "1083001223#0_1",
    "862794316#0_0",
    "862794316#0_1"
]

conectado = False

try:
    traci.start([
        SUMO,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--no-step-log", "true"
    ])

    conectado = True

    acumulados = {carril: 0 for carril in CARRILES}
    maximos = {carril: 0 for carril in CARRILES}
    muestras = 0

    with open(
        "observaciones_semaforo.csv",
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as archivo:

        escritor = csv.writer(archivo)

        escritor.writerow([
            "tiempo_s",
            "fase",
            "vehiculos_detenidos_A",
            "vehiculos_detenidos_B",
            "vehiculos_totales"
        ])

        while traci.simulation.getTime() < DURACION:

            traci.simulationStep()

            fase = traci.trafficlight.getPhase(TLS_ID)

            colas = {}

            for carril in CARRILES:
                colas[carril] = (
                    traci.lane.getLastStepHaltingNumber(carril)
                )

            cola_A = (
                colas["1083001223#0_0"]
                + colas["1083001223#0_1"]
            )

            cola_B = (
                colas["862794316#0_0"]
                + colas["862794316#0_1"]
            )

            total = cola_A + cola_B

            escritor.writerow([
                traci.simulation.getTime(),
                fase,
                cola_A,
                cola_B,
                total
            ])

            for carril in CARRILES:
                acumulados[carril] += colas[carril]
                maximos[carril] = max(
                    maximos[carril],
                    colas[carril]
                )

            muestras += 1

    print("\n===== RESULTADOS =====")
    print("Tiempo simulado:", DURACION, "segundos")
    print("Muestras:", muestras)

    for carril in CARRILES:
        promedio = acumulados[carril] / muestras

        print("\nCarril:", carril)
        print("Cola promedio:", round(promedio, 2))
        print("Cola máxima:", maximos[carril])

    print("\nArchivo guardado: observaciones_semaforo.csv")

finally:
    if conectado:
        traci.close()