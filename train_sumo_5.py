import os
import csv
import random
import traci
import sumolib

from agents.sumo_q_learning import QLearningAgent


# ==================================================
# CONFIGURACIÓN GENERAL
# ==================================================

CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

DURACION = 4556
EPISODIOS = 100

SEMILLA_BASE = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

ARCHIVO_CSV = "resultados_entrenamiento_5.csv"


# ==================================================
# CINCO SEMÁFOROS Y SUS CARRILES
# ==================================================

SEMAFOROS = {
    "262567760": {
        "A": [
            "1083001223#0_0",
            "1083001223#0_1"
        ],
        "B": [
            "862794316#0_0",
            "862794316#0_1"
        ]
    },

    "262567775": {
        "A": [
            "88757025#0_0",
            "88757025#0_1"
        ],
        "B": [
            "1083001225#0_1",
            "1083001225#0_2"
        ]
    },

    "262567777": {
        "A": [
            "1060493360#3_1",
            "1060493360#3_2"
        ],
        "B": [
            "908369205#0_0",
            "908369205#0_1"
        ]
    },

    "264377450": {
        "A": [
            "1083001233_0",
            "1083001233_1"
        ],
        "B": [
            "1056806207#0_0",
            "1056806207#0_1"
        ]
    },

    "265804326": {
        "A": [
            "88877450#2_0",
            "88877450#2_1"
        ],
        "B": [
            "1083001234#0_0",
            "1083001234#0_1"
        ]
    }
}


# Cada semáforo tendrá un archivo diferente.
ARCHIVOS_MODELO = {
    tls_id: f"q_table_independiente_{tls_id}.pkl"
    for tls_id in SEMAFOROS
}


# ==================================================
# CREAR LOS CINCO AGENTES
# ==================================================

agentes = {}

for tls_id in SEMAFOROS:

    agentes[tls_id] = QLearningAgent(
        learning_rate=0.1,
        discount_factor=0.95,
        epsilon=1.0,
        epsilon_min=0.05,
        epsilon_decay=0.97
    )


# ==================================================
# OBTENER COLAS
# ==================================================

def obtener_colas(tls_id):

    carriles_a = SEMAFOROS[tls_id]["A"]
    carriles_b = SEMAFOROS[tls_id]["B"]

    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in carriles_a
    )

    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in carriles_b
    )

    return cola_a, cola_b


# ==================================================
# CALCULAR RECOMPENSA
# ==================================================

def calcular_recompensa(cola_a, cola_b):

    cola_total = cola_a + cola_b
    desequilibrio = abs(cola_a - cola_b)

    return -cola_total - 0.25 * desequilibrio


# ==================================================
# INSTALAR CONTROLADOR EN LOS CINCO SEMÁFOROS
# ==================================================

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
            f"No se encontró el programa original de {tls_id}."
        )

    fases_originales = logica_original.phases

    if len(fases_originales) != 4:
        raise RuntimeError(
            f"El semáforo {tls_id} no tiene cuatro fases."
        )

    nuevas_fases = []

    for i, fase in enumerate(fases_originales):

        if i in (0, 2):

            nueva_fase = traci.trafficlight.Phase(
                100000,
                fase.state,
                name=fase.name
            )

        else:

            nueva_fase = traci.trafficlight.Phase(
                fase.duration,
                fase.state,
                name=fase.name
            )

        nuevas_fases.append(nueva_fase)

    nueva_logica = traci.trafficlight.Logic(
        "rl_agent",
        0,
        0,
        nuevas_fases
    )

    traci.trafficlight.setProgramLogic(
        tls_id,
        nueva_logica
    )

    traci.trafficlight.setProgram(
        tls_id,
        "rl_agent"
    )

    traci.trafficlight.setPhase(
        tls_id,
        0
    )


# ==================================================
# PREPARAR EL ESTADO DE CADA SEMÁFORO
# ==================================================

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
            "recompensas_aprendidas": 0
        }

    return estados


# ==================================================
# REGISTRAR UNA EXPERIENCIA DE APRENDIZAJE
# ==================================================

def aprender_transicion(
    tls_id,
    control,
    nuevo_estado,
    done
):

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
        done=done
    )

    control["decisiones"] += 1
    control["recompensa_total"] += recompensa
    control["recompensas_aprendidas"] += 1

    control["pendiente"] = None


# ==================================================
# ACTUALIZAR EL APRENDIZAJE DE CADA AGENTE
# ==================================================

def actualizar_agente(tls_id, control, tiempo_actual):

    pendiente = control["pendiente"]

    if pendiente is None:
        return

    fase_actual = traci.trafficlight.getPhase(tls_id)

    cola_a, cola_b = obtener_colas(tls_id)

    # Acumular la recompensa observada durante la acción.
    pendiente["recompensa_total"] += calcular_recompensa(
        cola_a,
        cola_b
    )

    pendiente["muestras"] += 1

    # No aprender hasta que haya regresado el verde.
    if fase_actual not in (0, 2):
        return

    fase_anterior = pendiente["fase"]

    accion = pendiente["accion"]

    # Acción 0: mantener el mismo verde durante el intervalo.
    if accion == 0:

        tiempo_transcurrido = (
            tiempo_actual - pendiente["tiempo_inicio"]
        )

        if tiempo_transcurrido < INTERVALO_DECISION:
            return

    # Acción 1: esperar hasta que termine el amarillo
    # y comience el verde del otro grupo.
    elif fase_actual == fase_anterior:

        return

    nuevo_grupo = 0 if fase_actual == 0 else 1

    nuevo_estado = agentes[tls_id].get_state(
        cola_a,
        cola_b,
        nuevo_grupo
    )

    aprender_transicion(
        tls_id,
        control,
        nuevo_estado,
        done=False
    )

    # Preparar la siguiente decisión.
    if fase_actual != fase_anterior:

        control["inicio_verde"] = tiempo_actual

        control["proxima_decision"] = (
            tiempo_actual + TIEMPO_MINIMO_VERDE
        )

    else:

        control["proxima_decision"] = (
            tiempo_actual + INTERVALO_DECISION
        )


# ==================================================
# CERRAR TRANSICIONES PENDIENTES AL FINAL DEL EPISODIO
# ==================================================

def finalizar_transiciones_pendientes(controles):

    for tls_id in SEMAFOROS:

        control = controles[tls_id]

        if control["pendiente"] is None:
            continue

        # Incorporar la última observación disponible.
        cola_a, cola_b = obtener_colas(tls_id)

        pendiente = control["pendiente"]

        pendiente["recompensa_total"] += calcular_recompensa(
            cola_a,
            cola_b
        )

        pendiente["muestras"] += 1

        # Al terminar SUMO no existe un siguiente estado futuro
        # dentro de este episodio. Por eso se utiliza done=True.
        if pendiente["accion"] == 1:

            # Si el episodio termina durante el amarillo,
            # el grupo de destino es el contrario al verde
            # desde el que se solicitó el cambio.
            nuevo_grupo = 1 if pendiente["fase"] == 0 else 0

        else:

            # Si la acción era mantener, se conserva
            # el grupo original.
            nuevo_grupo = (
                0 if pendiente["fase"] == 0 else 1
            )

        nuevo_estado = agentes[tls_id].get_state(
            cola_a,
            cola_b,
            nuevo_grupo
        )

        aprender_transicion(
            tls_id,
            control,
            nuevo_estado,
            done=True
        )


# ==================================================
# TOMAR DECISIONES INDEPENDIENTES
# ==================================================

def controlar_semaforo(tls_id, control, tiempo_actual):

    fase = traci.trafficlight.getPhase(tls_id)

    # Primero completar el aprendizaje anterior.
    actualizar_agente(
        tls_id,
        control,
        tiempo_actual
    )

    # No tomar decisiones durante el amarillo.
    if fase not in (0, 2):
        return

    # Si todavía está aprendiendo una decisión anterior,
    # no iniciar otra.
    if control["pendiente"] is not None:
        return

    # Esperar hasta que corresponda decidir.
    if tiempo_actual < control["proxima_decision"]:
        return

    cola_a, cola_b = obtener_colas(tls_id)

    grupo_verde = 0 if fase == 0 else 1

    agente = agentes[tls_id]

    estado = agente.get_state(
        cola_a,
        cola_b,
        grupo_verde
    )

    accion = agente.choose_action(estado)

    tiempo_verde = (
        tiempo_actual - control["inicio_verde"]
    )

    # No permitir que el verde supere el máximo.
    if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
        accion = 1

    control["pendiente"] = {
        "estado": estado,
        "accion": accion,
        "fase": fase,
        "tiempo_inicio": tiempo_actual,
        "recompensa_total": 0,
        "muestras": 0
    }

    # Acción 0: mantener el verde.
    if accion == 0:
        return

    # Acción 1: solicitar cambio a amarillo.
    traci.trafficlight.setPhase(
        tls_id,
        fase + 1
    )

    control["cambios"] += 1


# ==================================================
# GUARDAR MODELOS
# ==================================================

def guardar_modelos():

    for tls_id, agente in agentes.items():

        agente.save(
            ARCHIVOS_MODELO[tls_id]
        )


# ==================================================
# RECUPERAR ENTRENAMIENTO
# ==================================================

def recuperar_entrenamiento():

    if not os.path.exists(ARCHIVO_CSV):

        for tls_id in SEMAFOROS:

            if os.path.exists(ARCHIVOS_MODELO[tls_id]):

                raise RuntimeError(
                    "Hay un modelo anterior sin su CSV. "
                    "No se sobrescribirá automáticamente."
                )

        with open(
            ARCHIVO_CSV,
            "w",
            newline="",
            encoding="utf-8"
        ) as archivo:

            escritor = csv.writer(archivo)

            escritor.writerow([
                "episodio",
                "semaforo",
                "decisiones",
                "cambios",
                "recompensa_promedio",
                "epsilon"
            ])

        return 0

    with open(
        ARCHIVO_CSV,
        "r",
        newline="",
        encoding="utf-8"
    ) as archivo:

        lector = csv.DictReader(archivo)

        columnas = [
            "episodio",
            "semaforo",
            "decisiones",
            "cambios",
            "recompensa_promedio",
            "epsilon"
        ]

        if lector.fieldnames != columnas:

            raise ValueError(
                "El CSV de entrenamiento tiene columnas incorrectas."
            )

        filas = list(lector)

    if not filas:
        return 0

    ultimo = max(
        int(fila["episodio"])
        for fila in filas
    )

    if ultimo < 0 or ultimo > EPISODIOS:
        raise ValueError("Número de episodio inválido.")

    if ultimo > 0:

        for tls_id in SEMAFOROS:

            archivo_modelo = ARCHIVOS_MODELO[tls_id]

            if not os.path.exists(archivo_modelo):

                raise FileNotFoundError(
                    f"Falta el modelo independiente de {tls_id}."
                )

            agentes[tls_id].load(archivo_modelo)

    return ultimo


# ==================================================
# EJECUTAR UN EPISODIO
# ==================================================

def ejecutar_episodio(numero_episodio):

    semilla = SEMILLA_BASE + numero_episodio - 1

    random.seed(semilla)

    print("\n" + "=" * 55)
    print(f"EPISODIO {numero_episodio}/{EPISODIOS}")
    print(f"Semilla: {semilla}")
    print("=" * 55)

    traci.start([
        SUMO,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(semilla),
        "--no-step-log", "true",
        "--scale", ESCALA_TRAFICO
    ])

    try:

        tls_disponibles = traci.trafficlight.getIDList()

        for tls_id in SEMAFOROS:

            if tls_id not in tls_disponibles:

                raise RuntimeError(
                    f"No existe el semáforo {tls_id} en SUMO."
                )

            instalar_programa_agente(tls_id)

        controles = crear_estado_control()

        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):

            tiempo_actual = traci.simulation.getTime()

            # Cada agente toma decisiones usando
            # exclusivamente la información de su cruce.
            for tls_id in SEMAFOROS:

                controlar_semaforo(
                    tls_id,
                    controles[tls_id],
                    tiempo_actual
                )

            traci.simulationStep()

        # Cerrar cualquier experiencia que haya quedado pendiente.
        finalizar_transiciones_pendientes(controles)

        # Reducir exploración al terminar el episodio.
        for agente in agentes.values():
            agente.decay_exploration()

        # Guardar los modelos con el mismo epsilon
        # que se registrará en el CSV.
        guardar_modelos()

        # ==========================================
        # GUARDAR RESULTADOS DEL EPISODIO
        # ==========================================

        with open(
            ARCHIVO_CSV,
            "a",
            newline="",
            encoding="utf-8"
        ) as archivo:

            escritor = csv.writer(archivo)

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
                    numero_episodio,
                    tls_id,
                    control["decisiones"],
                    control["cambios"],
                    promedio,
                    epsilon_actual
                ])

                print(
                    f"\nSemáforo: {tls_id}"
                    f"\nDecisiones aprendidas: {control['decisiones']}"
                    f"\nCambios: {control['cambios']}"
                    f"\nRecompensa promedio: {promedio:.4f}"
                    f"\nEpsilon: {epsilon_actual:.4f}"
                )

            archivo.flush()

        print(
            f"\nEpisodio {numero_episodio} guardado correctamente."
        )

    finally:

        traci.close()


# ==================================================
# ENTRENAMIENTO COMPLETO
# ==================================================

def entrenar():

    ultimo_episodio = recuperar_entrenamiento()

    print("\n" + "=" * 55)
    print("ENTRENAMIENTO DE CINCO SEMÁFOROS")
    print("=" * 55)

    print(f"Episodios completados: {ultimo_episodio}")
    print(f"Episodios previstos: {EPISODIOS}")
    print(f"Semáforos independientes: {len(SEMAFOROS)}")

    for tls_id, agente in agentes.items():

        print(
            f"Semáforo {tls_id}: "
            f"{len(agente.q_table)} estados aprendidos"
        )

    if ultimo_episodio >= EPISODIOS:

        print("\nEl entrenamiento ya está completo.")
        return

    try:

        for numero in range(
            ultimo_episodio + 1,
            EPISODIOS + 1
        ):

            ejecutar_episodio(numero)

    except KeyboardInterrupt:

        print("\nEntrenamiento interrumpido.")
        print("Se conservaron los episodios guardados.")
        return

    print("\n" + "=" * 55)
    print("ENTRENAMIENTO FINALIZADO")
    print("=" * 55)

    print("Modelos independientes guardados:")

    for tls_id in SEMAFOROS:
        print(ARCHIVOS_MODELO[tls_id])

    print(f"\nResultados: {ARCHIVO_CSV}")


# ==================================================
# EJECUTAR
# ==================================================

if __name__ == "__main__":

    entrenar()