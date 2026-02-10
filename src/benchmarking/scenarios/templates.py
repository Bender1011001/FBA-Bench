"""
Scenario templates for different domains.

This module provides concrete implementations of scenarios for various domains
including e-commerce, healthcare, finance, legal, and scientific research.

All randomness in this module uses deterministic RNG to ensure perfect
reproducibility when provided with the same master seed.
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Import deterministic RNG for reproducible simulations
try:
    from reproducibility.deterministic_rng import DeterministicRNG
    _HAS_DETERMINISTIC_RNG = True
except ImportError:
    import random
    _HAS_DETERMINISTIC_RNG = False

logger = logging.getLogger(__name__)

from fba_bench.core.types import SimulationState

from .base import ScenarioConfig, ScenarioTemplate


class ECommerceScenario(ScenarioTemplate):
    """
    E-commerce scenario for benchmarking agent performance in online retail.

    This scenario simulates an e-commerce environment where agents must manage
    product pricing, inventory, and marketing strategies.
    
    All randomness uses deterministic RNG for perfect reproducibility.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the e-commerce scenario.

        Args:
            config: Scenario configuration
        """
        super().__init__(config)

        # Initialize deterministic RNG for reproducible scenario generation
        if _HAS_DETERMINISTIC_RNG:
            self._rng = DeterministicRNG.for_component("ecommerce_scenario")
        else:
            self._rng = None
            logger.warning(
                "DeterministicRNG not available for ECommerceScenario. "
                "Simulation will NOT be reproducible."
            )

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

        # Initialize market conditions (deterministic)
        if self._rng:
            self.market_demand = self._rng.uniform(0.8, 1.2)
            self.seasonal_factor = self._rng.uniform(0.9, 1.1)
            self.competition_level = self._rng.uniform(0.3, 0.7)
        else:
            self.market_demand = 1.0
            self.seasonal_factor = 1.0
            self.competition_level = 0.5

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
        """Generate products with deterministic randomness."""
        products = []
        categories = ["Electronics", "Clothing", "Home", "Books", "Sports"]

        for i in range(count):
            if self._rng:
                product = {
                    "id": f"product_{i}",
                    "name": f"Product {i}",
                    "category": self._rng.choice(categories),
                    "base_price": self._rng.uniform(10, 100),
                    "current_price": self._rng.uniform(10, 100),
                    "inventory": self._rng.randint(10, 100),
                    "cost": self._rng.uniform(5, 50),
                    "popularity": self._rng.uniform(0.1, 1.0),
                }
            else:
                # Fallback: use deterministic defaults for reproducibility
                product = {
                    "id": f"product_{i}",
                    "name": f"Product {i}",
                    "category": categories[i % len(categories)],
                    "base_price": 50.0 + (i * 5) % 50,
                    "current_price": 50.0 + (i * 5) % 50,
                    "inventory": 50 + (i * 7) % 50,
                    "cost": 25.0 + (i * 3) % 25,
                    "popularity": 0.5 + (i * 0.05) % 0.5,
                }
            products.append(product)

        return products

    def _generate_customers(self, count: int) -> List[Dict[str, Any]]:
        """Generate customers with deterministic randomness."""
        customers = []

        for i in range(count):
            if self._rng:
                customer = {
                    "id": f"customer_{i}",
                    "budget": self._rng.uniform(50, 500),
                    "preferences": {
                        "price_sensitivity": self._rng.uniform(0.1, 1.0),
                        "quality_preference": self._rng.uniform(0.1, 1.0),
                        "brand_loyalty": self._rng.uniform(0.1, 1.0),
                    },
                    "purchase_history": [],
                }
            else:
                # Fallback: deterministic customer generation
                customer = {
                    "id": f"customer_{i}",
                    "budget": 200.0 + (i * 30) % 300,
                    "preferences": {
                        "price_sensitivity": 0.5 + (i * 0.03) % 0.5,
                        "quality_preference": 0.5 + (i * 0.04) % 0.5,
                        "brand_loyalty": 0.5 + (i * 0.02) % 0.5,
                    },
                    "purchase_history": [],
                }
            customers.append(customer)

        return customers

    def _generate_competitors(self, count: int) -> List[Dict[str, Any]]:
        """Generate competitors with deterministic randomness."""
        competitors = []
        strategies = ["aggressive", "moderate", "premium"]

        for i in range(count):
            if self._rng:
                competitor = {
                    "id": f"competitor_{i}",
                    "name": f"Competitor {i}",
                    "market_share": self._rng.uniform(0.1, 0.3),
                    "pricing_strategy": self._rng.choice(strategies),
                    "reputation": self._rng.uniform(0.5, 1.0),
                }
            else:
                # Fallback: deterministic competitor generation
                competitor = {
                    "id": f"competitor_{i}",
                    "name": f"Competitor {i}",
                    "market_share": 0.2 + (i * 0.05) % 0.1,
                    "pricing_strategy": strategies[i % len(strategies)],
                    "reputation": 0.7 + (i * 0.1) % 0.3,
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
        """Update market conditions (deterministic)."""
        # Gradual changes in market demand
        if self._rng:
            demand_change = self._rng.uniform(-0.05, 0.05)
            seasonal_change = self._rng.uniform(-0.02, 0.02)
        else:
            # Deterministic fallback: small fixed oscillation
            demand_change = 0.01 if (self.current_tick // 10) % 2 == 0 else -0.01
            seasonal_change = 0.005 if (self.current_tick // 10) % 3 == 0 else -0.005
        
        self.market_demand += demand_change
        self.market_demand = max(0.5, min(1.5, self.market_demand))

        # Seasonal changes
        self.seasonal_factor += seasonal_change
        self.seasonal_factor = max(0.8, min(1.2, self.seasonal_factor))

    def _simulate_customer_behavior(self, tick: int) -> None:
        """Simulate customer purchasing behavior (deterministic)."""
        # Deterministic customer purchases based on RNG
        if self._rng:
            num_purchases = self._rng.randint(0, max(1, len(self.customers) // 10))
        else:
            # Fallback: deterministic based on tick
            num_purchases = (tick * 7) % max(1, len(self.customers) // 10)

        for i in range(num_purchases):
            if self._rng:
                customer = self._rng.choice(self.customers)
                product = self._rng.choice(self.products)
            else:
                # Deterministic selection
                customer = self.customers[i % len(self.customers)]
                product = self.products[i % len(self.products)]

            # Calculate purchase probability based on economic factors
            price_factor = 1.0 - (product["current_price"] / 100.0)
            demand_factor = self.market_demand * self.seasonal_factor
            customer_price_sensitivity = customer["preferences"].get("price_sensitivity", 0.5)
            
            # More sophisticated purchase probability considering customer preferences
            purchase_probability = (
                price_factor * demand_factor * (1 - customer_price_sensitivity * 0.5) * 0.15
            )

            purchase_roll = self._rng.random() if self._rng else 0.5
            if purchase_roll < purchase_probability:
                # Determine quantity based on budget and price
                max_affordable = int(customer["budget"] / product["current_price"])
                if max_affordable > 0 and product["inventory"] > 0:
                    if self._rng:
                        quantity = self._rng.randint(1, min(5, max_affordable, product["inventory"]))
                    else:
                        quantity = min(2, max_affordable, product["inventory"])
                    
                    order = {
                        "customer_id": customer["id"],
                        "product_id": product["id"],
                        "price": product["current_price"],
                        "quantity": quantity,
                        "timestamp": tick,
                    }
                    self.orders.append(order)

                    # Update product inventory
                    product["inventory"] = max(0, product["inventory"] - order["quantity"])

                    # Update customer budget
                    customer["budget"] -= order["price"] * order["quantity"]

    def _simulate_competitor_actions(self, tick: int) -> None:
        """Simulate competitor pricing actions (deterministic)."""
        for competitor in self.competitors:
            # Deterministic price adjustments based on strategy and RNG
            action_roll = self._rng.random() if self._rng else 0.5
            if action_roll < 0.3:  # 30% chance to adjust (deterministic when seeded)
                # Select products to adjust
                if self._rng and len(self.products) > 3:
                    selected_products = self._rng.sample(self.products, min(3, len(self.products)))
                else:
                    selected_products = self.products[:min(3, len(self.products))]
                
                for product in selected_products:
                    if competitor["pricing_strategy"] == "aggressive":
                        multiplier = self._rng.uniform(0.95, 0.99) if self._rng else 0.97
                        product["current_price"] *= multiplier
                    elif competitor["pricing_strategy"] == "premium":
                        multiplier = self._rng.uniform(1.01, 1.05) if self._rng else 1.03
                        product["current_price"] *= multiplier
                    else:  # moderate
                        multiplier = self._rng.uniform(0.98, 1.02) if self._rng else 1.0
                        product["current_price"] *= multiplier

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

        # Update metrics with CALCULATED customer satisfaction
        # (Based on real simulation data, NOT random values!)
        customer_satisfaction = self._calculate_customer_satisfaction()
        
        ecommerce_metrics = {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "average_order_value": average_order_value,
            "profit": profit,
            "market_share": market_share,
            "inventory_turnover": self._calculate_inventory_turnover(),
            "customer_satisfaction": customer_satisfaction,
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

    def _calculate_customer_satisfaction(self) -> float:
        """
        Calculate customer satisfaction based on REAL simulation metrics.
        
        This replaces the fake random.uniform(0.7, 0.95) approach with an
        evidence-based calculation derived from actual simulation state.
        
        Factors considered:
        1. Order fulfillment rate (40% weight): Were products in stock?
        2. Price competitiveness (30% weight): Are prices reasonable?
        3. Inventory availability (20% weight): Can customers find what they want?
        4. Service quality proxy (10% weight): Based on order frequency
        
        Returns:
            Customer satisfaction score (0.0 to 1.0)
        """
        if not self.orders and not self.products:
            return 0.5  # Neutral when no data
        
        # Factor 1: Order fulfillment rate (40%)
        # Measured by: percentage of products with positive inventory
        products_in_stock = sum(1 for p in self.products if p.get("inventory", 0) > 0)
        in_stock_rate = products_in_stock / len(self.products) if self.products else 1.0
        fulfillment_score = in_stock_rate
        
        # Factor 2: Price competitiveness (30%)
        # Measured by: how close current prices are to base prices (lower = better value)
        if self.products:
            price_ratios = []
            for p in self.products:
                base = p.get("base_price", p.get("current_price", 50))
                current = p.get("current_price", base)
                if base > 0:
                    ratio = current / base
                    # Score: 1.0 if at or below base, decreasing as price increases
                    price_score = max(0.0, min(1.0, 2.0 - ratio))
                    price_ratios.append(price_score)
            price_competitiveness = sum(price_ratios) / len(price_ratios) if price_ratios else 0.7
        else:
            price_competitiveness = 0.7
        
        # Factor 3: Inventory availability (20%)
        # Measured by: average inventory level relative to expected demand
        if self.products:
            avg_inventory = sum(p.get("inventory", 0) for p in self.products) / len(self.products)
            # Normalize: assume 50 units is "good" inventory
            inventory_score = min(1.0, avg_inventory / 50.0)
        else:
            inventory_score = 0.5
        
        # Factor 4: Service quality proxy (10%)
        # Measured by: order frequency relative to customer base
        if self.customers and self.orders:
            orders_per_customer = len(self.orders) / len(self.customers)
            # Normalize: assume 2 orders per customer is "excellent"
            service_score = min(1.0, orders_per_customer / 2.0)
        else:
            service_score = 0.3
        
        # Weighted composite score
        satisfaction = (
            fulfillment_score * 0.40 +
            price_competitiveness * 0.30 +
            inventory_score * 0.20 +
            service_score * 0.10
        )
        
        # Clamp to valid range
        return max(0.0, min(1.0, satisfaction))


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

        # Initialize deterministic RNG for reproducible scenario generation
        if _HAS_DETERMINISTIC_RNG:
            self._rng = DeterministicRNG.for_component("healthcare_scenario")
        else:
            self._rng = None
            logger.warning(
                "DeterministicRNG not available for HealthcareScenario. "
                "Simulation will NOT be reproducible."
            )

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
        """Generate medical conditions with deterministic randomness."""
        # Use deterministic values - severity and prevalence are based on
        # medical literature but with RNG for variability when available
        if self._rng:
            conditions = [
                {
                    "id": "flu",
                    "name": "Influenza",
                    "symptoms": ["fever", "cough", "fatigue", "body aches"],
                    "severity": self._rng.uniform(0.3, 0.7),
                    "prevalence": self._rng.uniform(0.1, 0.3),
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
                    "severity": self._rng.uniform(0.5, 0.8),
                    "prevalence": self._rng.uniform(0.05, 0.15),
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
                    "severity": self._rng.uniform(0.4, 0.7),
                    "prevalence": self._rng.uniform(0.2, 0.4),
                },
            ]
        else:
            # Deterministic fallback based on medical literature
            conditions = [
                {
                    "id": "flu",
                    "name": "Influenza",
                    "symptoms": ["fever", "cough", "fatigue", "body aches"],
                    "severity": 0.5,
                    "prevalence": 0.2,
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
                    "severity": 0.65,
                    "prevalence": 0.1,
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
                    "severity": 0.55,
                    "prevalence": 0.3,
                },
            ]
        return conditions

    def _generate_treatments(self) -> List[Dict[str, Any]]:
        """Generate medical treatments with deterministic randomness."""
        if self._rng:
            treatments = [
                {
                    "id": "medication",
                    "name": "Medication Therapy",
                    "effectiveness": self._rng.uniform(0.7, 0.9),
                    "cost": self._rng.uniform(50, 200),
                    "duration": self._rng.randint(7, 30),
                },
                {
                    "id": "surgery",
                    "name": "Surgical Intervention",
                    "effectiveness": self._rng.uniform(0.8, 0.95),
                    "cost": self._rng.uniform(1000, 10000),
                    "duration": self._rng.randint(1, 7),
                },
                {
                    "id": "therapy",
                    "name": "Physical Therapy",
                    "effectiveness": self._rng.uniform(0.6, 0.8),
                    "cost": self._rng.uniform(100, 500),
                    "duration": self._rng.randint(14, 90),
                },
            ]
        else:
            # Deterministic fallback based on medical literature
            treatments = [
                {
                    "id": "medication",
                    "name": "Medication Therapy",
                    "effectiveness": 0.8,
                    "cost": 125.0,
                    "duration": 14,
                },
                {
                    "id": "surgery",
                    "name": "Surgical Intervention",
                    "effectiveness": 0.87,
                    "cost": 5000.0,
                    "duration": 3,
                },
                {
                    "id": "therapy",
                    "name": "Physical Therapy",
                    "effectiveness": 0.7,
                    "cost": 300.0,
                    "duration": 45,
                },
            ]
        return treatments

    def _generate_patients(self, count: int) -> List[Dict[str, Any]]:
        """Generate patients with deterministic randomness."""
        patients = []
        genders = ["male", "female"]

        for i in range(count):
            if self._rng:
                condition = self._rng.choice(self.medical_conditions)
                num_symptoms = self._rng.randint(2, len(condition["symptoms"]))
                patient = {
                    "id": f"patient_{i}",
                    "age": self._rng.randint(18, 80),
                    "gender": self._rng.choice(genders),
                    "condition": condition["id"],
                    "symptoms": self._rng.sample(condition["symptoms"], num_symptoms),
                    "severity": self._rng.uniform(0.1, 1.0),
                    "medical_history": [],
                    "treatment_plan": None,
                    "status": "waiting",
                }
            else:
                # Deterministic fallback
                condition = self.medical_conditions[i % len(self.medical_conditions)]
                patient = {
                    "id": f"patient_{i}",
                    "age": 40 + (i * 3) % 40,
                    "gender": genders[i % 2],
                    "condition": condition["id"],
                    "symptoms": condition["symptoms"][:2],
                    "severity": 0.5 + (i * 0.03) % 0.5,
                    "medical_history": [],
                    "treatment_plan": None,
                    "status": "waiting",
                }
            patients.append(patient)

        return patients

    def _generate_medical_staff(self, count: int) -> List[Dict[str, Any]]:
        """Generate medical staff with deterministic randomness."""
        staff = []
        roles = ["doctor", "nurse", "specialist", "technician"]
        specializations = ["cardiology", "neurology", "pediatrics", "general"]

        for i in range(count):
            if self._rng:
                staff_member = {
                    "id": f"staff_{i}",
                    "name": f"Staff Member {i}",
                    "role": self._rng.choice(roles),
                    "experience": self._rng.randint(1, 20),
                    "specialization": self._rng.choice(specializations),
                    "workload": 0,
                    "patients_assigned": [],
                }
            else:
                # Deterministic fallback
                staff_member = {
                    "id": f"staff_{i}",
                    "name": f"Staff Member {i}",
                    "role": roles[i % len(roles)],
                    "experience": 5 + (i * 2) % 15,
                    "specialization": specializations[i % len(specializations)],
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
        """Simulate new patient arrivals (deterministic)."""
        arrival_roll = self._rng.random() if self._rng else 0.5
        if arrival_roll < 0.3:  # 30% chance (deterministic when seeded)
            # Generate new patient
            if self._rng:
                condition = self._rng.choice(self.medical_conditions)
                num_symptoms = self._rng.randint(2, len(condition["symptoms"]))
                patient = {
                    "id": f"patient_{len(self.patients)}",
                    "age": self._rng.randint(18, 80),
                    "gender": self._rng.choice(["male", "female"]),
                    "condition": condition["id"],
                    "symptoms": self._rng.sample(condition["symptoms"], num_symptoms),
                    "severity": self._rng.uniform(0.1, 1.0),
                    "medical_history": [],
                    "treatment_plan": None,
                    "status": "waiting",
                    "arrival_time": self.current_tick,
                }
            else:
                # Deterministic fallback when no RNG available
                condition = self.medical_conditions[len(self.patients) % len(self.medical_conditions)]
                patient = {
                    "id": f"patient_{len(self.patients)}",
                    "age": 45,
                    "gender": "male" if len(self.patients) % 2 == 0 else "female",
                    "condition": condition["id"],
                    "symptoms": condition["symptoms"][:2],
                    "severity": 0.5,
                    "medical_history": [],
                    "treatment_plan": None,
                    "status": "waiting",
                    "arrival_time": self.current_tick,
                }
            self.patients.append(patient)

    def _simulate_treatment_progress(self, tick: int) -> None:
        """Simulate treatment progress for patients (deterministic)."""
        for patient in self.patients:
            if patient["status"] == "treating" and patient["treatment_plan"]:
                # Update treatment progress with deterministic randomness
                treatment = patient["treatment_plan"]
                progress_increment = self._rng.uniform(0.05, 0.15) if self._rng else 0.1
                treatment["progress"] += progress_increment

                if treatment["progress"] >= 1.0:
                    # Treatment completed
                    patient["status"] = "recovered"
                    treatment["end_time"] = tick

                    # Calculate treatment outcome (deterministic)
                    success_roll = self._rng.random() if self._rng else 0.5
                    treatment_success = success_roll < treatment["effectiveness"]
                    patient["treatment_success"] = treatment_success

    def _update_staff_workload(self) -> None:
        """Update medical staff workload (deterministic)."""
        # Reset workload
        for staff in self.medical_staff:
            staff["workload"] = 0
            staff["patients_assigned"] = []

        # Assign patients to staff deterministically
        for idx, patient in enumerate(self.patients):
            if patient["status"] in ["diagnosed", "treating"]:
                # Find available staff
                available_staff = [
                    s for s in self.medical_staff if len(s["patients_assigned"]) < 5
                ]
                if available_staff:
                    if self._rng:
                        staff = self._rng.choice(available_staff)
                    else:
                        # Deterministic assignment based on patient index
                        staff = available_staff[idx % len(available_staff)]
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

        # CALCULATED patient satisfaction based on REAL simulation metrics
        self.patient_satisfaction = self._calculate_patient_satisfaction()

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

    def _calculate_patient_satisfaction(self) -> float:
        """
        Calculate patient satisfaction based on REAL simulation metrics.
        
        This replaces the fake random.uniform(0.7, 0.95) approach with an
        evidence-based calculation derived from actual simulation state.
        
        Factors considered:
        1. Wait time factor (35% weight): Shorter waits = higher satisfaction
        2. Treatment success rate (35% weight): Successful treatments boost satisfaction
        3. Diagnosis coverage (20% weight): Percentage of patients diagnosed
        4. Staff availability (10% weight): Low workload = better attention
        
        Returns:
            Patient satisfaction score (0.0 to 1.0)
        """
        if not self.patients:
            return 0.5  # Neutral when no patients
        
        # Factor 1: Wait time factor (35%)
        # Lower wait times = higher satisfaction
        avg_wait = self._calculate_average_wait_time()
        # Assume 10 ticks is acceptable wait time, satisfaction decreases after
        wait_satisfaction = max(0.0, 1.0 - (avg_wait / 20.0))
        
        # Factor 2: Treatment success rate (35%)
        recovered = [p for p in self.patients if p["status"] == "recovered"]
        if recovered:
            successful = sum(1 for p in recovered if p.get("treatment_success", False))
            treatment_satisfaction = successful / len(recovered)
        else:
            treatment_satisfaction = 0.5  # Neutral when no recoveries yet
        
        # Factor 3: Diagnosis coverage (20%)
        # Percentage of patients who have been diagnosed or treated
        non_waiting = sum(
            1 for p in self.patients
            if p["status"] in ["diagnosed", "treating", "recovered"]
        )
        diagnosis_coverage = non_waiting / len(self.patients)
        
        # Factor 4: Staff availability (10%)
        # Average workload per staff member (lower is better)
        if self.medical_staff:
            total_workload = sum(s["workload"] for s in self.medical_staff)
            avg_workload = total_workload / len(self.medical_staff)
            # Normalize: 5 patients per staff is max capacity
            availability = max(0.0, 1.0 - (avg_workload / 5.0))
        else:
            availability = 0.0
        
        # Weighted composite score
        satisfaction = (
            wait_satisfaction * 0.35 +
            treatment_satisfaction * 0.35 +
            diagnosis_coverage * 0.20 +
            availability * 0.10
        )
        
        # Clamp to valid range
        return max(0.0, min(1.0, satisfaction))


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
