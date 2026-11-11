"""Entrena el agente Q-Learning sobre la intersección.

Uso:
    python train.py                # entrena 2000 episodios
    python train.py --episodes 500 # entrena menos
"""
import argparse

from simulation import Intersection, SimConfig
from agents import QLearningAgent


def train(episodes: int, seed: int, out_path: str) -> QLearningAgent:
    cfg = SimConfig(seed=seed)
    env = Intersection(cfg)
    agent = QLearningAgent(num_actions=env.num_actions, seed=seed)

    recent_rewards = []
    for ep in range(1, episodes + 1):
        state = env.reset()
        done = False
        total_reward = 0.0

        while not done:
            action = agent.act(state, explore=True)
            result = env.step(action)
            agent.learn(state, action, result.reward, result.state, result.done)
            state = result.state
            total_reward += result.reward
            done = result.done

        agent.decay_epsilon()
        recent_rewards.append(total_reward)

        # Log de progreso cada 100 episodios.
        if ep % 100 == 0:
            avg = sum(recent_rewards[-100:]) / len(recent_rewards[-100:])
            m = env.metrics()
            print(
                f"Ep {ep:4d} | recompensa media {avg:8.1f} "
                f"| espera/paso {m['avg_waiting_per_step']:5.2f} "
                f"| eps {agent.epsilon:.3f} "
                f"| estados aprendidos {len(agent.q)}"
            )

    agent.save(out_path)
    print(f"\n✅ Agente guardado en: {out_path}")
    return agent


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=str, default="q_table.pkl")
    args = p.parse_args()
    train(args.episodes, args.seed, args.out)
