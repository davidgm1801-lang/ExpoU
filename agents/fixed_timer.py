"""Agente baseline: semáforo de tiempo fijo.

Representa el semáforo "tonto" tradicional: cambia de fase cada N pasos
sin mirar cuántos carros hay. Es nuestro punto de comparación para
demostrar cuánto mejora el agente de aprendizaje por refuerzo.
"""
from simulation.intersection import ACTION_KEEP, ACTION_SWITCH


class FixedTimerAgent:
    def __init__(self, green_duration: int = 10):
        # Cada fase dura 'green_duration' pasos antes de cambiar.
        self.green_duration = green_duration
        self._steps_in_phase = 0

    def reset(self) -> None:
        self._steps_in_phase = 0

    def act(self, state: tuple) -> int:
        """Ignora el estado por completo: solo cuenta el tiempo."""
        self._steps_in_phase += 1
        if self._steps_in_phase >= self.green_duration:
            self._steps_in_phase = 0
            return ACTION_SWITCH
        return ACTION_KEEP
