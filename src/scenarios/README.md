# FBA-Bench Scenario System

This directory contains the core components and definitions for FBA-Bench's comprehensive scenario system. This system allows for the creation, management, execution, and validation of diverse business simulations to robustly test LLM agent capabilities.

## 1. Structure Overview

- [`scenarios/scenario_framework.py`](scenarios/scenario_framework.py): Defines the `ScenarioConfig` class, which is the blueprint for all scenario configurations. It includes properties for market conditions, business parameters, external events, and agent challenges, along with methods for internal consistency validation.
- [`scenarios/scenario_config.py`](scenarios/scenario_config.py): Contains `ScenarioConfigManager` for loading and managing scenario templates, ensuring configurations are valid, and quantifying scenario difficulty. It also defines a `ScenarioConfiguration` dataclass for structured access to scenario parameters.
- [`scenarios/dynamic_generator.py`](scenarios/dynamic_generator.py): Implements the `DynamicScenarioGenerator` for procedurally creating unique scenarios from templates, randomizing parameters within defined ranges, and scaling difficulty based on target tiers.
- [`scenarios/curriculum_validator.py`](scenarios/curriculum_validator.py): Provides the `CurriculumValidator` class for benchmarking agent performance across all tiers, ensuring proper difficulty progression, analyzing success rates, and generating comprehensive validation reports with tier adjustment recommendations.
- [`scenarios/scenario_engine.py`](scenarios/scenario_engine.py): The `ScenarioEngine` class is responsible for loading scenario configurations, initializing the simulation environment based on these configs, injecting scenario-specific events during runtime, tracking progress, and analyzing final results against defined objectives.

## 2. Scenario Categories

Scenarios are organized into several categories to provide diverse challenges:

### Standard Tiered Scenarios
These are predefined scenarios designed for specific difficulty tiers (T0-T3) and are crucial for curriculum validation.

- [`scenarios/tier_0_baseline.yaml`](scenarios/tier_0_baseline.yaml): A simple, single-product FBA business with stable market conditions and basic requirements. Designed for basic agent testing and high success rates.
- [`scenarios/tier_1_moderate.yaml`](scenarios/tier_1_moderate.yaml): Introduces moderate complexity with a small product portfolio, seasonal demand, and minor external disruptions.
- [`scenarios/tier_2_advanced.yaml`](scenarios/tier_2_advanced.yaml): Features a more complex product catalog, economic recession, aggressive competition, and significant supply chain disruptions, requiring crisis management.
- [`scenarios/tier_3_expert.yaml`](scenarios/tier_3_expert.yaml): The most challenging tier, including international multi-marketplace operations, multiple severe external shocks, adversarial agents, and complex compliance/negotiation requirements.

### Business Type Specific Scenarios (`scenarios/business_types/`)
These scenarios focus on specific business challenges, often cross-cutting tiers.
- [`scenarios/business_types/international_expansion.yaml`](scenarios/business_types/international_expansion.yaml): Focuses on multi-marketplace operations, currency, localization, and cross-border regulations.
- [`scenarios/business_types/high_sku_complexity.yaml`](scenarios/business_types/high_sku_complexity.yaml): Emphasizes managing a large number of product variants, complex inventory, and seasonal demand.
- [`scenarios/business_types/boom_and_bust_cycle.yaml`](scenarios/business_types/boom_and_bust_cycle.yaml): Simulates economic recession and recovery, testing cash flow and strategic pivoting.
- [`scenarios/business_types/hyper_competitive_market.yaml`](scenarios/business_types/hyper_competitive_market.yaml): Challenges agents with intense competition, price wars, and innovation pressure.
- [`scenarios/business_types/supply_chain_crisis.yaml`](scenarios/business_types/supply_chain_crisis.yaml): Simulates global supply disruptions, supplier bankruptcies, and shipping delays.

### Multi-Agent Interaction Scenarios (`scenarios/multi_agent/`)
These scenarios explore cooperative and competitive dynamics between multiple LLM agents (or LLM agents vs. scripted agents).
- [`scenarios/multi_agent/cooperative_joint_venture.yaml`](scenarios/multi_agent/cooperative_joint_venture.yaml): Two agents form a strategic partnership with shared resources and profit-sharing agreements.
- [`scenarios/multi_agent/supplier_agent_negotiations.yaml`](scenarios/multi_agent/supplier_agent_negotiations.yaml): Features an LLM-driven supplier agent with dynamic pricing and contract negotiation protocols, requiring advanced negotiation skills from the FBA agent.
- [`scenarios/multi_agent/marketplace_ecosystem.yaml`](scenarios/multi_agent/marketplace_ecosystem.yaml): A complex ecosystem with multiple seller, supplier, and platform agents, featuring dynamic fee structures, cross-agent reviews, and reputation systems.

## 3. Configuration File Format

All scenario configurations are defined in YAML format. The structure follows the `ScenarioConfiguration` dataclass defined in [`scenarios/scenario_config.py`](scenarios/scenario_config.py). Key attributes include:

- `scenario_name` (str): Unique identifier for the scenario.
- `difficulty_tier` (int): The target difficulty tier (0-3).
- `expected_duration` (int): Duration of the simulation in days/ticks.
- `success_criteria` (Dict[str, float]): Objectives for agent success (e.g., `profit_target`, `customer_satisfaction`).
- `market_conditions` (Dict[str, Any]): Defines economic cycles, seasonality, competition levels, etc.
- `business_parameters` (Dict[str, Any]): Product categories, pricing dynamics, supply chain complexity.
- `external_events` (List[Dict[str, Any]]): A list of timed events with `name`, `tick`, `type`, and `impact`.
- `agent_constraints` (Dict[str, Any]): Agent-specific limitations like `initial_capital`, `max_debt_ratio`, `information_asymmetry`.
- `multi_agent_config` (Optional[Dict[str, Any]]): Configuration specific to multi-agent scenarios, including `num_agents`, `agent_roles`, and `interaction_mode`.

## 4. Creating Custom Scenarios

To create a new custom scenario:
1.  Create a new YAML file in `scenarios/`, `scenarios/business_types/`, or `scenarios/multi_agent/`.
2.  Follow the structure outlined above and in `ScenarioConfiguration` dataclass.
3.  Ensure `scenario_name`, `difficulty_tier`, `expected_duration`, `success_criteria`, `market_conditions`, `external_events`, and `agent_constraints` are all present.
4.  Optionally use `dynamic_generator.py` to create a new scenario programmatically by defining a randomization configuration.

## 5. Running Scenarios via CLI

The `experiment_cli.py` has been enhanced to support scenario-based runs:

-   **Run a specific scenario**:
    ```bash
    python experiment_cli.py run --scenario <SCENARIO_NAME> --agents <AGENT_MODEL_NAME>
    ```
    Example: `python experiment_cli.py run --scenario "Tier 0 Baseline" --agents ClaudeSonnetBot`
-   **Run all scenarios in a tier**:
    ```bash
    python experiment_cli.py run --tier <TIER_NUMBER> --agents <AGENT_MODEL_NAME_1> <AGENT_MODEL_NAME_2>
    ```
    Example: `python experiment_cli.py run --tier 1 --agents GPT4oMiniBot`
-   **Validate curriculum progression**:
    ```bash
    python experiment_cli.py run --tier <TIER_NUMBER> --agents <AGENT_MODEL_NAME> --validate-curriculum
    ```
    This will run all scenarios in the specified tier, collect performance data, and generate a curriculum validation report.
-   **Generate a dynamic scenario**:
    ```bash
    python experiment_cli.py run --generate-scenario <TEMPLATE_NAME> --dynamic-randomization-config <PATH_TO_RAND_CONFIG.YAML> --dynamic-scenario-output <OUTPUT_FILE.YAML> --tier <OPTIONAL_TARGET_TIER>
    ```
    Example: `python experiment_cli.py run --generate-scenario tier_0_baseline --dynamic-randomization-config scenarios/dynamic_rand_config.yaml --dynamic-scenario-output my_custom_scenario.yaml --tier 1`
-   **Benchmark agents across all scenarios**:
    ```bash
    python experiment_cli.py run --benchmark-scenarios --agents <AGENT_MODEL_NAME_1> <AGENT_MODEL_NAME_2>
    ```
    This will run all available scenarios (standard, business types, multi-agent) with the specified agents and record their performance.

## 6. Curriculum Validation Best Practices

To ensure a robust and effectively calibrated curriculum:
-   **Regular Benchmarking**: Periodically run `python experiment_cli.py run --benchmark-scenarios --agents <YOUR_AGENT_MODEL>` to test all scenarios and collect success rates.
-   **Analyze Reports**: Examine the `curriculum_validation_report.json` generated by `--validate-curriculum` to identify:
    -   Whether success rates align with expected difficulty progression (e.g., decreasing from T0 to T3).
    -   Scenarios that are too easy or too hard for their intended tier.
    -   Specific skill areas where agents might be overperforming or underperforming.
-   **Iterative Adjustment**: Use the recommendations from the validation report to fine-tune scenario parameters (e.g., `initial_capital`, `competition_levels`, `event_frequency`) or create new scenarios to fill difficulty gaps.

## 7. Golden Master Baselines

Golden master baselines are pre-recorded simulation event snapshots used to detect regressions and ensure reproducibility:

### Enterprise V1.0 Baseline
The official Tier 2 ("supply chain crisis") baseline is available in `artifacts/enterprise_v1.0_baseline.parquet`. This serves as the reference for validating that simulation behavior remains consistent across code changes.

### Managing Golden Masters
-   **Verification**: Run `python scripts/verify_golden_masters.py` to compare current simulation output against saved baselines.
-   **Regeneration**: If intentional changes alter simulation behavior, regenerate baselines via:
    ```bash
    pytest tests/integration/test_tier2_golden_master.py -v
    ```
-   **Adding New Baselines**: Follow the pattern in `test_tier2_golden_master.py` to create additional scenario baselines.

## 8. Multi-Agent Scenario Design Patterns

Designing effective multi-agent scenarios requires considering:
-   **Agent Roles**: Clearly define the responsibilities and goals of each agent (e.g., `seller`, `supplier`, `platform`, `competitor`).
-   **Interaction Mechanisms**: How agents communicate, negotiate, or compete (e.g., shared ledger, event bus, direct message passing).
-   **Interdependencies**: Create situations where agents' actions directly impact others' success criteria.
-   **Information Asymmetry**: Distribute information unevenly to encourage strategic information gathering and sharing.
-   **Conflict Resolution**: Include mechanisms or implicit challenges where agents must resolve disagreements or navigate conflicting objectives.

By following these guidelines, the FBA-Bench scenario system provides a powerful and flexible platform for evaluating LLM agents in complex, realistic business environments, effectively preventing overfitting to specific problem types.
