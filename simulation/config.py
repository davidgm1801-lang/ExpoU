"""Parámetros de configuración de la simulación.

Centralizamos aquí todos los números para poder experimentar fácilmente
sin tocar la lógica del entorno.
"""
from dataclasses import dataclass


@dataclass
class SimConfig:
    # --- Direcciones de la intersección ---
    # Agrupamos en 2 fases enfrentadas (como un cruce real):
    #   Fase 0 -> Norte-Sur en verde
    #   Fase 1 -> Este-Oeste en verde
    directions = ("N", "S", "E", "O")

    # --- Dinámica del tráfico ---
    # Probabilidad de que llegue un carro nuevo a cada dirección en cada paso.
    # Lo hacemos distinto por dirección para que el agente tenga algo que aprender:
    # si todas las direcciones fueran iguales, un temporizador fijo bastaría.
    arrival_rates = {"N": 0.35, "S": 0.35, "E": 0.12, "O": 0.12}

    # Cuántos carros cruzan por paso cuando el semáforo está en verde.
    cars_passing_per_step: int = 2

    # Cola máxima por dirección (para acotar el espacio de estados).
    max_queue: int = 20

    # --- Reglas del semáforo ---
    # Tiempo mínimo que una fase debe permanecer en verde antes de poder cambiar.
    # Evita el "flickering" (cambios demasiado rápidos) que sería irreal y peligroso.
    min_green_steps: int = 3

    # Pasos de "amarillo" / despeje al cambiar de fase, durante los cuales
    # ninguna dirección avanza (modela el ámbar + todo-rojo de seguridad).
    yellow_steps: int = 2

    # --- Episodio ---
    steps_per_episode: int = 300

    # Semilla para reproducibilidad (None = aleatorio).
    seed: int | None = None
