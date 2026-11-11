"""Compara el agente Q-Learning entrenado contra el semáforo de tiempo fijo.

Ejecuta ambos agentes sobre los MISMOS episodios (misma semilla) para una
comparación justa, y reporta el tiempo de espera promedio y carros atendidos.

Uso:
    python evaluate.py                 # usa q_table.pkl
    python evaluate.py --episodes 100
"""
import argparse

from simulation import Intersection, SimConfig
from agents import QLearningAgent, FixedTimerAgent


def run_agent(agent, episodes: int, base_seed: int, explore_kwarg: bool | None):
    """Corre un agente sobre 'episodes' episodios y promedia las métricas."""
    totals = {"avg_waiting_per_step": 0.0, "total_passed": 0, "max_queue_seen": 0}

    for ep in range(episodes):
        # Misma semilla por episodio para ambos agentes -> comparación justa.
        cfg = SimConfig(seed=base_seed + ep)
        env = Intersection(cfg)
        agent.reset()
        state = env.reset()
        done = False

        while not done:
            if explore_kwarg is None:
                action = agent.act(state)
            else:
                action = agent.act(state, explore=explore_kwarg)
            result = env.step(action)
            state = result.state
            done = result.done

        m = env.metrics()
        totals["avg_waiting_per_step"] += m["avg_waiting_per_step"]
        totals["total_passed"] += m["total_passed"]
        totals["max_queue_seen"] = max(totals["max_queue_seen"], m["max_queue_seen"])

    totals["avg_waiting_per_step"] /= episodes
    totals["total_passed"] /= episodes
    return totals


def main(model_path: str, episodes: int, seed: int) -> None:
    env = Intersection(SimConfig())

    rl = QLearningAgent(num_actions=env.num_actions)
    rl.load(model_path)

    fixed = FixedTimerAgent(green_duration=10)

    print(f"Evaluando sobre {episodes} episodios...\n")
    rl_m = run_agent(rl, episodes, seed, explore_kwarg=False)
    fx_m = run_agent(fixed, episodes, seed, explore_kwarg=None)

    print("=" * 56)
    print(f"{'Métrica':<34}{'Fijo':>10}{'RL':>12}")
    print("-" * 56)
    print(f"{'Carros esperando / paso':<34}{fx_m['avg_waiting_per_step']:>10.2f}"
          f"{rl_m['avg_waiting_per_step']:>12.2f}")
    print(f"{'Carros atendidos / episodio':<34}{fx_m['total_passed']:>10.1f}"
          f"{rl_m['total_passed']:>12.1f}")
    print(f"{'Cola máxima observada':<34}{fx_m['max_queue_seen']:>10d}"
          f"{rl_m['max_queue_seen']:>12d}")
    print("=" * 56)

    improvement = (
        (fx_m["avg_waiting_per_step"] - rl_m["avg_waiting_per_step"])
        / fx_m["avg_waiting_per_step"] * 100
    )
    print(f"\n🚦 El agente RL reduce la espera promedio en {improvement:.1f}% "
          f"frente al semáforo de tiempo fijo.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=str, default="q_table.pkl")
    p.add_argument("--episodes", type=int, default=100)
    p.add_argument("--seed", type=int, default=1000)
    args = p.parse_args()
    main(args.model, args.episodes, args.seed)
