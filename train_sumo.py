import os
import csv
import random
import traci
import sumolib

from agents.sumo_q_learning import QLearningAgent


# ==========================================
# CONFIGURACIÓN
# ==========================================

CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")

TLS_ID = "262567760"

DURACION = 4556
EPISODIOS = 100

SEMILLA_BASE = 42
ESCALA_TRAFICO = "2"

INTERVALO_DECISION = 5
TIEMPO_MINIMO_VERDE = 10
TIEMPO_MAXIMO_VERDE = 50

ARCHIVO_CSV = "resultados_entrenamiento.csv"
ARCHIVO_MODELO = "q_table_sumo.pkl"

CARRILES_A = [
    "1083001223#0_0",
    "1083001223#0_1"
]

CARRILES_B = [
    "862794316#0_0",
    "862794316#0_1"
]


# ==========================================
# CREAR AGENTE
# ==========================================

agente = QLearningAgent(
    learning_rate=0.1,
    discount_factor=0.95,
    epsilon=1.0,
    epsilon_min=0.05,
    epsilon_decay=0.97
)


# ==========================================
# RECUPERAR PROGRESO
# ==========================================

def obtener_ultimo_episodio():

    if not os.path.exists(ARCHIVO_CSV):
        raise FileNotFoundError(
            f"No se encontró {ARCHIVO_CSV}. "
            "No se iniciará un entrenamiento nuevo automáticamente."
        )

    with open(
        ARCHIVO_CSV,
        "r",
        newline="",
        encoding="utf-8"
    ) as archivo:

        lector = csv.DictReader(archivo)

        columnas_esperadas = [
            "episodio",
            "decisiones",
            "cambios",
            "recompensa_promedio",
            "epsilon"
        ]

        if lector.fieldnames != columnas_esperadas:
            raise ValueError(
                "El CSV no tiene las columnas esperadas."
            )

        filas = list(lector)

    if not filas:
        return 0

    ultimo = int(filas[-1]["episodio"])

    if ultimo < 0 or ultimo > EPISODIOS:
        raise ValueError(
            f"Número de episodio inválido en el CSV: {ultimo}"
        )

    return ultimo


# ==========================================
# OBTENER COLAS DE VEHÍCULOS
# ==========================================

def obtener_colas():

    cola_a = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in CARRILES_A
    )

    cola_b = sum(
        traci.lane.getLastStepHaltingNumber(carril)
        for carril in CARRILES_B
    )

    return cola_a, cola_b


# ==========================================
# INSTALAR PROGRAMA DEL AGENTE
# ==========================================

def instalar_programa_agente():

    programa_actual = traci.trafficlight.getProgram(TLS_ID)

    programas = traci.trafficlight.getAllProgramLogics(TLS_ID)

    logica_original = None

    for programa in programas:

        if programa.programID == programa_actual:
            logica_original = programa
            break

    if logica_original is None:
        raise RuntimeError(
            "No se encontró el programa original del semáforo."
        )

    fases_originales = logica_original.phases

    if len(fases_originales) != 4:
        raise RuntimeError(
            "El semáforo no tiene las cuatro fases esperadas."
        )

    nuevas_fases = []

    for i, fase in enumerate(fases_originales):

        # Fases 0 y 2: verde.
        if i in (0, 2):

            nueva_fase = traci.trafficlight.Phase(
                100000,
                fase.state,
                name=fase.name
            )

        # Fases 1 y 3: amarillo.
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
        TLS_ID,
        nueva_logica
    )

    traci.trafficlight.setProgram(
        TLS_ID,
        "rl_agent"
    )

    traci.trafficlight.setPhase(
        TLS_ID,
        0
    )

    print("Controlador Q-Learning instalado.")


# ==========================================
# CALCULAR RECOMPENSA
# ==========================================

def calcular_recompensa(cola_a, cola_b):

    cola_total = cola_a + cola_b

    desequilibrio = abs(cola_a - cola_b)

    recompensa = (
        -cola_total
        - 0.25 * desequilibrio
    )

    return recompensa


# ==========================================
# CERRAR SUMO DE FORMA SEGURA
# ==========================================

def cerrar_sumo():

    try:
        traci.close()

    except Exception as error:
        print(
            "Aviso al cerrar SUMO: "
            f"{error}"
        )


# ==========================================
# EJECUTAR UN EPISODIO
# ==========================================

def ejecutar_episodio(numero_episodio):

    semilla = SEMILLA_BASE + numero_episodio - 1

    # Semilla independiente para la exploración
    # del agente en cada episodio.
    random.seed(semilla)

    print("\n" + "=" * 50)
    print(
        f"INICIANDO EPISODIO "
        f"{numero_episodio}/{EPISODIOS}"
    )
    print("=" * 50)

    print(f"Semilla: {semilla}")

    traci.start([
        SUMO,
        "-c", CONFIG,
        "--end", str(DURACION),
        "--seed", str(semilla),
        "--no-step-log", "true",
        "--scale", ESCALA_TRAFICO,
        "--output-prefix", "entrenamiento_"
    ])

    try:

        instalar_programa_agente()

        inicio_verde = traci.simulation.getTime()

        decisiones = 0
        cambios = 0
        recompensa_total = 0

        while (
            traci.simulation.getTime() < DURACION
            and traci.simulation.getMinExpectedNumber() > 0
        ):

            fase = traci.trafficlight.getPhase(TLS_ID)

            # Solo tomar decisiones durante el verde.
            if fase not in (0, 2):

                traci.simulationStep()
                continue

            tiempo_actual = traci.simulation.getTime()

            tiempo_verde = tiempo_actual - inicio_verde

            # Respetar el mínimo de verde.
            if tiempo_verde < TIEMPO_MINIMO_VERDE:

                traci.simulationStep()
                continue

            # Observar las colas.
            cola_a, cola_b = obtener_colas()

            grupo_verde = 0 if fase == 0 else 1

            estado = agente.get_state(
                cola_a,
                cola_b,
                grupo_verde
            )

            # 0 = mantener verde.
            # 1 = cambiar a amarillo.
            accion = agente.choose_action(estado)

            # Límite máximo de verde.
            if tiempo_verde >= TIEMPO_MAXIMO_VERDE:
                accion = 1

            if accion == 1:

                traci.trafficlight.setPhase(
                    TLS_ID,
                    fase + 1
                )

                cambios += 1

            # ==================================
            # OBSERVAR DURANTE EL INTERVALO
            # ==================================

            tiempo_objetivo = (
                traci.simulation.getTime()
                + INTERVALO_DECISION
            )

            suma_recompensas = 0
            muestras = 0

            while (
                traci.simulation.getTime() < tiempo_objetivo
                and traci.simulation.getMinExpectedNumber() > 0
                and traci.simulation.getTime() < DURACION
            ):

                traci.simulationStep()

                cola_a_actual, cola_b_actual = obtener_colas()

                suma_recompensas += calcular_recompensa(
                    cola_a_actual,
                    cola_b_actual
                )

                muestras += 1

            # ==================================
            # ESPERAR A QUE TERMINE EL AMARILLO
            # ==================================

            while (
                traci.trafficlight.getPhase(TLS_ID) not in (0, 2)
                and traci.simulation.getMinExpectedNumber() > 0
                and traci.simulation.getTime() < DURACION
            ):

                traci.simulationStep()

                cola_a_actual, cola_b_actual = obtener_colas()

                suma_recompensas += calcular_recompensa(
                    cola_a_actual,
                    cola_b_actual
                )

                muestras += 1

            # ==================================
            # COMPROBAR NUEVA FASE
            # ==================================

            nueva_fase = traci.trafficlight.getPhase(TLS_ID)

            if nueva_fase not in (0, 2):
                break

            nueva_cola_a, nueva_cola_b = obtener_colas()

            nuevo_grupo_verde = (
                0 if nueva_fase == 0 else 1
            )

            nuevo_estado = agente.get_state(
                nueva_cola_a,
                nueva_cola_b,
                nuevo_grupo_verde
            )

            if nueva_fase != fase:
                inicio_verde = traci.simulation.getTime()

            # ==================================
            # CALCULAR RECOMPENSA PROMEDIO
            # ==================================

            if muestras > 0:
                recompensa = suma_recompensas / muestras
            else:
                recompensa = 0

            # ==================================
            # APRENDER
            # ==================================

            agente.learn(
                estado,
                accion,
                recompensa,
                nuevo_estado,
                done=False
            )

            decisiones += 1
            recompensa_total += recompensa

        # ==================================
        # FINALIZAR EPISODIO
        # ==================================

        promedio = (
            recompensa_total / decisiones
            if decisiones > 0
            else 0
        )

        agente.decay_exploration()

        print(f"Decisiones: {decisiones}")
        print(f"Cambios: {cambios}")
        print(f"Recompensa promedio: {promedio:.4f}")
        print(f"Epsilon: {agente.epsilon:.4f}")

        # Primero guardar el modelo.
        agente.save(ARCHIVO_MODELO)

        # Después registrar el episodio en el CSV.
        with open(
            ARCHIVO_CSV,
            "a",
            newline="",
            encoding="utf-8"
        ) as archivo:

            escritor = csv.writer(archivo)

            escritor.writerow([
                numero_episodio,
                decisiones,
                cambios,
                promedio,
                agente.epsilon
            ])

            archivo.flush()

        print(
            f"Episodio {numero_episodio} guardado correctamente."
        )

    finally:

        cerrar_sumo()


# ==========================================
# ENTRENAMIENTO
# ==========================================

def entrenar():

    # Comprobar que existe el modelo.
    if not os.path.exists(ARCHIVO_MODELO):
        raise FileNotFoundError(
            "No se encontró la tabla Q. "
            "No se iniciará un entrenamiento nuevo."
        )

    # Recuperar el modelo anterior.
    agente.load(ARCHIVO_MODELO)

    if not agente.q_table:
        raise RuntimeError(
            "La tabla Q está vacía. No se puede continuar."
        )

    # Recuperar el número de episodios terminados.
    ultimo_episodio = obtener_ultimo_episodio()

    print("\n" + "=" * 50)
    print("RECUPERACIÓN DEL ENTRENAMIENTO")
    print("=" * 50)

    print(f"Episodios completados: {ultimo_episodio}")
    print(f"Episodios totales previstos: {EPISODIOS}")
    print(f"Epsilon recuperado: {agente.epsilon:.4f}")
    print(f"Estados aprendidos: {len(agente.q_table)}")

    if ultimo_episodio >= EPISODIOS:

        print("\nEl entrenamiento ya llegó a su objetivo.")
        return

    siguiente_episodio = ultimo_episodio + 1

    print(
        f"\nEl entrenamiento continuará desde "
        f"el episodio {siguiente_episodio}."
    )

    try:

        for numero_episodio in range(
            siguiente_episodio,
            EPISODIOS + 1
        ):

            ejecutar_episodio(numero_episodio)

    except KeyboardInterrupt:

        print("\n\nEntrenamiento interrumpido por el usuario.")
        print(
            "Se conservaron el modelo y los resultados "
            "del último episodio completado."
        )
        return

    # ==================================
    # RESULTADOS FINALES
    # ==================================

    print("\n" + "=" * 50)
    print("ENTRENAMIENTO FINALIZADO")
    print("=" * 50)

    print(f"Modelo guardado en {ARCHIVO_MODELO}")
    print(f"Resultados guardados en {ARCHIVO_CSV}")
    print(f"Episodios completados: {EPISODIOS}")


# ==========================================
# EJECUTAR
# ==========================================

if __name__ == "__main__":

    entrenar()


