import os
import traci
import sumolib

# Ubicación de la configuración de SUMO
carpeta = os.path.dirname(os.path.abspath(__file__))
configuracion = os.path.join(carpeta, "osm.sumocfg")

# Seleccionar SUMO sin interfaz gráfica para esta prueba
sumo = sumolib.checkBinary("sumo")

# Iniciar la simulación y conectar Python mediante TraCI
traci.start([
    sumo,
    "-c", configuracion,
    "--no-step-log", "true"
])

try:
    # Consultar los semáforos de la red
    semaforos = traci.trafficlight.getIDList()

    print("\nSemáforos detectados:")
    for semaforo in semaforos:
        print("ID:", semaforo)

    # Avanzar la simulación
    for _ in range(10):
        traci.simulationStep()

    print("\nPython se comunicó correctamente con SUMO.")

finally:
    traci.close()