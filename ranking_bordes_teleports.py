"""
==================================================================
RANKING DE BORDES CON MAS TELEPORTS - Etapa 3 (ExpoU)
==================================================================

Proposito
---------
El diagnostico anterior (localizar_teleports.py) mostro que el
colapso de la IA en las semillas 42 y 44 NO ocurre en los carriles
de los 5 semaforos controlados, sino en "otros" (resto de la red).

Esta herramienta responde la pregunta siguiente:

    ¿En QUE bordes concretos de la red se concentran esos teleports,
    y estan esos bordes AGUAS ABAJO de las intersecciones controladas?

Si los bordes mas afectados son salidas (o descendientes cercanos) de
los 5 semaforos, se confirma la hipotesis de "spillover": la IA deja
pasar mas trafico que luego satura zonas no controladas.

Metodo
------
En cada paso consulta getStartingTeleportIDList() y registra el BORDE
(edge) donde esta cada vehiculo justo antes de teletransportarse.
Produce un ranking de bordes por numero de teleports, para baseline e
IA, y marca los bordes que son SALIDA DIRECTA de alguno de los 5
semaforos (segun getControlledLinks, visto en la Etapa 1).

NO modifica ni guarda tablas Q. Solo lee los modelos.

Como ejecutar (Windows, .venv activo, dentro de ExpoU):

    python .\\ranking_bordes_teleports.py

Genera 'ranking_bordes_teleports.csv' y un resumen por consola con el
TOP de bordes de cada brazo/semilla.
==================================================================
"""

import os
import csv
import pickle
from collections import defaultdict

import traci
import sumolib


# ==================================================
# CONFIGURACION
# ==================================================

CONFIG = os.path.join("sumo_bogota", "osm.sumocfg")

DURACION = 4556
ESCALA_TRAFICO = "2"

SEMILLAS = [42, 44, 45]

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

SUMO = sumolib.checkBinary("sumo")

ARCHIVO_RESULTADOS = "ranking_bordes_teleports.csv"
TOP_N = 15  # cuantos bordes mostrar en el ranking de consola


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

# Bordes de ENTRADA de los 5 semaforos (parte del carril antes de "_").
BORDES_ENTRADA = set()
for _g in SEMAFOROS.values():
    for _carriles in _g.values():
        for _c in _carriles:
            BORDES_ENTRADA.add(_c.rsplit("_", 1)[0])

# Bordes de SALIDA DIRECTA de los 5 semaforos (de getControlledLinks,
# inspeccion de la Etapa 1). Edge = parte antes de "_".
BORDES_SALIDA = {
    # 262567760
    "88757025#0", "88861379#0",
    # 262567775
    "961101065#0", "1083001228#0",
    # 262567777
    "1083001225#0", "915587469#0",
    # 264377450
    "1083001234#0", "88756929",
    # 265804326
    "1174580781#0", "66953367#0",
}


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
# CONTROL IA
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
# OBTENER EL BORDE DE UN VEHICULO
# ==================================================

def borde_de_vehiculo(vid):
    try:
        carril = traci.vehicle.getLaneID(vid)
    except traci.TraCIException:
        return None
    if not carril:
        return None
    # Carriles internos de intersecciones empiezan por ":".
    if carril.startswith(":"):
        return carril  # lo dejamos como interno
    return carril.rsplit("_", 1)[0]


# ==================================================
# UNA CORRIDA: cuenta teleports por BORDE
# ==================================================

def ejecutar_corrida(brazo, semilla):
    agentes = {}
    controles = {}
    if brazo == "ia":
        for tls_id in SEMAFOROS:
            agentes[tls_id] = AgenteEvaluacion(ARCHIVOS_MODELO[tls_id])
            controles[tls_id] = nuevo_control()

    conteo = defaultdict(int)
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
            for vid in traci.simulation.getStartingTeleportIDList():
                b = borde_de_vehiculo(vid)
                if b is not None:
                    conteo[b] += 1
                total += 1

            traci.simulationStep()

            if brazo == "ia":
                for tls_id in SEMAFOROS:
                    controlar_semaforo_ia(
                        tls_id, agentes[tls_id], controles[tls_id]
                    )

        for vid in traci.simulation.getStartingTeleportIDList():
            b = borde_de_vehiculo(vid)
            if b is not None:
                conteo[b] += 1
            total += 1

    finally:
        traci.close()

    return dict(conteo), total


# ==================================================
# CLASIFICAR UN BORDE RESPECTO A LOS 5 SEMAFOROS
# ==================================================

def clasificar_borde(borde):
    if borde in BORDES_SALIDA:
        return "SALIDA de TLS"
    if borde in BORDES_ENTRADA:
        return "ENTRADA de TLS"
    if borde.startswith(":"):
        return "interno"
    return "red no controlada"


# ==================================================
# PRINCIPAL
# ==================================================

def main():
    print("=" * 66)
    print("RANKING DE BORDES CON MAS TELEPORTS - Etapa 3")
    print("=" * 66)
    print(f"Semillas: {SEMILLAS}")

    filas = []
    resultados = {}

    for brazo in ("baseline", "ia"):
        for semilla in SEMILLAS:
            print(f"\n-> {brazo} | semilla {semilla} ...")
            conteo, total = ejecutar_corrida(brazo, semilla)
            resultados[(brazo, semilla)] = (conteo, total)
            print(f"   total teleports = {total}, "
                  f"bordes distintos = {len(conteo)}")

            for borde, n in conteo.items():
                filas.append({
                    "brazo": brazo,
                    "semilla": semilla,
                    "borde": borde,
                    "teleports": n,
                    "clase": clasificar_borde(borde),
                })

    # Guardar CSV completo.
    with open(
        ARCHIVO_RESULTADOS, "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(
            f, fieldnames=["brazo", "semilla", "borde", "teleports", "clase"]
        )
        w.writeheader()
        # Ordenar por brazo, semilla, teleports desc.
        for fila in sorted(
            filas,
            key=lambda x: (x["brazo"], x["semilla"], -x["teleports"]),
        ):
            w.writerow(fila)

    print("\n" + "=" * 66)
    print(f"CSV completo guardado en: {ARCHIVO_RESULTADOS}")
    print("=" * 66)

    # Resumen: TOP de bordes por corrida, con su clasificacion.
    for (brazo, semilla), (conteo, total) in sorted(resultados.items()):
        print(f"\nTOP {TOP_N} bordes | {brazo} | semilla {semilla} "
              f"(total={total}):")
        top = sorted(conteo.items(), key=lambda x: -x[1])[:TOP_N]
        for borde, n in top:
            print(f"   {n:>5}  {borde:<22} [{clasificar_borde(borde)}]")

    # Analisis de interes: cuantos teleports caen en SALIDA de TLS vs
    # red no controlada, comparando baseline e IA en semillas malas.
    print("\n" + "=" * 66)
    print("TELEPORTS POR CLASE DE BORDE (baseline -> IA)")
    print("=" * 66)
    clases = ["SALIDA de TLS", "ENTRADA de TLS", "interno",
              "red no controlada"]
    for semilla in SEMILLAS:
        print(f"\n  Semilla {semilla}:")
        cb, _ = resultados[("baseline", semilla)]
        ci, _ = resultados[("ia", semilla)]
        for clase in clases:
            sb = sum(n for b, n in cb.items()
                     if clasificar_borde(b) == clase)
            si = sum(n for b, n in ci.items()
                     if clasificar_borde(b) == clase)
            marca = "  <== aumenta con IA" if si > sb else ""
            print(f"    {clase:<20} {sb:>5} -> {si:>5} "
                  f"(delta {si - sb:+d}){marca}")


if __name__ == "__main__":
    main()
