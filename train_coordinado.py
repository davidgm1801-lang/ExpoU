"""
==================================================================
ENTRENAMIENTO COORDINADO - Etapa 4 (ExpoU)
==================================================================

Objetivo
--------
Entrenar cinco agentes Q-Learning que ademas de observar sus propias
colas, observan la PRESION de su vecino aguas abajo, para no inundarlo.
Esto ataca la causa raiz hallada en la Etapa 3 (efecto de red: dar
verde hacia un vecino saturado dispersa atascos por la red).

Topologia de vecindad (derivada de getControlledLinks, Etapa 1)
---------------------------------------------------------------
Salida de un grupo de un semaforo -> entrada de un vecino:

  262567760 (sale por grupo A: 88861379#0 / 88757025#0) --> 262567775
  262567777 (sale por grupo A: 915587469 / 1083001225)   --> 262567775
  264377450 (sale por grupo B: 1083001234)               --> 265804326

Para cada semaforo definimos, por grupo (A/B), a que vecino alimenta
(si alimenta a alguno). Cuando el agente considera dar/servir un grupo,
mira la cola del vecino destino de ESE grupo; si supera un umbral, la
"presion_vecino" es 1.

Protege modelos previos
-----------------------
Guarda en q_table_coord_<id>.pkl y resultados_entrenamiento_coord.csv.
No toca los modelos v1 ni v2.

Episodios parametrizables con EPISODIOS_COORD (por defecto 60).

Como ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\train_coordinado.py
==================================================================
"""

import os
import csv
import random
import traci
import sumolib

from agents.coordinated_agent import CoordinatedQLearningAgent
from config_semaforos import SEMAFOROS, VECINO_DESTINO, archivos_modelo


# ==================================================
# CONFIGURACION (identica a los entrenamientos previos)
# ==================================================

CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556
EPISODIOS = int(os.environ.get("EPISODIOS_COORD", "60"))

SEMILLA_BASE = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

# Umbral de cola del vecino para considerarlo "congestionado".
UMBRAL_PRESION_VECINO = 4

# (ARCHIVO_CSV se define mas abajo, junto al prefijo de los modelos.)


# ==================================================
# SEMAFOROS Y TOPOLOGIA
# ==================================================
# Se importan de config_semaforos.py (fuente unica). Para escalar a mas
# intersecciones basta editar ese archivo; este entrenador no cambia.

# Prefijo de los modelos. Por defecto "q_table_coord_" (los 5 de la
# Etapa 4). Si se controla un conjunto distinto (p. ej. 10 semaforos),
# conviene usar otro prefijo para NO sobrescribir los modelos previos.
# Se ajusta con la variable de entorno PREFIJO_COORD.
PREFIJO_COORD = os.environ.get("PREFIJO_COORD", "q_table_coord_")
ARCHIVOS_MODELO = archivos_modelo(PREFIJO_COORD)

# El CSV de resultados acompaña al prefijo para no mezclar corridas.
ARCHIVO_CSV = (
    "resultados_entrenamiento_coord.csv"
    if PREFIJO_COORD == "q_table_coord_"
    else f"resultados_entrenamiento_{PREFIJO_COORD.rstrip('_')}.csv"
)


# ==================================================
# AGENTES
# ==================================================

agentes = {}
for tls_id in SEMAFOROS:
    agentes[tls_id] = CoordinatedQLearningAgent(
        learning_rate=0.1,
        discount_factor=0.95,
        epsilon=1.0,
        epsilon_min=0.05,
        epsilon_decay=0.97,
    )


# ==================================================
# UTILIDADES
# ==================================================

def obtener_colas(tls_id):
    g = SEMAFOROS[tls_id]
    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(c) for c in g["A"]
    )
    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(c) for c in g["B"]
    )
    return cola_a, cola_b


def cola_total_semaforo(tls_id):
    a, b = obtener_colas(tls_id)
    return a + b


def presion_vecino(tls_id, grupo_verde):
    """
    Presion del vecino al que apunta el grupo que ACTUALMENTE tiene
    verde. 1 si ese vecino esta congestionado, 0 si no o si no hay
    vecino relevante.
    """
    grupo = "A" if grupo_verde == 0 else "B"
    destinos = VECINO_DESTINO.get(tls_id, {})
    if grupo not in destinos:
        return 0
    vecino_id, _grupo_dest = destinos[grupo]
    return 1 if cola_total_semaforo(vecino_id) >= UMBRAL_PRESION_VECINO else 0


def calcular_recompensa(tls_id, cola_a, cola_b, grupo_verde):
    """
    Recompensa local (como antes) MAS una penalizacion si el grupo con
    verde esta alimentando a un vecino congestionado. Asi el agente
    aprende a no inundar vecinos llenos.
    """
    cola_total = cola_a + cola_b
    desequilibrio = abs(cola_a - cola_b)
    recompensa = -cola_total - 0.25 * desequilibrio

    # Penalizacion de coordinacion: si estoy sirviendo (verde) un grupo
    # que vierte a un vecino saturado, penalizo.
    if presion_vecino(tls_id, grupo_verde) == 1:
        recompensa -= 2.0

    return recompensa


def instalar_programa_agente(tls_id):
    programa_actual = traci.trafficlight.getProgram(tls_id)
    programas = traci.trafficlight.getAllProgramLogics(tls_id)

    logica_original = None
    for p in programas:
        if p.programID == programa_actual:
            logica_original = p
            break
    if logica_original is None:
        raise RuntimeError(f"Sin programa original en {tls_id}.")

    fases = logica_original.phases
    if len(fases) != 4:
        raise RuntimeError(f"{tls_id} no tiene 4 fases.")

    nuevas = []
    for i, fase in enumerate(fases):
        dur = 100000 if i in (0, 2) else fase.duration
        nuevas.append(
            traci.trafficlight.Phase(dur, fase.state, name=fase.name)
        )

    traci.trafficlight.setProgramLogic(
        tls_id, traci.trafficlight.Logic("rl_agent", 0, 0, nuevas)
    )
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


def estado_coordinado(tls_id, cola_a, cola_b, grupo_verde):
    pv = presion_vecino(tls_id, grupo_verde)
    return agentes[tls_id].get_state(cola_a, cola_b, grupo_verde, pv)


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
        pendiente["estado"], pendiente["accion"],
        recompensa, nuevo_estado, done=done,
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

    grupo_actual = 0 if fase_actual == 0 else 1
    pendiente["recompensa_total"] += calcular_recompensa(
        tls_id, cola_a, cola_b, grupo_actual
    )
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
    nuevo_estado = estado_coordinado(tls_id, cola_a, cola_b, nuevo_grupo)

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
        grupo_actual = 0 if pendiente["fase"] == 0 else 1
        pendiente["recompensa_total"] += calcular_recompensa(
            tls_id, cola_a, cola_b, grupo_actual
        )
        pendiente["muestras"] += 1

        if pendiente["accion"] == 1:
            nuevo_grupo = 1 if pendiente["fase"] == 0 else 0
        else:
            nuevo_grupo = 0 if pendiente["fase"] == 0 else 1

        nuevo_estado = estado_coordinado(
            tls_id, cola_a, cola_b, nuevo_grupo
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
    estado = estado_coordinado(tls_id, cola_a, cola_b, grupo_verde)
    accion = agentes[tls_id].choose_action(estado)

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
# RECUPERACION / REANUDACION
# ==================================================

def recuperar_entrenamiento():
    if not os.path.exists(ARCHIVO_CSV):
        for tls_id in SEMAFOROS:
            if os.path.exists(ARCHIVOS_MODELO[tls_id]):
                raise RuntimeError(
                    "Hay modelos coord sin su CSV. No se sobrescribe."
                )
        with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "episodio", "semaforo", "decisiones",
                "cambios", "recompensa_promedio", "epsilon",
            ])
        return 0

    with open(ARCHIVO_CSV, "r", newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        esperado = [
            "episodio", "semaforo", "decisiones",
            "cambios", "recompensa_promedio", "epsilon",
        ]
        if lector.fieldnames != esperado:
            raise ValueError("CSV coord con columnas incorrectas.")
        filas = list(lector)

    if not filas:
        return 0

    ultimo = max(int(fila["episodio"]) for fila in filas)
    if ultimo < 0 or ultimo > EPISODIOS:
        raise ValueError("Numero de episodio invalido.")

    if ultimo > 0:
        for tls_id in SEMAFOROS:
            if not os.path.exists(ARCHIVOS_MODELO[tls_id]):
                raise FileNotFoundError(f"Falta modelo coord {tls_id}.")
            agentes[tls_id].load(ARCHIVOS_MODELO[tls_id])

    return ultimo


# ==================================================
# UN EPISODIO
# ==================================================

def ejecutar_episodio(numero_episodio):
    semilla = SEMILLA_BASE + numero_episodio - 1
    random.seed(semilla)

    print("\n" + "=" * 55)
    print(f"EPISODIO {numero_episodio}/{EPISODIOS} (coord) | Semilla {semilla}")
    print("=" * 55)

    traci.start([
        SUMO, "-c", CONFIG,
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
            t = traci.simulation.getTime()
            for tls_id in SEMAFOROS:
                controlar_semaforo(tls_id, controles[tls_id], t)
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
                eps = agentes[tls_id].epsilon
                escritor.writerow([
                    numero_episodio, tls_id,
                    control["decisiones"], control["cambios"],
                    promedio, eps,
                ])
                print(
                    f"  {tls_id}: dec={control['decisiones']} "
                    f"cambios={control['cambios']} "
                    f"recomp={promedio:.4f} eps={eps:.4f}"
                )
            f.flush()

    finally:
        traci.close()


def entrenar():
    ultimo = recuperar_entrenamiento()

    print("\n" + "=" * 55)
    print("ENTRENAMIENTO COORDINADO (Etapa 4)")
    print(f"Estado ampliado con presion de vecino (umbral {UMBRAL_PRESION_VECINO})")
    print(f"Episodios objetivo: {EPISODIOS} | completados: {ultimo}")
    print("=" * 55)

    if ultimo >= EPISODIOS:
        print("\nEl entrenamiento coordinado ya esta completo.")
        return

    try:
        for numero in range(ultimo + 1, EPISODIOS + 1):
            ejecutar_episodio(numero)
    except KeyboardInterrupt:
        print("\nInterrumpido. Episodios guardados.")
        return

    print("\n" + "=" * 55)
    print("ENTRENAMIENTO COORDINADO FINALIZADO")
    for tls_id in SEMAFOROS:
        print(" ", ARCHIVOS_MODELO[tls_id])
    print(f"Resultados: {ARCHIVO_CSV}")
    print("=" * 55)


if __name__ == "__main__":
    entrenar()
