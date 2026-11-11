"""
==================================================================
EVALUACION COORDINADA - Etapa 4 (ExpoU)
==================================================================

Evalua los agentes COORDINADOS (q_table_coord_<id>.pkl, estado con
presion de vecino) frente al baseline de SUMO, con la MISMA metodologia
de la Etapa 2: 5 semillas emparejadas (42-46), epsilon=0, headless.

Produce 'evaluacion_coordinado.csv' con las mismas columnas que
'evaluacion_etapa2.csv', para comparar directamente las tres
configuraciones:
    baseline | IA v1 (local) | IA coord (este)

NO modifica ni guarda tablas Q.

Como ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\evaluar_coordinado.py
==================================================================
"""

import os
import csv
import pickle
import xml.etree.ElementTree as ET

import traci
import sumolib

from agents.coordinated_agent import CoordinatedQLearningAgent


# ==================================================
# CONFIGURACION (identica a evaluar_etapa2.py)
# ==================================================

CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556
ESCALA_TRAFICO = "2"
SEMILLAS = [42, 43, 44, 45, 46]

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50
UMBRAL_PRESION_VECINO = 4

ARCHIVO_RESULTADOS = "evaluacion_coordinado.csv"
DIR_SALIDAS = "salidas_evaluacion"


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

ARCHIVOS_MODELO = {
    tls_id: f"q_table_coord_{tls_id}.pkl"
    for tls_id in SEMAFOROS
}

VECINO_DESTINO = {
    "262567760": {"A": ("262567775", "A")},
    "262567777": {"A": ("262567775", "B")},
    "264377450": {"B": ("265804326", "B")},
}


# ==================================================
# AGENTE SOLO-LECTURA COORDINADO
# ==================================================

class AgenteCoordEval(CoordinatedQLearningAgent):
    def __init__(self, ruta_modelo):
        super().__init__()
        with open(ruta_modelo, "rb") as f:
            datos = pickle.load(f)
        self.q_table = datos["q_table"]
        if not self.q_table:
            raise RuntimeError(f"Tabla Q vacia: {ruta_modelo}")
        self.epsilon = 0

    def elegir_accion(self, estado):
        if estado not in self.q_table:
            return 0
        v = self.q_table[estado]
        return 0 if v[0] >= v[1] else 1


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
    grupo = "A" if grupo_verde == 0 else "B"
    destinos = VECINO_DESTINO.get(tls_id, {})
    if grupo not in destinos:
        return 0
    vecino_id, _ = destinos[grupo]
    return 1 if cola_total_semaforo(vecino_id) >= UMBRAL_PRESION_VECINO else 0


def nuevo_control():
    return {
        "inicio_verde": 0,
        "siguiente_decision": 0,
        "fase_anterior": 0,
        "cola_total": 0,
        "cola_maxima": 0,
        "muestras": 0,
    }


def instalar_controlador_ia(tls_id, control):
    prog = traci.trafficlight.getProgram(tls_id)
    logica = None
    for p in traci.trafficlight.getAllProgramLogics(tls_id):
        if p.programID == prog:
            logica = p
            break
    if logica is None:
        raise RuntimeError(f"Sin programa original en {tls_id}.")
    fases = logica.phases
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
    t = traci.simulation.getTime()
    control["inicio_verde"] = t
    control["siguiente_decision"] = t + TIEMPO_MINIMO_VERDE
    control["fase_anterior"] = 0


def controlar_semaforo_ia(tls_id, agente, control):
    fase = traci.trafficlight.getPhase(tls_id)
    t = traci.simulation.getTime()

    if fase in (1, 3):
        control["fase_anterior"] = fase
        return

    if control["fase_anterior"] in (1, 3):
        control["inicio_verde"] = t
        control["siguiente_decision"] = t + INTERVALO_DECISION

    control["fase_anterior"] = fase
    tiempo_verde = t - control["inicio_verde"]

    if tiempo_verde < TIEMPO_MINIMO_VERDE:
        return
    if t < control["siguiente_decision"]:
        return

    cola_a, cola_b = obtener_colas(tls_id)
    grupo_verde = 0 if fase == 0 else 1
    pv = presion_vecino(tls_id, grupo_verde)
    estado = agente.get_state(cola_a, cola_b, grupo_verde, pv)
    accion = agente.elegir_accion(estado)

    cola_total = cola_a + cola_b
    control["cola_total"] += cola_total
    control["muestras"] += 1
    control["cola_maxima"] = max(control["cola_maxima"], cola_total)

    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    if accion == 1:
        traci.trafficlight.setPhase(tls_id, fase + 1)
        control["fase_anterior"] = fase + 1
    else:
        control["siguiente_decision"] = t + INTERVALO_DECISION


def medir_colas_baseline(tls_id, control):
    cola_a, cola_b = obtener_colas(tls_id)
    cola_total = cola_a + cola_b
    control["cola_total"] += cola_total
    control["muestras"] += 1
    control["cola_maxima"] = max(control["cola_maxima"], cola_total)


# ==================================================
# UNA CORRIDA
# ==================================================

def ejecutar_corrida(brazo, semilla, prefijo):
    archivo_trip = f"{prefijo}_tripinfos.xml"
    archivo_stats = f"{prefijo}_stats.xml"

    agentes = {}
    if brazo == "ia":
        for tls_id in SEMAFOROS:
            agentes[tls_id] = AgenteCoordEval(ARCHIVOS_MODELO[tls_id])

    controles = {tls_id: nuevo_control() for tls_id in SEMAFOROS}

    comando = [
        SUMO, "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(semilla),
        "--scale", ESCALA_TRAFICO,
        "--no-step-log", "true",
        "--duration-log.statistics", "true",
        "--tripinfo-output", archivo_trip,
        "--statistic-output", archivo_stats,
    ]

    traci.start(comando)
    try:
        disponibles = set(traci.trafficlight.getIDList())
        for tls_id in SEMAFOROS:
            if tls_id not in disponibles:
                raise RuntimeError(f"Falta el semaforo {tls_id}.")
        if brazo == "ia":
            for tls_id in SEMAFOROS:
                instalar_controlador_ia(tls_id, controles[tls_id])

        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):
            traci.simulationStep()
            for tls_id in SEMAFOROS:
                if brazo == "ia":
                    controlar_semaforo_ia(
                        tls_id, agentes[tls_id], controles[tls_id]
                    )
                else:
                    medir_colas_baseline(tls_id, controles[tls_id])
    finally:
        traci.close()

    metricas = leer_metricas(archivo_trip, archivo_stats)

    cola_prom_total = 0.0
    cola_max_total = 0
    for tls_id in SEMAFOROS:
        c = controles[tls_id]
        prom = c["cola_total"] / c["muestras"] if c["muestras"] else 0.0
        cola_prom_total += prom
        cola_max_total = max(cola_max_total, c["cola_maxima"])
    metricas["cola_promedio_suma_5tls"] = round(cola_prom_total, 3)
    metricas["cola_maxima_global"] = cola_max_total

    return metricas


def leer_metricas(archivo_trip, archivo_stats):
    m = {
        "completados": 0, "espera_promedio": 0.0,
        "duracion_promedio": 0.0, "timeloss_promedio": 0.0,
        "velocidad_promedio": 0.0, "teleports_total": 0,
        "teleports_jam": 0, "teleports_yield": 0,
        "teleports_wronglane": 0, "colisiones": 0,
        "cargados": 0, "insertados": 0,
    }

    if os.path.exists(archivo_trip):
        viajes = ET.parse(archivo_trip).getroot().findall("tripinfo")
        n = len(viajes)
        if n > 0:
            espera = sum(float(v.get("waitingTime", 0)) for v in viajes)
            dur = sum(float(v.get("duration", 0)) for v in viajes)
            tl = sum(float(v.get("timeLoss", 0)) for v in viajes)
            dist = sum(float(v.get("routeLength", 0)) for v in viajes)
            m["completados"] = n
            m["espera_promedio"] = round(espera / n, 3)
            m["duracion_promedio"] = round(dur / n, 3)
            m["timeloss_promedio"] = round(tl / n, 3)
            m["velocidad_promedio"] = round(dist / dur if dur > 0 else 0, 3)

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


CAMPOS_CSV = [
    "brazo", "semilla", "completados", "espera_promedio",
    "duracion_promedio", "timeloss_promedio", "velocidad_promedio",
    "cola_promedio_suma_5tls", "cola_maxima_global",
    "teleports_total", "teleports_jam", "teleports_yield",
    "teleports_wronglane", "colisiones", "cargados", "insertados",
]


def promedio(vals):
    return sum(vals) / len(vals) if vals else 0.0


def main():
    print("=" * 64)
    print("EVALUACION COORDINADA (Etapa 4) - Baseline vs IA coord")
    print("=" * 64)
    print(f"Modelos: q_table_coord_<id>.pkl")
    print(f"Semillas: {SEMILLAS} | Salida: {ARCHIVO_RESULTADOS}")

    os.makedirs(DIR_SALIDAS, exist_ok=True)
    filas = []

    for brazo in ("baseline", "ia"):
        for semilla in SEMILLAS:
            print(f"\n-> {brazo} | semilla {semilla} ...")
            prefijo = os.path.join(
                DIR_SALIDAS, f"coord_{brazo}_semilla{semilla}"
            )
            m = ejecutar_corrida(brazo, semilla, prefijo)
            fila = {"brazo": brazo, "semilla": semilla}
            fila.update(m)
            filas.append(fila)
            print(
                f"   completados={m['completados']} "
                f"espera={m['espera_promedio']} "
                f"teleports={m['teleports_total']}"
            )

    with open(ARCHIVO_RESULTADOS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        w.writeheader()
        for fila in filas:
            w.writerow(fila)

    print("\n" + "=" * 64)
    print(f"Resultados en: {ARCHIVO_RESULTADOS}")
    print("=" * 64)

    base = [f for f in filas if f["brazo"] == "baseline"]
    ia = [f for f in filas if f["brazo"] == "ia"]
    metricas = [
        ("completados", "Completados", "mas=mejor"),
        ("espera_promedio", "Espera (s)", "menos=mejor"),
        ("duracion_promedio", "Duracion (s)", "menos=mejor"),
        ("timeloss_promedio", "Time loss (s)", "menos=mejor"),
        ("velocidad_promedio", "Velocidad (m/s)", "mas=mejor"),
        ("teleports_total", "Teleports (LIMIT)", "menos=mejor"),
    ]
    print("\nRESUMEN (promedio sobre semillas):\n")
    print(f"{'Metrica':<22}{'Baseline':>12}{'IA coord':>12}   Sentido")
    print("-" * 62)
    for clave, nombre, sentido in metricas:
        b = promedio([f[clave] for f in base])
        i = promedio([f[clave] for f in ia])
        print(f"{nombre:<22}{b:>12.3f}{i:>12.3f}   {sentido}")
    print(
        "\nNOTA: comparar par-a-par por semilla (no solo promedios) y "
        "siempre junto a los teleports."
    )


if __name__ == "__main__":
    main()
