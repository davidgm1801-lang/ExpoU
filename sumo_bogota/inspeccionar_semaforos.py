
import traci
import sumolib

CONFIG = "osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

try:
    # Iniciar SUMO
    traci.start([
        SUMO,
        "-c", CONFIG,
        "--no-step-log", "true"
    ])

    semaforos = traci.trafficlight.getIDList()

    print("\n========== INSPECCIÓN DE SEMÁFOROS ==========")
    print(f"Total de semáforos: {len(semaforos)}")

    for tls_id in semaforos:
        print("\n" + "=" * 55)
        print(f"SEMÁFORO: {tls_id}")

        # Programa activo
        programa_actual = traci.trafficlight.getProgram(tls_id)
        print(f"Programa activo: {programa_actual}")

        # Obtener programas y fases
        programas = traci.trafficlight.getAllProgramLogics(tls_id)

        for programa in programas:
            if programa.programID == programa_actual:
                print(f"Tipo de programa: {programa.type}")
                print(f"Número de fases: {len(programa.phases)}")

                for i, fase in enumerate(programa.phases):
                    print(
                        f"  Fase {i + 1}: "
                        f"duración={fase.duration}s | "
                        f"mínimo={fase.minDur}s | "
                        f"máximo={fase.maxDur}s | "
                        f"estado={fase.state}"
                    )

                print("Parámetros:", programa.subParameter)

        # Obtener conexiones
        conexiones = traci.trafficlight.getControlledLinks(tls_id)

        carriles_entrada = sorted({
            conexion[0]
            for grupo in conexiones
            for conexion in grupo
            if conexion and conexion[0]
        })

        print("\nCarriles de entrada controlados:")
        for carril in carriles_entrada:
            print(f"  - {carril}")

        print("\nConexiones controladas:")

        for indice, grupo in enumerate(conexiones):
            print(f"\nSeñal {indice}:")

            for conexion in grupo:
                carril_entrada = conexion[0]
                carril_salida = conexion[1]
                carril_via = conexion[2]

                print(f"  Entrada: {carril_entrada}")
                print(f"  Salida:  {carril_salida}")
                print(f"  Vía:     {carril_via}")

finally:
    traci.close()
    print("\nInspección finalizada.")
