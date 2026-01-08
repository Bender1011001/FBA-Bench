2026-01-05 23:59:43 | src/agent_runners/__init__.py | PROCESSED | Fixed lazy loading __getattr__ to correctly resolve all items in __all__ from candidate modules and added agent_registry to candidates.
2026-01-07 13:18:49 | src/agent_runners/agent_manager.py | PROCESSED | Fixed 4 bugs: 1) Undefined variable 'e' in exception handler (line 972), 2) Undefined variable 'e' in learn() method (line 1179), 3) Non-existent method list_active_agents() replaced with active_agents().values() (line 524), 4) Missing prompt_metadata argument in AgentDecisionEvent constructor (line 654)
2026-01-07 13:20:12 | src/agent_runners/agent_registry.py | PROCESSED | No issues found. File is clean.
2026-01-07 13:21:20 | src/agent_runners/base_runner.py | PROCESSED | Fixed 1 bug: Removed duplicate async_cleanup method definition (lines 554-561 shadowed 536-543).
2026-01-07 13:21:49 | src/agent_runners/compat.py | PROCESSED | No issues found. File is clean.
2026-01-07 13:22:14 | src/agent_runners/configs/__init__.py | PROCESSED | No issues found.
2026-01-07 13:22:47 | src/agent_runners/configs/config_schema.py | PROCESSED | No issues found.
2026-01-07 13:22:47 | src/agent_runners/configs/framework_configs.py | PROCESSED | No issues found.
2026-01-07 13:23:41 | src/agent_runners/crewai_runner.py | PROCESSED | No issues found. Import error for 'crewai' is expected (soft dependency).
2026-01-07 13:24:09 | src/agent_runners/dependency_manager.py | PROCESSED | No issues found.
2026-01-07 13:24:48 | src/agent_runners/diy_runner.py | PROCESSED | No real issues. Pylint E1101 errors are false positives due to Pydantic FieldInfo type confusion.
2026-01-07 13:25:54 | src/agent_runners/langchain_runner.py | PROCESSED | No issues found.
2026-01-07 13:25:54 | src/agent_runners/registry.py | PROCESSED | Fixed 1 bug: Added missing Union import.
2026-01-07 13:25:54 | src/agent_runners/runner_factory.py | PROCESSED | No issues found.
2026-01-07 13:26:44 | src/agent_runners/simulation_runner.py | PROCESSED | No issues found.
2026-01-07 13:26:44 | src/agent_runners/unified_runner_factory.py | PROCESSED | No issues found.
2026-01-07 13:26:44 | src/agent_runners/examples/framework_demo.py | PROCESSED | No issues. Import errors expected (example script context).
2026-01-07 13:28:09 | src/agents/__init__.py | PROCESSED | Fixed 1 bug: Added missing SkillCoordinator import.
2026-01-07 13:28:09 | src/agents/advanced_agent.py | PROCESSED | No issues found.
2026-01-07 13:28:09 | src/agents/base.py | PROCESSED | No issues found.
2026-01-07 13:29:41 | src/agents/cognitive_config.py | PROCESSED | No issues found.
2026-01-07 13:29:41 | src/agents/hierarchical_planner.py | PROCESSED | No issues found.
2026-01-07 13:29:41 | src/agents/multi_domain_controller.py | PROCESSED | No issues found.
2026-01-07 13:29:41 | src/agents/registry.py | PROCESSED | No issues found.
2026-01-07 13:29:41 | src/agents/skill_config.py | PROCESSED | Fixed 1 bug: Added missing Tuple import.
2026-01-07 13:29:41 | src/agents/skill_coordinator.py | PROCESSED | No issues found.
2026-01-07 13:29:41 | src/agents/baseline/baseline_agent_v1.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/coordination/__init__.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/coordination/coordination.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/coordination/crisis.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/coordination/models.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/coordination/performance.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/coordination/resources.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/planning/__init__.py | PROCESSED | Fixed 2 bugs: added datetime import and fixed missing event publishing imports.
2026-01-07 13:32:03 | src/agents/planning/events.py | PROCESSED | Fixed 1 bug: added missing imports for EventBus and models.
2026-01-07 13:32:03 | src/agents/planning/generation.py | PROCESSED | No issues found.
2026-01-07 13:32:03 | src/agents/planning/models.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/planning/utils.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/planning/validation.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/__init__.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/base.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/base_skill.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/calculator.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/customer_service.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/extract_fields.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/financial_analyst.py | PROCESSED | No issues found.
2026-01-07 13:32:53 | src/agents/skill_modules/lookup.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skill_modules/marketing_manager.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skill_modules/product_sourcing.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skill_modules/registry.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skill_modules/summarize.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skill_modules/supply_manager.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skill_modules/transform_text.py | PROCESSED | No issues found.
2026-01-07 13:34:21 | src/agents/skills/__init__.py | PROCESSED | Fixed 1 bug: passed missing resource_allocation argument to ConflictResolver constructor.
2026-01-07 13:34:21 | src/agents/skills/conflicts.py | PROCESSED | Fixed 1 bug: added missing Money import.
2026-01-07 13:34:21 | src/agents/skills/dispatch.py | PROCESSED | Fixed 1 bug: added missing datetime import.
2026-01-07 13:34:21 | src/agents/skills/metrics.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/agents/skills/models.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/agents/skills/resources.py | PROCESSED | Fixed bug via src/fba_bench_core/money.py (added abs method).
2026-01-07 13:39:23 | src/agents/skills/utils.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/baseline_bots/bot_factory.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/baseline_bots/claude_sonnet_bot.py | PROCESSED | No issues found (import errors resolved with correct PYTHONPATH).
2026-01-07 13:39:23 | src/baseline_bots/gpt_3_5_bot.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/baseline_bots/gpt_4o_mini_bot.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/baseline_bots/greedy_script_bot.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/baseline_bots/grok_4_bot.py | PROCESSED | No issues found.
2026-01-07 13:39:23 | src/benchmarking/__init__.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/agents/__init__.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/agents/base.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/agents/registry.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/agents/unified_agent.py | PROCESSED | Fixed missing re import in regex search methods.
2026-01-07 16:06:44 | src/benchmarking/config/__init__.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/config/manager.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/config/pydantic_config.py | PROCESSED | Fixed multiple issues: added @classmethod to validators, renamed default_factory to use lambdas, and suppressed FieldInfo member errors.
2026-01-07 16:06:44 | src/benchmarking/config/schema.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/config/schema_manager.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/core/__init__.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/core/config.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/core/engine.py | PROCESSED | Fixed multiple bugs: 1) Undefined variable coro in run_benchmark_sync, 2) Removed redundant broken code block, 3) Added pylint disable for false positive not-callable on scenario getter.
2026-01-07 16:06:44 | src/benchmarking/core/models.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/core/results.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/core/validation.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/evaluation/__init__.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/evaluation/enhanced_evaluation_framework.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/integration/__init__.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/integration/agent_adapter.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/integration/analyze_gpt5_learning.py | PROCESSED | No issues found.
2026-01-07 16:06:44 | src/benchmarking/metrics/registry.py | PROCESSED | Added get_metrics_by_category for engine compatibility.
2026-01-07 16:26:06 | src/benchmarking/integration/integration_manager.py | PROCESSED | Fixed relative imports and matched updated AgentManager API (create_agent, get_agent_runner, list_agents, async stop).
2026-01-07 16:26:06 | src/benchmarking/integration/manager.py | PROCESSED | Fixed E1101 via src/metrics/metric_suite.py (added _handle_general_event).
2026-01-07 16:26:06 | src/benchmarking/integration/metrics_adapter.py | PROCESSED | Fixed E1101 via src/metrics/metric_suite.py (added _handle_general_event).
2026-01-07 16:26:06 | src/benchmarking/metrics/__init__.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/accuracy_score.py | PROCESSED | Fixed false positive FieldInfo member error with pylint disable.
2026-01-07 16:26:06 | src/benchmarking/metrics/advanced_cognitive.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/aggregate.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/base.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/business_intelligence.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/comparative_analysis.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/completeness.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/cost_efficiency.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/cross_domain.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/custom_scriptable.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/ethical_safety.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/extensible_metrics.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/keyword_coverage.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/policy_compliance.py | PROCESSED | No issues found.
2026-01-07 16:26:06 | src/benchmarking/metrics/registry.py | PROCESSED | No issues found (confirmed clean).
2026-01-07 16:26:06 | src/benchmarking/metrics/robustness.py | PROCESSED | No issues found.
2026-01-08 00:00:00 | src/benchmarking/registry/global_registry.py | PROCESSED | Fixed E0203 (access before definition) by using getattr on _initialized in __init__.
2026-01-08 00:00:00 | src/benchmarking/registry/global_variables.py | PROCESSED | Fixed E0203 (access before definition) by using getattr on _initialized in __init__.
2026-01-08 00:00:00 | src/benchmarking/scenarios/__init__.py | PROCESSED | Fixed E0603 (__all__ issues) by adding missing imports and removing non-existent config classes.
2026-01-08 00:00:00 | src/benchmarking/scenarios/base.py | PROCESSED | Converted ScenarioConfig to Pydantic BaseModel, added missing execution_history to BaseScenario, and fixed vfn callable check.
2026-01-08 00:00:00 | src/benchmarking/scenarios/demand_forecasting.py | PROCESSED | Suppressed Pylint false positives for unary operand type on FieldInfo and fixed model_json_schema call.
2026-01-08 00:00:00 | src/benchmarking/scenarios/marketing_campaign.py | PROCESSED | No issues found (confirmed clean).
2026-01-08 00:00:00 | src/benchmarking/scenarios/price_optimization.py | PROCESSED | No issues found (confirmed clean).
2026-01-08 00:00:00 | src/benchmarking/scenarios/registry.py | PROCESSED | Fixed E1101 (no member _scenarios) by declaring the attribute at class level.
2026-01-08 00:00:00 | src/benchmarking/scenarios/supply_chain_disruption.py | PROCESSED | No issues found (confirmed clean).
2026-01-08 00:00:00 | src/benchmarking/scenarios/templates.py | PROCESSED | Fixed E0602 by adding missing statistics import.
2026-01-08 00:00:00 | src/benchmarking/utils/asyncio_compat.py | PROCESSED | No issues found (confirmed clean).
2026-01-08 00:00:00 | src/benchmarking/utils/error_handling.py | PROCESSED | Fixed E0402 (relative import beyond top-level) by converting to absolute import.
