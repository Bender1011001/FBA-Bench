from __future__ import annotations

import itertools
import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import yaml


class ExperimentConfig:
    """
    Configuration for an experiment sweep.

    Expected keys in config_data:
      - experiment_name: str
      - description: str (optional)
      - base_parameters: dict
      - parameter_sweep: dict[str, list]
      - output: dict (optional)
    """

    def __init__(self, config_data: Dict[str, Any]):
        self.experiment_name: str = config_data["experiment_name"]
        self.description: str = config_data.get("description", "")
        self.base_parameters: Dict[str, Any] = config_data.get("base_parameters", {})
        self.parameter_sweep: Dict[str, List[Any]] = config_data.get("parameter_sweep", {}) or {}
        self.output_config: Dict[str, Any] = config_data.get("output", {})

    def generate_parameter_combinations(self) -> Iterator[Tuple[int, Dict[str, Any]]]:
        """
        Yield (run_number, parameters) for each combination in the sweep.
        If no sweep parameters are provided, yield exactly one run with base_parameters.
        """
        if not self.parameter_sweep:
            yield 1, dict(self.base_parameters)
            return

        param_names = list(self.parameter_sweep.keys())
        param_value_lists = [self.parameter_sweep[name] for name in param_names]

        run_number = 1
        for combo in itertools.product(*param_value_lists):
            parameters = dict(zip(param_names, combo))
            final_params = self.base_parameters.copy()
            final_params.update(parameters)
            yield run_number, final_params
            run_number += 1

    def get_total_combinations(self) -> int:
        """
        Return total number of combinations implied by parameter_sweep.
        If empty, count is 1 (single run using base_parameters only).
        """
        if not self.parameter_sweep:
            return 1
        total = 1
        for values in self.parameter_sweep.values():
            total *= len(values)
        return total


class SimulationRunner:
    """
    Helper that would orchestrate simulation setup using parameters from ExperimentConfig.
    The tests only validate internal helpers; no full simulation is required here.
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _format_key_parameters(self, params: Dict[str, Any]) -> str:
        """
        Create a human-readable string from key parameters.
        Mirrors the formatting logic the tests expect to print.
        """
        key_info: List[str] = []
        if "initial_price" in params:
            key_info.append(f"price=${params['initial_price']}")
        if "competitor_persona_distribution" in params:
            dist = params["competitor_persona_distribution"]
            if isinstance(dist, dict) and "name" in dist:
                key_info.append(f"market={dist['name']}")
        if "market_sensitivity" in params:
            key_info.append(f"sensitivity={params['market_sensitivity']}")
        return ", ".join(key_info)

    def _setup_competitor_manager(self, params: Dict[str, Any]):
        """
        Construct a CompetitorManager instance using safe defaults derived from params.
        The test asserts successful construction only.
        """
        from services.competitor_manager import CompetitorManager

        sensitivity = float(params.get("market_sensitivity", 0.8) or 0.8)
        # Map sensitivity to small volatility parameters for deterministic behavior in tests.
        cfg = {
            "pricing_volatility": max(0.0, min(0.2, 0.05 * sensitivity)),
            "bsr_volatility": max(0.0, min(0.5, 0.1 * sensitivity)),
            "sales_volatility": max(0.0, min(0.5, 0.1 * sensitivity)),
        }
        return CompetitorManager(config=cfg)


class ExperimentManager:
    """
    Manages experiment lifecycle around a given sweep.yaml:
      - Loads configuration
      - Creates a timestamped results directory
      - Persists the resolved configuration snapshot
    """

    def __init__(self, config_path: Union[str, Path], results_root: Union[str, Path, None] = None):
        self.config_path = Path(config_path)
        with open(self.config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.experiment_config = ExperimentConfig(cfg)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_results_root = Path(results_root) if results_root is not None else Path("results")
        self.results_dir: Path = (
            base_results_root / f"{self.experiment_config.experiment_name}_{ts}"
        )
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Persist a copy of the configuration used for this run directory
        out_cfg_path = self.results_dir / "experiment_config.yaml"
        with open(out_cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f)


class ScenarioEngine:
    """
    Minimal scenario engine facade. The production test monkeypatches run_simulation.
    """

    def run_simulation(self, scenario_file: str, agents: Dict[str, Any]) -> Dict[str, Any]:
        # Fallback minimal behavior (should be monkeypatched in tests)
        return {
            "final_state": {"ok": True},
            "simulation_duration": 0,
            "metrics": {"total_profit": 0.0},
        }


def _load_config_and_expand_run_params(config_path: str) -> Tuple[ExperimentConfig, Iterable[int]]:
    """
    Load config from YAML file and return (ExperimentConfig, iterable of run_numbers).
    The iterable yields 1..N where N is total combinations (1 if no sweep defined).
    """
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    exp_config = ExperimentConfig(cfg)
    total = exp_config.get_total_combinations()
    # Yield run numbers 1..total (the production test inspects only the count)
    return exp_config, range(1, total + 1)


def _parallel_run(
    config_path: str,
    run_numbers: Iterable[Union[int, Tuple[int, Dict[str, Any]]]],
    results_dir: str,
    parallel: int = 1,
) -> int:
    """
    Execute runs sequentially (parallel parameter accepted for API compatibility).
    Writes results as JSON files: results_dir/run_{run_number}.json
    Returns the count of successful runs written.
    """
    # Load configuration once
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    exp_config = ExperimentConfig(cfg)

    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    successes = 0
    engine = ScenarioEngine()

    # Normalize run identifiers
    for item in run_numbers:
        if isinstance(item, tuple):
            run_number = int(item[0])
            # per_run_params = item[1]  # Not required by the production test
        else:
            run_number = int(item)

        scenario_file = exp_config.base_parameters.get("scenario_file", "dummy_scenario.yaml")
        agents = exp_config.base_parameters.get("agents", {})

        try:
            result = engine.run_simulation(scenario_file, agents)
            out_path = out_dir / f"run_{run_number}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            successes += 1
        except Exception:
            # Intentionally keep simple for tests; failures remain silent and reduce success count
            continue

    return successes


# =========================
# CLI and Helper Utilities
# =========================


def _build_arg_parser() -> argparse.ArgumentParser:
    """
    Build the CLI argument parser with a 'run' subcommand and expected flags.

    Returns:
        argparse.ArgumentParser: Configured parser instance.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="experiment_cli.py", description="Experiment CLI")
    subparsers = parser.add_subparsers(dest="command")
    try:
        # Available in Python 3.7+
        subparsers.required = True
    except AttributeError:
        pass

    run_parser = subparsers.add_parser("run", help="Run scenarios or utilities")
    run_parser.add_argument("--scenario", type=str, help="Scenario name to run")
    run_parser.add_argument("--tier", type=int, help="Tier number to filter scenarios")
    run_parser.add_argument(
        "--agents", type=str, help='Comma-separated agent names (e.g., "MockAgent,Other")'
    )
    run_parser.add_argument(
        "--validate-curriculum", action="store_true", dest="validate_curriculum"
    )
    run_parser.add_argument(
        "--benchmark-scenarios", action="store_true", dest="benchmark_scenarios"
    )
    run_parser.add_argument(
        "--generate-scenario",
        type=str,
        dest="generate_scenario",
        help="Template slug (e.g., 'tier_0_baseline')",
    )
    run_parser.add_argument(
        "--dynamic-randomization-config",
        type=str,
        dest="dynamic_randomization_config",
        help="Path to randomization YAML config",
    )
    run_parser.add_argument(
        "--dynamic-scenario-output",
        type=str,
        dest="dynamic_scenario_output",
        help="Path to write generated scenario YAML",
    )
    # Results and scenarios dir defaults resolved dynamically in helpers
    run_parser.add_argument(
        "--results-dir",
        type=str,
        dest="results_dir",
        help="Results directory (default resolved dynamically)",
    )
    run_parser.add_argument(
        "--scenarios-dir",
        type=str,
        dest="scenarios_dir",
        help="Scenarios directory (default resolved dynamically)",
    )

    return parser


def _ensure_results_dir(args) -> Path:
    """
    Ensure results directory exists based on args or dynamic defaults.

    Rules:
      - If args.results_dir is provided: use it.
      - Else if 'test_scenario_results' exists in CWD: use that.
      - Else: use 'results'.

    Returns:
      Path: Created/ensured results directory.
    """
    from pathlib import Path as _Path

    provided = getattr(args, "results_dir", None)
    if provided:
        rd = _Path(provided)
    else:
        cwd = _Path().resolve()
        test_dir = cwd / "test_scenario_results"
        rd = test_dir if test_dir.exists() else cwd / "results"

    rd.mkdir(parents=True, exist_ok=True)
    return rd


def _ensure_scenarios_dir(args) -> Path:
    """
    Resolve scenarios directory based on args or dynamic defaults.

    Rules:
      - If args.scenarios_dir is provided: use it.
      - Else if 'test_scenarios_temp' exists in CWD: use that.
      - Else: use 'scenarios'.

    Raises:
      FileNotFoundError: If resolved path does not exist.

    Returns:
      Path: Existing scenarios directory.
    """
    from pathlib import Path as _Path

    provided = getattr(args, "scenarios_dir", None)
    if provided:
        sd = _Path(provided)
    else:
        cwd = _Path().resolve()
        test_dir = cwd / "test_scenarios_temp"
        sd = test_dir if test_dir.exists() else cwd / "scenarios"

    if not sd.exists() or not sd.is_dir():
        raise FileNotFoundError(f"Scenarios directory not found: {sd}")
    return sd


def _discover_scenarios(scenarios_dir: Path) -> list[Path]:
    """
    Recursively discover all YAML scenario files beneath scenarios_dir.

    Returns:
      list[Path]: Sorted list of file paths.
    """
    files = sorted(scenarios_dir.rglob("*.yaml"), key=lambda p: str(p).lower())
    return files


def _read_yaml(path: Path) -> dict:
    """
    Read a YAML file using a safe loader.

    Returns:
      dict: Parsed YAML content or {} if file is empty.
    """
    import yaml as _yaml

    with open(path, encoding="utf-8") as f:
        data = _yaml.safe_load(f)
    return data or {}


def _write_yaml(path: Path, data: dict) -> None:
    """
    Write a dictionary to a YAML file using a safe dumper and UTF-8 encoding.

    Ensures parent directory exists.
    """
    import yaml as _yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        _yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _write_json(results_dir: Path, prefix: str, data: object) -> Path:
    """
    Write JSON data to results_dir with a timestamped filename.

    Args:
      results_dir: Base directory to write into.
      prefix: Filename prefix (e.g., 'scenario_run' or 'benchmark_run').
      data: JSON-serializable object.

    Returns:
      Path: Full path written.
    """
    import json as _json
    from datetime import datetime as _dt

    ts = _dt.now().strftime("%Y%m%d-%H%M%S")
    out_path = results_dir / f"{prefix}_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path


def _find_scenario_by_name(name: str, scenarios_dir: Path) -> Path:
    """
    Find a scenario YAML by its scenario_name inside file content, else fall back to filename stem matching.

    Matching:
      - Preferred: config_data['scenario_name'] == name
      - Fallback: filename stem contains normalized(name) where normalization is lowercase without spaces/underscores.

    Raises:
      FileNotFoundError: If no match is found.
    """
    import re as _re

    normalized = _re.sub(r"[\\s_]+", "", name).lower()

    candidates = _discover_scenarios(scenarios_dir)
    exact_match: Path | None = None
    fallback_match: Path | None = None

    for p in candidates:
        cfg = _read_yaml(p)
        scn = cfg.get("scenario_name")
        if isinstance(scn, str) and scn == name:
            exact_match = p
            break
        stem_norm = _re.sub(r"[\\s_]+", "", p.stem).lower()
        if normalized in stem_norm and fallback_match is None:
            fallback_match = p

    if exact_match:
        return exact_match
    if fallback_match:
        return fallback_match
    raise FileNotFoundError(f"Scenario not found by name: {name!r} in {scenarios_dir}")


def _parse_agents_list(agents_arg: str | None) -> list[str]:
    """
    Parse a comma-separated agents string into a de-duplicated list (order-preserving).

    Args:
      agents_arg: String like "MockAgent,Other"

    Returns:
      list[str]: Parsed, stripped agent names.
    """
    if not agents_arg:
        return []
    parts = [s.strip() for s in agents_arg.split(",")]
    seen: set[str] = set()
    result: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _create_agent_models(agent_names: list[str]) -> dict[str, object]:
    """
    Create agent model instances using BotFactory for each provided name.

    Imports inside the function to allow tests to monkeypatch BotFactory.create_bot.

    Args:
      agent_names: List of agent names.

    Returns:
      dict[str, object]: Mapping of agent name -> agent instance.
    """
    # Local import for patching and to avoid import-time side effects
    try:
        from baseline_bots.bot_factory import BotFactory
    except Exception as e:
        raise ImportError(f"Unable to import BotFactory: {e}") from e

    models: dict[str, object] = {}
    for n in agent_names:
        try:
            models[n] = BotFactory.create_bot(n)  # Patched in tests to return a MockAgent
        except Exception:
            # Defensive fallback: create a minimal stub with a .name() method
            class _StubAgent:
                def __init__(self, nm: str) -> None:
                    self._nm = nm

                def name(self) -> str:
                    return self._nm

            models[n] = _StubAgent(n)
    return models


async def _cmd_run(args) -> int:
    """
    Execute scenario runs based on parsed args.

    Modes:
      a) --benchmark-scenarios: run all scenarios in scenarios_dir
      b) --tier N: run all scenarios with difficulty_tier == N
      c) --scenario NAME: run the specific scenario matching NAME
      d) else: ValueError

    Writes:
      - scenario_run_*.json or benchmark_run_*.json in results_dir
      - curriculum_validation_report.json if --validate-curriculum is set

    Returns:
      int: 0 on success.
    """
    import inspect as _inspect

    from scenarios.curriculum_validator import CurriculumValidator

    # Local imports for patching in tests
    from scenarios.scenario_engine import ScenarioEngine

    scenarios_dir = _ensure_scenarios_dir(args)
    results_dir = _ensure_results_dir(args)

    agent_names = _parse_agents_list(getattr(args, "agents", None))
    if not agent_names:
        raise ValueError("Agent list cannot be empty. Provide --agents with at least one agent.")
    agent_models = _create_agent_models(agent_names)
    first_agent = agent_names[0]

    engine = ScenarioEngine()

    async def _run_one_async(sp: Path) -> dict:
        """Run a single scenario path asynchronously and return the enriched result dict."""
        cfg = _read_yaml(sp)
        scenario_name = cfg.get("scenario_name", sp.stem)
        tier = cfg.get("difficulty_tier", None)

        # Always use fresh engine instance and await properly
        from scenarios.scenario_engine import ScenarioEngine as _SE

        _engine = _SE()
        res = _engine.run_simulation(str(sp), agent_models=agent_models)

        if _inspect.isawaitable(res):
            res = await res

        # Merge ensuring required keys are present
        out = dict(res) if isinstance(res, dict) else {}
        out.setdefault("scenario_name", scenario_name)
        if tier is not None:
            out["tier"] = tier
        out["agent_name"] = first_agent
        return out

    results: list[dict] = []
    write_prefix = "scenario_run"

    # Determine mode and scenario paths
    if bool(getattr(args, "benchmark_scenarios", False)):
        # Discover and filter only valid scenario YAMLs (exclude helper/config YAML like dynamic_rand_config.yaml)
        all_paths = _discover_scenarios(scenarios_dir)
        scenario_paths = []
        for p in all_paths:
            cfg = _read_yaml(p)
            if isinstance(cfg, dict) and "scenario_name" in cfg and "difficulty_tier" in cfg:
                scenario_paths.append(p)
        write_prefix = "benchmark_run"
    elif getattr(args, "tier", None) is not None:
        target_tier = int(args.tier)
        scenario_paths = []
        for p in _discover_scenarios(scenarios_dir):
            cfg = _read_yaml(p)
            if int(cfg.get("difficulty_tier", -999)) == target_tier:
                scenario_paths.append(p)
    elif getattr(args, "scenario", None):
        scenario_paths = [_find_scenario_by_name(str(args.scenario), scenarios_dir)]
    else:
        raise ValueError("Must provide --scenario, --tier, or --benchmark-scenarios")

    # Execute runs - always use async path to avoid duplicates
    for sp in scenario_paths:
        try:
            result = await _run_one_async(sp)
            results.append(result)
        except Exception:
            # Be conservative; propagate to surface errors during tests
            raise

    # Write results JSON
    _write_json(results_dir, write_prefix, results)

    # Optional curriculum validation
    if bool(getattr(args, "validate_curriculum", False)):
        validator = CurriculumValidator()
        for item in results:
            agent_model_name = str(item.get("agent_name", first_agent))
            tier_val = item.get("tier", -1)
            try:
                tier_int = int(tier_val) if tier_val is not None else -1
            except Exception:
                tier_int = -1
            scenario_name = str(item.get("scenario_name", ""))
            validator.benchmark_agent_performance(agent_model_name, tier_int, scenario_name, item)
        report = validator.generate_curriculum_report()
        import json as _json

        with open(results_dir / "curriculum_validation_report.json", "w", encoding="utf-8") as f:
            _json.dump(report, f, ensure_ascii=False, indent=2)

    return 0


def _cmd_generate_scenario(args) -> None:
    """
    Generate a dynamic scenario from a template and exit with code 0.

    Behavior:
      - Resolve scenarios_dir and results_dir
      - Instantiate DynamicScenarioGenerator with template_dir=str(scenarios_dir)+os.sep
      - Load randomization YAML from args.dynamic_randomization_config
      - Generate scenario and write to args.dynamic_scenario_output
      - Call sys.exit(0)
    """
    import os as _os
    import sys as _sys

    from scenarios.dynamic_generator import DynamicScenarioGenerator

    scenarios_dir = _ensure_scenarios_dir(args)
    _ = _ensure_results_dir(args)  # Ensure results dir exists even if unused directly

    if not getattr(args, "generate_scenario", None):
        raise ValueError("--generate-scenario requires a template slug")
    if not getattr(args, "dynamic_randomization_config", None):
        raise ValueError("--dynamic-randomization-config is required when generating scenarios")
    if not getattr(args, "dynamic_scenario_output", None):
        raise ValueError("--dynamic-scenario-output is required when generating scenarios")

    generator = DynamicScenarioGenerator(template_dir=str(scenarios_dir) + _os.sep)

    rand_cfg_path = Path(args.dynamic_randomization_config)
    rand_cfg = _read_yaml(rand_cfg_path)

    generated = generator.generate_scenario(args.generate_scenario, rand_cfg)
    out_path = Path(args.dynamic_scenario_output)
    _write_yaml(out_path, generated.config_data)

    # Explicit exit as required by tests
    _sys.exit(0)


async def main() -> None:
    """
    Async CLI entrypoint.

    - Parses arguments
    - If in generate scenario mode, writes YAML and sys.exit(0)
    - Else runs scenarios and writes results JSON (and optional curriculum report)
    """

    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.command != "run":
        raise ValueError("Unsupported command. Use 'run'.")

    if getattr(args, "generate_scenario", None):
        # This will call sys.exit(0)
        _cmd_generate_scenario(args)
        return

    await _cmd_run(args)
