"""Agente de aprendizaje por refuerzo con Q-Learning tabular.

Q-Learning aprende una tabla Q[estado][acción] que estima la recompensa
futura esperada de tomar cada acción en cada estado. Con el tiempo, el
agente aprende a elegir la acción que minimiza las colas.

Usamos Q-Learning tabular (en vez de deep RL) porque:
  - El espacio de estados es pequeño y discreto -> cabe en una tabla.
  - Es transparente: puedes inspeccionar la tabla aprendida.
  - Entrena en segundos sin GPU.
"""
from __future__ import annotations

import pickle
import random
from collections import defaultdict


class QLearningAgent:
    def __init__(
        self,
        num_actions: int,
        alpha: float = 0.1,      # tasa de aprendizaje: cuánto pesa cada nueva experiencia
        gamma: float = 0.95,     # factor de descuento: cuánto importa el futuro
        epsilon: float = 1.0,    # exploración inicial (100% aleatorio al empezar)
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        seed: int | None = None,
    ):
        self.num_actions = num_actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self._rng = random.Random(seed)

        # Q-table: estado -> lista de valores Q (uno por acción).
        # defaultdict para que estados nuevos arranquen en 0 automáticamente.
        self.q: dict[tuple, list[float]] = defaultdict(
            lambda: [0.0] * self.num_actions
        )

    def act(self, state: tuple, explore: bool = True) -> int:
        """Elige una acción con política epsilon-greedy.

        Con probabilidad epsilon explora (acción aleatoria); si no, explota
        (la mejor acción conocida). En evaluación, explore=False -> siempre explota.
        """
        if explore and self._rng.random() < self.epsilon:
            return self._rng.randrange(self.num_actions)
        return self._argmax(self.q[state])

    def learn(self, state, action, reward, next_state, done) -> None:
        """Actualiza Q con la ecuación de Bellman (regla de Q-Learning)."""
        current = self.q[state][action]
        # El mejor valor futuro estimado desde el siguiente estado.
        future = 0.0 if done else max(self.q[next_state])
        target = reward + self.gamma * future
        # Movemos el valor actual un poco hacia el objetivo.
        self.q[state][action] = current + self.alpha * (target - current)

    def decay_epsilon(self) -> None:
        """Reduce la exploración gradualmente a medida que el agente aprende."""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def reset(self) -> None:
        """Compatibilidad de interfaz con el baseline (no necesita estado interno)."""

    # ------------------------------------------------------------------ #
    # Persistencia
    # ------------------------------------------------------------------ #
    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(dict(self.q), f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.q = defaultdict(lambda: [0.0] * self.num_actions, data)

    # ------------------------------------------------------------------ #
    def _argmax(self, values: list[float]) -> int:
        """argmax con desempate aleatorio (evita sesgar siempre a la acción 0)."""
        best = max(values)
        candidates = [i for i, v in enumerate(values) if v == best]
        return self._rng.choice(candidates)
