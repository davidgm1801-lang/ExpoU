"""
==================================================================
AGENTE GENERICO COORDINADO - Sistema de 18 coordinadas (ExpoU)
==================================================================

Combina lo mejor de dos sistemas:
  - GENERICO: maneja cualquier numero de grupos verdes (sistema 19).
  - COORDINADO: observa la presion del vecino aguas abajo (Etapa 4,
    que gano 5/5 al baseline).

Estado
------
  (cola_grupo_activo, cola_max_otros, indice_activo, presion_vecino)

  - Los tres primeros, como el agente generico.
  - presion_vecino: 0/1 segun si el vecino hacia el que vierte el
    grupo activo esta congestionado. Si el grupo no tiene vecino
    controlado, es 0.

Accion: 0 = mantener verde, 1 = avanzar al siguiente grupo.

La hipotesis (respaldada por la Etapa 4) es que esta senal evita que
los agentes inunden a sus vecinos, reduciendo los atascos que se
propagan por la red — la causa de la inestabilidad detectada en la
Etapa 3.
==================================================================
"""

from agents.generic_agent import GenericQLearningAgent


class GenericCoordinatedAgent(GenericQLearningAgent):

    def get_state(
        self,
        cola_activo,
        cola_max_otros,
        indice_activo,
        presion_vecino=0,
    ):
        return (
            self.classify_queue(cola_activo),
            self.classify_queue(cola_max_otros),
            int(indice_activo),
            int(presion_vecino),
        )
