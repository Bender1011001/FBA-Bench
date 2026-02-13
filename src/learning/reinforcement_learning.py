from __future__ import annotations

from typing import List

import numpy as np


class ReinforcementLearning:
    """Simple tabular Q-learning implementation used by unit tests."""

    def __init__(
        self,
        *,
        state_space_size: int,
        action_space_size: int,
        learning_rate: float = 0.01,
        discount_factor: float = 0.99,
        exploration_rate: float = 0.1,
    ) -> None:
        self._state_space_size = int(state_space_size)
        self._action_space_size = int(action_space_size)
        self._learning_rate = float(learning_rate)
        self._discount_factor = float(discount_factor)
        self._exploration_rate = float(exploration_rate)

        self._q_table = np.zeros(
            (self._state_space_size, self._action_space_size), dtype=float
        )

    def select_action(self, state: int) -> int:
        state_i = int(state)
        if np.random.random() < self._exploration_rate:
            return int(np.random.choice(self._action_space_size))
        return int(np.argmax(self._q_table[state_i]))

    def update_q_table(
        self, state: int, action: int, reward: float, next_state: int
    ) -> None:
        s = int(state)
        a = int(action)
        ns = int(next_state)
        r = float(reward)

        best_next = float(np.max(self._q_table[ns]))
        td_target = r + self._discount_factor * best_next
        td_error = td_target - self._q_table[s, a]
        self._q_table[s, a] = self._q_table[s, a] + self._learning_rate * td_error

    def decay_exploration_rate(
        self, *, decay_rate: float = 0.99, min_rate: float = 0.0
    ) -> None:
        self._exploration_rate = max(
            float(min_rate), self._exploration_rate * float(decay_rate)
        )

    def get_policy(self) -> List[int]:
        return [int(np.argmax(self._q_table[s])) for s in range(self._state_space_size)]

    def save_model(self, filepath: str) -> None:
        np.save(filepath, self._q_table)

    def load_model(self, filepath: str) -> None:
        self._q_table = np.load(filepath)
