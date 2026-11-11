"""
==================================================================
LOCALIZAR TELEPORTS POR SEMAFORO - Etapa 3 (ExpoU)
==================================================================

Proposito
---------
La Etapa 2 mostro que la politica de IA es INESTABLE: supera al
baseline en 3 de 5 semillas, pero COLAPSA en 2 (semillas 42 y 44),
con un fuerte aumento de teleports por atasco.

El evaluador de la Etapa 2 solo cuenta teleports GLOBALES. Esta
herramienta de DIAGNOSTICO los atribuye al carril/semaforo donde el
vehiculo estaba JUSTO ANTES de ser teletransportado, para responder:

    ¿En que interseccion(es) se rompe la politica de IA?

Metodo
------
En cada paso se consulta traci.simulation.getStartingTeleportIDList()
(vehiculos que EMPIEZAN a teletransportarse en ese paso). Para cada
uno se obtiene su carril actual (getLaneID) y se atribuye:
  - al semaforo que controla ese carril de entrada, si coincide; o
  - a "otros" si el carril no pertenece a ningun semaforo monitoreado.

NO modifica ni guarda tablas Q. Solo lee los modelos independientes.

Como ejecutar (Windows, .venv activo, dentro de ExpoU):

    python .\\localizar_teleports.py

Por defecto corre AMBOS brazos (baseline e IA) en las semillas
42, 44 (malas) y 45 (buena, de control). Genera
'teleports_por_semaforo.csv' y un resumen por consola.
==================================================================
"""

import os
import csv
import pickle

import traci
import sumolib


# ==================================================
# CONFIGURACION
# ==================================================

CONFIG = os.path.join("sumo_bogota", "osm.sumocfg")

DURACION = 4556
ESCALA_TRAFICO = "2"

# Semillas a diagnosticar: dos "malas" (colapso de IA) y una "buena".
SEMILLAS = [42, 44, 45]

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

SUMO = sumolib.checkBinary("sumo")

ARCHIVO_RESULTADOS = "teleports_por_semaforo.csv"


# ==================================================
# SEMAFOROS Y CARRILES (verificados en Etapa 1)
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

ARCHIVOS_MODELO = {
    tls_id: f"q_table_independiente_{tls_id}.pkl"
    for tls_id in SEMAFOROS
}

# Mapa inverso: carril de entrada -> tls_id. Sirve para atribuir un
# teleport al semaforo cuyo carril monitoreado coincide.
CARRIL_A_TLS = {}
for _tls, _grupos in SEMAFOROS.items():
    for _grupo, _carriles in _grupos.items():
        for _c in _carriles:
            CARRIL_A_TLS[_c] = _tls

# Tambien registramos los BORDES (edges) de cada carril, porque un
# vehiculo atascado puede estar en el borde aunque no exactamente en
# el carril _0/_1 listado. El edge es la parte antes de "_".
BORDE_A_TLS = {}
for _c, _tls in CARRIL_A_TLS.items():
    _edge = _c.rsplit("_", 1)[0]
    BORDE_A_TLS[_edge] = _tls


# ==================================================
# AGENTE SOLO-LECTURA (epsilon = 0)
# ==================================================

class AgenteEvaluacion:
    def __init__(self, ruta_modelo):
        with open(ruta_modelo, "rb") as f:
            datos = pickle.load(f)
        self.q_table = datos["q_table"]
        if not self.q_table:
            raise RuntimeError(f"Tabla Q vacia: {ruta_modelo}")

    @staticmethod
    def clasificar_cola(cola):
        if cola == 0:
            return 0
        elif cola <= 3:
            return 1
        else:
            return 2

    def get_state(self, cola_a, cola_b, grupo_verde):
        return (
            self.clasificar_cola(cola_a),
            self.clasificar_cola(cola_b),
            grupo_verde,
        )

    def elegir_accion(self, estado):
        if estado not in self.q_table:
            return 0
        v = self.q_table[estado]
        return 0 if v[0] >= v[1] else 1


# ==================================================
# CONTROL (igual que en evaluar_etapa2.py)
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


def nuevo_control():
    return {
        "inicio_verde": 0,
        "siguiente_decision": 0,
        "fase_anterior": 0,
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
    estado = agente.get_state(cola_a, cola_b, grupo_verde)
    accion = agente.elegir_accion(estado)

    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    if accion == 1:
        traci.trafficlight.setPhase(tls_id, fase + 1)
        control["fase_anterior"] = fase + 1
    else:
        control["siguiente_decision"] = t + INTERVALO_DECISION


# ==================================================
# ATRIBUIR UN TELEPORT A UN SEMAFORO
# ==================================================

def atribuir_teleport(vehiculo_id):
    """
    Devuelve el tls_id al que corresponde el carril donde esta el
    vehiculo que empieza a teletransportarse, o 'otros' si no
    pertenece a ningun semaforo monitoreado.
    """
    try:
        carril = traci.vehicle.getLaneID(vehiculo_id)
    except traci.TraCIException:
        return "otros"

    if not carril:
        return "otros"

    # Coincidencia exacta por carril.
    if carril in CARRIL_A_TLS:
        return CARRIL_A_TLS[carril]

    # Coincidencia por borde (edge) sin el sufijo de carril.
    edge = carril.rsplit("_", 1)[0]
    if edge in BORDE_A_TLS:
        return BORDE_A_TLS[edge]

    return "otros"


# ==================================================
# UNA CORRIDA CON CONTEO DE TELEPORTS POR SEMAFORO
# ==================================================

def ejecutar_corrida(brazo, semilla):
    agentes = {}
    controles = {}
    if brazo == "ia":
        for tls_id in SEMAFOROS:
            agentes[tls_id] = AgenteEvaluacion(ARCHIVOS_MODELO[tls_id])
            controles[tls_id] = nuevo_control()

    # Contadores de teleports por semaforo + "otros".
    conteo = {tls_id: 0 for tls_id in SEMAFOROS}
    conteo["otros"] = 0
    total = 0

    comando = [
        SUMO,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(semilla),
        "--scale", ESCALA_TRAFICO,
        "--no-step-log", "true",
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
            # IMPORTANTE: atribuir ANTES del step, mientras el
            # vehiculo aun tiene carril valido. getStartingTeleportIDList
            # reporta los que empiezan a teletransportarse en el paso
            # recien simulado.
            for vid in traci.simulation.getStartingTeleportIDList():
                conteo[atribuir_teleport(vid)] += 1
                total += 1

            traci.simulationStep()

            if brazo == "ia":
                for tls_id in SEMAFOROS:
                    controlar_semaforo_ia(
                        tls_id, agentes[tls_id], controles[tls_id]
                    )

        # Capturar teleports del ultimo paso.
        for vid in traci.simulation.getStartingTeleportIDList():
            conteo[atribuir_teleport(vid)] += 1
            total += 1

    finally:
        traci.close()

    conteo["total"] = total
    return conteo


# ==================================================
# PROGRAMA PRINCIPAL
# ==================================================

def main():
    print("=" * 64)
    print("LOCALIZACION DE TELEPORTS POR SEMAFORO - Etapa 3")
    print("=" * 64)
    print(f"Semillas: {SEMILLAS}")

    orden_tls = list(SEMAFOROS.keys()) + ["otros", "total"]
    campos = ["brazo", "semilla"] + orden_tls

    filas = []

    for brazo in ("baseline", "ia"):
        for semilla in SEMILLAS:
            print(f"\n-> {brazo} | semilla {semilla} ...")
            conteo = ejecutar_corrida(brazo, semilla)
            fila = {"brazo": brazo, "semilla": semilla}
            fila.update(conteo)
            filas.append(fila)
            resumen = " | ".join(
                f"{tls}={conteo[tls]}" for tls in orden_tls
            )
            print(f"   {resumen}")

    with open(
        ARCHIVO_RESULTADOS, "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for fila in filas:
            w.writerow(fila)

    print("\n" + "=" * 64)
    print(f"Resultados guardados en: {ARCHIVO_RESULTADOS}")
    print("=" * 64)

    # Comparacion rapida baseline vs IA por semaforo.
    print("\nTELEPORTS POR SEMAFORO (baseline -> IA), por semilla:")
    for semilla in SEMILLAS:
        b = next(
            x for x in filas
            if x["brazo"] == "baseline" and x["semilla"] == semilla
        )
        i = next(
            x for x in filas
            if x["brazo"] == "ia" and x["semilla"] == semilla
        )
        print(f"\n  Semilla {semilla}:")
        for tls in orden_tls:
            delta = i[tls] - b[tls]
            marca = "  <== aumenta con IA" if delta > 0 else ""
            print(
                f"    {tls:<12} {b[tls]:>5} -> {i[tls]:>5} "
                f"(delta {delta:+d}){marca}"
            )


if __name__ == "__main__":
    main()
