import os
import csv
import traci
import sumolib

# Carpeta donde está este archivo
carpeta = os.path.dirname(os.path.abspath(__file__))
configuracion = os.path.join(carpeta, "osm.sumocfg")

sumo = sumolib.checkBinary("sumo")
paso = 0.1

# Resultados de esta prueba
archivo_csv = os.path.join(carpeta, "metricas_fijas.csv")

traci.start([
    sumo,
    "-c", configuracion,
    "--seed", "42",
    "--no-step-log", "true"
])

espera_total = 0
vehiculos_detenidos_total = 0
pasos = 0

try:
    with open(archivo_csv, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)

        escritor.writerow([
            "tiempo_s",
            "vehiculos_activos",
            "vehiculos_detenidos",
            "espera_acumulada_s",
            "vehiculos_llegados"
        ])

        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()

            vehiculos = traci.vehicle.getIDList()
            detenidos = 0

            for vehiculo in vehiculos:
                velocidad = traci.vehicle.getSpeed(vehiculo)

                if velocidad < 0.1:
                    detenidos += 1

            espera_total += detenidos * paso
            vehiculos_detenidos_total += detenidos
            pasos += 1

            escritor.writerow([
                traci.simulation.getTime(),
                len(vehiculos),
                detenidos,
                espera_total,
                traci.simulation.getArrivedNumber()
            ])

finally:
    traci.close()

llegados = traci.simulation.getArrivedNumber() if False else 0

print("\nSimulación finalizada.")
print(f"Espera acumulada: {espera_total:.2f} segundos")
print(f"Vehículos-detenidos acumulados: {vehiculos_detenidos_total}")
print(f"Datos guardados en: {archivo_csv}")