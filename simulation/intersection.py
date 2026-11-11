"""Entorno de simulación de una intersección de 4 vías.

Modela un cruce con dos fases de semáforo (Norte-Sur y Este-Oeste).
Expone una interfaz estilo Gym: reset() y step(action).

El entorno es deliberadamente discreto y simple para que el estado
sea manejable con Q-Learning tabular, pero captura los compromisos
reales: colas que crecen, tiempo de despeje (amarillo) y un verde
mínimo por seguridad.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .config import SimConfig


# Qué direcciones avanzan en cada fase.
PHASE_DIRECTIONS = {
    0: ("N", "S"),   # Fase 0: eje Norte-Sur en verde
    1: ("E", "O"),   # Fase 1: eje Este-Oeste en verde
}

# Las dos acciones que el agente puede tomar en cada paso de decisión.
ACTION_KEEP = 0    # mantener la fase actual
ACTION_SWITCH = 1  # cambiar a la otra fase


@dataclass
class StepResult:
    """Lo que devuelve step(): resultado de un paso de simulación."""
    state: tuple
    reward: float
    done: bool
    info: dict = field(default_factory=dict)


class Intersection:
    def __init__(self, config: SimConfig | None = None):
        self.cfg = config or SimConfig()
        self._rng = random.Random(self.cfg.seed)
        self.reset()

    # ------------------------------------------------------------------ #
    # API estilo Gym
    # ------------------------------------------------------------------ #
    def reset(self) -> tuple:
        """Reinicia la intersección a un estado vacío y devuelve el estado inicial."""
        self.queues = {d: 0 for d in self.cfg.directions}
        self.current_phase = 0          # arrancamos con Norte-Sur en verde
        self.time_in_phase = 0          # pasos desde el último cambio de fase
        self.yellow_remaining = 0       # pasos de amarillo pendientes
        self.step_count = 0

        # Métricas acumuladas (para evaluación).
        self.total_wait = 0             # suma de carros esperando en todos los pasos
        self.total_passed = 0           # carros que lograron cruzar
        self.max_queue_seen = 0

        return self._get_state()

    def step(self, action: int) -> StepResult:
        """Avanza la simulación un paso aplicando la acción del agente.

        action: ACTION_KEEP (0) o ACTION_SWITCH (1).
        """
        self._apply_action(action)
        self._spawn_arrivals()
        passed = self._move_cars()

        # Métricas.
        waiting_now = sum(self.queues.values())
        self.total_wait += waiting_now
        self.total_passed += passed
        self.max_queue_seen = max(self.max_queue_seen, max(self.queues.values()))

        # Recompensa: penalizamos la cantidad total de carros esperando.
        # Minimizar esto equivale a minimizar el tiempo de espera agregado.
        reward = -float(waiting_now)

        self.step_count += 1
        self.time_in_phase += 1
        done = self.step_count >= self.cfg.steps_per_episode

        info = {"passed": passed, "waiting": waiting_now}
        return StepResult(self._get_state(), reward, done, info)

    # ------------------------------------------------------------------ #
    # Dinámica interna
    # ------------------------------------------------------------------ #
    def _apply_action(self, action: int) -> None:
        """Procesa la decisión de mantener o cambiar de fase, respetando
        el verde mínimo y disparando el periodo de amarillo al cambiar."""
        # Si estamos en amarillo, nadie decide nada: consumimos el despeje.
        if self.yellow_remaining > 0:
            self.yellow_remaining -= 1
            return

        can_switch = self.time_in_phase >= self.cfg.min_green_steps
        if action == ACTION_SWITCH and can_switch:
            # Inicia transición: empieza el amarillo y se prepara el cambio.
            self.yellow_remaining = self.cfg.yellow_steps
            self.current_phase = 1 - self.current_phase
            self.time_in_phase = 0

    def _spawn_arrivals(self) -> None:
        """Llegada estocástica de carros nuevos a cada dirección."""
        for d in self.cfg.directions:
            if self._rng.random() < self.cfg.arrival_rates[d]:
                self.queues[d] = min(self.queues[d] + 1, self.cfg.max_queue)

    def _move_cars(self) -> int:
        """Deja cruzar carros de las direcciones con verde.
        Durante el amarillo no cruza nadie (despeje de seguridad)."""
        if self.yellow_remaining > 0:
            return 0

        passed = 0
        for d in PHASE_DIRECTIONS[self.current_phase]:
            moving = min(self.queues[d], self.cfg.cars_passing_per_step)
            self.queues[d] -= moving
            passed += moving
        return passed

    # ------------------------------------------------------------------ #
    # Representación del estado
    # ------------------------------------------------------------------ #
    def _get_state(self) -> tuple:
        """Discretiza el estado para Q-Learning tabular.

        Para mantener la tabla Q manejable, agrupamos las colas en niveles
        (bins) en lugar de usar el conteo exacto. Representamos el tráfico
        por EJE (NS vs EO), que es lo que importa para decidir la fase.
        """
        ns = self.queues["N"] + self.queues["S"]
        eo = self.queues["E"] + self.queues["O"]
        return (
            self._bin(ns),
            self._bin(eo),
            self.current_phase,
            1 if self.yellow_remaining > 0 else 0,
            min(self.time_in_phase, self.cfg.min_green_steps),  # saturado
        )

    @staticmethod
    def _bin(count: int) -> int:
        """Agrupa un conteo de carros en niveles discretos: 0, bajo, medio, alto, saturado."""
        if count == 0:
            return 0
        if count <= 3:
            return 1
        if count <= 7:
            return 2
        if count <= 12:
            return 3
        return 4

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    @property
    def num_actions(self) -> int:
        return 2

    def metrics(self) -> dict:
        """Resumen de desempeño del episodio."""
        steps = max(self.step_count, 1)
        return {
            "avg_waiting_per_step": self.total_wait / steps,
            "total_passed": self.total_passed,
            "max_queue_seen": self.max_queue_seen,
        }
