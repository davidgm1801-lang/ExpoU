"""Visualización en vivo de la intersección con Pygame.

Muestra la intersección, las colas de carros en cada dirección, el estado
del semáforo y las métricas en tiempo real. Permite alternar entre el
agente RL y el semáforo de tiempo fijo para comparar visualmente.

Controles:
    ESPACIO  -> alternar entre agente RL y semáforo fijo
    R        -> reiniciar episodio
    +/-      -> acelerar / ralentizar la simulación
    ESC/Q    -> salir

Uso:
    python visualize.py                # usa q_table.pkl
"""
import argparse
import sys

import pygame

from simulation import Intersection, SimConfig
from simulation.intersection import PHASE_DIRECTIONS
from agents import QLearningAgent, FixedTimerAgent

# --- Colores ---
BG = (30, 32, 38)
ROAD = (55, 58, 66)
CAR = (90, 170, 255)
CAR_PED = (255, 190, 80)
GREEN = (60, 220, 100)
RED = (230, 70, 70)
YELLOW = (240, 210, 70)
TEXT = (230, 230, 235)
MUTED = (150, 155, 165)

W, H = 900, 700
CENTER = (W // 2, H // 2 - 40)
ROAD_W = 120
CAR_SIZE = 16
CAR_GAP = 4


class Visualizer:
    def __init__(self, model_path: str):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Semáforo Inteligente con RL 🚦")
        self.font = pygame.font.SysFont("consolas", 18)
        self.big = pygame.font.SysFont("consolas", 26, bold=True)
        self.clock = pygame.time.Clock()
        self.fps = 6

        self.env = Intersection(SimConfig(seed=None))

        self.rl = QLearningAgent(num_actions=self.env.num_actions)
        self.rl.load(model_path)
        self.fixed = FixedTimerAgent(green_duration=10)

        self.use_rl = True
        self.state = self.env.reset()

    @property
    def agent(self):
        return self.rl if self.use_rl else self.fixed

    def act(self):
        if self.use_rl:
            return self.rl.act(self.state, explore=False)
        return self.fixed.act(self.state)

    def reset(self):
        self.agent.reset()
        self.state = self.env.reset()

    # ------------------------------------------------------------------ #
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.use_rl = not self.use_rl
                        self.reset()
                    elif event.key == pygame.K_r:
                        self.reset()
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.fps = min(60, self.fps + 2)
                    elif event.key == pygame.K_MINUS:
                        self.fps = max(1, self.fps - 2)

            action = self.act()
            result = self.env.step(action)
            self.state = result.state
            if result.done:
                self.reset()

            self.draw()
            self.clock.tick(self.fps)

        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------ #
    def draw(self):
        self.screen.fill(BG)
        self._draw_roads()
        self._draw_lights()
        self._draw_queues()
        self._draw_hud()
        pygame.display.flip()

    def _draw_roads(self):
        cx, cy = CENTER
        pygame.draw.rect(self.screen, ROAD, (cx - ROAD_W // 2, 0, ROAD_W, H))
        pygame.draw.rect(self.screen, ROAD, (0, cy - ROAD_W // 2, W, ROAD_W))

    def _draw_lights(self):
        """Dibuja los 4 semáforos. Verde si su eje tiene paso y no hay amarillo."""
        cx, cy = CENTER
        green_dirs = PHASE_DIRECTIONS[self.env.current_phase]
        is_yellow = self.env.yellow_remaining > 0

        def color_for(direction):
            if is_yellow:
                return YELLOW
            return GREEN if direction in green_dirs else RED

        off = ROAD_W // 2 + 16
        positions = {
            "N": (cx, cy - off),
            "S": (cx, cy + off),
            "E": (cx + off, cy),
            "O": (cx - off, cy),
        }
        for d, (x, y) in positions.items():
            pygame.draw.circle(self.screen, color_for(d), (x, y), 10)

    def _draw_queues(self):
        """Dibuja los carros esperando como una fila en cada aproximación."""
        cx, cy = CENTER
        q = self.env.queues

        # Norte: fila que sube desde el centro hacia arriba.
        for i in range(q["N"]):
            y = cy - ROAD_W // 2 - 30 - i * (CAR_SIZE + CAR_GAP)
            self._car(cx - 28, y)
        # Sur.
        for i in range(q["S"]):
            y = cy + ROAD_W // 2 + 20 + i * (CAR_SIZE + CAR_GAP)
            self._car(cx + 12, y)
        # Este.
        for i in range(q["E"]):
            x = cx + ROAD_W // 2 + 20 + i * (CAR_SIZE + CAR_GAP)
            self._car(x, cy - 28)
        # Oeste.
        for i in range(q["O"]):
            x = cx - ROAD_W // 2 - 30 - i * (CAR_SIZE + CAR_GAP)
            self._car(x, cy + 12)

    def _car(self, x, y):
        pygame.draw.rect(self.screen, CAR, (x, y, CAR_SIZE, CAR_SIZE), border_radius=3)

    def _draw_hud(self):
        mode = "RL (Inteligente)" if self.use_rl else "Tiempo Fijo"
        mode_color = GREEN if self.use_rl else MUTED
        m = self.env.metrics()

        self._text(self.big, f"Modo: {mode}", 20, 20, mode_color)
        y = 60
        lines = [
            f"Paso: {self.env.step_count}/{self.env.cfg.steps_per_episode}",
            f"Esperando ahora: {sum(self.env.queues.values())}",
            f"Espera promedio/paso: {m['avg_waiting_per_step']:.2f}",
            f"Carros atendidos: {m['total_passed']}",
            f"FPS: {self.fps}",
        ]
        for line in lines:
            self._text(self.font, line, 20, y, TEXT)
            y += 26

        help_lines = [
            "ESPACIO: cambiar modo   R: reiniciar",
            "+/-: velocidad   ESC: salir",
        ]
        yy = H - 54
        for line in help_lines:
            self._text(self.font, line, 20, yy, MUTED)
            yy += 24

    def _text(self, font, s, x, y, color):
        self.screen.blit(font.render(s, True, color), (x, y))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=str, default="q_table.pkl")
    args = p.parse_args()
    Visualizer(args.model).run()
