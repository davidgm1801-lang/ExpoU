"""
==================================================================
ENTRENAMIENTO GENERICO COORDINADO - 18 intersecciones (ExpoU)
==================================================================

Entrena un agente por semaforo controlable (como train_generico.py)
PERO con coordinacion: cada agente observa la presion del vecino al
que vierte el grupo activo, y la recompensa penaliza alimentar a un
vecino saturado. Combina cobertura (18) + coordinacion (Etapa 4).

Requiere: autodetectar_semaforos.py ejecutado (el JSON ahora incluye,
por grupo, el campo "vecino").

Modelos: q_table_gencoord_<id>.pkl  |  CSV: resultados_entrenamiento_gencoord.csv
Episodios: EPISODIOS_GENCOORD (por defecto 50).

Ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\train_generico_coord.py
==================================================================
"""

import os
import csv
import json
import random
import traci
import sumolib

from agents.generic_coordinated_agent import GenericCoordinatedAgent


CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556
EPISODIOS = int(os.environ.get("EPISODIOS_GENCOORD", "50"))
SEMILLA_BASE = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50
UMBRAL_PRESION_VECINO = 4
PENALIZACION_VECINO = 2.0

ARCHIVO_JSON = "config_auto_semaforos.json"
ARCHIVO_CSV = "resultados_entrenamiento_gencoord.csv"
PREFIJO_MODELO = "q_table_gencoord_"


def cargar_config():
    if not os.path.exists(ARCHIVO_JSON):
        raise FileNotFoundError(
            f"No existe {ARCHIVO_JSON}. Ejecuta autodetectar_semaforos.py "
            "(version con vecindad)."
        )
    with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


SEMAFOROS = cargar_config()
ARCHIVOS_MODELO = {tid: f"{PREFIJO_MODELO}{tid}.pkl" for tid in SEMAFOROS}
agentes = {tid: GenericCoordinatedAgent() for tid in SEMAFOROS}


# ==================================================
# COLAS, VECINDAD, ESTADO
# ==================================================

def colas_por_grupo(tls_id):
    colas = []
    for grupo in SEMAFOROS[tls_id]["grupos"]:
        colas.append(sum(
            traci.lane.getLastStepHaltingNumber(c)
            for c in grupo["carriles"]
        ))
    return colas


def cola_total_tls(tls_id):
    return sum(colas_por_grupo(tls_id))


def indice_grupo_activo(tls_id):
    fase = traci.trafficlight.getPhase(tls_id)
    for idx, g in enumerate(SEMAFOROS[tls_id]["grupos"]):
        if g["fase"] == fase:
            return idx
    return None


def presion_vecino(tls_id, idx_grupo):
    """1 si el vecino al que vierte el grupo activo esta congestionado."""
    grupo = SEMAFOROS[tls_id]["grupos"][idx_grupo]
    vecino = grupo.get("vecino")
    if not vecino or vecino not in SEMAFOROS:
        return 0
    return 1 if cola_total_tls(vecino) >= UMBRAL_PRESION_VECINO else 0


def estado_de(tls_id, idx, colas):
    cola_activo = colas[idx]
    otros = [c for i, c in enumerate(colas) if i != idx]
    pv = presion_vecino(tls_id, idx)
    return agentes[tls_id].get_state(
        cola_activo, max(otros) if otros else 0, idx, pv
    )


def calcular_recompensa(tls_id, colas, idx):
    total = sum(colas)
    desequilibrio = (max(colas) - min(colas)) if colas else 0
    r = -total - 0.25 * desequilibrio
    # Penalizar si el grupo activo vierte a un vecino saturado.
    if presion_vecino(tls_id, idx) == 1:
        r -= PENALIZACION_VECINO
    return r


# ==================================================
# CONTROL (igual mecanica que train_generico)
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
        dur = 100000 if i in fases_verdes else fase.duration
        nuevas.append(
            traci.trafficlight.Phase(dur, fase.state, name=fase.name)
        )
    traci.trafficlight.setProgramLogic(
        tls_id, traci.trafficlight.Logic("rl_agent", 0, 0, nuevas)
    )
    traci.trafficlight.setProgram(tls_id, "rl_agent")
    traci.trafficlight.setPhase(
        tls_id, SEMAFOROS[tls_id]["grupos"][0]["fase"]
    )


def nuevo_control():
    return {
        "inicio_verde": 0, "proxima_decision": TIEMPO_MINIMO_VERDE,
        "pendiente": None, "decisiones": 0, "cambios": 0,
        "recompensa_total": 0.0, "recompensas_aprendidas": 0,
    }


def aprender_transicion(tls_id, control, nuevo_estado, done):
    pend = control["pendiente"]
    if pend is None:
        return
    r = (pend["recompensa_total"] / pend["muestras"]
         if pend["muestras"] > 0 else 0)
    agentes[tls_id].learn(
        pend["estado"], pend["accion"], r, nuevo_estado, done=done
    )
    control["decisiones"] += 1
    control["recompensa_total"] += r
    control["recompensas_aprendidas"] += 1
    control["pendiente"] = None


def avanzar(tls_id):
    fase = traci.trafficlight.getPhase(tls_id)
    n = SEMAFOROS[tls_id]["n_fases"]
    traci.trafficlight.setPhase(tls_id, (fase + 1) % n)


def controlar(tls_id, control, t):
    idx = indice_grupo_activo(tls_id)

    pend = control["pendiente"]
    if pend is not None:
        colas = colas_por_grupo(tls_id)
        idx_recomp = idx if idx is not None else pend["idx"]
        pend["recompensa_total"] += calcular_recompensa(tls_id, colas, idx_recomp)
        pend["muestras"] += 1
        if idx is not None:
            if pend["accion"] == 0:
                if t - pend["tiempo_inicio"] >= INTERVALO_DECISION:
                    aprender_transicion(
                        tls_id, control, estado_de(tls_id, idx, colas), False
                    )
                    control["proxima_decision"] = t + INTERVALO_DECISION
            else:
                if idx != pend["idx"]:
                    aprender_transicion(
                        tls_id, control, estado_de(tls_id, idx, colas), False
                    )
                    control["inicio_verde"] = t
                    control["proxima_decision"] = t + TIEMPO_MINIMO_VERDE

    if idx is None:
        return
    if control["pendiente"] is not None:
        return
    if t < control["proxima_decision"]:
        return

    colas = colas_por_grupo(tls_id)
    estado = estado_de(tls_id, idx, colas)
    accion = agentes[tls_id].choose_action(estado)

    if t - control["inicio_verde"] >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    control["pendiente"] = {
        "estado": estado, "accion": accion, "idx": idx,
        "tiempo_inicio": t, "recompensa_total": 0.0, "muestras": 0,
    }

    if accion == 1:
        avanzar(tls_id)
        control["cambios"] += 1


def finalizar(controles):
    for tls_id in SEMAFOROS:
        control = controles[tls_id]
        if control["pendiente"] is None:
            continue
        colas = colas_por_grupo(tls_id)
        pend = control["pendiente"]
        idx = indice_grupo_activo(tls_id)
        if idx is None:
            idx = pend["idx"]
        pend["recompensa_total"] += calcular_recompensa(tls_id, colas, idx)
        pend["muestras"] += 1
        aprender_transicion(
            tls_id, control, estado_de(tls_id, idx, colas), True
        )


def guardar_modelos():
    for tid, agente in agentes.items():
        agente.save(ARCHIVOS_MODELO[tid])


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


def ejecutar_episodio(numero):
    semilla = SEMILLA_BASE + numero - 1
    random.seed(semilla)
    print("\n" + "=" * 55)
    print(f"EPISODIO {numero}/{EPISODIOS} (gen-coord) | Semilla {semilla}")
    print("=" * 55)

    traci.start([
        SUMO, "-c", CONFIG, "--end", str(DURACION),
        "--seed", str(semilla), "--no-step-log", "true",
        "--scale", ESCALA_TRAFICO,
    ])
    try:
        disponibles = traci.trafficlight.getIDList()
        activos = [t for t in SEMAFOROS if t in disponibles]
        for tls_id in activos:
            instalar_programa(tls_id)
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
                prom = (c["recompensa_total"] / c["recompensas_aprendidas"]
                        if c["recompensas_aprendidas"] > 0 else 0)
                w.writerow([
                    numero, tls_id, c["decisiones"], c["cambios"],
                    prom, agentes[tls_id].epsilon,
                ])
            f.flush()
        print(f"  {len(activos)} semaforos coordinados. Modelos guardados.")
    finally:
        traci.close()


def entrenar():
    ultimo = recuperar()
    print("\n" + "=" * 55)
    print("ENTRENAMIENTO GENERICO COORDINADO (18 intersecciones)")
    print(f"Semaforos: {len(SEMAFOROS)} | con vecino: "
          f"{sum(1 for d in SEMAFOROS.values() for g in d['grupos'] if g.get('vecino'))} grupos")
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
    print("ENTRENAMIENTO GEN-COORD FINALIZADO")
    print(f"Modelos: {PREFIJO_MODELO}<id>.pkl  |  CSV: {ARCHIVO_CSV}")
    print("=" * 55)


if __name__ == "__main__":
    entrenar()
