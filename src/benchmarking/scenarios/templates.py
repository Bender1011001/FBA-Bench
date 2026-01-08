"""
Scenario templates for different domains.

This module provides concrete implementations of scenarios for various domains
including e-commerce, healthcare, finance, legal, and scientific research.
"""

import logging
import random
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from fba_bench.core.types import SimulationState

from .base import ScenarioConfig, ScenarioTemplate


class ECommerceScenario(ScenarioTemplate):
    """
    E-commerce scenario for benchmarking agent performance in online retail.

    This scenario simulates an e-commerce environment where agents must manage
    product pricing, inventory, and marketing strategies.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the e-commerce scenario.

        Args:
            config: Scenario configuration
        """
        super().__init__(config)

        # E-commerce specific state
        self.products = []
        self.customers = []
        self.orders = []
        self.competitors = []

        # Market conditions
        self.market_demand = 1.0
        self.seasonal_factor = 1.0
        self.competition_level = 0.5

    def _validate_domain_parameters(self) -> List[str]:
        """
        Validate e-commerce specific parameters.

        Returns:
            List of validation errors
        """
        errors = []

        # Validate product count
        product_count = self.parameters.get("product_count", 10)
        if not isinstance(product_count, int) or product_count <= 0:
            errors.append("product_count must be a positive integer")

        # Validate customer count
        customer_count = self.parameters.get("customer_count", 100)
        if not isinstance(customer_count, int) or customer_count <= 0:
            errors.append("customer_count must be a positive integer")

        # Validate initial budget
        initial_budget = self.parameters.get("initial_budget", 10000)
        if not isinstance(initial_budget, (int, float)) or initial_budget <= 0:
            errors.append("initial_budget must be a positive number")

        return errors

    async def initialize(self, parameters: Dict[str, Any]) -> None:
        """
        Initialize the e-commerce scenario.

        Args:
            parameters: Scenario-specific parameters
        """
        await super().initialize(parameters)

        # Extract parameters
        product_count = parameters.get("product_count", 10)
        customer_count = parameters.get("customer_count", 100)
        initial_budget = parameters.get("initial_budget", 10000)

        # Generate products
        self.products = self._generate_products(product_count)

        # Generate customers
        self.customers = self._generate_customers(customer_count)

        # Generate competitors
        self.competitors = self._generate_competitors(3)

        # Initialize market conditions
        self.market_demand = random.uniform(0.8, 1.2)
        self.seasonal_factor = random.uniform(0.9, 1.1)
        self.competition_level = random.uniform(0.3, 0.7)

        # Update global state
        self.global_state.update(
            {
                "products": len(self.products),
                "customers": len(self.customers),
                "competitors": len(self.competitors),
                "initial_budget": initial_budget,
                "market_demand": self.market_demand,
                "seasonal_factor": self.seasonal_factor,
                "competition_level": self.competition_level,
            }
        )

        logger.info(
            f"Initialized e-commerce scenario with {len(self.products)} products and {len(self.customers)} customers"
        )

    def _generate_products(self, count: int) -> List[Dict[str, Any]]:
        """Generate random products."""
        products = []
        categories = ["Electronics", "Clothing", "Home", "Books", "Sports"]

        for i in range(count):
            product = {
                "id": f"product_{i}",
                "name": f"Product {i}",
                "category": random.choice(categories),
                "base_price": random.uniform(10, 100),
                "current_price": random.uniform(10, 100),
                "inventory": random.randint(10, 100),
                "cost": random.uniform(5, 50),
                "popularity": random.uniform(0.1, 1.0),
            }
            products.append(product)

        return products

    def _generate_customers(self, count: int) -> List[Dict[str, Any]]:
        """Generate random customers."""
        customers = []

        for i in range(count):
            customer = {
                "id": f"customer_{i}",
                "budget": random.uniform(50, 500),
                "preferences": {
                    "price_sensitivity": random.uniform(0.1, 1.0),
                    "quality_preference": random.uniform(0.1, 1.0),
                    "brand_loyalty": random.uniform(0.1, 1.0),
                },
                "purchase_history": [],
            }
            customers.append(customer)

        return customers

    def _generate_competitors(self, count: int) -> List[Dict[str, Any]]:
        """Generate random competitors."""
        competitors = []

        for i in range(count):
            competitor = {
                "id": f"competitor_{i}",
                "name": f"Competitor {i}",
                "market_share": random.uniform(0.1, 0.3),
                "pricing_strategy": random.choice(
                    ["aggressive", "moderate", "premium"]
                ),
                "reputation": random.uniform(0.5, 1.0),
            }
            competitors.append(competitor)

        return competitors

    async def update_tick(self, tick: int, state: SimulationState) -> None:
        """
        Update the e-commerce scenario for a specific tick.

        Args:
            tick: Current tick number
            state: Current simulation state
        """
        await super().update_tick(tick, state)

        # Simulate market changes
        if tick % 10 == 0:  # Every 10 ticks
            self._update_market_conditions()

        # Simulate customer behavior
        self._simulate_customer_behavior(tick)

        # Simulate competitor actions
        if tick % 5 == 0:  # Every 5 ticks
            self._simulate_competitor_actions(tick)

    def _update_market_conditions(self) -> None:
        """Update market conditions."""
        # Gradual changes in market demand
        self.market_demand += random.uniform(-0.05, 0.05)
        self.market_demand = max(0.5, min(1.5, self.market_demand))

        # Seasonal changes
        self.seasonal_factor += random.uniform(-0.02, 0.02)
        self.seasonal_factor = max(0.8, min(1.2, self.seasonal_factor))

    def _simulate_customer_behavior(self, tick: int) -> None:
        """Simulate customer purchasing behavior."""
        # Random customer purchases
        num_purchases = random.randint(0, len(self.customers) // 10)

        for _ in range(num_purchases):
            customer = random.choice(self.customers)
            product = random.choice(self.products)

            # Calculate purchase probability
            price_factor = 1.0 - (product["current_price"] / 100.0)
            demand_factor = self.market_demand * self.seasonal_factor

            purchase_probability = price_factor * demand_factor * 0.1

            if random.random() < purchase_probability:
                # Make purchase
                order = {
                    "customer_id": customer["id"],
                    "product_id": product["id"],
                    "price": product["current_price"],
                    "quantity": random.randint(1, 5),
                    "timestamp": tick,
                }
                self.orders.append(order)

                # Update product inventory
                product["inventory"] -= order["quantity"]

                # Update customer budget
                customer["budget"] -= order["price"] * order["quantity"]

    def _simulate_competitor_actions(self, tick: int) -> None:
        """Simulate competitor pricing actions."""
        for competitor in self.competitors:
            # Random price adjustments
            if random.random() < 0.3:  # 30% chance
                # Adjust prices of random products
                for product in random.sample(self.products, min(3, len(self.products))):
                    if competitor["pricing_strategy"] == "aggressive":
                        product["current_price"] *= random.uniform(0.95, 0.99)
                    elif competitor["pricing_strategy"] == "premium":
                        product["current_price"] *= random.uniform(1.01, 1.05)
                    else:  # moderate
                        product["current_price"] *= random.uniform(0.98, 1.02)

    async def evaluate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """
        Evaluate agent performance in e-commerce scenario.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary with performance metrics
        """
        base_metrics = await super().evaluate_agent_performance(agent_id)

        if agent_id not in self.agent_states:
            return base_metrics

        agent_state = self.agent_states[agent_id]

        # Calculate e-commerce specific metrics
        total_revenue = sum(order["price"] * order["quantity"] for order in self.orders)
        total_orders = len(self.orders)
        average_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # Calculate profit (simplified)
        total_cost = sum(
            product["cost"] * order["quantity"]
            for order in self.orders
            for product in self.products
            if product["id"] == order["product_id"]
        )
        profit = total_revenue - total_cost

        # Calculate market share
        agent_orders = [
            order for order in self.orders if order.get("agent_id") == agent_id
        ]
        market_share = len(agent_orders) / total_orders if total_orders > 0 else 0

        # Update metrics
        ecommerce_metrics = {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "average_order_value": average_order_value,
            "profit": profit,
            "market_share": market_share,
            "inventory_turnover": self._calculate_inventory_turnover(),
            "customer_satisfaction": random.uniform(0.7, 0.95),  # Simulated
        }

        base_metrics.update(ecommerce_metrics)
        return base_metrics

    def _calculate_inventory_turnover(self) -> float:
        """Calculate inventory turnover ratio."""
        total_sold = sum(order["quantity"] for order in self.orders)
        total_inventory = sum(product["inventory"] for product in self.products)

        if total_inventory == 0:
            return 0.0

        return total_sold / total_inventory


class HealthcareScenario(ScenarioTemplate):
    """
    Healthcare scenario for benchmarking agent performance in medical diagnostics.

    This scenario simulates a healthcare environment where agents must diagnose
    patients, recommend treatments, and manage healthcare resources.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the healthcare scenario.

        Args:
            config: Scenario configuration
        """
        super().__init__(config)

        # Healthcare specific state
        self.patients = []
        self.medical_conditions = []
        self.treatments = []
        self.medical_staff = []

        # Healthcare metrics
        self.diagnostic_accuracy = 0.0
        self.treatment_effectiveness = 0.0
        self.patient_satisfaction = 0.0

    def _validate_domain_parameters(self) -> List[str]:
        """
        Validate healthcare specific parameters.

        Returns:
            List of validation errors
        """
        errors = []

        # Validate patient count
        patient_count = self.parameters.get("patient_count", 50)
        if not isinstance(patient_count, int) or patient_count <= 0:
            errors.append("patient_count must be a positive integer")

        # Validate medical staff count
        staff_count = self.parameters.get("medical_staff_count", 10)
        if not isinstance(staff_count, int) or staff_count <= 0:
            errors.append("medical_staff_count must be a positive integer")

        return errors

    async def initialize(self, parameters: Dict[str, Any]) -> None:
        """
        Initialize the healthcare scenario.

        Args:
            parameters: Scenario-specific parameters
        """
        await super().initialize(parameters)

        # Extract parameters
        patient_count = parameters.get("patient_count", 50)
        staff_count = parameters.get("medical_staff_count", 10)

        # Generate medical conditions
        self.medical_conditions = self._generate_medical_conditions()

        # Generate treatments
        self.treatments = self._generate_treatments()

        # Generate patients
        self.patients = self._generate_patients(patient_count)

        # Generate medical staff
        self.medical_staff = self._generate_medical_staff(staff_count)

        # Update global state
        self.global_state.update(
            {
                "patients": len(self.patients),
                "medical_conditions": len(self.medical_conditions),
                "treatments": len(self.treatments),
                "medical_staff": len(self.medical_staff),
            }
        )

        logger.info(
            f"Initialized healthcare scenario with {len(self.patients)} patients and {len(self.medical_staff)} staff"
        )

    def _generate_medical_conditions(self) -> List[Dict[str, Any]]:
        """Generate medical conditions."""
        conditions = [
            {
                "id": "flu",
                "name": "Influenza",
                "symptoms": ["fever", "cough", "fatigue", "body aches"],
                "severity": random.uniform(0.3, 0.7),
                "prevalence": random.uniform(0.1, 0.3),
            },
            {
                "id": "diabetes",
                "name": "Type 2 Diabetes",
                "symptoms": [
                    "increased thirst",
                    "frequent urination",
                    "fatigue",
                    "blurred vision",
                ],
                "severity": random.uniform(0.5, 0.8),
                "prevalence": random.uniform(0.05, 0.15),
            },
            {
                "id": "hypertension",
                "name": "High Blood Pressure",
                "symptoms": [
                    "headaches",
                    "shortness of breath",
                    "nosebleeds",
                    "chest pain",
                ],
                "severity": random.uniform(0.4, 0.7),
                "prevalence": random.uniform(0.2, 0.4),
            },
        ]
        return conditions

    def _generate_treatments(self) -> List[Dict[str, Any]]:
        """Generate medical treatments."""
        treatments = [
            {
                "id": "medication",
                "name": "Medication Therapy",
                "effectiveness": random.uniform(0.7, 0.9),
                "cost": random.uniform(50, 200),
                "duration": random.randint(7, 30),
            },
            {
                "id": "surgery",
                "name": "Surgical Intervention",
                "effectiveness": random.uniform(0.8, 0.95),
                "cost": random.uniform(1000, 10000),
                "duration": random.randint(1, 7),
            },
            {
                "id": "therapy",
                "name": "Physical Therapy",
                "effectiveness": random.uniform(0.6, 0.8),
                "cost": random.uniform(100, 500),
                "duration": random.randint(14, 90),
            },
        ]
        return treatments

    def _generate_patients(self, count: int) -> List[Dict[str, Any]]:
        """Generate patients."""
        patients = []

        for i in range(count):
            # Assign random condition
            condition = random.choice(self.medical_conditions)

            patient = {
                "id": f"patient_{i}",
                "age": random.randint(18, 80),
                "gender": random.choice(["male", "female"]),
                "condition": condition["id"],
                "symptoms": random.sample(
                    condition["symptoms"], random.randint(2, len(condition["symptoms"]))
                ),
                "severity": random.uniform(0.1, 1.0),
                "medical_history": [],
                "treatment_plan": None,
                "status": "waiting",  # waiting, diagnosed, treating, recovered
            }
            patients.append(patient)

        return patients

    def _generate_medical_staff(self, count: int) -> List[Dict[str, Any]]:
        """Generate medical staff."""
        staff = []
        roles = ["doctor", "nurse", "specialist", "technician"]

        for i in range(count):
            staff_member = {
                "id": f"staff_{i}",
                "name": f"Staff Member {i}",
                "role": random.choice(roles),
                "experience": random.randint(1, 20),
                "specialization": random.choice(
                    ["cardiology", "neurology", "pediatrics", "general"]
                ),
                "workload": 0,
                "patients_assigned": [],
            }
            staff.append(staff_member)

        return staff

    async def update_tick(self, tick: int, state: SimulationState) -> None:
        """
        Update the healthcare scenario for a specific tick.

        Args:
            tick: Current tick number
            state: Current simulation state
        """
        await super().update_tick(tick, state)

        # Simulate patient flow
        if tick % 5 == 0:  # Every 5 ticks
            self._simulate_patient_arrival()

        # Simulate treatment progress
        self._simulate_treatment_progress(tick)

        # Simulate staff workload
        self._update_staff_workload()

    def _simulate_patient_arrival(self) -> None:
        """Simulate new patient arrivals."""
        if random.random() < 0.3:  # 30% chance
            # Generate new patient
            condition = random.choice(self.medical_conditions)

            patient = {
                "id": f"patient_{len(self.patients)}",
                "age": random.randint(18, 80),
                "gender": random.choice(["male", "female"]),
                "condition": condition["id"],
                "symptoms": random.sample(
                    condition["symptoms"], random.randint(2, len(condition["symptoms"]))
                ),
                "severity": random.uniform(0.1, 1.0),
                "medical_history": [],
                "treatment_plan": None,
                "status": "waiting",
                "arrival_time": self.current_tick,
            }
            self.patients.append(patient)

    def _simulate_treatment_progress(self, tick: int) -> None:
        """Simulate treatment progress for patients."""
        for patient in self.patients:
            if patient["status"] == "treating" and patient["treatment_plan"]:
                # Update treatment progress
                treatment = patient["treatment_plan"]
                treatment["progress"] += random.uniform(0.05, 0.15)

                if treatment["progress"] >= 1.0:
                    # Treatment completed
                    patient["status"] = "recovered"
                    treatment["end_time"] = tick

                    # Calculate treatment outcome
                    treatment_success = random.random() < treatment["effectiveness"]
                    patient["treatment_success"] = treatment_success

    def _update_staff_workload(self) -> None:
        """Update medical staff workload."""
        # Reset workload
        for staff in self.medical_staff:
            staff["workload"] = 0
            staff["patients_assigned"] = []

        # Assign patients to staff
        for patient in self.patients:
            if patient["status"] in ["diagnosed", "treating"]:
                # Find available staff
                available_staff = [
                    s for s in self.medical_staff if len(s["patients_assigned"]) < 5
                ]
                if available_staff:
                    staff = random.choice(available_staff)
                    staff["patients_assigned"].append(patient["id"])
                    staff["workload"] += 1

    async def evaluate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """
        Evaluate agent performance in healthcare scenario.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary with performance metrics
        """
        base_metrics = await super().evaluate_agent_performance(agent_id)

        if agent_id not in self.agent_states:
            return base_metrics

        # Calculate healthcare specific metrics
        total_patients = len(self.patients)
        diagnosed_patients = len(
            [
                p
                for p in self.patients
                if p["status"] in ["diagnosed", "treating", "recovered"]
            ]
        )
        treated_patients = len(
            [p for p in self.patients if p["status"] in ["treating", "recovered"]]
        )
        recovered_patients = len(
            [p for p in self.patients if p["status"] == "recovered"]
        )

        # Calculate diagnostic accuracy (simplified)
        agent_diagnoses = [
            p for p in self.patients if p.get("diagnosed_by") == agent_id
        ]
        if agent_diagnoses:
            correct_diagnoses = sum(
                1 for p in agent_diagnoses if p.get("diagnosis_correct", False)
            )
            self.diagnostic_accuracy = correct_diagnoses / len(agent_diagnoses)

        # Calculate treatment effectiveness
        agent_treatments = [
            p
            for p in self.patients
            if p.get("treated_by") == agent_id and p["status"] == "recovered"
        ]
        if agent_treatments:
            successful_treatments = sum(
                1 for p in agent_treatments if p.get("treatment_success", False)
            )
            self.treatment_effectiveness = successful_treatments / len(agent_treatments)

        # Calculate patient satisfaction (simulated)
        self.patient_satisfaction = random.uniform(0.7, 0.95)

        # Update metrics
        healthcare_metrics = {
            "total_patients": total_patients,
            "diagnosed_patients": diagnosed_patients,
            "treated_patients": treated_patients,
            "recovered_patients": recovered_patients,
            "diagnostic_accuracy": self.diagnostic_accuracy,
            "treatment_effectiveness": self.treatment_effectiveness,
            "patient_satisfaction": self.patient_satisfaction,
            "average_wait_time": self._calculate_average_wait_time(),
        }

        base_metrics.update(healthcare_metrics)
        return base_metrics

    def _calculate_average_wait_time(self) -> float:
        """Calculate average patient wait time."""
        waiting_patients = [p for p in self.patients if p["status"] == "waiting"]
        if not waiting_patients:
            return 0.0

        total_wait_time = sum(
            self.current_tick - p.get("arrival_time", self.current_tick)
            for p in waiting_patients
        )

        return total_wait_time / len(waiting_patients)


class FinancialScenario(ScenarioTemplate):
    """
    Financial scenario for benchmarking agent performance in financial analysis.

    This scenario simulates a financial environment where agents must analyze
    market data, make investment decisions, and manage portfolios.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the financial scenario.

        Args:
            config: Scenario configuration
        """
        super().__init__(config)

        # Financial specific state
        self.market_data = []
        self.portfolios = {}
        self.instruments = []
        self.market_conditions = {
            "volatility": 0.2,
            "trend": "stable",
            "liquidity": 0.7,
        }

    def _validate_domain_parameters(self) -> List[str]:
        """
        Validate financial specific parameters.

        Returns:
            List of validation errors
        """
        errors = []

        # Validate initial capital
        initial_capital = self.parameters.get("initial_capital", 100000)
        if not isinstance(initial_capital, (int, float)) or initial_capital <= 0:
            errors.append("initial_capital must be a positive number")

        # Validate instrument count
        instrument_count = self.parameters.get("instrument_count", 20)
        if not isinstance(instrument_count, int) or instrument_count <= 0:
            errors.append("instrument_count must be a positive integer")

        return errors

    async def initialize(self, parameters: Dict[str, Any]) -> None:
        """
        Initialize the financial scenario.

        Args:
            parameters: Scenario-specific parameters
        """
        await super().initialize(parameters)

        # Extract parameters
        initial_capital = parameters.get("initial_capital", 100000)
        instrument_count = parameters.get("instrument_count", 20)

        # Generate financial instruments
        self.instruments = self._generate_instruments(instrument_count)

        # Initialize market data
        self.market_data = self._initialize_market_data()

        # Update global state
        self.global_state.update(
            {
                "initial_capital": initial_capital,
                "instruments": len(self.instruments),
                "market_volatility": self.market_conditions["volatility"],
                "market_trend": self.market_conditions["trend"],
                "market_liquidity": self.market_conditions["liquidity"],
            }
        )

        logger.info(
            f"Initialized financial scenario with {len(self.instruments)} instruments"
        )

    def _generate_instruments(self, count: int) -> List[Dict[str, Any]]:
        """Generate financial instruments."""
        instruments = []
        types = ["stock", "bond", "commodity", "currency", "derivative"]

        for i in range(count):
            instrument = {
                "id": f"instrument_{i}",
                "name": f"Instrument {i}",
                "type": random.choice(types),
                "current_price": random.uniform(10, 1000),
                "volatility": random.uniform(0.1, 0.5),
                "trend": random.choice(["bullish", "bearish", "stable"]),
                "liquidity": random.uniform(0.3, 1.0),
                "market_cap": random.uniform(1000000, 1000000000),
            }
            instruments.append(instrument)

        return instruments

    def _initialize_market_data(self) -> List[Dict[str, Any]]:
        """Initialize market data."""
        market_data = []

        for instrument in self.instruments:
            # Generate historical prices
            prices = []
            current_price = instrument["current_price"]

            for i in range(30):  # 30 days of history
                # Random walk with trend
                change = random.uniform(-0.05, 0.05)
                if instrument["trend"] == "bullish":
                    change += 0.01
                elif instrument["trend"] == "bearish":
                    change -= 0.01

                current_price *= 1 + change
                prices.append(current_price)

            market_data.append(
                {
                    "instrument_id": instrument["id"],
                    "prices": prices,
                    "volume": [random.randint(1000, 100000) for _ in range(30)],
                }
            )

        return market_data

    async def update_tick(self, tick: int, state: SimulationState) -> None:
        """
        Update the financial scenario for a specific tick.

        Args:
            tick: Current tick number
            state: Current simulation state
        """
        await super().update_tick(tick, state)

        # Update market conditions
        self._update_market_conditions(tick)

        # Update instrument prices
        self._update_instrument_prices(tick)

        # Generate market events
        if random.random() < 0.1:  # 10% chance
            self._generate_market_event(tick)

    def _update_market_conditions(self, tick: int) -> None:
        """Update market conditions."""
        # Gradual changes in volatility
        self.market_conditions["volatility"] += random.uniform(-0.02, 0.02)
        self.market_conditions["volatility"] = max(
            0.1, min(0.5, self.market_conditions["volatility"])
        )

        # Trend changes
        if random.random() < 0.05:  # 5% chance
            trends = ["bullish", "bearish", "stable"]
            self.market_conditions["trend"] = random.choice(trends)

        # Liquidity changes
        self.market_conditions["liquidity"] += random.uniform(-0.05, 0.05)
        self.market_conditions["liquidity"] = max(
            0.3, min(1.0, self.market_conditions["liquidity"])
        )

    def _update_instrument_prices(self, tick: int) -> None:
        """Update instrument prices."""
        for instrument in self.instruments:
            # Calculate price change
            volatility_factor = (
                instrument["volatility"] * self.market_conditions["volatility"]
            )

            # Apply trend
            trend_factor = 0.0
            if instrument["trend"] == "bullish":
                trend_factor = 0.005
            elif instrument["trend"] == "bearish":
                trend_factor = -0.005

            # Random change
            random_change = random.uniform(-volatility_factor, volatility_factor)

            # Update price
            price_change = (trend_factor + random_change) * instrument["current_price"]
            instrument["current_price"] += price_change

            # Ensure price doesn't go negative
            instrument["current_price"] = max(0.01, instrument["current_price"])

            # Update market data
            market_data = next(
                (
                    md
                    for md in self.market_data
                    if md["instrument_id"] == instrument["id"]
                ),
                None,
            )
            if market_data:
                market_data["prices"].append(instrument["current_price"])
                if len(market_data["prices"]) > 100:  # Keep last 100 prices
                    market_data["prices"].pop(0)

                market_data["volume"].append(random.randint(1000, 100000))
                if len(market_data["volume"]) > 100:
                    market_data["volume"].pop(0)

    def _generate_market_event(self, tick: int) -> None:
        """Generate random market events."""
        events = [
            "earnings_report",
            "economic_indicator",
            "news_event",
            "regulatory_change",
            "market_sentiment_shift",
        ]

        event = random.choice(events)
        affected_instruments = random.sample(
            self.instruments, random.randint(1, len(self.instruments))
        )

        for instrument in affected_instruments:
            if event == "earnings_report":
                # Positive or negative earnings
                if random.random() < 0.6:  # 60% positive
                    instrument["current_price"] *= random.uniform(1.02, 1.08)
                else:
                    instrument["current_price"] *= random.uniform(0.92, 0.98)

            elif event == "economic_indicator":
                # Economic news affects all instruments similarly
                multiplier = random.uniform(0.98, 1.02)
                instrument["current_price"] *= multiplier

            elif event == "news_event":
                # Random news impact
                instrument["current_price"] *= random.uniform(0.95, 1.05)

            elif event == "regulatory_change":
                # Regulatory changes can have significant impact
                instrument["current_price"] *= random.uniform(0.9, 1.1)

            elif event == "market_sentiment_shift":
                # Sentiment shifts affect trend
                instrument["trend"] = random.choice(["bullish", "bearish", "stable"])

    async def evaluate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """
        Evaluate agent performance in financial scenario.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary with performance metrics
        """
        base_metrics = await super().evaluate_agent_performance(agent_id)

        if agent_id not in self.agent_states:
            return base_metrics

        agent_state = self.agent_states[agent_id]

        # Get agent portfolio
        portfolio = self.portfolios.get(agent_id, {})

        # Calculate financial metrics
        initial_capital = self.global_state.get("initial_capital", 100000)
        current_value = portfolio.get("current_value", initial_capital)

        # Calculate returns
        total_return = (current_value - initial_capital) / initial_capital

        # Calculate risk metrics (simplified)
        portfolio_value_history = portfolio.get("value_history", [initial_capital])
        if len(portfolio_value_history) > 1:
            returns = [
                (portfolio_value_history[i] - portfolio_value_history[i - 1])
                / portfolio_value_history[i - 1]
                for i in range(1, len(portfolio_value_history))
            ]
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
        else:
            volatility = 0.0

        # Calculate Sharpe ratio (simplified, assuming risk-free rate of 2%)
        risk_free_rate = 0.02
        sharpe_ratio = (
            (total_return - risk_free_rate) / volatility if volatility > 0 else 0.0
        )

        # Calculate diversification
        holdings = portfolio.get("holdings", {})
        diversification = (
            len(holdings) / len(self.instruments) if self.instruments else 0.0
        )

        # Update metrics
        financial_metrics = {
            "initial_capital": initial_capital,
            "current_value": current_value,
            "total_return": total_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "diversification": diversification,
            "number_of_trades": portfolio.get("number_of_trades", 0),
            "win_rate": portfolio.get("win_rate", 0.0),
        }

        base_metrics.update(financial_metrics)
        return base_metrics


class LegalScenario(ScenarioTemplate):
    """
    Legal scenario for benchmarking agent performance in legal document review.

    This scenario simulates a legal environment where agents must review documents,
    identify relevant information, and make legal judgments.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the legal scenario.

        Args:
            config: Scenario configuration
        """
        super().__init__(config)

        # Legal specific state
        self.documents = []
        self.cases = []
        self.legal_issues = []
        self.regulations = []

        # Legal metrics
        self.document_accuracy = 0.0
        self.issue_identification_rate = 0.0
        self.compliance_score = 0.0

    def _validate_domain_parameters(self) -> List[str]:
        """
        Validate legal specific parameters.

        Returns:
            List of validation errors
        """
        errors = []

        # Validate document count
        document_count = self.parameters.get("document_count", 100)
        if not isinstance(document_count, int) or document_count <= 0:
            errors.append("document_count must be a positive integer")

        # Validate case complexity
        case_complexity = self.parameters.get("case_complexity", "medium")
        if case_complexity not in ["simple", "medium", "complex"]:
            errors.append("case_complexity must be one of: simple, medium, complex")

        return errors

    async def initialize(self, parameters: Dict[str, Any]) -> None:
        """
        Initialize the legal scenario.

        Args:
            parameters: Scenario-specific parameters
        """
        await super().initialize(parameters)

        # Extract parameters
        document_count = parameters.get("document_count", 100)
        case_complexity = parameters.get("case_complexity", "medium")

        # Generate regulations
        self.regulations = self._generate_regulations()

        # Generate legal issues
        self.legal_issues = self._generate_legal_issues()

        # Generate documents
        self.documents = self._generate_documents(document_count)

        # Generate cases
        self.cases = self._generate_cases(10, case_complexity)

        # Update global state
        self.global_state.update(
            {
                "documents": len(self.documents),
                "cases": len(self.cases),
                "legal_issues": len(self.legal_issues),
                "regulations": len(self.regulations),
                "case_complexity": case_complexity,
            }
        )

        logger.info(
            f"Initialized legal scenario with {len(self.documents)} documents and {len(self.cases)} cases"
        )

    def _generate_regulations(self) -> List[Dict[str, Any]]:
        """Generate legal regulations."""
        regulations = [
            {
                "id": "privacy_law",
                "name": "Privacy Protection Act",
                "description": "Regulates the collection and use of personal data",
                "severity": "high",
                "jurisdiction": "federal",
            },
            {
                "id": "contract_law",
                "name": "Contract Regulation Act",
                "description": "Governs the formation and enforcement of contracts",
                "severity": "medium",
                "jurisdiction": "state",
            },
            {
                "id": "employment_law",
                "name": "Employment Standards Act",
                "description": "Sets minimum standards for employment conditions",
                "severity": "medium",
                "jurisdiction": "state",
            },
            {
                "id": "intellectual_property",
                "name": "Intellectual Property Protection Act",
                "description": "Protects intellectual property rights",
                "severity": "high",
                "jurisdiction": "federal",
            },
        ]
        return regulations

    def _generate_legal_issues(self) -> List[Dict[str, Any]]:
        """Generate legal issues."""
        issues = [
            {
                "id": "data_breach",
                "name": "Data Breach",
                "description": "Unauthorized access to personal data",
                "relevant_regulations": ["privacy_law"],
                "severity": "high",
                "typical_outcomes": ["fines", "injunction", "damages"],
            },
            {
                "id": "breach_of_contract",
                "name": "Breach of Contract",
                "description": "Failure to fulfill contractual obligations",
                "relevant_regulations": ["contract_law"],
                "severity": "medium",
                "typical_outcomes": ["damages", "specific_performance", "termination"],
            },
            {
                "id": "employment_dispute",
                "name": "Employment Dispute",
                "description": "Dispute between employer and employee",
                "relevant_regulations": ["employment_law"],
                "severity": "medium",
                "typical_outcomes": ["settlement", "damages", "reinstatement"],
            },
            {
                "id": "ip_infringement",
                "name": "Intellectual Property Infringement",
                "description": "Unauthorized use of intellectual property",
                "relevant_regulations": ["intellectual_property"],
                "severity": "high",
                "typical_outcomes": ["injunction", "damages", "royalties"],
            },
        ]
        return issues

    def _generate_documents(self, count: int) -> List[Dict[str, Any]]:
        """Generate legal documents."""
        documents = []
        document_types = ["contract", "brief", "motion", "pleading", "discovery"]

        for i in range(count):
            # Assign random legal issues
            num_issues = random.randint(0, 3)
            issues = random.sample(
                self.legal_issues, min(num_issues, len(self.legal_issues))
            )

            document = {
                "id": f"document_{i}",
                "type": random.choice(document_types),
                "title": f"Document {i}",
                "content": f"Content of document {i}",
                "relevant_issues": [issue["id"] for issue in issues],
                "confidentiality": random.choice(
                    ["public", "confidential", "privileged"]
                ),
                "page_count": random.randint(1, 50),
                "creation_date": datetime.now()
                - timedelta(days=random.randint(0, 365)),
            }
            documents.append(document)

        return documents

    def _generate_cases(self, count: int, complexity: str) -> List[Dict[str, Any]]:
        """Generate legal cases."""
        cases = []

        for i in range(count):
            # Assign random legal issues
            num_issues = (
                1 if complexity == "simple" else (2 if complexity == "medium" else 3)
            )
            issues = random.sample(
                self.legal_issues, min(num_issues, len(self.legal_issues))
            )

            # Assign relevant documents
            relevant_docs = random.sample(self.documents, random.randint(5, 20))

            case = {
                "id": f"case_{i}",
                "name": f"Case {i}",
                "description": f"Legal case {i}",
                "complexity": complexity,
                "relevant_issues": [issue["id"] for issue in issues],
                "relevant_documents": [doc["id"] for doc in relevant_docs],
                "status": "active",  # active, settled, dismissed
                "filing_date": datetime.now() - timedelta(days=random.randint(30, 365)),
                "deadline": datetime.now() + timedelta(days=random.randint(30, 180)),
            }
            cases.append(case)

        return cases

    async def update_tick(self, tick: int, state: SimulationState) -> None:
        """
        Update the legal scenario for a specific tick.

        Args:
            tick: Current tick number
            state: Current simulation state
        """
        await super().update_tick(tick, state)

        # Simulate document processing
        if tick % 3 == 0:  # Every 3 ticks
            self._simulate_document_processing()

        # Simulate case progress
        self._simulate_case_progress(tick)

        # Simulate new legal issues
        if random.random() < 0.1:  # 10% chance
            self._simulate_new_legal_issue(tick)

    def _simulate_document_processing(self) -> None:
        """Simulate document processing."""
        # Random document reviews
        unreviewed_docs = [d for d in self.documents if not d.get("reviewed", False)]
        if unreviewed_docs:
            num_reviews = min(random.randint(1, 5), len(unreviewed_docs))
            for doc in random.sample(unreviewed_docs, num_reviews):
                doc["reviewed"] = True
                doc["review_accuracy"] = random.uniform(0.7, 0.95)

    def _simulate_case_progress(self, tick: int) -> None:
        """Simulate case progress."""
        for case in self.cases:
            if case["status"] == "active":
                # Random progress
                if random.random() < 0.2:  # 20% chance of progress
                    # Update case status
                    if random.random() < 0.7:  # 70% chance of positive progress
                        case["progress"] = case.get("progress", 0) + random.uniform(
                            0.1, 0.3
                        )
                    else:  # 30% chance of setback
                        case["progress"] = case.get("progress", 0) - random.uniform(
                            0.05, 0.15
                        )

                    # Check if case should be resolved
                    if case.get("progress", 0) >= 1.0:
                        case["status"] = random.choice(["settled", "dismissed"])
                        case["resolution_date"] = tick

    def _simulate_new_legal_issue(self, tick: int) -> None:
        """Simulate new legal issues arising."""
        # Add new issue to random documents
        if self.documents:
            affected_docs = random.sample(
                self.documents, random.randint(1, min(5, len(self.documents)))
            )
            for doc in affected_docs:
                if "relevant_issues" not in doc:
                    doc["relevant_issues"] = []

                # Add random issue if not already present
                available_issues = [
                    issue
                    for issue in self.legal_issues
                    if issue["id"] not in doc["relevant_issues"]
                ]
                if available_issues:
                    new_issue = random.choice(available_issues)
                    doc["relevant_issues"].append(new_issue["id"])

    async def evaluate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """
        Evaluate agent performance in legal scenario.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary with performance metrics
        """
        base_metrics = await super().evaluate_agent_performance(agent_id)

        if agent_id not in self.agent_states:
            return base_metrics

        agent_state = self.agent_states[agent_id]

        # Calculate legal specific metrics
        total_documents = len(self.documents)
        reviewed_documents = len(
            [d for d in self.documents if d.get("reviewed_by") == agent_id]
        )

        # Calculate document accuracy
        agent_reviews = [d for d in self.documents if d.get("reviewed_by") == agent_id]
        if agent_reviews:
            accuracies = [d.get("review_accuracy", 0.0) for d in agent_reviews]
            self.document_accuracy = sum(accuracies) / len(accuracies)

        # Calculate issue identification rate
        total_issues = sum(len(d.get("relevant_issues", [])) for d in self.documents)
        identified_issues = sum(
            len(d.get("identified_issues", []))
            for d in self.documents
            if d.get("reviewed_by") == agent_id
        )
        self.issue_identification_rate = (
            identified_issues / total_issues if total_issues > 0 else 0.0
        )

        # Calculate compliance score
        agent_cases = [c for c in self.cases if c.get("handled_by") == agent_id]
        if agent_cases:
            compliant_cases = sum(
                1 for c in agent_cases if c.get("compliance_score", 0) > 0.8
            )
            self.compliance_score = compliant_cases / len(agent_cases)

        # Update metrics
        legal_metrics = {
            "total_documents": total_documents,
            "reviewed_documents": reviewed_documents,
            "document_accuracy": self.document_accuracy,
            "issue_identification_rate": self.issue_identification_rate,
            "compliance_score": self.compliance_score,
            "cases_handled": len(agent_cases),
            "average_review_time": self._calculate_average_review_time(agent_id),
        }

        base_metrics.update(legal_metrics)
        return base_metrics

    def _calculate_average_review_time(self, agent_id: str) -> float:
        """Calculate average document review time."""
        agent_reviews = [d for d in self.documents if d.get("reviewed_by") == agent_id]
        if not agent_reviews:
            return 0.0

        total_time = sum(
            d.get("review_end_time", 0) - d.get("review_start_time", 0)
            for d in agent_reviews
        )

        return total_time / len(agent_reviews)


class ScientificScenario(ScenarioTemplate):
    """
    Scientific scenario for benchmarking agent performance in research.

    This scenario simulates a scientific research environment where agents must
    analyze data, form hypotheses, and conduct experiments.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the scientific scenario.

        Args:
            config: Scenario configuration
        """
        super().__init__(config)

        # Scientific specific state
        self.datasets = []
        self.hypotheses = []
        self.experiments = []
        self.publications = []

        # Research metrics
        self.hypothesis_accuracy = 0.0
        self.experiment_reproducibility = 0.0
        self.research_impact = 0.0

    def _validate_domain_parameters(self) -> List[str]:
        """
        Validate scientific specific parameters.

        Returns:
            List of validation errors
        """
        errors = []

        # Validate dataset count
        dataset_count = self.parameters.get("dataset_count", 20)
        if not isinstance(dataset_count, int) or dataset_count <= 0:
            errors.append("dataset_count must be a positive integer")

        # Validate research field
        research_field = self.parameters.get("research_field", "general")
        valid_fields = ["biology", "physics", "chemistry", "psychology", "general"]
        if research_field not in valid_fields:
            errors.append(f"research_field must be one of: {', '.join(valid_fields)}")

        return errors

    async def initialize(self, parameters: Dict[str, Any]) -> None:
        """
        Initialize the scientific scenario.

        Args:
            parameters: Scenario-specific parameters
        """
        await super().initialize(parameters)

        # Extract parameters
        dataset_count = parameters.get("dataset_count", 20)
        research_field = parameters.get("research_field", "general")

        # Generate datasets
        self.datasets = self._generate_datasets(dataset_count, research_field)

        # Generate initial hypotheses
        self.hypotheses = self._generate_initial_hypotheses(10)

        # Update global state
        self.global_state.update(
            {
                "datasets": len(self.datasets),
                "hypotheses": len(self.hypotheses),
                "research_field": research_field,
            }
        )

        logger.info(
            f"Initialized scientific scenario with {len(self.datasets)} datasets in {research_field}"
        )

    def _generate_datasets(self, count: int, field: str) -> List[Dict[str, Any]]:
        """Generate research datasets."""
        datasets = []

        for i in range(count):
            dataset = {
                "id": f"dataset_{i}",
                "name": f"Dataset {i}",
                "field": field,
                "size": random.randint(100, 10000),
                "quality": random.uniform(0.5, 1.0),
                "complexity": random.uniform(0.1, 1.0),
                "noise_level": random.uniform(0.0, 0.3),
                "missing_data": random.uniform(0.0, 0.2),
                "features": random.randint(5, 100),
            }
            datasets.append(dataset)

        return datasets

    def _generate_initial_hypotheses(self, count: int) -> List[Dict[str, Any]]:
        """Generate initial research hypotheses."""
        hypotheses = []

        for i in range(count):
            hypothesis = {
                "id": f"hypothesis_{i}",
                "statement": f"Research hypothesis {i}",
                "confidence": random.uniform(0.3, 0.8),
                "evidence": [],
                "status": "untested",  # untested, supported, refuted
                "testability": random.uniform(0.5, 1.0),
            }
            hypotheses.append(hypothesis)

        return hypotheses

    async def update_tick(self, tick: int, state: SimulationState) -> None:
        """
        Update the scientific scenario for a specific tick.

        Args:
            tick: Current tick number
            state: Current simulation state
        """
        await super().update_tick(tick, state)

        # Simulate data analysis
        if tick % 2 == 0:  # Every 2 ticks
            self._simulate_data_analysis()

        # Simulate hypothesis testing
        self._simulate_hypothesis_testing(tick)

        # Simulate experiment execution
        if tick % 5 == 0:  # Every 5 ticks
            self._simulate_experiment_execution(tick)

    def _simulate_data_analysis(self) -> None:
        """Simulate data analysis activities."""
        # Random dataset analysis
        unanalyzed_datasets = [d for d in self.datasets if not d.get("analyzed", False)]
        if unanalyzed_datasets:
            num_analyses = min(random.randint(1, 3), len(unanalyzed_datasets))
            for dataset in random.sample(unanalyzed_datasets, num_analyses):
                dataset["analyzed"] = True
                dataset["analysis_quality"] = random.uniform(0.6, 0.95)
                dataset["insights"] = random.randint(1, 5)

    def _simulate_hypothesis_testing(self, tick: int) -> None:
        """Simulate hypothesis testing."""
        for hypothesis in self.hypotheses:
            if hypothesis["status"] == "untested":
                # Random testing
                if random.random() < 0.15:  # 15% chance
                    # Test hypothesis
                    test_result = random.random()
                    if test_result < 0.6:  # 60% chance of support
                        hypothesis["status"] = "supported"
                    else:
                        hypothesis["status"] = "refuted"

                    hypothesis["test_date"] = tick
                    hypothesis["evidence_strength"] = random.uniform(0.3, 0.9)

    def _simulate_experiment_execution(self, tick: int) -> None:
        """Simulate experiment execution."""
        # Generate new experiments
        if random.random() < 0.3:  # 30% chance
            # Select random dataset and hypothesis
            if self.datasets and self.hypotheses:
                dataset = random.choice(self.datasets)
                hypothesis = random.choice(self.hypotheses)

                experiment = {
                    "id": f"experiment_{len(self.experiments)}",
                    "dataset_id": dataset["id"],
                    "hypothesis_id": hypothesis["id"],
                    "method": random.choice(
                        ["controlled", "observational", "simulation"]
                    ),
                    "status": "running",  # running, completed, failed
                    "start_time": tick,
                    "expected_duration": random.randint(5, 20),
                }
                self.experiments.append(experiment)

        # Update running experiments
        for experiment in self.experiments:
            if experiment["status"] == "running":
                experiment["progress"] = experiment.get("progress", 0) + random.uniform(
                    0.1, 0.2
                )

                if experiment["progress"] >= 1.0:
                    # Experiment completed
                    experiment["status"] = "completed"
                    experiment["end_time"] = tick
                    experiment["success"] = random.random() < 0.8  # 80% success rate
                    experiment["reproducibility"] = random.uniform(0.5, 0.95)

    async def evaluate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """
        Evaluate agent performance in scientific scenario.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary with performance metrics
        """
        base_metrics = await super().evaluate_agent_performance(agent_id)

        if agent_id not in self.agent_states:
            return base_metrics

        agent_state = self.agent_states[agent_id]

        # Calculate scientific specific metrics
        total_datasets = len(self.datasets)
        analyzed_datasets = len(
            [d for d in self.datasets if d.get("analyzed_by") == agent_id]
        )

        # Calculate hypothesis accuracy
        agent_hypotheses = [
            h for h in self.hypotheses if h.get("proposed_by") == agent_id
        ]
        if agent_hypotheses:
            tested_hypotheses = [
                h for h in agent_hypotheses if h["status"] != "untested"
            ]
            if tested_hypotheses:
                correct_hypotheses = sum(
                    1 for h in tested_hypotheses if h["status"] == "supported"
                )
                self.hypothesis_accuracy = correct_hypotheses / len(tested_hypotheses)

        # Calculate experiment reproducibility
        agent_experiments = [
            e for e in self.experiments if e.get("conducted_by") == agent_id
        ]
        if agent_experiments:
            completed_experiments = [
                e for e in agent_experiments if e["status"] == "completed"
            ]
            if completed_experiments:
                reproducibility_scores = [
                    e.get("reproducibility", 0.0) for e in completed_experiments
                ]
                self.experiment_reproducibility = sum(reproducibility_scores) / len(
                    reproducibility_scores
                )

        # Calculate research impact
        self.research_impact = random.uniform(0.3, 0.9)  # Simulated

        # Update metrics
        scientific_metrics = {
            "total_datasets": total_datasets,
            "analyzed_datasets": analyzed_datasets,
            "hypotheses_proposed": len(agent_hypotheses),
            "hypothesis_accuracy": self.hypothesis_accuracy,
            "experiments_conducted": len(agent_experiments),
            "experiment_reproducibility": self.experiment_reproducibility,
            "research_impact": self.research_impact,
            "publications": len(
                [p for p in self.publications if p.get("author") == agent_id]
            ),
        }

        base_metrics.update(scientific_metrics)
        return base_metrics
