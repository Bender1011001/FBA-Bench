"""
Unit tests for the core benchmarking engine.

This module contains comprehensive unit tests for the BenchmarkEngine class
and related components in the benchmarking framework, following pytest conventions
with parameterized tests and fixtures.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from benchmarking.config.manager import ConfigurationManager
from benchmarking.core.engine import (
    BenchmarkEngine,
    BenchmarkError,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkStatus,
)
from benchmarking.integration.manager import IntegrationManager


@pytest.fixture
def config_manager():
    """Create a mock configuration manager."""
    mock = Mock(spec=ConfigurationManager)
    # Add missing attributes that tests expect
    mock.initialize = Mock(return_value=None)
    mock.get_output_path = Mock(return_value="/tmp")
    return mock


@pytest.fixture
def integration_manager():
    """Create a mock integration manager."""
    mock = Mock(spec=IntegrationManager)
    # Add missing attributes that tests expect
    mock.initialize = Mock(return_value=None)
    return mock


@pytest.fixture
def engine(config_manager, integration_manager):
    """Create a BenchmarkEngine instance with mocked dependencies."""
    return BenchmarkEngine(config_manager, integration_manager)


@pytest.fixture
def test_config():
    """Create a test benchmark configuration."""
    return {
        "benchmark_id": "test_benchmark",
        "name": "Test Benchmark",
        "description": "A test benchmark configuration",
        "version": "1.0.0",
        "environment": {
            "deterministic": True,
            "random_seed": 42,
            "parallel_execution": False,
            "max_workers": 1,
        },
        "scenarios": [
            {
                "id": "test_scenario",
                "name": "Test Scenario",
                "type": "test",
                "enabled": True,
                "priority": 1,
                "config": {"duration": 100, "complexity": "medium"},
            }
        ],
        "agents": [
            {
                "id": "test_agent",
                "name": "Test Agent",
                "framework": "test",
                "enabled": True,
                "config": {"model": "test_model", "temperature": 0.5},
            }
        ],
        "metrics": {"categories": ["cognitive", "business"], "custom_metrics": []},
        "execution": {
            "runs_per_scenario": 2,
            "max_duration": 0,
            "timeout": 300,
            "retry_on_failure": True,
            "max_retries": 3,
        },
        "output": {
            "format": "json",
            "path": "./test_results",
            "include_detailed_logs": False,
            "include_audit_trail": True,
        },
        "validation": {
            "enabled": True,
            "statistical_significance": True,
            "confidence_level": 0.95,
            "reproducibility_check": True,
        },
        "metadata": {
            "author": "Test Author",
            "created": "2025-01-01T00:00:00Z",
            "tags": ["test"],
        },
    }


class TestBenchmarkEngine:
    """Test cases for BenchmarkEngine class."""

    def test_init(self, engine, config_manager, integration_manager):
        """Test BenchmarkEngine initialization."""
        assert isinstance(engine, BenchmarkEngine)
        assert engine.config_manager == config_manager
        assert engine.integration_manager == integration_manager
        assert len(engine.active_runs) == 0
        assert len(engine.completed_runs) == 0

    @pytest.mark.parametrize(
        "is_valid,expected_errors", [(True, []), (False, ["Invalid configuration"])]
    )
    def test_validate_configuration(
        self, engine, config_manager, test_config, is_valid, expected_errors
    ):
        """Test configuration validation with different scenarios."""
        # Mock config manager validation
        config_manager.validate_config.return_value = (is_valid, expected_errors)

        result_is_valid, errors = engine._validate_configuration(test_config)

        assert result_is_valid == is_valid
        assert errors == expected_errors
        config_manager.validate_config.assert_called_once_with(test_config)

    @pytest.mark.parametrize(
        "missing_field", ["benchmark_id", "name", "scenarios", "agents", "metrics"]
    )
    def test_validate_configuration_missing_required_fields(
        self, engine, test_config, missing_field
    ):
        """Test configuration validation with missing required fields."""
        invalid_config = test_config.copy()
        del invalid_config[missing_field]

        is_valid, errors = engine._validate_configuration(invalid_config)

        assert not is_valid
        assert any(missing_field in error for error in errors)

    def test_create_benchmark_run(self, engine, test_config):
        """Test creating a benchmark run."""
        run = engine._create_benchmark_run(test_config)

        assert isinstance(run, BenchmarkRun)
        assert run.benchmark_id == "test_benchmark"
        assert run.status == BenchmarkStatus.CREATED
        assert run.config == test_config
        assert run.start_time is not None
        assert run.end_time is None

    @pytest.mark.asyncio
    async def test_run_benchmark_success(
        self, engine, config_manager, integration_manager, test_config
    ):
        """Test successful benchmark execution."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])
        integration_manager.initialize.return_value = None

        # Mock scenario execution
        with patch.object(engine, "_execute_scenario") as mock_execute:
            mock_execute.return_value = {
                "scenario_id": "test_scenario",
                "status": "completed",
                "metrics": {"score": 0.85},
                "execution_time": 10.0,
            }

            # Run benchmark
            result = await engine.run_benchmark(test_config)

            # Verify result
            assert isinstance(result, BenchmarkResult)
            assert result.benchmark_id == "test_benchmark"
            assert result.status == BenchmarkStatus.COMPLETED
            assert result.overall_score > 0.0
            assert result.start_time is not None
            assert result.end_time is not None

    @pytest.mark.asyncio
    async def test_run_benchmark_invalid_config(
        self, engine, config_manager, test_config
    ):
        """Test benchmark execution with invalid configuration."""
        # Mock config manager validation with errors
        config_manager.validate_config.return_value = (False, ["Invalid config"])

        # Run benchmark and expect error
        with pytest.raises(BenchmarkError):
            await engine.run_benchmark(test_config)

    @pytest.mark.asyncio
    async def test_run_benchmark_already_running(self, engine, test_config):
        """Test benchmark execution when already running."""
        # Create an active run
        run = engine._create_benchmark_run(test_config)
        run.status = BenchmarkStatus.RUNNING
        engine.active_runs["test_benchmark"] = run

        # Run benchmark and expect error
        with pytest.raises(BenchmarkError):
            await engine.run_benchmark(test_config)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario_status,expected_status",
        [("completed", "completed"), ("failed", "failed"), ("timeout", "timeout")],
    )
    async def test_execute_scenario_with_different_statuses(
        self, engine, test_config, scenario_status, expected_status
    ):
        """Test scenario execution with different status outcomes."""
        scenario_config = test_config["scenarios"][0]
        agent_config = test_config["agents"][0]

        # Mock scenario and agent execution
        with (
            patch.object(engine, "_load_scenario") as mock_load_scenario,
            patch.object(engine, "_load_agent") as mock_load_agent,
        ):
            mock_scenario = Mock()
            mock_agent = Mock()

            if scenario_status == "completed":
                mock_scenario.run.return_value = {
                    "status": "completed",
                    "metrics": {"score": 0.9},
                    "events": [],
                    "execution_time": 5.0,
                }
            elif scenario_status == "failed":
                mock_scenario.run.side_effect = Exception("Scenario failed")
            elif scenario_status == "timeout":
                mock_scenario.run.side_effect = asyncio.TimeoutError("Scenario timeout")

            mock_load_scenario.return_value = mock_scenario
            mock_load_agent.return_value = mock_agent

            # Execute scenario
            result = await engine._execute_scenario(
                scenario_config, agent_config, test_config, 1
            )

            # Verify result
            assert result["scenario_id"] == "test_scenario"
            assert result["status"] == expected_status

    @pytest.mark.asyncio
    async def test_collect_metrics(self, engine):
        """Test metrics collection."""
        # Mock metrics collection
        with (
            patch.object(engine, "_calculate_cognitive_metrics") as mock_cognitive,
            patch.object(engine, "_calculate_business_metrics") as mock_business,
            patch.object(engine, "_calculate_technical_metrics") as mock_technical,
        ):
            mock_cognitive.return_value = {"reasoning": 0.8, "planning": 0.9}
            mock_business.return_value = {"roi": 0.85, "efficiency": 0.75}
            mock_technical.return_value = {"performance": 0.9, "reliability": 0.95}

            # Collect metrics
            metrics = await engine._collect_metrics(
                {"events": []}, {"agent_data": {}}, {"scenario_data": {}}
            )

            # Verify metrics
            assert "cognitive" in metrics
            assert "business" in metrics
            assert "technical" in metrics
            assert metrics["cognitive"]["reasoning"] == 0.8
            assert metrics["business"]["roi"] == 0.85
            assert metrics["technical"]["performance"] == 0.9

    @pytest.mark.parametrize(
        "run_results,expected_score,expected_time,expected_rate",
        [
            (
                [
                    {
                        "scenario_id": "test_scenario",
                        "agent_id": "test_agent",
                        "run_number": 1,
                        "metrics": {"score": 0.85},
                        "execution_time": 10.0,
                        "status": "completed",
                    },
                    {
                        "scenario_id": "test_scenario",
                        "agent_id": "test_agent",
                        "run_number": 2,
                        "metrics": {"score": 0.9},
                        "execution_time": 12.0,
                        "status": "completed",
                    },
                ],
                0.875,  # Average of 0.85 and 0.9
                11.0,  # Average of 10.0 and 12.0
                1.0,  # Both runs successful
            ),
            (
                [
                    {
                        "scenario_id": "test_scenario",
                        "agent_id": "test_agent",
                        "run_number": 1,
                        "metrics": {"score": 0.85},
                        "execution_time": 10.0,
                        "status": "completed",
                    },
                    {
                        "scenario_id": "test_scenario",
                        "agent_id": "test_agent",
                        "run_number": 2,
                        "metrics": {"score": 0.0},
                        "execution_time": 5.0,
                        "status": "failed",
                    },
                ],
                0.425,  # Average of 0.85 and 0.0
                7.5,  # Average of 10.0 and 5.0
                0.5,  # One run successful
            ),
        ],
    )
    def test_aggregate_results(
        self, engine, run_results, expected_score, expected_time, expected_rate
    ):
        """Test result aggregation with different scenarios."""
        # Aggregate results
        aggregated = engine._aggregate_results(run_results)

        # Verify aggregation
        assert "overall_score" in aggregated
        assert "average_execution_time" in aggregated
        assert "success_rate" in aggregated
        assert aggregated["overall_score"] == expected_score
        assert aggregated["average_execution_time"] == expected_time
        assert aggregated["success_rate"] == expected_rate

    def test_get_benchmark_status(self, engine, test_config):
        """Test getting benchmark status."""
        # Create a test run
        run = engine._create_benchmark_run(test_config)
        run.status = BenchmarkStatus.RUNNING
        engine.active_runs["test_benchmark"] = run

        # Get status
        status = engine.get_benchmark_status("test_benchmark")

        # Verify status
        assert status["benchmark_id"] == "test_benchmark"
        assert status["status"] == BenchmarkStatus.RUNNING
        assert status["start_time"] is not None

    def test_get_benchmark_status_not_found(self, engine):
        """Test getting benchmark status for non-existent benchmark."""
        status = engine.get_benchmark_status("non_existent")

        # Verify status
        assert status["benchmark_id"] == "non_existent"
        assert status["status"] == BenchmarkStatus.NOT_FOUND

    def test_list_benchmarks(self, engine, test_config):
        """Test listing benchmarks."""
        # Create test runs
        run1 = engine._create_benchmark_run(test_config)
        run1.status = BenchmarkStatus.COMPLETED
        engine.completed_runs.append(run1)

        run2 = engine._create_benchmark_run(test_config.copy())
        run2.benchmark_id = "test_benchmark_2"
        run2.status = BenchmarkStatus.RUNNING
        engine.active_runs["test_benchmark_2"] = run2

        # List benchmarks
        benchmarks = engine.list_benchmarks()

        # Verify list
        assert len(benchmarks) == 2
        assert any(b["benchmark_id"] == "test_benchmark" for b in benchmarks)
        assert any(b["benchmark_id"] == "test_benchmark_2" for b in benchmarks)

    def test_stop_benchmark(self, engine, test_config):
        """Test stopping a benchmark."""
        # Create a test run
        run = engine._create_benchmark_run(test_config)
        run.status = BenchmarkStatus.RUNNING
        engine.active_runs["test_benchmark"] = run

        # Stop benchmark
        result = engine.stop_benchmark("test_benchmark")

        # Verify stop
        assert result is True
        assert run.status == BenchmarkStatus.STOPPED
        assert run.end_time is not None

    def test_stop_benchmark_not_found(self, engine):
        """Test stopping a non-existent benchmark."""
        result = engine.stop_benchmark("non_existent")

        # Verify stop
        assert result is False

    @pytest.mark.parametrize(
        "max_age_days,expected_count",
        [
            (30, 1),
            (3650, 2),
        ],  # Only recent run should remain  # Both runs should remain (10 years)
    )
    def test_cleanup_completed_runs(
        self, engine, test_config, max_age_days, expected_count
    ):
        """Test cleanup of completed runs with different age thresholds."""
        # Create old completed run
        old_run = engine._create_benchmark_run(test_config)
        old_run.status = BenchmarkStatus.COMPLETED
        old_run.start_time = datetime.now().replace(year=2020)  # Old run
        engine.completed_runs.append(old_run)

        # Create recent completed run
        recent_run = engine._create_benchmark_run(test_config.copy())
        recent_run.benchmark_id = "recent_benchmark"
        recent_run.status = BenchmarkStatus.COMPLETED
        recent_run.start_time = datetime.now()
        engine.completed_runs.append(recent_run)

        # Cleanup runs older than max_age_days
        engine.cleanup_completed_runs(max_age_days=max_age_days)

        # Verify cleanup
        assert len(engine.completed_runs) == expected_count
        if expected_count == 1:
            assert engine.completed_runs[0].benchmark_id == "recent_benchmark"

    @pytest.mark.asyncio
    async def test_run_benchmark_with_timeout(
        self, engine, config_manager, test_config
    ):
        """Test benchmark execution with timeout."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])

        # Create a config with short timeout
        timeout_config = test_config.copy()
        timeout_config["execution"]["timeout"] = 0.1  # Very short timeout

        # Mock scenario execution that takes longer than timeout
        with patch.object(engine, "_execute_scenario") as mock_execute:

            async def slow_scenario(*args, **kwargs):
                await asyncio.sleep(0.2)  # Sleep longer than timeout
                return {
                    "scenario_id": "test_scenario",
                    "status": "completed",
                    "metrics": {"score": 0.85},
                    "execution_time": 10.0,
                }

            mock_execute.side_effect = slow_scenario

            # Run benchmark and expect timeout
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    engine.run_benchmark(timeout_config), timeout=0.5
                )


class TestBenchmarkResult:
    """Test cases for BenchmarkResult class."""

    @pytest.fixture
    def result(self):
        """Create a test BenchmarkResult."""
        return BenchmarkResult(
            benchmark_id="test_benchmark",
            status=BenchmarkStatus.COMPLETED,
            overall_score=0.85,
            start_time=datetime.now(),
            end_time=datetime.now(),
            config={"test": "config"},
            results={"scenario_results": []},
            metadata={"test": "metadata"},
        )

    def test_init(self, result):
        """Test BenchmarkResult initialization."""
        assert result.benchmark_id == "test_benchmark"
        assert result.status == BenchmarkStatus.COMPLETED
        assert result.overall_score == 0.85
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.config == {"test": "config"}
        assert result.results == {"scenario_results": []}
        assert result.metadata == {"test": "metadata"}

    def test_to_dict(self, result):
        """Test BenchmarkResult to_dict conversion."""
        result_dict = result.to_dict()

        assert result_dict["benchmark_id"] == "test_benchmark"
        assert result_dict["status"] == BenchmarkStatus.COMPLETED.value
        assert result_dict["overall_score"] == 0.85
        assert "start_time" in result_dict
        assert "end_time" in result_dict
        assert result_dict["config"] == {"test": "config"}
        assert result_dict["results"] == {"scenario_results": []}
        assert result_dict["metadata"] == {"test": "metadata"}

    @pytest.mark.parametrize(
        "status",
        [
            BenchmarkStatus.CREATED,
            BenchmarkStatus.RUNNING,
            BenchmarkStatus.COMPLETED,
            BenchmarkStatus.FAILED,
            BenchmarkStatus.STOPPED,
            BenchmarkStatus.TIMEOUT,
        ],
    )
    def test_different_statuses(self, status):
        """Test BenchmarkResult with different statuses."""
        result = BenchmarkResult(
            benchmark_id="test_benchmark",
            status=status,
            overall_score=0.85,
            start_time=datetime.now(),
            end_time=datetime.now(),
            config={},
            results={},
            metadata={},
        )

        assert result.status == status
        result_dict = result.to_dict()
        assert result_dict["status"] == status.value


class TestBenchmarkRun:
    """Test cases for BenchmarkRun class."""

    @pytest.fixture
    def run(self):
        """Create a test BenchmarkRun."""
        return BenchmarkRun(benchmark_id="test_benchmark", config={"test": "config"})

    def test_init(self, run):
        """Test BenchmarkRun initialization."""
        assert run.benchmark_id == "test_benchmark"
        assert run.config == {"test": "config"}
        assert run.status == BenchmarkStatus.CREATED
        assert run.start_time is not None
        assert run.end_time is None
        assert len(run.run_results) == 0

    def test_add_run_result(self, run):
        """Test adding run result."""
        result = {"test": "result"}
        run.add_run_result(result)

        assert len(run.run_results) == 1
        assert run.run_results[0] == result

    def test_to_dict(self, run):
        """Test BenchmarkRun to_dict conversion."""
        run_dict = run.to_dict()

        assert run_dict["benchmark_id"] == "test_benchmark"
        assert run_dict["status"] == BenchmarkStatus.CREATED.value
        assert "start_time" in run_dict
        assert run_dict["config"] == {"test": "config"}
        assert run_dict["run_results"] == []

    @pytest.mark.parametrize(
        "status",
        [
            BenchmarkStatus.CREATED,
            BenchmarkStatus.RUNNING,
            BenchmarkStatus.COMPLETED,
            BenchmarkStatus.FAILED,
            BenchmarkStatus.STOPPED,
            BenchmarkStatus.TIMEOUT,
        ],
    )
    def test_different_statuses(self, status):
        """Test BenchmarkRun with different statuses."""
        run = BenchmarkRun(benchmark_id="test_benchmark", config={})
        run.status = status

        assert run.status == status
        run_dict = run.to_dict()
        assert run_dict["status"] == status.value


class TestBenchmarkEngineExtended:
    """Extended test cases for BenchmarkEngine class."""

    @pytest.mark.asyncio
    async def test_initialize(self, engine, config_manager, integration_manager):
        """Test BenchmarkEngine initialization."""
        # Mock dependencies
        config_manager.initialize.return_value = None
        integration_manager.initialize.return_value = None

        # Initialize engine
        await engine.initialize()

        # Verify initialization
        assert engine._initialized is True
        config_manager.initialize.assert_called_once()
        integration_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, engine):
        """Test BenchmarkEngine initialization when already initialized."""
        engine._initialized = True

        # Initialize engine
        await engine.initialize()

        # Should not raise exception
        assert engine._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_exception(self, engine, config_manager):
        """Test BenchmarkEngine initialization with exception."""
        config_manager.initialize.side_effect = Exception(
            "Config initialization failed"
        )

        # Initialize engine and expect exception
        with pytest.raises(
            BenchmarkError, match="Failed to initialize benchmark engine"
        ):
            await engine.initialize()

        assert engine._initialized is False

    @pytest.mark.asyncio
    async def test_run_benchmark_not_initialized(self, engine, test_config):
        """Test benchmark execution when engine not initialized."""
        engine._initialized = False

        # Run benchmark and expect error
        with pytest.raises(BenchmarkError, match="Benchmark engine not initialized"):
            await engine.run_benchmark(test_config)

    @pytest.mark.asyncio
    async def test_run_benchmark_with_retry(self, engine, config_manager, test_config):
        """Test benchmark execution with retry on failure."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])

        # Mock scenario execution that fails first time then succeeds
        with patch.object(engine, "_execute_scenario") as mock_execute:
            mock_execute.side_effect = [
                Exception("First failure"),
                {
                    "scenario_id": "test_scenario",
                    "status": "completed",
                    "metrics": {"score": 0.85},
                    "execution_time": 10.0,
                },
            ]

            # Run benchmark
            result = await engine.run_benchmark(test_config)

            # Verify result
            assert isinstance(result, BenchmarkResult)
            assert result.benchmark_id == "test_benchmark"
            assert result.status == BenchmarkStatus.COMPLETED

            # Verify retry
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_run_benchmark_max_retries_exceeded(
        self, engine, config_manager, test_config
    ):
        """Test benchmark execution when max retries exceeded."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])

        # Mock scenario execution that always fails
        with patch.object(engine, "_execute_scenario") as mock_execute:
            mock_execute.side_effect = Exception("Always fails")

            # Run benchmark and expect failure
            result = await engine.run_benchmark(test_config)

            # Verify result
            assert isinstance(result, BenchmarkResult)
            assert result.benchmark_id == "test_benchmark"
            assert result.status == BenchmarkStatus.FAILED

            # Verify max retries
            assert mock_execute.call_count == 4  # Initial + 3 retries

    @pytest.mark.asyncio
    async def test_run_benchmark_with_retry_disabled(
        self, engine, config_manager, test_config
    ):
        """Test benchmark execution with retry disabled."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])

        # Create config with retry disabled
        no_retry_config = test_config.copy()
        no_retry_config["execution"]["retry_on_failure"] = False

        # Mock scenario execution that fails
        with patch.object(engine, "_execute_scenario") as mock_execute:
            mock_execute.side_effect = Exception("Failure")

            # Run benchmark and expect failure
            result = await engine.run_benchmark(no_retry_config)

            # Verify result
            assert isinstance(result, BenchmarkResult)
            assert result.benchmark_id == "test_benchmark"
            assert result.status == BenchmarkStatus.FAILED

            # Verify no retry
            assert mock_execute.call_count == 1

    @pytest.mark.asyncio
    async def test_run_benchmark_with_max_duration(
        self, engine, config_manager, test_config
    ):
        """Test benchmark execution with max duration."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])

        # Create config with max duration
        duration_config = test_config.copy()
        duration_config["execution"]["max_duration"] = 0.1  # Very short duration

        # Mock scenario execution that takes longer than max duration
        with patch.object(engine, "_execute_scenario") as mock_execute:

            async def slow_scenario(*args, **kwargs):
                await asyncio.sleep(0.2)  # Sleep longer than max duration
                return {
                    "scenario_id": "test_scenario",
                    "status": "completed",
                    "metrics": {"score": 0.85},
                    "execution_time": 10.0,
                }

            mock_execute.side_effect = slow_scenario

            # Run benchmark and expect timeout
            result = await engine.run_benchmark(duration_config)

            # Verify result
            assert isinstance(result, BenchmarkResult)
            assert result.benchmark_id == "test_benchmark"
            assert result.status == BenchmarkStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_run_benchmark_parallel_execution(
        self, engine, config_manager, test_config
    ):
        """Test benchmark execution with parallel execution enabled."""
        # Mock dependencies
        config_manager.validate_config.return_value = (True, [])

        # Create config with parallel execution
        parallel_config = test_config.copy()
        parallel_config["environment"]["parallel_execution"] = True
        parallel_config["environment"]["max_workers"] = 2
        parallel_config["scenarios"] = [
            {
                "id": "scenario1",
                "name": "Scenario 1",
                "type": "test",
                "enabled": True,
                "priority": 1,
                "config": {"duration": 100},
            },
            {
                "id": "scenario2",
                "name": "Scenario 2",
                "type": "test",
                "enabled": True,
                "priority": 1,
                "config": {"duration": 100},
            },
        ]

        # Mock scenario execution
        with patch.object(engine, "_execute_scenario") as mock_execute:
            mock_execute.return_value = {
                "scenario_id": "test_scenario",
                "status": "completed",
                "metrics": {"score": 0.85},
                "execution_time": 10.0,
            }

            # Run benchmark
            result = await engine.run_benchmark(parallel_config)

            # Verify result
            assert isinstance(result, BenchmarkResult)
            assert result.benchmark_id == "test_benchmark"
            assert result.status == BenchmarkStatus.COMPLETED

            # Verify parallel execution
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_save_benchmark_results(self, engine, test_config):
        """Test saving benchmark results."""
        # Create a test result
        result = BenchmarkResult(
            benchmark_id="test_benchmark",
            status=BenchmarkStatus.COMPLETED,
            overall_score=0.85,
            start_time=datetime.now(),
            end_time=datetime.now(),
            config=test_config,
            results={"scenario_results": []},
            metadata={"test": "metadata"},
        )

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock config manager to return temp directory
            engine.config_manager.get_output_path.return_value = temp_dir

            # Save results
            await engine._save_benchmark_results(result)

            # Verify file was created
            result_file = Path(temp_dir) / "test_benchmark.json"
            assert result_file.exists()

            # Verify file content
            with open(result_file) as f:
                saved_data = json.load(f)

            assert saved_data["benchmark_id"] == "test_benchmark"
            assert saved_data["status"] == BenchmarkStatus.COMPLETED.value
            assert saved_data["overall_score"] == 0.85

    @pytest.mark.asyncio
    async def test_save_benchmark_results_with_error(self, engine, test_config):
        """Test saving benchmark results with error."""
        # Create a test result
        result = BenchmarkResult(
            benchmark_id="test_benchmark",
            status=BenchmarkStatus.COMPLETED,
            overall_score=0.85,
            start_time=datetime.now(),
            end_time=datetime.now(),
            config=test_config,
            results={"scenario_results": []},
            metadata={"test": "metadata"},
        )

        # Mock config manager to raise exception
        engine.config_manager.get_output_path.side_effect = Exception(
            "Failed to get output path"
        )

        # Save results and expect exception
        with pytest.raises(BenchmarkError, match="Failed to save benchmark results"):
            await engine._save_benchmark_results(result)

    @pytest.mark.asyncio
    async def test_load_scenario(self, engine, test_config):
        """Test loading a scenario."""
        scenario_config = test_config["scenarios"][0]

        # Mock scenario registry
        with patch("benchmarking.core.engine.scenario_registry") as mock_registry:
            mock_scenario = Mock()
            mock_registry.get_scenario.return_value = mock_scenario

            # Load scenario
            scenario = await engine._load_scenario(scenario_config)

            # Verify scenario
            assert scenario == mock_scenario
            mock_registry.get_scenario.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_load_scenario_not_found(self, engine, test_config):
        """Test loading a scenario that doesn't exist."""
        scenario_config = test_config["scenarios"][0]

        # Mock scenario registry
        with patch("benchmarking.core.engine.scenario_registry") as mock_registry:
            mock_registry.get_scenario.return_value = None

            # Load scenario and expect exception
            with pytest.raises(BenchmarkError, match="Scenario test not found"):
                await engine._load_scenario(scenario_config)

    @pytest.mark.asyncio
    async def test_load_agent(self, engine, test_config):
        """Test loading an agent."""
        agent_config = test_config["agents"][0]

        # Mock agent registry - patch the engine's import
        with patch("benchmarking.core.engine.agent_registry") as mock_registry:
            mock_agent = Mock()
            mock_registry.get_agent.return_value = mock_agent
            # Ensure the registry has the get_agent method
            mock_registry.get_agent = Mock(return_value=mock_agent)

            # Load agent
            agent = await engine._load_agent(agent_config)

            # Verify agent
            assert agent == mock_agent
            mock_registry.get_agent.assert_called_once_with("test")
            mock_registry.get_agent.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_load_agent_not_found(self, engine, test_config):
        """Test loading an agent that doesn't exist."""
        agent_config = test_config["agents"][0]

        # Mock agent registry
        with patch("benchmarking.core.engine.agent_registry") as mock_registry:
            mock_registry.get_agent.return_value = None

            # Load agent and expect exception
            with pytest.raises(BenchmarkError, match="Agent test not found"):
                await engine._load_agent(agent_config)

    @pytest.mark.asyncio
    async def test_calculate_cognitive_metrics(self, engine):
        """Test calculating cognitive metrics."""
        # Mock events and data
        events = [{"type": "DecisionMade", "data": {"quality": 0.9}}]
        agent_data = {"reasoning": {"accuracy": 0.8}}
        scenario_data = {"complexity": "medium"}

        # Mock metrics registry
        with patch("benchmarking.core.engine.metrics_registry") as mock_registry:
            mock_metric = Mock()
            mock_metric.calculate.return_value = {"score": 0.85}
            mock_registry.get_metrics_by_category.return_value = {
                "decision": mock_metric
            }

            # Calculate metrics
            metrics = await engine._calculate_cognitive_metrics(
                events, agent_data, scenario_data
            )

            # Verify metrics
            assert "decision" in metrics
            assert metrics["decision"]["score"] == 0.85
            mock_registry.get_metrics_by_category.assert_called_once_with("cognitive")

    @pytest.mark.asyncio
    async def test_calculate_business_metrics(self, engine):
        """Test calculating business metrics."""
        # Mock events and data
        events = [{"type": "TransactionCompleted", "data": {"value": 100}}]
        agent_data = {"efficiency": {"time_saved": 10}}
        scenario_data = {"domain": "finance"}

        # Mock metrics registry
        with patch("benchmarking.core.engine.metrics_registry") as mock_registry:
            mock_metric = Mock()
            mock_metric.calculate.return_value = {"roi": 0.15}
            mock_registry.get_metrics_by_category.return_value = {
                "financial": mock_metric
            }

            # Calculate metrics
            metrics = await engine._calculate_business_metrics(
                events, agent_data, scenario_data
            )

            # Verify metrics
            assert "financial" in metrics
            assert metrics["financial"]["roi"] == 0.15
            mock_registry.get_metrics_by_category.assert_called_once_with("business")

    @pytest.mark.asyncio
    async def test_calculate_technical_metrics(self, engine):
        """Test calculating technical metrics."""
        # Mock events and data
        events = [{"type": "ApiCall", "data": {"response_time": 100}}]
        agent_data = {"performance": {"memory_usage": 50}}
        scenario_data = {"environment": "test"}

        # Mock metrics registry
        with patch("benchmarking.core.engine.metrics_registry") as mock_registry:
            mock_metric = Mock()
            mock_metric.calculate.return_value = {"latency": 100}
            mock_registry.get_metrics_by_category.return_value = {
                "performance": mock_metric
            }

            # Calculate metrics
            metrics = await engine._calculate_technical_metrics(
                events, agent_data, scenario_data
            )

            # Verify metrics
            assert "performance" in metrics
            assert metrics["performance"]["latency"] == 100
            mock_registry.get_metrics_by_category.assert_called_once_with("technical")

    @pytest.mark.asyncio
    async def test_calculate_metrics_with_exception(self, engine):
        """Test calculating metrics with exception."""
        # Mock metrics registry to raise exception
        with patch("benchmarking.core.engine.metrics_registry") as mock_registry:
            mock_registry.get_metrics_by_category.side_effect = Exception(
                "Metrics calculation failed"
            )

            # Calculate metrics
            metrics = await engine._collect_metrics({}, {}, {})

            # Verify error handling
            assert "error" in metrics
            assert metrics["error"] == "Metrics calculation failed"

    def test_aggregate_results_empty(self, engine):
        """Test aggregating empty results."""
        aggregated = engine._aggregate_results([])

        # Verify aggregation
        assert aggregated["overall_score"] == 0.0
        assert aggregated["average_execution_time"] == 0.0
        assert aggregated["success_rate"] == 0.0

    def test_aggregate_results_with_none_scores(self, engine):
        """Test aggregating results with None scores."""
        run_results = [
            {
                "scenario_id": "test_scenario",
                "agent_id": "test_agent",
                "run_number": 1,
                "metrics": {"score": 0.85},
                "execution_time": 10.0,
                "status": "completed",
            },
            {
                "scenario_id": "test_scenario",
                "agent_id": "test_agent",
                "run_number": 2,
                "metrics": {"score": None},
                "execution_time": 12.0,
                "status": "completed",
            },
        ]

        aggregated = engine._aggregate_results(run_results)

        # Verify aggregation
        assert aggregated["overall_score"] == 0.425  # Only first score counted
        assert aggregated["average_execution_time"] == 11.0
        assert aggregated["success_rate"] == 1.0

    def test_aggregate_results_with_missing_metrics(self, engine):
        """Test aggregating results with missing metrics."""
        run_results = [
            {
                "scenario_id": "test_scenario",
                "agent_id": "test_agent",
                "run_number": 1,
                "metrics": {"score": 0.85},
                "execution_time": 10.0,
                "status": "completed",
            },
            {
                "scenario_id": "test_scenario",
                "agent_id": "test_agent",
                "run_number": 2,
                "execution_time": 12.0,
                "status": "completed",
                # Missing metrics
            },
        ]

        aggregated = engine._aggregate_results(run_results)

        # Verify aggregation
        assert aggregated["overall_score"] == 0.425  # Only first score counted
        assert aggregated["average_execution_time"] == 11.0
        assert aggregated["success_rate"] == 1.0
