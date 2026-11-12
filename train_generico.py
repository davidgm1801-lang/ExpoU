"""
==================================================================
ENTRENAMIENTO GENERICO - Sistema de 19 intersecciones (ExpoU)
==================================================================

Entrena un agente Q-Learning por cada semaforo CONTROLABLE de la red
(los detectados por autodetectar_semaforos.py), funcione con 2, 3 o
mas grupos verdes. Un unico script cubre toda la red.

Mecanica de control (generica)
------------------------------
Cada semaforo tiene una lista de FASES VERDES (sus grupos). El agente:
  - Observa la cola del grupo activo y la cola maxima del resto.
  - Decide: 0 = mantener verde actual, 1 = avanzar al siguiente grupo.
  - Al avanzar, se pasa por la fase amarilla correspondiente (la fase
    siguiente a la verde en el programa original) y luego al verde del
    proximo grupo.

Recompensa
----------
  R = -(suma de colas de todos los grupos) - 0.25 * (desequilibrio),
  donde desequilibrio = cola_max_grupo - cola_min_grupo.
Penaliza congestion total y reparto desigual entre grupos.

Modelos
-------
Guarda q_table_gen_<id>.pkl y resultados_entrenamiento_gen.csv.
Episodios parametrizables con EPISODIOS_GEN (por defecto 50).

Requisito: ejecutar antes autodetectar_semaforos.py (genera el JSON).

Ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\train_generico.py
==================================================================
"""

import os
import csv
import json
import random
import traci
import sumolib

from agents.generic_agent import GenericQLearningAgent


CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556
EPISODIOS = int(os.environ.get("EPISODIOS_GEN", "50"))
SEMILLA_BASE = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

ARCHIVO_JSON = "config_auto_semaforos.json"
ARCHIVO_CSV = "resultados_entrenamiento_gen.csv"
PREFIJO_MODELO = "q_table_gen_"


# ==================================================
# CARGAR CONFIGURACION AUTODETECTADA
# ==================================================

def cargar_config():
    if not os.path.exists(ARCHIVO_JSON):
        raise FileNotFoundError(
            f"No existe {ARCHIVO_JSON}. Ejecuta primero "
            "autodetectar_semaforos.py"
        )
    with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


SEMAFOROS = cargar_config()
ARCHIVOS_MODELO = {tid: f"{PREFIJO_MODELO}{tid}.pkl" for tid in SEMAFOROS}

agentes = {
    tid: GenericQLearningAgent() for tid in SEMAFOROS
}


# ==================================================
# COLAS POR GRUPO
# ==================================================

def colas_por_grupo(tls_id):
    """Lista de colas (una por grupo verde) del semaforo."""
    colas = []
    for grupo in SEMAFOROS[tls_id]["grupos"]:
        c = sum(
            traci.lane.getLastStepHaltingNumber(carril)
            for carril in grupo["carriles"]
        )
        colas.append(c)
    return colas


def indice_grupo_activo(tls_id):
    """Indice del grupo cuyo 'fase' coincide con la fase verde actual."""
    fase_actual = traci.trafficlight.getPhase(tls_id)
    for idx, grupo in enumerate(SEMAFOROS[tls_id]["grupos"]):
        if grupo["fase"] == fase_actual:
            return idx
    return None  # estamos en amarillo o fase no-verde


def calcular_recompensa(colas):
    total = sum(colas)
    desequilibrio = (max(colas) - min(colas)) if colas else 0
    return -total - 0.25 * desequilibrio


def estado_de(tls_id, idx_activo, colas):
    cola_activo = colas[idx_activo]
    otros = [c for i, c in enumerate(colas) if i != idx_activo]
    cola_max_otros = max(otros) if otros else 0
    return agentes[tls_id].get_state(cola_activo, cola_max_otros, idx_activo)


# ==================================================
# INSTALAR CONTROLADOR (alargar fases verdes)
# ==================================================

def instalar_programa(tls_id):
    programa = traci.trafficlight.getProgram(tls_id)
    logica = None
    for p in traci.trafficlight.getAllProgramLogics(tls_id):
        if p.programID == programa:
            logica = p
            break
    if logica is None:
        raise RuntimeError(f"Sin programa original en {tls_id}.")

    fases_verdes = {g["fase"] for g in SEMAFOROS[tls_id]["grupos"]}
    nuevas = []
    for i, fase in enumerate(logica.phases):
        if i in fases_verdes:
            dur = 100000  # el agente decide cuando cambiar
        else:
            dur = fase.duration  # amarillos y otras: se respetan
        nuevas.append(
            traci.trafficlight.Phase(dur, fase.state, name=fase.name)
        )
    traci.trafficlight.setProgramLogic(
        tls_id, traci.trafficlight.Logic("rl_agent", 0, 0, nuevas)
    )
    traci.trafficlight.setProgram(tls_id, "rl_agent")
    # arrancar en la primera fase verde
    primera = SEMAFOROS[tls_id]["grupos"][0]["fase"]
    traci.trafficlight.setPhase(tls_id, primera)


# ==================================================
# ESTADO DE CONTROL
# ==================================================

def nuevo_control():
    return {
        "inicio_verde": 0,
        "proxima_decision": TIEMPO_MINIMO_VERDE,
        "pendiente": None,
        "decisiones": 0,
        "cambios": 0,
        "recompensa_total": 0.0,
        "recompensas_aprendidas": 0,
    }


def aprender_transicion(tls_id, control, nuevo_estado, done):
    pend = control["pendiente"]
    if pend is None:
        return
    recompensa = (
        pend["recompensa_total"] / pend["muestras"]
        if pend["muestras"] > 0 else 0
    )
    agentes[tls_id].learn(
        pend["estado"], pend["accion"], recompensa, nuevo_estado, done=done
    )
    control["decisiones"] += 1
    control["recompensa_total"] += recompensa
    control["recompensas_aprendidas"] += 1
    control["pendiente"] = None


def avanzar_a_siguiente_grupo(tls_id):
    """Pasa a la fase siguiente (amarillo) del grupo actual."""
    fase = traci.trafficlight.getPhase(tls_id)
    n = SEMAFOROS[tls_id]["n_fases"]
    traci.trafficlight.setPhase(tls_id, (fase + 1) % n)


def controlar(tls_id, control, t):
    idx = indice_grupo_activo(tls_id)

    # --- cerrar aprendizaje pendiente ---
    pend = control["pendiente"]
    if pend is not None:
        colas = colas_por_grupo(tls_id)
        pend["recompensa_total"] += calcular_recompensa(colas)
        pend["muestras"] += 1
        # solo aprendemos cuando volvemos a estar en verde
        if idx is not None:
            if pend["accion"] == 0:
                if t - pend["tiempo_inicio"] >= INTERVALO_DECISION:
                    nuevo_estado = estado_de(tls_id, idx, colas)
                    aprender_transicion(tls_id, control, nuevo_estado, False)
                    control["proxima_decision"] = t + INTERVALO_DECISION
            else:
                # accion de cambio: aprender cuando el grupo activo cambio
                if idx != pend["idx"]:
                    nuevo_estado = estado_de(tls_id, idx, colas)
                    aprender_transicion(tls_id, control, nuevo_estado, False)
                    control["inicio_verde"] = t
                    control["proxima_decision"] = t + TIEMPO_MINIMO_VERDE

    # no decidir en amarillo
    if idx is None:
        return
    if control["pendiente"] is not None:
        return
    if t < control["proxima_decision"]:
        return

    colas = colas_por_grupo(tls_id)
    estado = estado_de(tls_id, idx, colas)
    accion = agentes[tls_id].choose_action(estado)

    tiempo_verde = t - control["inicio_verde"]
    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    control["pendiente"] = {
        "estado": estado, "accion": accion, "idx": idx,
        "tiempo_inicio": t, "recompensa_total": 0.0, "muestras": 0,
    }

    if accion == 1:
        avanzar_a_siguiente_grupo(tls_id)
        control["cambios"] += 1


def finalizar(controles):
    for tls_id in SEMAFOROS:
        control = controles[tls_id]
        if control["pendiente"] is None:
            continue
        colas = colas_por_grupo(tls_id)
        pend = control["pendiente"]
        pend["recompensa_total"] += calcular_recompensa(colas)
        pend["muestras"] += 1
        idx = indice_grupo_activo(tls_id)
        if idx is None:
            idx = pend["idx"]
        nuevo_estado = estado_de(tls_id, idx, colas)
        aprender_transicion(tls_id, control, nuevo_estado, True)


def guardar_modelos():
    for tid, agente in agentes.items():
        agente.save(ARCHIVOS_MODELO[tid])


# ==================================================
# REANUDACION
# ==================================================

def recuperar():
    if not os.path.exists(ARCHIVO_CSV):
        with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "episodio", "semaforo", "decisiones",
                "cambios", "recompensa_promedio", "epsilon",
            ])
        return 0
    with open(ARCHIVO_CSV, "r", newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        return 0
    ultimo = max(int(x["episodio"]) for x in filas)
    if ultimo > 0:
        for tid in SEMAFOROS:
            if os.path.exists(ARCHIVOS_MODELO[tid]):
                agentes[tid].load(ARCHIVOS_MODELO[tid])
    return ultimo


# ==================================================
# EPISODIO
# ==================================================

def ejecutar_episodio(numero):
    semilla = SEMILLA_BASE + numero - 1
    random.seed(semilla)
    print("\n" + "=" * 55)
    print(f"EPISODIO {numero}/{EPISODIOS} (generico) | Semilla {semilla}")
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
        activos = []
        for tls_id in SEMAFOROS:
            if tls_id in disponibles:
                instalar_programa(tls_id)
                activos.append(tls_id)

        controles = {tid: nuevo_control() for tid in activos}

        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):
            t = traci.simulation.getTime()
            for tls_id in activos:
                controlar(tls_id, controles[tls_id], t)
            traci.simulationStep()

        finalizar(controles)
        for agente in agentes.values():
            agente.decay_exploration()
        guardar_modelos()

        with open(ARCHIVO_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for tls_id in activos:
                c = controles[tls_id]
                prom = (
                    c["recompensa_total"] / c["recompensas_aprendidas"]
                    if c["recompensas_aprendidas"] > 0 else 0
                )
                w.writerow([
                    numero, tls_id, c["decisiones"], c["cambios"],
                    prom, agentes[tls_id].epsilon,
                ])
            f.flush()
        print(f"  {len(activos)} semaforos controlados. Modelos guardados.")
    finally:
        traci.close()


def entrenar():
    ultimo = recuperar()
    print("\n" + "=" * 55)
    print("ENTRENAMIENTO GENERICO (19 intersecciones)")
    print(f"Semaforos controlables: {len(SEMAFOROS)}")
    print(f"Episodios objetivo: {EPISODIOS} | completados: {ultimo}")
    print("=" * 55)
    if ultimo >= EPISODIOS:
        print("\nYa esta completo.")
        return
    try:
        for n in range(ultimo + 1, EPISODIOS + 1):
            ejecutar_episodio(n)
    except KeyboardInterrupt:
        print("\nInterrumpido. Episodios guardados.")
        return
    print("\n" + "=" * 55)
    print("ENTRENAMIENTO GENERICO FINALIZADO")
    print(f"Modelos: {PREFIJO_MODELO}<id>.pkl  |  Resultados: {ARCHIVO_CSV}")
    print("=" * 55)


if __name__ == "__main__":
    entrenar()
