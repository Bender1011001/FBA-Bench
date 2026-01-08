"""
Scenario Registry for the FBA-Bench benchmarking framework.

This module provides a centralized registry to manage and access different
types of scenarios used in benchmark runs.
"""

from typing import Any, Dict, List, Type


class ScenarioRegistry:
    """
    A registry for managing benchmark scenarios.

    Allows for dynamic registration and retrieval of scenario implementations.
    """

    _instance = None
    _scenarios: Dict[str, Type[Any]]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ScenarioRegistry, cls).__new__(cls)
            cls._instance._scenarios = {}  # Store scenario classes
        return cls._instance

    def register(self, scenario_id: str, scenario_class: Type[Any]):
        """
        Register a scenario class with a unique ID.

        Args:
            scenario_id: A unique string identifier for the scenario.
            scenario_class: The class of the scenario to register.

        Raises:
            ValueError: If a scenario with the same ID is already registered.
        """
        if scenario_id in self._scenarios:
            raise ValueError(f"Scenario with ID '{scenario_id}' already registered.")
        self._scenarios[scenario_id] = scenario_class
        # print(f"Registered scenario: {scenario_id}") # For debugging

    def get(self, scenario_id: str) -> Type[Any]:
        """
        Retrieve a scenario class by its ID.

        Args:
            scenario_id: The unique string identifier for the scenario.

        Returns:
            The registered scenario class.

        Raises:
            KeyError: If no scenario with the given ID is registered.
        """
        try:
            return self._scenarios[scenario_id]
        except KeyError:
            raise KeyError(f"No scenario registered with ID '{scenario_id}'.")

    def list_scenarios(self) -> List[str]:
        """
        List all registered scenario IDs.

        Returns:
            A list of strings, where each string is a scenario ID.
        """
        return list(self._scenarios.keys())

    def clear(self):
        """
        Clears all registered scenarios.
        This method is primarily for testing or reinitialization purposes.
        """
        self._scenarios.clear()


# Global instance of the ScenarioRegistry for easy access
scenario_registry = ScenarioRegistry()
