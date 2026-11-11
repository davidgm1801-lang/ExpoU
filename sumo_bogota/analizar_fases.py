import traci
import sumolib

CONFIG = "osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

TLS_ID = "262567760"

conectado = False

try:
    # Iniciar SUMO
    traci.start([
        SUMO,
        "-c", CONFIG,
        "--no-step-log", "true"
    ])

    conectado = True

    # Obtener el programa activo
    programa_activo = traci.trafficlight.getProgram(TLS_ID)

    programas = traci.trafficlight.getAllProgramLogics(TLS_ID)

    programa = next(
        p for p in programas
        if p.programID == programa_activo
    )

    # Obtener conexiones controladas
    conexiones = traci.trafficlight.getControlledLinks(TLS_ID)

    print("\n========== SEMAFORO ==========")
    print("ID:", TLS_ID)
    print("Programa activo:", programa_activo)
    print("Cantidad de fases:", len(programa.phases))
    print("Cantidad de indices:", len(conexiones))

    # Analizar cada índice de señal
    for i, grupo in enumerate(conexiones):

        print("\n--------------------------------")
        print(f"INDICE DE SEÑAL: {i}")

        for conexion in grupo:
            entrada = conexion[0]
            salida = conexion[1]
            via = conexion[2]

            print("Entrada:", entrada)
            print("Salida:", salida)
            print("Via interna:", via)

        # Mostrar qué estado tiene este índice
        # durante cada fase
        print("\nEstados por fase:")

        for numero, fase in enumerate(programa.phases):

            estado = fase.state[i] if i < len(fase.state) else "?"

            print(
                f"Fase {numero + 1}: "
                f"estado={estado}, "
                f"duracion={fase.duration}"
            )

finally:
    if conectado:
        traci.close()