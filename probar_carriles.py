
import os
import traci
import sumolib

CONFIG = os.path.join("sumo_bogota", "osm.sumocfg")

SUMO = sumolib.checkBinary("sumo")

# Carriles de entrada de cada semáforo.
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

traci.start([
    SUMO,
    "-c", CONFIG,
    "--seed", "42",
    "--scale", "2"
])

try:
    carriles_existentes = set(traci.lane.getIDList())

    print("\nVERIFICACIÓN DE CARRILES")
    print("=" * 55)

    for tls_id, grupos in SEMAFOROS.items():
        print(f"\nSEMÁFORO: {tls_id}")

        for grupo, carriles in grupos.items():
            for carril in carriles:
                estado = (
                    "OK" if carril in carriles_existentes
                    else "NO ENCONTRADO"
                )
                print(f"Grupo {grupo}: {carril} -> {estado}")

    print("\nINICIANDO MEDICIÓN DE TRÁFICO...")
    print("=" * 55)

    # Simular 300 segundos.
    for segundo in range(300):
        traci.simulationStep()

        if (segundo + 1) % 50 == 0:
            print(f"\nTIEMPO: {segundo + 1} segundos")

            for tls_id, grupos in SEMAFOROS.items():

                colas = {}

                for grupo, carriles in grupos.items():
                    colas[grupo] = sum(
                        traci.lane.getLastStepHaltingNumber(carril)
                        for carril in carriles
                        if carril in carriles_existentes
                    )

                print(
                    f"{tls_id} | "
                    f"Cola A: {colas['A']} | "
                    f"Cola B: {colas['B']}"
                )

finally:
    traci.close()

print("\nPRUEBA TERMINADA.")
