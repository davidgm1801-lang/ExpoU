import random
import pickle


class QLearningAgent:

    def __init__(
        self,
        learning_rate=0.1,
        discount_factor=0.95,
        epsilon=1.0,
        epsilon_min=0.05,
        epsilon_decay=0.995
    ):

        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay

        self.q_table = {}

    def get_state(self, queue_a, queue_b, green_group):

        def classify_queue(queue):

            if queue == 0:
                return 0

            elif queue <= 3:
                return 1

            else:
                return 2

        return (
            classify_queue(queue_a),
            classify_queue(queue_b),
            green_group
        )

    def initialize_state(self, state):

        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]

    def choose_action(self, state):

        self.initialize_state(state)

        # Exploración: elegir una acción aleatoria.
        if random.random() < self.epsilon:
            return random.choice([0, 1])

        # Explotación: elegir la acción con mayor valor Q.
        values = self.q_table[state]
        best_value = max(values)

        best_actions = [
            action
            for action, value in enumerate(values)
            if value == best_value
        ]

        return random.choice(best_actions)

    def learn(self, state, action, reward, next_state, done=False):

        self.initialize_state(state)
        self.initialize_state(next_state)

        current_q = self.q_table[state][action]

        if done:
            future_q = 0
        else:
            future_q = max(self.q_table[next_state])

        new_q = current_q + self.alpha * (
            reward + self.gamma * future_q - current_q
        )

        self.q_table[state][action] = new_q

    def decay_exploration(self):

        self.epsilon = max(
            self.epsilon_min,
            self.epsilon * self.epsilon_decay
        )

    def save(self, filename="q_table_sumo.pkl"):

        data = {
            "q_table": self.q_table,
            "epsilon": self.epsilon
        }

        with open(filename, "wb") as file:
            pickle.dump(data, file)

    def load(self, filename="q_table_sumo.pkl"):

        try:

            with open(filename, "rb") as file:
                data = pickle.load(file)

            self.q_table = data["q_table"]
            self.epsilon = data["epsilon"]

            print("Modelo cargado correctamente.")

        except FileNotFoundError:

            print(
                "No existe un modelo anterior. "
                "Empezaremos desde cero."
            )

