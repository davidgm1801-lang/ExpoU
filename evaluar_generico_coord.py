"""
==================================================================
EVALUACION GENERICA COORDINADA - 18 intersecciones (ExpoU)
==================================================================

Evalua los agentes genericos coordinados (q_table_gencoord_<id>.pkl)
que controlan todos los semaforos controlables, frente al baseline de
SUMO. Misma metodologia: 5 semillas (42-46), epsilon=0, headless.
Genera 'evaluacion_generico_coord.csv'.

Requiere: autodetectar_semaforos.py y train_generico_coord.py.

Ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\evaluar_generico_coord.py
==================================================================
"""

import os
import csv
import json
import xml.etree.ElementTree as ET

import traci
import sumolib

from agents.generic_coordinated_agent import GenericCoordinatedAgent


CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556
ESCALA_TRAFICO = "2"
SEMILLAS = [42, 43, 44, 45, 46]

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50
UMBRAL_PRESION_VECINO = 4

ARCHIVO_JSON = "config_auto_semaforos.json"
PREFIJO_MODELO = "q_table_gencoord_"
ARCHIVO_RESULTADOS = "evaluacion_generico_coord.csv"
DIR_SALIDAS = "salidas_evaluacion"


with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
    SEMAFOROS = json.load(f)
ARCHIVOS_MODELO = {tid: f"{PREFIJO_MODELO}{tid}.pkl" for tid in SEMAFOROS}


def colas_por_grupo(tls_id):
    return [
        sum(traci.lane.getLastStepHaltingNumber(c) for c in g["carriles"])
        for g in SEMAFOROS[tls_id]["grupos"]
    ]


def cola_total_tls(tls_id):
    return sum(colas_por_grupo(tls_id))


def indice_grupo_activo(tls_id):
    fase = traci.trafficlight.getPhase(tls_id)
    for idx, g in enumerate(SEMAFOROS[tls_id]["grupos"]):
        if g["fase"] == fase:
            return idx
    return None


def presion_vecino(tls_id, idx):
    vecino = SEMAFOROS[tls_id]["grupos"][idx].get("vecino")
    if not vecino or vecino not in SEMAFOROS:
        return 0
    return 1 if cola_total_tls(vecino) >= UMBRAL_PRESION_VECINO else 0


def estado_de(agente, tls_id, idx, colas):
    cola_activo = colas[idx]
    otros = [c for i, c in enumerate(colas) if i != idx]
    pv = presion_vecino(tls_id, idx)
    return agente.get_state(cola_activo, max(otros) if otros else 0, idx, pv)


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
    traci.trafficlight.setPhase(tls_id, SEMAFOROS[tls_id]["grupos"][0]["fase"])


def nuevo_control():
    return {
        "inicio_verde": 0, "proxima_decision": TIEMPO_MINIMO_VERDE,
        "idx_prev": None, "cola_total": 0.0, "cola_maxima": 0, "muestras": 0,
    }


def avanzar(tls_id):
    fase = traci.trafficlight.getPhase(tls_id)
    n = SEMAFOROS[tls_id]["n_fases"]
    traci.trafficlight.setPhase(tls_id, (fase + 1) % n)


def controlar_ia(tls_id, agente, control, t):
    idx = indice_grupo_activo(tls_id)
    if idx is None:
        return
    if control["idx_prev"] is None or control["idx_prev"] != idx:
        control["inicio_verde"] = t
        control["proxima_decision"] = t + TIEMPO_MINIMO_VERDE
        control["idx_prev"] = idx
    if t < control["proxima_decision"]:
        return
    colas = colas_por_grupo(tls_id)
    estado = estado_de(agente, tls_id, idx, colas)
    accion = agente.best_action(estado)
    total = sum(colas)
    control["cola_total"] += total
    control["muestras"] += 1
    control["cola_maxima"] = max(control["cola_maxima"], total)
    if t - control["inicio_verde"] >= TIEMPO_MAXIMO_VERDE:
        accion = 1
    if accion == 1:
        avanzar(tls_id)
        control["idx_prev"] = None
    else:
        control["proxima_decision"] = t + INTERVALO_DECISION


def medir_baseline(tls_id, control):
    total = cola_total_tls(tls_id)
    control["cola_total"] += total
    control["muestras"] += 1
    control["cola_maxima"] = max(control["cola_maxima"], total)


def ejecutar_corrida(brazo, semilla, prefijo):
    archivo_trip = f"{prefijo}_tripinfos.xml"
    archivo_stats = f"{prefijo}_stats.xml"
    agentes = {}
    if brazo == "ia":
        for tid in SEMAFOROS:
            a = GenericCoordinatedAgent()
            a.load(ARCHIVOS_MODELO[tid])
            a.epsilon = 0
            agentes[tid] = a
    controles = {tid: nuevo_control() for tid in SEMAFOROS}

    traci.start([
        SUMO, "-c", CONFIG, "--end", str(DURACION),
        "--seed", str(semilla), "--scale", ESCALA_TRAFICO,
        "--no-step-log", "true", "--duration-log.statistics", "true",
        "--tripinfo-output", archivo_trip, "--statistic-output", archivo_stats,
    ])
    try:
        disponibles = set(traci.trafficlight.getIDList())
        activos = [t for t in SEMAFOROS if t in disponibles]
        if brazo == "ia":
            for tid in activos:
                instalar_programa(tid)
        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):
            traci.simulationStep()
            t = traci.simulation.getTime()
            for tid in activos:
                if brazo == "ia":
                    controlar_ia(tid, agentes[tid], controles[tid], t)
                else:
                    medir_baseline(tid, controles[tid])
    finally:
        traci.close()

    m = leer_metricas(archivo_trip, archivo_stats)
    cola_prom = sum(
        (c["cola_total"] / c["muestras"] if c["muestras"] else 0)
        for c in controles.values()
    )
    cola_max = max((c["cola_maxima"] for c in controles.values()), default=0)
    m["cola_promedio_suma_tls"] = round(cola_prom, 3)
    m["cola_maxima_global"] = cola_max
    return m


def leer_metricas(archivo_trip, archivo_stats):
    m = {
        "completados": 0, "espera_promedio": 0.0, "duracion_promedio": 0.0,
        "timeloss_promedio": 0.0, "velocidad_promedio": 0.0,
        "teleports_total": 0, "teleports_jam": 0, "teleports_yield": 0,
        "teleports_wronglane": 0, "colisiones": 0, "cargados": 0, "insertados": 0,
    }
    if os.path.exists(archivo_trip):
        v = ET.parse(archivo_trip).getroot().findall("tripinfo")
        n = len(v)
        if n:
            m["completados"] = n
            m["espera_promedio"] = round(sum(float(x.get("waitingTime", 0)) for x in v) / n, 3)
            m["duracion_promedio"] = round(sum(float(x.get("duration", 0)) for x in v) / n, 3)
            m["timeloss_promedio"] = round(sum(float(x.get("timeLoss", 0)) for x in v) / n, 3)
            dur = sum(float(x.get("duration", 0)) for x in v)
            dist = sum(float(x.get("routeLength", 0)) for x in v)
            m["velocidad_promedio"] = round(dist / dur if dur else 0, 3)
    if os.path.exists(archivo_stats):
        raiz = ET.parse(archivo_stats).getroot()
        veh = raiz.find("vehicles")
        if veh is not None:
            m["cargados"] = int(veh.get("loaded", 0))
            m["insertados"] = int(veh.get("inserted", 0))
        tele = raiz.find("teleports")
        if tele is not None:
            m["teleports_total"] = int(tele.get("total", 0))
            m["teleports_jam"] = int(tele.get("jam", 0))
            m["teleports_yield"] = int(tele.get("yield", 0))
            m["teleports_wronglane"] = int(tele.get("wrongLane", 0))
        safety = raiz.find("safety")
        if safety is not None:
            m["colisiones"] = int(safety.get("collisions", 0))
    return m


CAMPOS = [
    "brazo", "semilla", "completados", "espera_promedio",
    "duracion_promedio", "timeloss_promedio", "velocidad_promedio",
    "cola_promedio_suma_tls", "cola_maxima_global",
    "teleports_total", "teleports_jam", "teleports_yield",
    "teleports_wronglane", "colisiones", "cargados", "insertados",
]


def promedio(vals):
    return sum(vals) / len(vals) if vals else 0.0


def main():
    print("=" * 64)
    print("EVALUACION GENERICA COORDINADA - 18 vs baseline")
    print(f"Semaforos: {len(SEMAFOROS)} | Semillas: {SEMILLAS}")
    print(f"Salida: {ARCHIVO_RESULTADOS}")
    print("=" * 64)

    os.makedirs(DIR_SALIDAS, exist_ok=True)
    filas = []
    for brazo in ("baseline", "ia"):
        for s in SEMILLAS:
            print(f"\n-> {brazo} | semilla {s} ...")
            pref = os.path.join(DIR_SALIDAS, f"gencoord_{brazo}_semilla{s}")
            m = ejecutar_corrida(brazo, s, pref)
            fila = {"brazo": brazo, "semilla": s}
            fila.update(m)
            filas.append(fila)
            print(f"   completados={m['completados']} "
                  f"espera={m['espera_promedio']} teleports={m['teleports_total']}")

    with open(ARCHIVO_RESULTADOS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for fila in filas:
            w.writerow(fila)

    base = [f for f in filas if f["brazo"] == "baseline"]
    ia = [f for f in filas if f["brazo"] == "ia"]
    print("\n" + "=" * 64)
    print("RESUMEN (promedio sobre semillas)")
    print("=" * 64)
    for col, nom, sent in [
        ("completados", "Completados", "mas"),
        ("espera_promedio", "Espera (s)", "menos"),
        ("duracion_promedio", "Duracion (s)", "menos"),
        ("timeloss_promedio", "Time loss (s)", "menos"),
        ("teleports_total", "Teleports", "menos"),
    ]:
        b = promedio([f[col] for f in base])
        i = promedio([f[col] for f in ia])
        gana = sum(
            1 for s in SEMILLAS
            if (lambda fb, fi: (fi[col] > fb[col]) if sent == "mas"
                else (fi[col] < fb[col]))(
                next(f for f in base if f["semilla"] == s),
                next(f for f in ia if f["semilla"] == s))
        )
        print(f"  {nom:<16} base={b:>9.2f}  IA={i:>9.2f}  (IA gana {gana}/5)")
    print("\nNOTA: comparar par-a-par; teleports son limitacion de SUMO.")


if __name__ == "__main__":
    main()
