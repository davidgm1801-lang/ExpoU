
import os
import traci
import sumolib

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

CONFIG = os.path.join("sumo_bogota", "osm.sumocfg")

SEMAFOROS = [
    "262567760",
    "262567775",
    "262567777",
    "264377450",
    "265804326"
]

SUMO = sumolib.checkBinary("sumo")

# --------------------------------------------------
# INICIAR SUMO
# --------------------------------------------------

traci.start([
    SUMO,
    "-c", CONFIG
])

try:
    print("\n" + "=" * 65)
    print("INSPECCIÓN DE LOS CINCO SEMÁFOROS")
    print("=" * 65)

    semaforos_disponibles = traci.trafficlight.getIDList()

    for tls_id in SEMAFOROS:

        print("\n\n" + "#" * 65)
        print("SEMÁFORO:", tls_id)
        print("#" * 65)

        if tls_id not in semaforos_disponibles:
            print("ERROR: Semáforo no encontrado.")
            continue

        # Obtener las conexiones controladas
        conexiones = traci.trafficlight.getControlledLinks(tls_id)

        print("\nCONEXIONES POR ÍNDICE DE SEÑAL:")

        for indice, grupo in enumerate(conexiones):

            print(f"\nÍndice de señal {indice}:")

            if not grupo:
                print("  Sin conexiones.")
                continue

            for conexion in grupo:
                entrada, salida, via = conexion

                print("  Carril de entrada:", entrada)
                print("  Carril de salida:", salida)
                print("  Carril de conexión:", via)

        # Obtener los programas y fases
        programas = traci.trafficlight.getAllProgramLogics(tls_id)

        print("\nPROGRAMAS Y FASES:")

        for programa in programas:

            print("\nPrograma:", programa.programID)

            for i, fase in enumerate(programa.phases):
                print(
                    f"  Fase {i}: "
                    f"duración={fase.duration}, "
                    f"estado={fase.state}"
                )

finally:
    traci.close()

print("\nINSPECCIÓN TERMINADA.")
