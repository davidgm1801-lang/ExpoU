import os
import csv
import xml.etree.ElementTree as ET

import traci
import sumolib

from agents.sumo_q_learning import QLearningAgent


# ==================================================
# CONFIGURACION GENERAL
# ==================================================

CONFIG = "sumo_bogota/osm.sumocfg"

DURACION = 4556
SEMILLA = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

TIEMPO_AMARILLO = 3

SUMO_GUI = sumolib.checkBinary("sumo-gui")

ARCHIVO_VEHICULOS = "resultados_ia_5.xml"
ARCHIVO_RESUMEN = "resumen_ia_5.xml"
ARCHIVO_DECISIONES = "decisiones_ia_5.csv"


# ==================================================
# CINCO SEMAFOROS Y SUS CARRILES
# ==================================================

SEMAFOROS = {
    "262567760": {
        "A": [
            "1083001223#0_0",
            "1083001223#0_1"
        ],
        "B": [
            "862794316#0_0",
            "862794316#0_1"
        ]
    },

    "262567775": {
        "A": [
            "88757025#0_0",
            "88757025#0_1"
        ],
        "B": [
            "1083001225#0_1",
            "1083001225#0_2"
        ]
    },

    "262567777": {
        "A": [
            "1060493360#3_1",
            "1060493360#3_2"
        ],
        "B": [
            "908369205#0_0",
            "908369205#0_1"
        ]
    },

    "264377450": {
        "A": [
            "1083001233_0",
            "1083001233_1"
        ],
        "B": [
            "1056806207#0_0",
            "1056806207#0_1"
        ]
    },

    "265804326": {
        "A": [
            "88877450#2_0",
            "88877450#2_1"
        ],
        "B": [
            "1083001234#0_0",
            "1083001234#0_1"
        ]
    }
}


# ==================================================
# MODELOS Y ESTADISTICAS INDEPENDIENTES
# ==================================================

agentes = {}
estadisticas = {}


def cargar_agentes():

    print("\nCARGANDO AGENTES Q-LEARNING")
    print("-" * 50)

    for tls_id in SEMAFOROS:

        agente = QLearningAgent()

        # Cargar la tabla Q INDEPENDIENTE de este semaforo
        # (antes se cargaba por error la tabla compartida vieja
        # 'q_table_sumo.pkl' para los cinco, lo que NO evaluaba
        # los modelos entrenados en train_sumo_5.py).
        archivo_modelo = f"q_table_independiente_{tls_id}.pkl"
        agente.load(archivo_modelo)

        if not agente.q_table:
            raise RuntimeError(
                f"La tabla Q de {archivo_modelo} esta vacia. "
                "Ejecuta primero train_sumo_5.py."
            )

        # En esta simulacion solo explotamos
        # los conocimientos ya entrenados (sin exploracion).
        agente.epsilon = 0

        agentes[tls_id] = agente

        estadisticas[tls_id] = {
            "decisiones": 0,
            "cambios": 0,
            "cola_total": 0,
            "muestras": 0,
            "cola_maxima": 0,
            "inicio_verde": 0,
            "siguiente_decision": 0,
            "fase_anterior": 0
        }

        print(f"Agente preparado para semaforo {tls_id}")

    print("\nLos cinco agentes estan preparados.")


# ==================================================
# LIMPIAR RESULTADOS ANTERIORES
# ==================================================

def limpiar_archivos():

    archivos = [
        ARCHIVO_VEHICULOS,
        ARCHIVO_RESUMEN,
        ARCHIVO_DECISIONES
    ]

    for archivo in archivos:

        if os.path.exists(archivo):
            os.remove(archivo)


# ==================================================
# OBTENER COLAS DE UN SEMAFORO
# ==================================================

def obtener_colas(tls_id):

    carriles = SEMAFOROS[tls_id]

    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in carriles["A"]
    )

    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in carriles["B"]
    )

    return cola_a, cola_b


# ==================================================
# INSTALAR CONTROLADOR EN LOS CINCO SEMAFOROS
# ==================================================

def instalar_controladores():

    print("\nINSTALANDO CONTROLADORES")
    print("-" * 50)

    for tls_id in SEMAFOROS:

        programa_actual = traci.trafficlight.getProgram(tls_id)

        programas = traci.trafficlight.getAllProgramLogics(
            tls_id
        )

        logica_original = None

        for programa in programas:

            if programa.programID == programa_actual:
                logica_original = programa
                break

        if logica_original is None:
            raise RuntimeError(
                f"No se encontro el programa original de {tls_id}."
            )

        fases_originales = logica_original.phases

        if len(fases_originales) != 4:
            raise RuntimeError(
                f"El semaforo {tls_id} no tiene cuatro fases."
            )

        nuevas_fases = []

        for i, fase in enumerate(fases_originales):

            if i in (0, 2):

                nueva_fase = traci.trafficlight.Phase(
                    100000,
                    fase.state,
                    name=fase.name
                )

            else:

                nueva_fase = traci.trafficlight.Phase(
                    TIEMPO_AMARILLO,
                    fase.state,
                    name=fase.name
                )

            nuevas_fases.append(nueva_fase)

        nueva_logica = traci.trafficlight.Logic(
            "rl_agent",
            0,
            0,
            nuevas_fases
        )

        traci.trafficlight.setProgramLogic(
            tls_id,
            nueva_logica
        )

        traci.trafficlight.setProgram(
            tls_id,
            "rl_agent"
        )

        traci.trafficlight.setPhase(
            tls_id,
            0
        )

        tiempo_actual = traci.simulation.getTime()

        estadisticas[tls_id]["inicio_verde"] = tiempo_actual

        estadisticas[tls_id]["siguiente_decision"] = (
            tiempo_actual + TIEMPO_MINIMO_VERDE
        )

        estadisticas[tls_id]["fase_anterior"] = 0

        print(f"Controlador instalado: {tls_id}")


# ==================================================
# ELEGIR ACCION
# ==================================================

def elegir_accion(agente, estado):

    agente.initialize_state(estado)

    valores = agente.q_table[estado]

    if valores[0] >= valores[1]:
        return 0

    return 1


# ==================================================
# REGISTRAR DECISIONES
# ==================================================

def registrar_decision(
    archivo,
    tls_id,
    tiempo,
    fase,
    cola_a,
    cola_b,
    accion
):

    archivo.writerow([
        tls_id,
        tiempo,
        fase,
        cola_a,
        cola_b,
        accion
    ])


# ==================================================
# CONTROL INDEPENDIENTE DE CADA SEMAFORO
# ==================================================

def controlar_semaforo(tls_id, archivo_csv):

    datos = estadisticas[tls_id]
    agente = agentes[tls_id]

    fase = traci.trafficlight.getPhase(tls_id)
    tiempo_actual = traci.simulation.getTime()

    # Las fases 1 y 3 son amarillas.
    # No se toman decisiones durante el amarillo.
    if fase in (1, 3):

        datos["fase_anterior"] = fase
        return

    # Si acaba de terminar el amarillo,
    # comienza un nuevo periodo de verde.
    if datos["fase_anterior"] in (1, 3):

        datos["inicio_verde"] = tiempo_actual

        datos["siguiente_decision"] = (
            tiempo_actual + INTERVALO_DECISION
        )

    datos["fase_anterior"] = fase

    tiempo_verde = (
        tiempo_actual - datos["inicio_verde"]
    )

    # Respetar el tiempo minimo de verde.
    if tiempo_verde < TIEMPO_MINIMO_VERDE:
        return

    # Esperar al siguiente momento de decision.
    if tiempo_actual < datos["siguiente_decision"]:
        return

    cola_a, cola_b = obtener_colas(tls_id)

    grupo_verde = 0 if fase == 0 else 1

    estado = agente.get_state(
        cola_a,
        cola_b,
        grupo_verde
    )

    accion = elegir_accion(
        agente,
        estado
    )

    # Registrar informacion de las colas.
    cola_total = cola_a + cola_b

    datos["cola_total"] += cola_total
    datos["muestras"] += 1

    datos["cola_maxima"] = max(
        datos["cola_maxima"],
        cola_total
    )

    # Forzar cambio al alcanzar el maximo.
    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    datos["decisiones"] += 1

    registrar_decision(
        archivo_csv,
        tls_id,
        tiempo_actual,
        fase,
        cola_a,
        cola_b,
        accion
    )

    # Accion 1: solicitar cambio de fase.
    if accion == 1:

        traci.trafficlight.setPhase(
            tls_id,
            fase + 1
        )

        datos["cambios"] += 1

        datos["fase_anterior"] = fase + 1

    else:

        # Accion 0: conservar el verde.
        datos["siguiente_decision"] = (
            tiempo_actual + INTERVALO_DECISION
        )


# ==================================================
# ANALIZAR RESULTADOS DE VEHICULOS
# ==================================================

def analizar_vehiculos():

    if not os.path.exists(ARCHIVO_VEHICULOS):
        print("No se encontro el archivo de vehiculos.")
        return

    arbol = ET.parse(ARCHIVO_VEHICULOS)
    raiz = arbol.getroot()

    vehiculos = raiz.findall("tripinfo")

    if not vehiculos:

        print("No hay vehiculos que hayan completado su recorrido.")
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

    print("\n" + "=" * 55)
    print("RESULTADOS GENERALES - CINCO SEMAFOROS CON IA")
    print("=" * 55)

    print(f"Vehiculos que completaron su recorrido: {cantidad}")
    print(f"Tiempo promedio de espera: {espera_promedio:.2f} s")
    print(f"Duracion promedio: {duracion_promedio:.2f} s")
    print(f"Tiempo perdido promedio: {perdida_promedio:.2f} s")
    print(f"Velocidad promedio estimada: {velocidad_promedio:.2f} m/s")
    print(f"Distancia total: {distancia_total:.2f} m")


# ==================================================
# ANALIZAR RESUMEN DE SUMO
# ==================================================

def analizar_resumen():

    if not os.path.exists(ARCHIVO_RESUMEN):
        print("No se encontro el resumen de SUMO.")
        return

    arbol = ET.parse(ARCHIVO_RESUMEN)
    raiz = arbol.getroot()

    pasos = raiz.findall("step")

    if not pasos:
        print("El resumen no contiene pasos.")
        return

    ultimo = pasos[-1]

    print("\nESTADISTICAS GENERALES DE SUMO")

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


# ==================================================
# MOSTRAR RESULTADOS POR SEMAFORO
# ==================================================

def mostrar_resultados_semaforos():

    print("\n" + "=" * 60)
    print("RESULTADOS INDIVIDUALES POR SEMAFORO")
    print("=" * 60)

    for tls_id, datos in estadisticas.items():

        promedio_cola = (
            datos["cola_total"] / datos["muestras"]
            if datos["muestras"] > 0
            else 0
        )

        print(f"\nSemaforo: {tls_id}")
        print(f"Decisiones: {datos['decisiones']}")
        print(f"Cambios de fase: {datos['cambios']}")
        print(f"Cola promedio en decisiones: {promedio_cola:.2f}")
        print(f"Cola maxima observada: {datos['cola_maxima']}")


# ==================================================
# EJECUTAR SIMULACION
# ==================================================

def ejecutar_simulacion():

    print("=" * 60)
    print("SIMULACION CON CINCO SEMAFOROS CONTROLADOS POR IA")
    print("=" * 60)

    cargar_agentes()
    limpiar_archivos()

    traci.start([
        SUMO_GUI,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(SEMILLA),
        "--scale", ESCALA_TRAFICO,
        "--tripinfo-output", ARCHIVO_VEHICULOS,
        "--summary-output", ARCHIVO_RESUMEN,
        "--start",
        "--delay", "50"
    ])

    try:

        instalar_controladores()

        with open(
            ARCHIVO_DECISIONES,
            "w",
            newline="",
            encoding="utf-8"
        ) as archivo:

            escritor = csv.writer(archivo)

            escritor.writerow([
                "semaforo",
                "tiempo",
                "fase",
                "cola_A",
                "cola_B",
                "accion"
            ])

            print("\nSIMULACION EN EJECUCION...")
            print("Los cinco semaforos estan siendo controlados.")

            while (
                traci.simulation.getTime() < DURACION
                and traci.simulation.getMinExpectedNumber() > 0
            ):

                # Avanzar SUMO una sola vez.
                traci.simulationStep()

                # Cada semaforo toma su propia decision.
                for tls_id in SEMAFOROS:

                    controlar_semaforo(
                        tls_id,
                        escritor
                    )

        print("\nSIMULACION FINALIZADA.")

    finally:

        try:
            traci.close()

        except Exception as error:
            print(f"Aviso al cerrar SUMO: {error}")

    analizar_vehiculos()
    analizar_resumen()
    mostrar_resultados_semaforos()

    print("\nArchivo de decisiones:", ARCHIVO_DECISIONES)


# ==================================================
# INICIO
# ==================================================

if __name__ == "__main__":

    ejecutar_simulacion()
