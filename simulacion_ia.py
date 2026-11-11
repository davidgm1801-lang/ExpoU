import os
import xml.etree.ElementTree as ET

import traci
import sumolib

from agents.sumo_q_learning import QLearningAgent


# ==========================================
# CONFIGURACIÓN
# ==========================================

CONFIG = "sumo_bogota/osm.sumocfg"

TLS_ID = "262567760"

DURACION = 4556
SEMILLA = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

MODELO = "q_table_sumo.pkl"

SUMO_GUI = sumolib.checkBinary("sumo-gui")

ARCHIVO_VEHICULOS = "resultados_ia.xml"
ARCHIVO_RESUMEN = "resumen_ia.xml"

CARRILES_A = [
    "1083001223#0_0",
    "1083001223#0_1"
]

CARRILES_B = [
    "862794316#0_0",
    "862794316#0_1"
]


# ==========================================
# CARGAR MODELO
# ==========================================

agente = QLearningAgent()

agente.load(MODELO)

if not agente.q_table:
    raise RuntimeError(
        "La tabla Q está vacía. Ejecuta primero train_sumo.py."
    )

agente.epsilon = 0

print("Modelo Q-Learning cargado.")
print("Modo de decisión: explotación.")


# ==========================================
# LIMPIAR RESULTADOS ANTERIORES
# ==========================================

def limpiar_archivos():

    for archivo in [ARCHIVO_VEHICULOS, ARCHIVO_RESUMEN]:

        if os.path.exists(archivo):
            os.remove(archivo)


# ==========================================
# OBTENER COLAS
# ==========================================

def obtener_colas():

    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in CARRILES_A
    )

    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in CARRILES_B
    )

    return cola_a, cola_b


# ==========================================
# INSTALAR CONTROLADOR
# ==========================================

def instalar_programa_agente():

    programa_actual = traci.trafficlight.getProgram(TLS_ID)

    programas = traci.trafficlight.getAllProgramLogics(TLS_ID)

    logica_original = None

    for programa in programas:

        if programa.programID == programa_actual:
            logica_original = programa
            break

    if logica_original is None:
        raise RuntimeError(
            "No se encontró el programa original del semáforo."
        )

    fases_originales = logica_original.phases

    if len(fases_originales) != 4:
        raise RuntimeError(
            "El semáforo no tiene las cuatro fases esperadas."
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
                fase.duration,
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
        TLS_ID,
        nueva_logica
    )

    traci.trafficlight.setProgram(
        TLS_ID,
        "rl_agent"
    )

    traci.trafficlight.setPhase(
        TLS_ID,
        0
    )

    print("Controlador inteligente instalado.")


# ==========================================
# ELEGIR ACCIÓN
# ==========================================

def elegir_accion(estado):

    agente.initialize_state(estado)

    valores = agente.q_table[estado]

    if valores[0] >= valores[1]:
        return 0

    return 1


# ==========================================
# ANALIZAR RESULTADOS DE VEHÍCULOS
# ==========================================

def analizar_vehiculos():

    if not os.path.exists(ARCHIVO_VEHICULOS):
        print("No se encontró el archivo de resultados de vehículos.")
        return

    arbol = ET.parse(ARCHIVO_VEHICULOS)
    raiz = arbol.getroot()

    vehiculos = raiz.findall("tripinfo")

    if not vehiculos:
        print("No hay vehículos que hayan completado su recorrido.")
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

    print("\n" + "=" * 50)
    print("RESULTADOS DE TRÁFICO - SIMULACIÓN CON IA")
    print("=" * 50)

    print(f"Vehículos que completaron su recorrido: {cantidad}")
    print(f"Tiempo promedio de espera: {espera_promedio:.2f} s")
    print(f"Duración promedio del recorrido: {duracion_promedio:.2f} s")
    print(f"Tiempo perdido promedio: {perdida_promedio:.2f} s")
    print(f"Velocidad promedio estimada: {velocidad_promedio:.2f} m/s")
    print(f"Distancia total recorrida: {distancia_total:.2f} m")


# ==========================================
# ANALIZAR RESUMEN DE SUMO
# ==========================================

def analizar_resumen():

    if not os.path.exists(ARCHIVO_RESUMEN):
        print("\nNo se encontró el resumen de SUMO.")
        return

    arbol = ET.parse(ARCHIVO_RESUMEN)
    raiz = arbol.getroot()

    pasos = raiz.findall("step")

    if not pasos:
        print("\nEl resumen no contiene pasos de simulación.")
        return

    ultimo = pasos[-1]

    print("\nESTADÍSTICAS GENERALES DE SUMO")

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


# ==========================================
# EJECUTAR SIMULACIÓN CON IA
# ==========================================

def ejecutar_simulacion():

    print("=" * 50)
    print("SIMULACIÓN CON INTELIGENCIA ARTIFICIAL")
    print("=" * 50)

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

        instalar_programa_agente()

        inicio_verde = traci.simulation.getTime()

        decisiones = 0
        cambios = 0

        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):

            fase = traci.trafficlight.getPhase(TLS_ID)

            # Si está en amarillo, dejar que termine.
            if fase not in (0, 2):
                traci.simulationStep()
                continue

            tiempo_actual = traci.simulation.getTime()

            tiempo_verde = tiempo_actual - inicio_verde

            # Respetar el mínimo de verde.
            if tiempo_verde < TIEMPO_MINIMO_VERDE:
                traci.simulationStep()
                continue

            cola_a, cola_b = obtener_colas()

            grupo_verde = 0 if fase == 0 else 1

            estado = agente.get_state(
                cola_a,
                cola_b,
                grupo_verde
            )

            accion = elegir_accion(estado)

            if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
                accion = 1

                print(
                    f"Máximo verde alcanzado: "
                    f"{tiempo_verde:.0f} segundos."
                )

            decisiones += 1

            if accion == 1:

                traci.trafficlight.setPhase(
                    TLS_ID,
                    fase + 1
                )

                cambios += 1

                while (
                    traci.trafficlight.getPhase(TLS_ID) not in (0, 2)
                    and traci.simulation.getMinExpectedNumber() > 0
                    and traci.simulation.getTime() < DURACION
                ):
                    traci.simulationStep()

                inicio_verde = traci.simulation.getTime()

            else:

                tiempo_objetivo = (
                    traci.simulation.getTime()
                    + INTERVALO_DECISION
                )

                while (
                    traci.simulation.getTime() < tiempo_objetivo
                    and traci.simulation.getMinExpectedNumber() > 0
                    and traci.simulation.getTime() < DURACION
                ):
                    traci.simulationStep()

        print("\nSIMULACIÓN CON IA FINALIZADA")
        print(f"Decisiones tomadas: {decisiones}")
        print(f"Cambios de fase solicitados: {cambios}")

    finally:

        try:
            traci.close()
        except Exception as error:
            print(f"Aviso al cerrar SUMO: {error}")

    analizar_vehiculos()
    analizar_resumen()


# ==========================================
# EJECUTAR
# ==========================================

if __name__ == "__main__":

    ejecutar_simulacion()
