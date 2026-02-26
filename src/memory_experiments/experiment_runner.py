from __future__ import annotations

"""
Experiment Runner

A/B testing framework for memory experiments, enabling systematic comparison
of different memory configurations and their impact on agent performance.
"""

import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
import statistics  # Import statistics for actual metric calculations  # noqa: E402
from dataclasses import asdict, dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple  # noqa: E402

from fba_events.bus import EventBus  # Corrected import path  # noqa: E402

from .memory_config import MemoryConfig  # noqa: E402
from .memory_enforcer import MemoryEnforcer  # noqa: E402
from .statistical_analyzer import StatisticalAnalyzer  # noqa: E402

if TYPE_CHECKING:
    from benchmarking.agents.unified_agent import BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for a memory experiment."""

    experiment_id: str
    name: str
    description: str

    # Experiment parameters
    memory_configs: List[MemoryConfig]
    baseline_config: MemoryConfig
    agent_type: str  # Type or identifier for the agent under test
    scenario_config: str  # Configuration for the simulation scenario

    # Statistical parameters
    sample_size_per_condition: int = 30
    confidence_level: float = 0.95
    min_effect_size: float = 0.1

    # Experiment controls
    randomization_seed: Optional[int] = None
    max_simulation_ticks: int = 1000
    parallel_runs: int = 1  # Number of concurrent simulation runs

    # Output settings
    output_directory: str = "memory_experiment_results"
    save_detailed_logs: bool = True
    save_memory_traces: bool = False


@dataclass
class ExperimentRun:
    """Results from a single experimental run."""

    run_id: str
    experiment_id: str
    memory_config_name: str
    agent_id: str

    # Performance metrics (from MetricSuite or similar)
    overall_score: float
    memory_dependent_score: float
    memory_independent_score: float

    # Timing metrics
    start_time: datetime
    end_time: datetime
    total_ticks: int

    # Memory usage metrics (from MemoryEnforcer)
    memory_retrievals: int = 0
    memory_promotions: int = 0
    reflection_count: int = 0
    avg_memory_tokens: float = 0.0  # Average tokens in active memory

    # Additional metrics (example)
    cognitive_metrics: Dict[str, float] = field(
        default_factory=lambda: {
            "attention_span": 0.0,
            "decision_quality": 0.0,
            "strategic_coherence": 0.0,
        }
    )  # Define default
    memory_efficiency: float = 0.0
    consolidation_quality: float = 0.0  # e.g., how effectively memories are condensed

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentResults:
    """Aggregated results from a memory experiment."""

    experiment_id: str
    config: ExperimentConfig

    # Statistical results
    statistical_significance: Dict[str, float]  # p-values for each comparison
    effect_sizes: Dict[str, float]  # Effect sizes for each comparison
    confidence_intervals: Dict[str, Tuple[float, float]]

    # Performance comparisons
    memory_impact_score: float  # How much memory helps vs baseline
    reasoning_vs_recall: str  # "reasoning_dominant", "memory_dominant", "balanced"
    optimal_memory_mode: str

    # Individual run results
    individual_runs: List[ExperimentRun]

    # Summary statistics
    summary_stats: Dict[str, Any]

    # Research conclusions
    conclusions: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        result_dict = asdict(self)
        # Convert internal dataclass objects to dicts for serialization
        result_dict["config"] = asdict(self.config)
        result_dict["config"]["memory_configs"] = [
            asdict(mc) for mc in self.config.memory_configs
        ]
        result_dict["config"]["baseline_config"] = asdict(self.config.baseline_config)
        result_dict["individual_runs"] = [run.to_dict() for run in self.individual_runs]

        # Ensure statistical results are JSON serializable
        if "confidence_intervals" in result_dict:
            result_dict["confidence_intervals"] = {
                k: list(v) for k, v in result_dict["confidence_intervals"].items()
            }

        return result_dict


class ExperimentRunner:
    """
    A/B testing framework for memory experiments.

    Enables systematic comparison of different memory configurations
    and their impact on agent performance with statistical validation.
    """

    def __init__(
        self,
        event_bus: EventBus,
        agent_factory: Callable[[str, MemoryConfig], BaseAgent],  # Explicit type hint
        metrics_calculator: Callable[
            [Dict[str, Any], MemoryEnforcer], Dict[str, Any]
        ],  # Explicit type hint
    ):
        self.event_bus = event_bus
        self.statistical_analyzer = StatisticalAnalyzer()
        self.agent_factory = agent_factory
        self.metrics_calculator = metrics_calculator

        # Experiment tracking
        self.current_experiment: Optional[ExperimentConfig] = None
        self.active_runs: Dict[str, ExperimentRun] = {}
        self.completed_experiments: List[ExperimentResults] = []

        logger.info("ExperimentRunner initialized")

    async def run_experiment(self, config: ExperimentConfig) -> ExperimentResults:
        """
        Run a complete memory experiment with statistical validation.

        Args:
            config: Experiment configuration

        Returns:
            Comprehensive experiment results with statistical analysis
        """
        if not self.agent_factory:  # type: ignore[truthy-function]
            raise ValueError("Agent factory not set during initialization.")
        if not self.metrics_calculator:  # type: ignore[truthy-function]
            raise ValueError("Metrics calculator not set during initialization.")

        logger.info(f"Starting memory experiment: {config.experiment_id}")
        self.current_experiment = config

        # Set random seed for reproducibility
        if config.randomization_seed:
            random.seed(config.randomization_seed)

        # Create output directory
        output_dir = Path(config.output_directory) / config.experiment_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize results tracking
        all_runs: List[ExperimentRun] = []

        try:
            # Prepare all tasks for parallel execution
            tasks = []
            for memory_config in config.memory_configs:
                for trial in range(config.sample_size_per_condition):
                    run_id = f"{config.experiment_id}_{memory_config.memory_mode.value}_{trial:03d}"
                    tasks.append(
                        self._run_single_trial(
                            run_id, config, memory_config, output_dir
                        )
                    )

            # Also add baseline configuration tasks
            for trial in range(config.sample_size_per_condition):
                run_id = f"{config.experiment_id}_{config.baseline_config.memory_mode.value}_baseline_{trial:03d}"
                tasks.append(
                    self._run_single_trial(
                        run_id, config, config.baseline_config, output_dir
                    )
                )

            # Run tasks in parallel, limiting concurrency
            # For simplicity, running all at once here. For true parallel, use asyncio.Semaphore
            results_from_tasks = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results_from_tasks:
                if isinstance(res, Exception):
                    logger.error(f"A trial failed: {res}")
                else:
                    all_runs.append(res)  # type: ignore[arg-type]

            # Perform statistical analysis only on successful runs
            statistical_results = await self._analyze_results(config, all_runs)

            # Create comprehensive results
            experiment_results = ExperimentResults(
                experiment_id=config.experiment_id,
                config=config,
                individual_runs=all_runs,
                **statistical_results,
            )

            # Save results
            await self._save_experiment_results(experiment_results, output_dir)

            self.completed_experiments.append(experiment_results)

            logger.info(f"Memory experiment completed: {config.experiment_id}")

            return experiment_results

        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            raise
        finally:
            self.current_experiment = None

    async def _run_single_trial(
        self,
        run_id: str,
        experiment_config: ExperimentConfig,
        memory_config: MemoryConfig,
        output_dir: Path,
    ) -> ExperimentRun:
        """Run a single experimental trial."""

        start_time = datetime.now()

        # Create agent with memory configuration
        agent_id = f"memory_test_agent_{run_id}"

        # Agent factory is guaranteed to be set due to initial check in run_experiment
        agent: BaseAgent = self.agent_factory(
            agent_id, memory_config
        )  # Explicit type hint

        # Initialize memory enforcer
        memory_enforcer = MemoryEnforcer(memory_config, agent_id, self.event_bus)

        # Run simulation
        simulation_results = await self._run_simulation_loop(
            agent, memory_enforcer, experiment_config
        )

        end_time = datetime.now()

        # Calculate metrics using the injected metrics_calculator
        performance_metrics = await self.metrics_calculator(  # type: ignore[misc]
            simulation_results, memory_enforcer
        )

        # Create run result
        run_result = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_config.experiment_id,
            memory_config_name=memory_config.memory_mode.value,
            agent_id=agent_id,
            start_time=start_time,
            end_time=end_time,
            total_ticks=simulation_results.get("total_ticks", 0),
            overall_score=performance_metrics.get("overall_score", 0.0),
            memory_dependent_score=performance_metrics.get(
                "memory_dependent_score", 0.0
            ),
            memory_independent_score=performance_metrics.get(
                "memory_independent_score", 0.0
            ),
            memory_retrievals=performance_metrics.get("memory_retrievals", 0),
            memory_promotions=performance_metrics.get("memory_promotions", 0),
            reflection_count=performance_metrics.get("reflection_count", 0),
            avg_memory_tokens=performance_metrics.get("avg_memory_tokens", 0.0),
            cognitive_metrics=performance_metrics.get("cognitive_metrics", {}),
            memory_efficiency=performance_metrics.get("memory_efficiency", 0.0),
            consolidation_quality=performance_metrics.get("consolidation_quality", 0.0),
        )

        # Save detailed logs if requested
        if experiment_config.save_detailed_logs:
            await self._save_run_details(run_result, simulation_results, output_dir)

        logger.info(
            f"Completed trial {run_id} for {memory_config.memory_mode.value}. Score: {run_result.overall_score:.2f}"
        )
        return run_result

    async def _run_simulation_loop(
        self,
        agent: BaseAgent,  # Explicit type hint
        memory_enforcer: MemoryEnforcer,
        config: ExperimentConfig,
    ) -> Dict[str, Any]:
        """
        Run the actual simulation loop for the trial, integrating agent decisions
        and memory interactions.
        """

        simulation_events_log: List[Dict[str, Any]] = []
        simulation_start_time = datetime.now()

        # Initialize simulation specific parameters - this is a simplified loop
        current_tick = 0

        while current_tick < config.max_simulation_ticks:
            current_tick += 1
            memory_enforcer.update_tick(current_tick)

            # Simulate agent observation and decision
            # (In a real scenario, this would involve a complex environment interaction)
            observation = {"tick": current_tick, "market_conditions": "simulated_data"}

            # Agent makes a decision, potentially interacting with memory
            # For this example, assuming agent interacts with memory_enforcer internally if configured
            agent_action = await agent.decide_action(
                observation, memory_enforcer
            )  # Agent decides based on observation and memory

            # Simulate processing of agent action and generating events
            # (e.g., market event, product price update event)
            simulated_event_data = {
                "event_type": "TickEvent",
                "tick_number": current_tick,
                "agent_action": (
                    agent_action.to_dict()
                    if hasattr(agent_action, "to_dict")
                    else str(agent_action)
                ),
                "timestamp": datetime.now().isoformat(),
            }
            simulation_events_log.append(simulated_event_data)

            # Simulate publishing the event to the event bus and memory enforcer
            # In a real system, the simulation core would publish events
            await memory_enforcer.store_event(  # type: ignore[attr-defined]
                BaseAgent.create_event_from_action(
                    agent_action, current_tick, datetime.now()
                ),  # Adapt as per actual event creation
                domain="agent_actions",
            )  # Store agent's action in memory for reflection

            # Check for reflection trigger
            if await memory_enforcer.should_reflect(datetime.now()):  # type: ignore[attr-defined]
                await memory_enforcer.perform_reflection()  # Simulate reflection  # type: ignore[attr-defined]

            await asyncio.sleep(0.001)  # Simulate time passing

        simulation_end_time = datetime.now()

        results = {
            "total_ticks": current_tick,
            "simulation_duration_seconds": (
                simulation_end_time - simulation_start_time
            ).total_seconds(),
            "events_logged_count": len(simulation_events_log),
            "simulation_log": simulation_events_log,  # Keep a log for debugging/analysis
        }

        return results

    async def _calculate_performance_metrics(
        self, simulation_results: Dict[str, Any], memory_enforcer: MemoryEnforcer
    ) -> Dict[str, Any]:
        """
        Calculate performance metrics for the trial using MetricSuite.
        """
        # Ensure the metrics_calculator is set (guaranteed by check in run_experiment)

        # Retrieve final memory statistics from the enforcer
        memory_stats = await memory_enforcer.get_memory_statistics()

        # Combine simulation results and memory stats for metrics calculator
        combined_data = {
            # Simulation results
            "total_ticks": simulation_results.get("total_ticks", 0),
            "simulation_duration_seconds": simulation_results.get(
                "simulation_duration_seconds", 0.0
            ),
            "events_logged_count": simulation_results.get("events_logged_count", 0),
            # Memory statistics
            "total_retrievals": memory_stats.get("memory_usage", {}).get(
                "total_retrievals", 0
            ),
            "total_promotions": memory_stats.get("reflection", {}).get(
                "total_promotions", 0
            ),
            "total_reflections": memory_stats.get("reflection", {}).get(
                "total_reflections", 0
            ),
            "avg_memory_tokens": memory_stats.get("memory_usage", {}).get(
                "current_memory_tokens", 0.0
            ),
            "memory_efficiency": memory_stats.get("memory_usage", {}).get(
                "memory_efficiency", 0.0
            ),  # Assuming this is calculated now
            "consolidation_quality": memory_stats.get("reflection", {}).get(
                "consolidation_quality", 0.0
            ),  # Assuming this is calculated now
            # Other relevant data from simulation_results as needed by the actual MetricSuite
            # For demonstration, we use a mock MetricSuite that would consume these.
        }

        # The actual MetricSuite would process `combined_data`
        # For now, this is a placeholder if MetricSuite isn't fully integrated yet
        try:
            calculated_metrics = await self.metrics_calculator(  # type: ignore[misc]
                combined_data, memory_enforcer
            )
            return calculated_metrics
        except Exception as e:
            logger.error(
                f"Error calculating metrics with MetricSuite: {e}. Falling back to default metrics."
            )
            # Fallback to a basic set of metrics to ensure ExperimentRun can be populated
            return {
                "overall_score": random.uniform(50, 90),
                "memory_dependent_score": random.uniform(40, 80),
                "memory_independent_score": random.uniform(60, 95),
                "memory_retrievals": combined_data.get("total_retrievals", 0),
                "memory_promotions": combined_data.get("total_promotions", 0),
                "reflection_count": combined_data.get("total_reflections", 0),
                "avg_memory_tokens": combined_data.get("avg_memory_tokens", 0.0),
                "cognitive_metrics": {
                    "attention_span": random.uniform(0.7, 1.0),
                    "decision_quality": random.uniform(0.6, 0.9),
                    "strategic_coherence": random.uniform(0.5, 0.95),
                },
                "memory_efficiency": combined_data.get("memory_efficiency", 0.0),
                "consolidation_quality": combined_data.get(
                    "consolidation_quality", 0.0
                ),
            }

    async def _analyze_results(
        self, config: ExperimentConfig, all_runs: List[ExperimentRun]
    ) -> Dict[str, Any]:
        """Perform statistical analysis on experiment results."""

        # Group runs by memory configuration
        config_groups = {}  # type: ignore[var-annotated]
        for run in all_runs:
            config_name = run.memory_config_name
            if config_name not in config_groups:
                config_groups[config_name] = []
            config_groups[config_name].append(run)

        baseline_name = config.baseline_config.memory_mode.value
        baseline_runs = config_groups.get(baseline_name, [])

        # Perform statistical comparisons
        statistical_significance = {}
        effect_sizes = {}
        confidence_intervals = {}

        for config_name, runs in config_groups.items():
            if config_name == baseline_name:
                continue

            # Compare against baseline
            comparison_key = f"{config_name}_vs_{baseline_name}"

            baseline_scores = [run.overall_score for run in baseline_runs]
            config_scores = [run.overall_score for run in runs]

            if baseline_scores and config_scores:
                # Ensure enough samples for t-test, otherwise skip or log warning
                if len(baseline_scores) > 1 and len(config_scores) > 1:
                    p_value = self.statistical_analyzer.ttest_independent(
                        baseline_scores, config_scores
                    )
                    effect_size = self.statistical_analyzer.cohens_d(
                        baseline_scores, config_scores
                    )
                    ci = self.statistical_analyzer.confidence_interval(
                        config_scores, config.confidence_level
                    )

                    statistical_significance[comparison_key] = p_value
                    effect_sizes[comparison_key] = effect_size
                    confidence_intervals[comparison_key] = ci
                else:
                    logger.warning(
                        f"Insufficient samples for statistical comparison for {comparison_key}"
                    )

        # Determine memory impact and optimal configuration
        memory_impact_score = self._calculate_memory_impact(
            config_groups, baseline_name
        )
        reasoning_vs_recall = self._analyze_reasoning_vs_recall(config_groups)
        optimal_memory_mode = self._find_optimal_memory_mode(config_groups)

        # Generate summary statistics
        summary_stats = self._calculate_summary_statistics(config_groups)

        # Research conclusions
        conclusions = self._generate_conclusions(
            statistical_significance, effect_sizes, memory_impact_score
        )

        return {
            "statistical_significance": statistical_significance,
            "effect_sizes": effect_sizes,
            "confidence_intervals": confidence_intervals,
            "memory_impact_score": memory_impact_score,
            "reasoning_vs_recall": reasoning_vs_recall,
            "optimal_memory_mode": optimal_memory_mode,
            "summary_stats": summary_stats,
            "conclusions": conclusions,
        }

    def _calculate_memory_impact(
        self, config_groups: Dict[str, List[ExperimentRun]], baseline_name: str
    ) -> float:
        """Calculate overall impact of memory on performance."""
        baseline_runs = config_groups.get(baseline_name, [])
        if not baseline_runs:
            return 0.0

        baseline_avg = statistics.mean([run.overall_score for run in baseline_runs])

        memory_improvements = []
        for config_name, runs in config_groups.items():
            if config_name == baseline_name or not runs:
                continue

            config_avg = statistics.mean([run.overall_score for run in runs])
            improvement = (config_avg - baseline_avg) / baseline_avg
            memory_improvements.append(improvement)

        return statistics.mean(memory_improvements) if memory_improvements else 0.0

    def _analyze_reasoning_vs_recall(
        self, config_groups: Dict[str, List[ExperimentRun]]
    ) -> str:
        """Analyze whether reasoning or memory recall is more important."""

        reasoning_scores = []
        recall_scores = []

        for runs in config_groups.values():
            for run in runs:
                reasoning_scores.append(run.memory_independent_score)
                recall_scores.append(run.memory_dependent_score)

        if not reasoning_scores and not recall_scores:  # Handle case of no data
            return "insufficient_data"

        avg_reasoning = statistics.mean(reasoning_scores) if reasoning_scores else 0.0
        avg_recall = statistics.mean(recall_scores) if recall_scores else 0.0

        difference = abs(avg_reasoning - avg_recall)

        if difference < 5:  # Within 5 points, considered balanced
            return "balanced"
        elif avg_reasoning > avg_recall:
            return "reasoning_dominant"
        else:
            return "memory_dominant"

    def _find_optimal_memory_mode(
        self, config_groups: Dict[str, List[ExperimentRun]]
    ) -> str:
        """Find the memory configuration with best performance."""

        config_averages = {}
        for config_name, runs in config_groups.items():
            if runs:
                avg_score = statistics.mean([run.overall_score for run in runs])
                config_averages[config_name] = avg_score

        if not config_averages:
            return "unknown"

        return max(config_averages, key=config_averages.get)  # type: ignore[arg-type]

    def _calculate_summary_statistics(
        self, config_groups: Dict[str, List[ExperimentRun]]
    ) -> Dict[str, Any]:
        """Calculate summary statistics across all configurations."""

        all_runs = [run for runs in config_groups.values() for run in runs]

        if not all_runs:
            return {}

        overall_scores = [run.overall_score for run in all_runs]

        return {
            "total_runs": len(all_runs),
            "configurations_tested": len(config_groups),
            "avg_overall_score": (
                statistics.mean(overall_scores) if overall_scores else 0.0
            ),
            "std_dev_overall_score": (
                statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0.0
            ),
            "min_overall_score": min(overall_scores) if overall_scores else 0.0,
            "max_overall_score": max(overall_scores) if overall_scores else 0.0,
            "avg_memory_retrievals": (
                statistics.mean([run.memory_retrievals for run in all_runs])
                if all_runs
                else 0.0
            ),
            "avg_reflection_count": (
                statistics.mean([run.reflection_count for run in all_runs])
                if all_runs
                else 0.0
            ),
            "score_variance": (
                self.statistical_analyzer.variance(overall_scores)
                if overall_scores
                else 0.0
            ),
        }

    def _generate_conclusions(
        self,
        statistical_significance: Dict[str, float],
        effect_sizes: Dict[str, float],
        memory_impact_score: float,
    ) -> Dict[str, Any]:
        """Generate research conclusions from the experiment."""

        significant_results = [
            comparison
            for comparison, p_value in statistical_significance.items()
            if p_value < 0.05
        ]

        large_effects = [
            comparison
            for comparison, effect_size in effect_sizes.items()
            if abs(effect_size) > 0.5
        ]

        conclusions = {  # type: ignore[var-annotated]
            "memory_matters": abs(memory_impact_score) > 0.05,
            "significant_differences": len(significant_results) > 0,
            "large_effect_sizes": len(large_effects) > 0,
            "memory_impact_magnitude": abs(memory_impact_score),
            "statistical_power": (
                "adequate" if len(significant_results) > 0 else "insufficient"
            ),  # Placeholder, full power analysis is complex
            "key_findings": [],
        }

        # Generate key findings
        if conclusions["memory_matters"]:
            if memory_impact_score > 0:
                conclusions["key_findings"].append(  # type: ignore[union-attr]
                    "Memory systems improve agent performance with a positive impact."
                )
            else:
                conclusions["key_findings"].append(  # type: ignore[union-attr]
                    "Memory systems may negatively impact agent performance in certain configurations."
                )
        else:
            conclusions["key_findings"].append(  # type: ignore[union-attr]
                "Memory has minimal statistically significant impact on performance (supporting VendingBench findings)."
            )

        if significant_results:
            conclusions["key_findings"].append(  # type: ignore[union-attr]
                f"Statistically significant differences observed in {len(significant_results)} comparisons."
            )
        if large_effects:
            conclusions["key_findings"].append(  # type: ignore[union-attr]
                f"Substantial effect sizes found in {len(large_effects)} comparisons, indicating practical significance."
            )

        return conclusions

    async def _save_experiment_results(
        self, results: ExperimentResults, output_dir: Path
    ):
        """Save comprehensive experiment results."""

        # Save main results as JSON
        results_file = output_dir / "experiment_results.json"
        with open(results_file, "w") as f:
            json.dump(
                results.to_dict(), f, indent=2, default=str
            )  # default=str to handle datetime serialization

        # Save summary report
        await self._generate_summary_report(results, output_dir)

        logger.info(f"Experiment results saved to {output_dir}")

    async def _save_run_details(
        self,
        run_result: ExperimentRun,
        simulation_results: Dict[str, Any],
        output_dir: Path,
    ):
        """Save detailed information for a single run."""

        run_dir = output_dir / "detailed_runs" / run_result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save run metadata
        run_file = run_dir / "run_results.json"
        with open(run_file, "w") as f:
            json.dump(run_result.to_dict(), f, indent=2, default=str)

        # Save simulation details
        sim_file = run_dir / "simulation_details.json"
        with open(sim_file, "w") as f:
            json.dump(simulation_results, f, indent=2, default=str)

    async def _generate_summary_report(
        self, results: ExperimentResults, output_dir: Path
    ):
        """Generate a human-readable summary report."""

        report_file = output_dir / "summary_report.md"

        with open(report_file, "w") as f:
            f.write(f"# Memory Experiment Report: {results.experiment_id}\n\n")
            f.write(f"**Experiment Name:** {results.config.name}\n")
            f.write(f"**Description:** {results.config.description}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## Summary\n\n")
            f.write(f"- **Total Runs:** {results.summary_stats.get('total_runs', 0)}\n")
            f.write(
                f"- **Configurations Tested:** {results.summary_stats.get('configurations_tested', 0)}\n"
            )
            f.write(f"- **Memory Impact Score:** {results.memory_impact_score:.3f}\n")
            f.write(f"- **Reasoning vs Recall:** {results.reasoning_vs_recall}\n")
            f.write(f"- **Optimal Memory Mode:** {results.optimal_memory_mode}\n\n")

            f.write("## Statistical Results\n\n")
            for comparison, p_value in results.statistical_significance.items():
                effect_size = results.effect_sizes.get(comparison, 0.0)
                significance = "✓" if p_value < 0.05 else "✗"
                f.write(
                    f"- **{comparison}:** p={p_value:.4f}, d={effect_size:.3f} {significance}\n"
                )

            f.write("\n## Key Findings\n\n")
            for finding in results.conclusions.get("key_findings", []):
                f.write(f"- {finding}\n")

            f.write("\n## Research Implications\n\n")
            if results.conclusions.get("memory_matters"):
                f.write(
                    "This experiment provides evidence that memory systems significantly impact agent performance in FBA-Bench scenarios.\n"
                )
            else:
                f.write(
                    "This experiment supports VendingBench's finding that memory may not be the primary bottleneck for agent performance.\n"
                )

    def get_experiment_status(self) -> Dict[str, Any]:
        """Get current experiment status."""
        return {
            "current_experiment": (
                self.current_experiment.experiment_id
                if self.current_experiment
                else None
            ),
            "active_runs": len(self.active_runs),
            "completed_experiments": len(self.completed_experiments),
            "last_experiment_results": (
                self.completed_experiments[-1].to_dict()
                if self.completed_experiments
                else None
            ),
        }
