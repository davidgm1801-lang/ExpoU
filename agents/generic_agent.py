"""
==================================================================
AGENTE Q-LEARNING GENERICO MULTI-GRUPO - Sistema de 19 (ExpoU)
==================================================================

Generaliza el agente local para manejar semaforos con CUALQUIER
numero de grupos verdes (1, 2, 3...), no solo 2 (A/B). Asi un mismo
diseno sirve para las 19 intersecciones de la red.

Estado
------
  (cola_grupo_activo, cola_max_otros, indice_grupo_activo)

  - cola_grupo_activo : clase de cola del grupo que tiene verde ahora.
  - cola_max_otros    : clase de la cola MAXIMA entre los demas grupos
                        (resume "cuanto presiona el resto" sin explotar
                        el espacio de estados con N grupos).
  - indice_grupo_activo : que grupo tiene verde (0..N-1).

Las colas se discretizan en 3 clases (0 / 1-3 / >3) por defecto.
Esta representacion es de tamano ACOTADO aunque N crezca: el estado no
depende del numero de grupos salvo por 'indice_grupo_activo'.

Acciones
--------
  0 = mantener el grupo verde actual.
  1 = pasar al siguiente grupo verde (rotacion ciclica).

Es decir, la decision es siempre binaria (quedarse o avanzar), lo que
mantiene la tabla Q pequena y el aprendizaje estable, funcione el
semaforo con 2 o con 5 grupos.
==================================================================
"""

import random
import pickle


class GenericQLearningAgent:

    def __init__(
        self,
        learning_rate=0.1,
        discount_factor=0.95,
        epsilon=1.0,
        epsilon_min=0.05,
        epsilon_decay=0.97,
        queue_thresholds=None,
    ):
        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        if queue_thresholds is None:
            queue_thresholds = [0, 3]
        self.queue_thresholds = queue_thresholds
        self.q_table = {}

    def classify_queue(self, queue):
        for i, limite in enumerate(self.queue_thresholds):
            if queue <= limite:
                return i
        return len(self.queue_thresholds)

    def get_state(self, cola_activo, cola_max_otros, indice_activo):
        return (
            self.classify_queue(cola_activo),
            self.classify_queue(cola_max_otros),
            int(indice_activo),
        )

    def initialize_state(self, state):
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]

    def choose_action(self, state):
        self.initialize_state(state)
        if random.random() < self.epsilon:
            return random.choice([0, 1])
        valores = self.q_table[state]
        mejor = max(valores)
        mejores = [a for a, v in enumerate(valores) if v == mejor]
        return random.choice(mejores)

    def best_action(self, state):
        # Determinista (para evaluacion, epsilon=0).
        if state not in self.q_table:
            return 0
        v = self.q_table[state]
        return 0 if v[0] >= v[1] else 1

    def learn(self, state, action, reward, next_state, done=False):
        self.initialize_state(state)
        self.initialize_state(next_state)
        actual = self.q_table[state][action]
        futuro = 0 if done else max(self.q_table[next_state])
        self.q_table[state][action] = actual + self.alpha * (
            reward + self.gamma * futuro - actual
        )

    def decay_exploration(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def save(self, filename):
        with open(filename, "wb") as f:
            pickle.dump({"q_table": self.q_table, "epsilon": self.epsilon}, f)

    def load(self, filename):
        with open(filename, "rb") as f:
            datos = pickle.load(f)
        self.q_table = datos["q_table"]
        self.epsilon = datos["epsilon"]
