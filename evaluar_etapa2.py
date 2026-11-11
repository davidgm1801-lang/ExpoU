"""
==================================================================
EVALUACION ETAPA 2 - ExpoU
==================================================================

Objetivo
--------
Comparar, en condiciones IDENTICAS y reproducibles, dos controladores
de los cinco semaforos:

  - BASELINE : el controlador original de SUMO (programa fijo).
  - IA       : los cinco agentes Q-Learning con sus tablas
               INDEPENDIENTES, evaluados con epsilon = 0 (sin
               exploracion aleatoria -> politica determinista).

El experimento corre AMBOS brazos sobre el MISMO conjunto de semillas
(emparejadas), de modo que la unica diferencia entre dos corridas con
la misma semilla sea QUIEN controla los semaforos.

Esta metodologia fue acordada en la Etapa 2 (ver EVALUACION_ETAPA2.md).

Caracteristicas clave
---------------------
  - Modo headless (binario 'sumo', sin GUI, sin delay) para que las
    10 corridas sean rapidas y automatizables.
  - NO modifica ni guarda ninguna tabla Q. Solo lee los modelos.
  - Cada corrida escribe sus propios tripinfos/stats con prefijo
    propio, y de ahi se extraen las metricas.
  - Resultado final: un CSV con una fila por (brazo, semilla) y todas
    las metricas prioritarias, incluyendo SIEMPRE los teleports.

Como ejecutar (en Windows, con el .venv activo y dentro de ExpoU):

    python .\\evaluar_etapa2.py

Que esperar:
  - 10 corridas (5 semillas x 2 brazos), sin ventana grafica.
  - Al final, el archivo 'evaluacion_etapa2.csv' y un resumen por
    consola comparando baseline vs IA.
==================================================================
"""

import os
import csv
import xml.etree.ElementTree as ET

import traci
import sumolib


# ==================================================
# CONFIGURACION GENERAL (identica a train/diagnostico)
# ==================================================

CONFIG = os.path.join("sumo_bogota", "osm.sumocfg")

DURACION = 4556
ESCALA_TRAFICO = "2"

# Semillas emparejadas acordadas para la evaluacion.
SEMILLAS = [42, 43, 44, 45, 46]

# Parametros de control (identicos a train_sumo_5.py).
INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

# Binario SIN interfaz grafica: evaluacion rapida.
SUMO = sumolib.checkBinary("sumo")

# ==================================================
# VERSION DE MODELO A EVALUAR
# ==================================================
# Variable de entorno VERSION_MODELO: "v1" (por defecto) o "v2".
#   v1 -> modelos q_table_independiente_<id>.pkl, cola de 3 niveles [0,3]
#   v2 -> modelos q_table_v2_<id>.pkl,            cola de 5 niveles [0,2,5,10]
# El brazo baseline es identico en ambos casos (control original de SUMO);
# lo unico que cambia es que modelos usa el brazo IA.
VERSION_MODELO = os.environ.get("VERSION_MODELO", "v1").lower()

if VERSION_MODELO == "v2":
    PREFIJO_MODELO = "q_table_v2_"
    UMBRALES_COLA = [0, 2, 5, 10]
    ARCHIVO_RESULTADOS = "evaluacion_etapa2_v2.csv"
else:
    PREFIJO_MODELO = "q_table_independiente_"
    UMBRALES_COLA = [0, 3]
    ARCHIVO_RESULTADOS = "evaluacion_etapa2.csv"

# Carpeta temporal para las salidas por corrida.
DIR_SALIDAS = "salidas_evaluacion"


# ==================================================
# CINCO SEMAFOROS Y SUS CARRILES
# (verificados en la Etapa 1 contra getControlledLinks)
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
    tls_id: f"{PREFIJO_MODELO}{tls_id}.pkl"
    for tls_id in SEMAFOROS
}


# ==================================================
# AGENTE Q-LEARNING SOLO-LECTURA
# ==================================================
# Se define una clase minima aqui para NO depender de guardar/alterar
# modelos. Carga la tabla Q de un .pkl y elige acciones de forma
# determinista (epsilon = 0). No escribe nada en disco.

import pickle


class AgenteEvaluacion:
    """Carga una tabla Q entrenada y la explota sin exploracion."""

    def __init__(self, ruta_modelo, queue_thresholds=None):
        with open(ruta_modelo, "rb") as archivo:
            datos = pickle.load(archivo)

        self.q_table = datos["q_table"]

        if not self.q_table:
            raise RuntimeError(
                f"La tabla Q de '{ruta_modelo}' esta vacia."
            )

        # Umbrales de discretizacion de la cola. Deben coincidir con los
        # usados al ENTRENAR el modelo que se esta evaluando.
        #   v1 (original): [0, 3]          -> 3 niveles
        #   v2 (Etapa 3):  [0, 2, 5, 10]   -> 5 niveles
        if queue_thresholds is None:
            queue_thresholds = [0, 3]
        self.queue_thresholds = queue_thresholds

    def clasificar_cola(self, cola):
        for i, limite in enumerate(self.queue_thresholds):
            if cola <= limite:
                return i
        return len(self.queue_thresholds)

    def get_state(self, cola_a, cola_b, grupo_verde):
        return (
            self.clasificar_cola(cola_a),
            self.clasificar_cola(cola_b),
            grupo_verde,
        )

    def elegir_accion(self, estado):
        # Si el estado nunca se vio en entrenamiento, por defecto
        # mantener el verde (accion 0). Es la opcion conservadora.
        if estado not in self.q_table:
            return 0

        valores = self.q_table[estado]

        # Determinista: ante empate, mantener (accion 0).
        if valores[0] >= valores[1]:
            return 0
        return 1


# ==================================================
# UTILIDADES DE COLAS
# ==================================================

def obtener_colas(tls_id):
    carriles = SEMAFOROS[tls_id]

    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(c)
        for c in carriles["A"]
    )
    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(c)
        for c in carriles["B"]
    )
    return cola_a, cola_b


# ==================================================
# INSTALAR CONTROLADOR DE IA (extiende las fases verdes)
# ==================================================
# Solo se usa en el brazo IA. En el brazo baseline NO se toca el
# semaforo: se deja el programa original de SUMO.

def instalar_controlador_ia(tls_id, control):
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
            # Fases verdes: duracion muy larga; el agente decide
            # cuando cambiar.
            nuevas_fases.append(
                traci.trafficlight.Phase(
                    100000, fase.state, name=fase.name
                )
            )
        else:
            # Fases amarillas: se conservan tal cual.
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

    tiempo = traci.simulation.getTime()
    control["inicio_verde"] = tiempo
    control["siguiente_decision"] = tiempo + TIEMPO_MINIMO_VERDE
    control["fase_anterior"] = 0


# ==================================================
# CONTROL DE UN SEMAFORO POR SU AGENTE (brazo IA)
# ==================================================

def controlar_semaforo_ia(tls_id, agente, control):
    fase = traci.trafficlight.getPhase(tls_id)
    tiempo = traci.simulation.getTime()

    # No se decide durante el amarillo (fases 1 y 3).
    if fase in (1, 3):
        control["fase_anterior"] = fase
        return

    # Al terminar el amarillo empieza un nuevo verde.
    if control["fase_anterior"] in (1, 3):
        control["inicio_verde"] = tiempo
        control["siguiente_decision"] = tiempo + INTERVALO_DECISION

    control["fase_anterior"] = fase

    tiempo_verde = tiempo - control["inicio_verde"]

    # Respetar el verde minimo.
    if tiempo_verde < TIEMPO_MINIMO_VERDE:
        return

    # Esperar al proximo momento de decision.
    if tiempo < control["siguiente_decision"]:
        return

    cola_a, cola_b = obtener_colas(tls_id)
    grupo_verde = 0 if fase == 0 else 1

    estado = agente.get_state(cola_a, cola_b, grupo_verde)
    accion = agente.elegir_accion(estado)

    # Registrar metricas de cola (para las columnas 9 y 10).
    cola_total = cola_a + cola_b
    control["cola_total"] += cola_total
    control["muestras"] += 1
    control["cola_maxima"] = max(control["cola_maxima"], cola_total)

    # Forzar cambio si se alcanzo el verde maximo.
    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    control["decisiones"] += 1

    if accion == 1:
        traci.trafficlight.setPhase(tls_id, fase + 1)
        control["cambios"] += 1
        control["fase_anterior"] = fase + 1
    else:
        control["siguiente_decision"] = tiempo + INTERVALO_DECISION


# ==================================================
# MEDICION DE COLAS EN EL BRAZO BASELINE
# ==================================================
# En baseline no controlamos el semaforo, pero igual medimos las colas
# en los mismos carriles para poder comparar colas promedio/maxima.

def medir_colas_baseline(tls_id, control):
    cola_a, cola_b = obtener_colas(tls_id)
    cola_total = cola_a + cola_b
    control["cola_total"] += cola_total
    control["muestras"] += 1
    control["cola_maxima"] = max(control["cola_maxima"], cola_total)


# ==================================================
# ESTADO DE CONTROL POR SEMAFORO
# ==================================================

def nuevo_control():
    return {
        "inicio_verde": 0,
        "siguiente_decision": 0,
        "fase_anterior": 0,
        "decisiones": 0,
        "cambios": 0,
        "cola_total": 0,
        "cola_maxima": 0,
        "muestras": 0,
    }


# ==================================================
# EJECUTAR UNA CORRIDA (un brazo, una semilla)
# ==================================================

def ejecutar_corrida(brazo, semilla, prefijo_salida):
    """
    brazo: "baseline" o "ia".
    Devuelve un diccionario de metricas de la corrida.
    """
    archivo_trip = f"{prefijo_salida}_tripinfos.xml"
    archivo_stats = f"{prefijo_salida}_stats.xml"

    # Preparar agentes solo en el brazo IA.
    agentes = {}
    if brazo == "ia":
        for tls_id in SEMAFOROS:
            agentes[tls_id] = AgenteEvaluacion(
                ARCHIVOS_MODELO[tls_id],
                queue_thresholds=UMBRALES_COLA,
            )

    controles = {tls_id: nuevo_control() for tls_id in SEMAFOROS}

    comando = [
        SUMO,
        "-c", CONFIG,
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
        # Validar que los 5 semaforos existen.
        disponibles = set(traci.trafficlight.getIDList())
        for tls_id in SEMAFOROS:
            if tls_id not in disponibles:
                raise RuntimeError(
                    f"No existe el semaforo {tls_id} en SUMO."
                )

        # Instalar el controlador de IA (solo brazo IA).
        if brazo == "ia":
            for tls_id in SEMAFOROS:
                instalar_controlador_ia(tls_id, controles[tls_id])

        # Bucle principal.
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

    # Extraer metricas de los archivos generados.
    metricas = leer_metricas(archivo_trip, archivo_stats)

    # Agregar metricas de cola medidas por nosotros.
    cola_prom_total = 0.0
    cola_max_total = 0
    for tls_id in SEMAFOROS:
        c = controles[tls_id]
        prom = c["cola_total"] / c["muestras"] if c["muestras"] else 0.0
        cola_prom_total += prom
        cola_max_total = max(cola_max_total, c["cola_maxima"])

    metricas["cola_promedio_suma_5tls"] = round(cola_prom_total, 3)
    metricas["cola_maxima_global"] = cola_max_total

    return metricas, controles


# ==================================================
# LEER METRICAS DE tripinfos.xml Y stats.xml
# ==================================================

def leer_metricas(archivo_trip, archivo_stats):
    metricas = {
        "completados": 0,
        "espera_promedio": 0.0,
        "duracion_promedio": 0.0,
        "timeloss_promedio": 0.0,
        "velocidad_promedio": 0.0,
        "teleports_total": 0,
        "teleports_jam": 0,
        "teleports_yield": 0,
        "teleports_wronglane": 0,
        "colisiones": 0,
        "cargados": 0,
        "insertados": 0,
    }

    # --- tripinfos.xml: solo vehiculos que completaron viaje ---
    if os.path.exists(archivo_trip):
        arbol = ET.parse(archivo_trip)
        viajes = arbol.getroot().findall("tripinfo")

        n = len(viajes)
        if n > 0:
            espera = sum(float(v.get("waitingTime", 0)) for v in viajes)
            duracion = sum(float(v.get("duration", 0)) for v in viajes)
            timeloss = sum(float(v.get("timeLoss", 0)) for v in viajes)
            distancia = sum(
                float(v.get("routeLength", 0)) for v in viajes
            )

            metricas["completados"] = n
            metricas["espera_promedio"] = round(espera / n, 3)
            metricas["duracion_promedio"] = round(duracion / n, 3)
            metricas["timeloss_promedio"] = round(timeloss / n, 3)
            metricas["velocidad_promedio"] = round(
                distancia / duracion if duracion > 0 else 0.0, 3
            )

    # --- stats.xml: totales de SUMO (teleports, colisiones...) ---
    if os.path.exists(archivo_stats):
        arbol = ET.parse(archivo_stats)
        raiz = arbol.getroot()

        veh = raiz.find("vehicles")
        if veh is not None:
            metricas["cargados"] = int(veh.get("loaded", 0))
            metricas["insertados"] = int(veh.get("inserted", 0))

        tele = raiz.find("teleports")
        if tele is not None:
            metricas["teleports_total"] = int(tele.get("total", 0))
            metricas["teleports_jam"] = int(tele.get("jam", 0))
            metricas["teleports_yield"] = int(tele.get("yield", 0))
            metricas["teleports_wronglane"] = int(
                tele.get("wrongLane", 0)
            )

        safety = raiz.find("safety")
        if safety is not None:
            metricas["colisiones"] = int(safety.get("collisions", 0))

    return metricas


# ==================================================
# PROGRAMA PRINCIPAL
# ==================================================

CAMPOS_CSV = [
    "brazo",
    "semilla",
    "completados",
    "espera_promedio",
    "duracion_promedio",
    "timeloss_promedio",
    "velocidad_promedio",
    "cola_promedio_suma_5tls",
    "cola_maxima_global",
    "teleports_total",
    "teleports_jam",
    "teleports_yield",
    "teleports_wronglane",
    "colisiones",
    "cargados",
    "insertados",
]


def main():
    print("=" * 64)
    print("EVALUACION - Baseline (SUMO) vs IA (5 agentes)")
    print("=" * 64)
    print(f"Version de modelo IA: {VERSION_MODELO} "
          f"(umbrales de cola {UMBRALES_COLA})")
    print(f"Modelos: {PREFIJO_MODELO}<id>.pkl")
    print(f"Semillas: {SEMILLAS}")
    print(f"Duracion por corrida: {DURACION} s | Escala: {ESCALA_TRAFICO}")
    print(f"Total de corridas: {len(SEMILLAS) * 2}")
    print(f"Salida: {ARCHIVO_RESULTADOS}")

    os.makedirs(DIR_SALIDAS, exist_ok=True)

    filas = []

    for brazo in ("baseline", "ia"):
        for semilla in SEMILLAS:
            etiqueta = f"{brazo} | semilla {semilla}"
            print("\n" + "-" * 64)
            print(f"CORRIDA: {etiqueta}")
            print("-" * 64)

            prefijo = os.path.join(
                DIR_SALIDAS, f"{brazo}_semilla{semilla}"
            )

            metricas, _ = ejecutar_corrida(brazo, semilla, prefijo)

            fila = {"brazo": brazo, "semilla": semilla}
            fila.update(metricas)
            filas.append(fila)

            print(
                f"  completados={metricas['completados']} | "
                f"espera={metricas['espera_promedio']} | "
                f"duracion={metricas['duracion_promedio']} | "
                f"teleports={metricas['teleports_total']}"
            )

    # Guardar CSV.
    with open(
        ARCHIVO_RESULTADOS, "w", newline="", encoding="utf-8"
    ) as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_CSV)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)

    print("\n" + "=" * 64)
    print("EVALUACION FINALIZADA")
    print(f"Resultados guardados en: {ARCHIVO_RESULTADOS}")
    print("=" * 64)

    imprimir_resumen(filas)


# ==================================================
# RESUMEN COMPARATIVO EN CONSOLA
# ==================================================

def promedio(valores):
    return sum(valores) / len(valores) if valores else 0.0


def imprimir_resumen(filas):
    base = [f for f in filas if f["brazo"] == "baseline"]
    ia = [f for f in filas if f["brazo"] == "ia"]

    metricas_resumen = [
        ("completados", "Vehiculos completados", "mas=mejor"),
        ("espera_promedio", "Espera promedio (s)", "menos=mejor"),
        ("duracion_promedio", "Duracion promedio (s)", "menos=mejor"),
        ("timeloss_promedio", "Time loss promedio (s)", "menos=mejor"),
        ("velocidad_promedio", "Velocidad promedio (m/s)", "mas=mejor"),
        ("cola_promedio_suma_5tls", "Cola prom. (suma 5 TLS)", "menos=mejor"),
        ("cola_maxima_global", "Cola maxima global", "menos=mejor"),
        ("teleports_total", "Teleports (LIMITACION)", "menos=mejor"),
        ("colisiones", "Colisiones", "menos=mejor"),
    ]

    print("\nRESUMEN (promedio sobre las semillas):\n")
    print(
        f"{'Metrica':<28}{'Baseline':>12}{'IA':>12}"
        f"   {'Sentido'}"
    )
    print("-" * 70)

    for clave, nombre, sentido in metricas_resumen:
        b = promedio([f[clave] for f in base])
        i = promedio([f[clave] for f in ia])
        print(f"{nombre:<28}{b:>12.3f}{i:>12.3f}   {sentido}")

    print(
        "\nNOTA: con 5 semillas no se afirman resultados estadisticamente"
        "\nsignificativos. Los teleports son una LIMITACION conocida: un"
        "\nvehiculo atascado es teletransportado y deja de contar en los"
        "\npromedios, por lo que un mayor numero de 'completados' puede"
        "\nincluir vehiculos dificiles que el otro brazo perdio."
    )


if __name__ == "__main__":
    main()
