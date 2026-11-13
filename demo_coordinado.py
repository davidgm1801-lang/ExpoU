"""
==================================================================
DEMO VISUAL - 5 SEMAFOROS COORDINADOS vs FIJO (ExpoU)
==================================================================

Demostracion con ventana grafica (SUMO-GUI) de la solucion GANADORA
del proyecto: los 5 agentes Q-Learning COORDINADOS (modelos
q_table_coord_<id>.pkl), que en la evaluacion superaron al semaforo
fijo de SUMO en 5/5 semillas (mas viajes completados, menos teleports).

Permite ELEGIR el controlador y COMPARAR:

  # Modo IA coordinada (ventana grafica)
  python .\\demo_coordinado.py --modo ia

  # Modo semaforo fijo original de SUMO (ventana grafica)
  python .\\demo_coordinado.py --modo fijo

  # Comparar ambos (corre fijo e IA, sin ventana, e imprime la tabla)
  python .\\demo_coordinado.py --modo comparar

Opciones utiles:
  --semilla 42      semilla de trafico (por defecto 42)
  --delay 80        milisegundos entre pasos en la ventana (ritmo visual)
  --sin-gui         fuerza modo sin ventana (para los modos ia/fijo)

Que veras en la ventana
-----------------------
  - Los semaforos controlados cambian de fase de forma ADAPTATIVA
    (extienden el verde cuando hay cola, lo cortan cuando no), en vez
    de tiempos fijos.
  - Al final se imprime un resumen con las metricas de esa corrida.

NOTA honesta: la diferencia de rendimiento es estadistica (se aprecia
mejor en los numeros que a simple vista). Para la presentacion, combina
el video con la tabla de metricas del modo --comparar.

Requiere: modelos q_table_coord_<id>.pkl entrenados (en el repo).
==================================================================
"""

import os
import sys
import csv
import pickle
import argparse
import xml.etree.ElementTree as ET

import traci
import sumolib


CONFIG = "sumo_bogota/osm.sumocfg"

DURACION = 4556
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50
UMBRAL_PRESION_VECINO = 4


# ==================================================
# SEMAFOROS Y VECINDAD (los 5 coordinados de la Etapa 4)
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

VECINO_DESTINO = {
    "262567760": {"A": ("262567775", "A")},
    "262567777": {"A": ("262567775", "B")},
    "264377450": {"B": ("265804326", "B")},
}

ARCHIVOS_MODELO = {
    tls_id: f"q_table_coord_{tls_id}.pkl" for tls_id in SEMAFOROS
}


# ==================================================
# AGENTE COORDINADO SOLO-LECTURA (epsilon=0)
# ==================================================

class AgenteDemo:
    def __init__(self, ruta):
        with open(ruta, "rb") as f:
            datos = pickle.load(f)
        self.q_table = datos["q_table"]

    @staticmethod
    def clasificar(cola):
        if cola == 0:
            return 0
        elif cola <= 3:
            return 1
        return 2

    def get_state(self, cola_a, cola_b, grupo, presion):
        return (self.clasificar(cola_a), self.clasificar(cola_b),
                grupo, int(presion))

    def accion(self, estado):
        if estado not in self.q_table:
            return 0
        v = self.q_table[estado]
        return 0 if v[0] >= v[1] else 1


# ==================================================
# UTILIDADES
# ==================================================

def obtener_colas(tls_id):
    g = SEMAFOROS[tls_id]
    a = sum(traci.lane.getLastStepHaltingNumber(c) for c in g["A"])
    b = sum(traci.lane.getLastStepHaltingNumber(c) for c in g["B"])
    return a, b


def cola_total(tls_id):
    a, b = obtener_colas(tls_id)
    return a + b


def presion_vecino(tls_id, grupo_verde):
    grupo = "A" if grupo_verde == 0 else "B"
    dests = VECINO_DESTINO.get(tls_id, {})
    if grupo not in dests:
        return 0
    vecino, _ = dests[grupo]
    return 1 if cola_total(vecino) >= UMBRAL_PRESION_VECINO else 0


def instalar_ia(tls_id, control):
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
        nuevas.append(traci.trafficlight.Phase(dur, fase.state, name=fase.name))
    traci.trafficlight.setProgramLogic(
        tls_id, traci.trafficlight.Logic("rl_agent", 0, 0, nuevas))
    traci.trafficlight.setProgram(tls_id, "rl_agent")
    traci.trafficlight.setPhase(tls_id, 0)
    t = traci.simulation.getTime()
    control["inicio_verde"] = t
    control["siguiente"] = t + TIEMPO_MINIMO_VERDE
    control["fase_prev"] = 0


def controlar_ia(tls_id, agente, control):
    fase = traci.trafficlight.getPhase(tls_id)
    t = traci.simulation.getTime()
    if fase in (1, 3):
        control["fase_prev"] = fase
        return
    if control["fase_prev"] in (1, 3):
        control["inicio_verde"] = t
        control["siguiente"] = t + INTERVALO_DECISION
    control["fase_prev"] = fase
    verde = t - control["inicio_verde"]
    if verde < TIEMPO_MINIMO_VERDE:
        return
    if t < control["siguiente"]:
        return
    a, b = obtener_colas(tls_id)
    grupo = 0 if fase == 0 else 1
    pv = presion_vecino(tls_id, grupo)
    accion = agente.accion(agente.get_state(a, b, grupo, pv))
    if verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1
    if accion == 1:
        traci.trafficlight.setPhase(tls_id, fase + 1)
        control["fase_prev"] = fase + 1
    else:
        control["siguiente"] = t + INTERVALO_DECISION


# ==================================================
# UNA CORRIDA
# ==================================================

def correr(modo, semilla, usar_gui, delay):
    """modo: 'ia' o 'fijo'. Devuelve metricas."""
    binario = "sumo-gui" if usar_gui else "sumo"
    SUMO = sumolib.checkBinary(binario)

    trip = f"demo_{modo}_tripinfos.xml"
    stats = f"demo_{modo}_stats.xml"

    comando = [
        SUMO, "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(semilla),
        "--scale", ESCALA_TRAFICO,
        "--no-step-log", "true",
        "--duration-log.statistics", "true",
        "--tripinfo-output", trip,
        "--statistic-output", stats,
    ]
    if usar_gui:
        comando += ["--start", "--delay", str(delay), "--quit-on-end"]

    agentes, controles = {}, {}
    if modo == "ia":
        for tls_id in SEMAFOROS:
            ruta = ARCHIVOS_MODELO[tls_id]
            if not os.path.exists(ruta):
                print(f"ERROR: falta el modelo {ruta}. "
                      "Entrena con train_coordinado.py.")
                sys.exit(1)
            agentes[tls_id] = AgenteDemo(ruta)
            controles[tls_id] = {}

    traci.start(comando)
    try:
        if modo == "ia":
            for tls_id in SEMAFOROS:
                instalar_ia(tls_id, controles[tls_id])
        while (traci.simulation.getTime() < DURACION
               and traci.simulation.getMinExpectedNumber() > 0):
            traci.simulationStep()
            if modo == "ia":
                for tls_id in SEMAFOROS:
                    controlar_ia(tls_id, agentes[tls_id], controles[tls_id])
    finally:
        traci.close()

    return leer_metricas(trip, stats)


def leer_metricas(trip, stats):
    m = {"completados": 0, "espera": 0.0, "duracion": 0.0,
         "timeloss": 0.0, "teleports": 0}
    if os.path.exists(trip):
        v = ET.parse(trip).getroot().findall("tripinfo")
        n = len(v)
        if n:
            m["completados"] = n
            m["espera"] = round(sum(float(x.get("waitingTime", 0)) for x in v) / n, 1)
            m["duracion"] = round(sum(float(x.get("duration", 0)) for x in v) / n, 1)
            m["timeloss"] = round(sum(float(x.get("timeLoss", 0)) for x in v) / n, 1)
    if os.path.exists(stats):
        tele = ET.parse(stats).getroot().find("teleports")
        if tele is not None:
            m["teleports"] = int(tele.get("total", 0))
    return m


def imprimir_metricas(titulo, m):
    print(f"\n--- {titulo} ---")
    print(f"  Vehiculos completados : {m['completados']}")
    print(f"  Espera promedio (s)   : {m['espera']}")
    print(f"  Duracion promedio (s) : {m['duracion']}")
    print(f"  Time loss promedio (s): {m['timeloss']}")
    print(f"  Teleports             : {m['teleports']}")


# ==================================================
# PRINCIPAL
# ==================================================

def main():
    ap = argparse.ArgumentParser(description="Demo ExpoU: IA coordinada vs fijo")
    ap.add_argument("--modo", choices=["ia", "fijo", "comparar"],
                    default="ia", help="controlador a demostrar")
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--delay", type=int, default=80,
                    help="ms entre pasos en la ventana (ritmo visual)")
    ap.add_argument("--sin-gui", action="store_true",
                    help="correr sin ventana grafica")
    args = ap.parse_args()

    print("=" * 60)
    print("DEMO ExpoU - 5 semaforos COORDINADOS vs semaforo fijo")
    print("=" * 60)

    if args.modo == "comparar":
        print("Modo COMPARAR: corriendo ambos sin ventana "
              f"(semilla {args.semilla})...\n")
        m_fijo = correr("fijo", args.semilla, usar_gui=False, delay=0)
        m_ia = correr("ia", args.semilla, usar_gui=False, delay=0)
        imprimir_metricas("SEMAFORO FIJO (baseline)", m_fijo)
        imprimir_metricas("IA COORDINADA", m_ia)
        print("\n" + "=" * 60)
        print("COMPARACION (IA - fijo):")
        print(f"  Completados : {m_ia['completados'] - m_fijo['completados']:+d} "
              "(mas = mejor)")
        print(f"  Espera (s)  : {m_ia['espera'] - m_fijo['espera']:+.1f} "
              "(menos = mejor)")
        print(f"  Teleports   : {m_ia['teleports'] - m_fijo['teleports']:+d} "
              "(menos = mejor)")
        print("=" * 60)
    else:
        usar_gui = not args.sin_gui
        etiqueta = ("IA COORDINADA" if args.modo == "ia"
                    else "SEMAFORO FIJO (baseline)")
        print(f"Modo {etiqueta} | semilla {args.semilla} | "
              f"{'ventana' if usar_gui else 'sin ventana'}")
        if usar_gui:
            print("Se abrira SUMO-GUI. Pulsa Play si no arranca solo.\n")
        m = correr(args.modo, args.semilla, usar_gui, args.delay)
        imprimir_metricas(etiqueta, m)
        print("\nSugerencia: corre 'python .\\demo_coordinado.py --modo comparar'")
        print("para ver la tabla IA vs fijo con las mismas condiciones.")


if __name__ == "__main__":
    main()
