"""
==================================================================
ENTRENAMIENTO v2 - Etapa 3 (Parte B) - ExpoU
==================================================================

Que cambia respecto a train_sumo_5.py
--------------------------------------
UNICA diferencia de diseno: la DISCRETIZACION DE LA COLA pasa de 3 a
5 niveles, para que el agente distinga congestion leve de severa.

  - v1 (original): 0 / 1-3 / >3            -> umbrales [0, 3]
  - v2 (este):     0 / 1-2 / 3-5 / 6-10 / >10 -> umbrales [0, 2, 5, 10]

El espacio de estados pasa de 3x3x2 = 18 a 5x5x2 = 50.

Todo lo demas (logica de transiciones, recompensa, intervalos,
tiempos de verde) es IDENTICO a train_sumo_5.py, para que la
comparacion sea justa.

Proteccion de los modelos v1
----------------------------
Este script NO toca los modelos originales. Guarda en archivos con
nombre propio:
  - modelos : q_table_v2_<id>.pkl
  - log     : resultados_entrenamiento_v2.csv

Numero de episodios
-------------------
Parametrizable con la variable de entorno EPISODIOS_V2 (por defecto 40,
un entrenamiento REDUCIDO para ver la tendencia rapido). Ejemplos:

  # 40 episodios (por defecto)
  python .\\train_sumo_5_v2.py

  # (PowerShell) 30 episodios
  $env:EPISODIOS_V2=30; python .\\train_sumo_5_v2.py

ADVERTENCIA: con pocos episodios y 50 estados, la cobertura de estados
sera parcial. Es un experimento de TENDENCIA, no comparable 1:1 con los
100 episodios del modelo v1.
==================================================================
"""

import os
import csv
import random
import traci
import sumolib

from agents.sumo_q_learning import QLearningAgent


# ==================================================
# CONFIGURACION GENERAL (identica a v1 salvo lo indicado)
# ==================================================

CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556

# Episodios reducidos y parametrizables (Parte B).
EPISODIOS = int(os.environ.get("EPISODIOS_V2", "40"))

SEMILLA_BASE = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

# --- CAMBIO v2: discretizacion mas fina de la cola ---
UMBRALES_COLA_V2 = [0, 2, 5, 10]

# Salidas propias (NO sobrescriben las de v1).
ARCHIVO_CSV = "resultados_entrenamiento_v2.csv"


# ==================================================
# CINCO SEMAFOROS Y SUS CARRILES (identicos a v1)
# ==================================================

SEMAFOROS = {
    "262567760": {
        "A": ["1083001223#0_0", "1083001223#0_1"],
        "B": ["862794316#0_0", "862794316#0_1"],
    },
    "262567775": {
        "A": ["88757025#0_0", "88757025#0_1"],
        "B": ["1083001225#0_1", "1083001225#0_2"],
    },
    "262567777": {
        "A": ["1060493360#3_1", "1060493360#3_2"],
        "B": ["908369205#0_0", "908369205#0_1"],
    },
    "264377450": {
        "A": ["1083001233_0", "1083001233_1"],
        "B": ["1056806207#0_0", "1056806207#0_1"],
    },
    "265804326": {
        "A": ["88877450#2_0", "88877450#2_1"],
        "B": ["1083001234#0_0", "1083001234#0_1"],
    },
}

# Modelos v2 con nombre propio.
ARCHIVOS_MODELO = {
    tls_id: f"q_table_v2_{tls_id}.pkl"
    for tls_id in SEMAFOROS
}


# ==================================================
# CREAR LOS CINCO AGENTES (con umbrales v2)
# ==================================================

agentes = {}

for tls_id in SEMAFOROS:
    agentes[tls_id] = QLearningAgent(
        learning_rate=0.1,
        discount_factor=0.95,
        epsilon=1.0,
        epsilon_min=0.05,
        epsilon_decay=0.97,
        queue_thresholds=UMBRALES_COLA_V2,
    )


# ==================================================
# UTILIDADES (identicas a v1)
# ==================================================

def obtener_colas(tls_id):
    carriles_a = SEMAFOROS[tls_id]["A"]
    carriles_b = SEMAFOROS[tls_id]["B"]
    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(c) for c in carriles_a
    )
    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(c) for c in carriles_b
    )
    return cola_a, cola_b


def calcular_recompensa(cola_a, cola_b):
    cola_total = cola_a + cola_b
    desequilibrio = abs(cola_a - cola_b)
    return -cola_total - 0.25 * desequilibrio


def instalar_programa_agente(tls_id):
    programa_actual = traci.trafficlight.getProgram(tls_id)
    programas = traci.trafficlight.getAllProgramLogics(tls_id)

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
            nuevas_fases.append(
                traci.trafficlight.Phase(
                    100000, fase.state, name=fase.name
                )
            )
        else:
            nuevas_fases.append(
                traci.trafficlight.Phase(
                    fase.duration, fase.state, name=fase.name
                )
            )

    nueva_logica = traci.trafficlight.Logic(
        "rl_agent", 0, 0, nuevas_fases
    )
    traci.trafficlight.setProgramLogic(tls_id, nueva_logica)
    traci.trafficlight.setProgram(tls_id, "rl_agent")
    traci.trafficlight.setPhase(tls_id, 0)


def crear_estado_control():
    estados = {}
    for tls_id in SEMAFOROS:
        estados[tls_id] = {
            "inicio_verde": 0,
            "proxima_decision": TIEMPO_MINIMO_VERDE,
            "pendiente": None,
            "decisiones": 0,
            "cambios": 0,
            "recompensa_total": 0,
            "recompensas_aprendidas": 0,
        }
    return estados


def aprender_transicion(tls_id, control, nuevo_estado, done):
    pendiente = control["pendiente"]
    if pendiente is None:
        return

    agente = agentes[tls_id]
    recompensa = (
        pendiente["recompensa_total"] / pendiente["muestras"]
        if pendiente["muestras"] > 0
        else 0
    )
    agente.learn(
        pendiente["estado"],
        pendiente["accion"],
        recompensa,
        nuevo_estado,
        done=done,
    )
    control["decisiones"] += 1
    control["recompensa_total"] += recompensa
    control["recompensas_aprendidas"] += 1
    control["pendiente"] = None


def actualizar_agente(tls_id, control, tiempo_actual):
    pendiente = control["pendiente"]
    if pendiente is None:
        return

    fase_actual = traci.trafficlight.getPhase(tls_id)
    cola_a, cola_b = obtener_colas(tls_id)

    pendiente["recompensa_total"] += calcular_recompensa(cola_a, cola_b)
    pendiente["muestras"] += 1

    if fase_actual not in (0, 2):
        return

    fase_anterior = pendiente["fase"]
    accion = pendiente["accion"]

    if accion == 0:
        if tiempo_actual - pendiente["tiempo_inicio"] < INTERVALO_DECISION:
            return
    elif fase_actual == fase_anterior:
        return

    nuevo_grupo = 0 if fase_actual == 0 else 1
    nuevo_estado = agentes[tls_id].get_state(cola_a, cola_b, nuevo_grupo)

    aprender_transicion(tls_id, control, nuevo_estado, done=False)

    if fase_actual != fase_anterior:
        control["inicio_verde"] = tiempo_actual
        control["proxima_decision"] = tiempo_actual + TIEMPO_MINIMO_VERDE
    else:
        control["proxima_decision"] = tiempo_actual + INTERVALO_DECISION


def finalizar_transiciones_pendientes(controles):
    for tls_id in SEMAFOROS:
        control = controles[tls_id]
        if control["pendiente"] is None:
            continue

        cola_a, cola_b = obtener_colas(tls_id)
        pendiente = control["pendiente"]
        pendiente["recompensa_total"] += calcular_recompensa(cola_a, cola_b)
        pendiente["muestras"] += 1

        if pendiente["accion"] == 1:
            nuevo_grupo = 1 if pendiente["fase"] == 0 else 0
        else:
            nuevo_grupo = 0 if pendiente["fase"] == 0 else 1

        nuevo_estado = agentes[tls_id].get_state(
            cola_a, cola_b, nuevo_grupo
        )
        aprender_transicion(tls_id, control, nuevo_estado, done=True)


def controlar_semaforo(tls_id, control, tiempo_actual):
    fase = traci.trafficlight.getPhase(tls_id)

    actualizar_agente(tls_id, control, tiempo_actual)

    if fase not in (0, 2):
        return
    if control["pendiente"] is not None:
        return
    if tiempo_actual < control["proxima_decision"]:
        return

    cola_a, cola_b = obtener_colas(tls_id)
    grupo_verde = 0 if fase == 0 else 1
    agente = agentes[tls_id]
    estado = agente.get_state(cola_a, cola_b, grupo_verde)
    accion = agente.choose_action(estado)

    tiempo_verde = tiempo_actual - control["inicio_verde"]
    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    control["pendiente"] = {
        "estado": estado,
        "accion": accion,
        "fase": fase,
        "tiempo_inicio": tiempo_actual,
        "recompensa_total": 0,
        "muestras": 0,
    }

    if accion == 0:
        return

    traci.trafficlight.setPhase(tls_id, fase + 1)
    control["cambios"] += 1


def guardar_modelos():
    for tls_id, agente in agentes.items():
        agente.save(ARCHIVOS_MODELO[tls_id])


# ==================================================
# RECUPERAR ENTRENAMIENTO v2
# ==================================================

def recuperar_entrenamiento():
    if not os.path.exists(ARCHIVO_CSV):
        for tls_id in SEMAFOROS:
            if os.path.exists(ARCHIVOS_MODELO[tls_id]):
                raise RuntimeError(
                    "Hay un modelo v2 anterior sin su CSV. "
                    "No se sobrescribira automaticamente."
                )

        with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "episodio", "semaforo", "decisiones",
                "cambios", "recompensa_promedio", "epsilon",
            ])
        return 0

    with open(ARCHIVO_CSV, "r", newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas = [
            "episodio", "semaforo", "decisiones",
            "cambios", "recompensa_promedio", "epsilon",
        ]
        if lector.fieldnames != columnas:
            raise ValueError("El CSV v2 tiene columnas incorrectas.")
        filas = list(lector)

    if not filas:
        return 0

    ultimo = max(int(fila["episodio"]) for fila in filas)
    if ultimo < 0 or ultimo > EPISODIOS:
        raise ValueError("Numero de episodio invalido.")

    if ultimo > 0:
        for tls_id in SEMAFOROS:
            if not os.path.exists(ARCHIVOS_MODELO[tls_id]):
                raise FileNotFoundError(
                    f"Falta el modelo v2 de {tls_id}."
                )
            agentes[tls_id].load(ARCHIVOS_MODELO[tls_id])

    return ultimo


# ==================================================
# EJECUTAR UN EPISODIO
# ==================================================

def ejecutar_episodio(numero_episodio):
    semilla = SEMILLA_BASE + numero_episodio - 1
    random.seed(semilla)

    print("\n" + "=" * 55)
    print(f"EPISODIO {numero_episodio}/{EPISODIOS} (v2) | Semilla: {semilla}")
    print("=" * 55)

    traci.start([
        SUMO,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(semilla),
        "--no-step-log", "true",
        "--scale", ESCALA_TRAFICO,
    ])

    try:
        disponibles = traci.trafficlight.getIDList()
        for tls_id in SEMAFOROS:
            if tls_id not in disponibles:
                raise RuntimeError(f"No existe el semaforo {tls_id}.")
            instalar_programa_agente(tls_id)

        controles = crear_estado_control()

        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):
            tiempo_actual = traci.simulation.getTime()
            for tls_id in SEMAFOROS:
                controlar_semaforo(tls_id, controles[tls_id], tiempo_actual)
            traci.simulationStep()

        finalizar_transiciones_pendientes(controles)

        for agente in agentes.values():
            agente.decay_exploration()

        guardar_modelos()

        with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            for tls_id in SEMAFOROS:
                control = controles[tls_id]
                promedio = (
                    control["recompensa_total"]
                    / control["recompensas_aprendidas"]
                    if control["recompensas_aprendidas"] > 0
                    else 0
                )
                epsilon_actual = agentes[tls_id].epsilon
                escritor.writerow([
                    numero_episodio, tls_id,
                    control["decisiones"], control["cambios"],
                    promedio, epsilon_actual,
                ])
                print(
                    f"  {tls_id}: decisiones={control['decisiones']} "
                    f"cambios={control['cambios']} "
                    f"recompensa={promedio:.4f} eps={epsilon_actual:.4f}"
                )
            f.flush()

    finally:
        traci.close()


# ==================================================
# ENTRENAMIENTO COMPLETO
# ==================================================

def entrenar():
    ultimo = recuperar_entrenamiento()

    print("\n" + "=" * 55)
    print("ENTRENAMIENTO v2 (Etapa 3, Parte B)")
    print(f"Discretizacion de cola: umbrales {UMBRALES_COLA_V2} (5 niveles)")
    print(f"Episodios objetivo: {EPISODIOS}")
    print(f"Episodios ya completados: {ultimo}")
    print("=" * 55)

    if ultimo >= EPISODIOS:
        print("\nEl entrenamiento v2 ya esta completo.")
        return

    try:
        for numero in range(ultimo + 1, EPISODIOS + 1):
            ejecutar_episodio(numero)
    except KeyboardInterrupt:
        print("\nEntrenamiento v2 interrumpido. Episodios guardados.")
        return

    print("\n" + "=" * 55)
    print("ENTRENAMIENTO v2 FINALIZADO")
    print("Modelos v2 guardados:")
    for tls_id in SEMAFOROS:
        print(" ", ARCHIVOS_MODELO[tls_id])
    print(f"Resultados: {ARCHIVO_CSV}")
    print("=" * 55)


if __name__ == "__main__":
    entrenar()
