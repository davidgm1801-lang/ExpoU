import traci
import sumolib
import os

config = os.path.join("sumo_bogota", "osm.sumocfg")

sumo_binary = sumolib.checkBinary("sumo")

traci.start([
    sumo_binary,
    "-c", config,
    "--start"
])

for tls_id in traci.trafficlight.getIDList():
    print("\nSEMÁFORO:", tls_id)

    logica = traci.trafficlight.getAllProgramLogics(tls_id)

    for programa in logica:
        print("Programa:", programa.programID)

        for i, fase in enumerate(programa.phases):
            print(
                "Fase:", i,
                "| Duración:", fase.duration,
                "| Estado:", fase.state
            )

traci.close()