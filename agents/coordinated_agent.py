"""
==================================================================
AGENTE Q-LEARNING COORDINADO - Etapa 4 (ExpoU)
==================================================================

Motivacion
----------
Las Etapas 1-3 demostraron que agentes locales AISLADOS no bastan:
su efecto queda ahogado por la red que no controlan, y la politica
es inestable (colapsa en ciertas realizaciones de trafico).

La hipotesis de la Etapa 4 es que la INESTABILIDAD viene de que cada
agente decide a ciegas respecto a sus vecinos: puede dar verde hacia
un vecino ya saturado y provocar atascos aguas abajo.

Solucion: ampliar el ESTADO de cada agente con una senal de
"presion del vecino aguas abajo". Asi el agente puede evitar inundar
un vecino lleno.

Estado (coordinado)
-------------------
  (clase_cola_A, clase_cola_B, grupo_verde, presion_vecino)

  - clase_cola_A / clase_cola_B : discretizacion de las colas propias
    (reutiliza el esquema de QLearningAgent; por defecto 3 niveles).
  - grupo_verde : 0 o 1 (que grupo tiene verde ahora).
  - presion_vecino : 0 (vecino despejado) / 1 (vecino congestionado),
    referida al vecino hacia el que apunta el grupo que PODRIA recibir
    el verde. Si el agente no tiene vecino relevante, es siempre 0.

Esto multiplica el espacio de estados por 2 respecto al agente local,
lo cual es asumible.

Acciones (iguales que antes): 0 = mantener verde, 1 = pedir cambio.

Compatibilidad
--------------
Hereda de QLearningAgent (agents/sumo_q_learning.py) y solo redefine
el estado. El resto (learn, choose_action, save/load, epsilon) se
reutiliza sin cambios.
==================================================================
"""

from agents.sumo_q_learning import QLearningAgent


class CoordinatedQLearningAgent(QLearningAgent):
    """Agente Q-Learning que incorpora la presion de un vecino."""

    def get_state(
        self,
        queue_a,
        queue_b,
        green_group,
        neighbor_pressure=0,
    ):
        # Reutiliza la discretizacion de colas de la clase base y
        # agrega la dimension de presion del vecino (0 o 1).
        return (
            self.classify_queue(queue_a),
            self.classify_queue(queue_b),
            green_group,
            int(neighbor_pressure),
        )
