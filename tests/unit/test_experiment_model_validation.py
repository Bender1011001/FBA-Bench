from datetime import datetime

import pytest
from pydantic import ValidationError

from fba_bench_api.models.experiment import ExperimentORM
from fba_bench_api.models.experiments import (
    BenchmarkConfigRequest,
    ConfigTemplateSave,
    ExperimentCreateRequest,
    ExperimentParticipant,
    ExperimentResultsResponse,
    ExperimentRun,
    ExperimentRunCreate,
    ExperimentRunResponse,
    ExperimentStatusResponse,
    RunProgress,
    RunStatus,
    RunStatusType,
)


def test_experiment_model_validation():
    """Test Experiment model validation."""
    # Valid experiment
    experiment = ExperimentORM(
        id="test-id",
        name="Test Experiment",
        description="Test description",
        agent_id="agent-1",
        scenario_id="scenario-1",
        params={"key": "value"},
        status="draft",
    )
    assert experiment.name == "Test Experiment"
    assert experiment.status == "draft"


def test_config_template_save():
    """Test ConfigTemplateSave model."""
    template = ConfigTemplateSave(
        config_id="config-1",
        template_name="Test Config",
        description="Test description",
    )
    assert template.config_id == "config-1"
    assert template.template_name == "Test Config"

    # Invalid extra field
    with pytest.raises(ValidationError):
        ConfigTemplateSave(
            config_id="config-2",
            template_name="Invalid",
            description="Invalid",
            config_yaml="key: value",
        )


def test_benchmark_config_request():
    """Test BenchmarkConfigRequest model."""
    request = BenchmarkConfigRequest(
        simulationSettings={"scenario_id": "scenario-1"},
        agentConfigs=[{"agent_id": "agent-1"}],
        llmSettings={"provider": "openrouter"},
        constraints={"budget": 10},
        experimentSettings={"iterations": 10},
    )
    assert request.simulationSettings["scenario_id"] == "scenario-1"
    assert request.agentConfigs[0]["agent_id"] == "agent-1"

    # Invalid missing required settings
    with pytest.raises(ValidationError):
        BenchmarkConfigRequest(
            simulationSettings={},
            agentConfigs=[],
            llmSettings={},
            constraints={},
        )


def test_experiment_create_request():
    """Test ExperimentCreateRequest model."""
    request = ExperimentCreateRequest(
        experiment_name="New Experiment",
        description="Description",
        base_parameters={"scenario_id": "scenario-1"},
        parameter_sweep={"seed": [1, 2, 3]},
    )
    assert request.experiment_name == "New Experiment"
    assert request.parallel_workers == 1  # Default

    # Invalid parallel worker count
    with pytest.raises(ValidationError):
        ExperimentCreateRequest(
            experiment_name="Invalid",
            description="Invalid",
            base_parameters={"scenario_id": "scenario-1"},
            parameter_sweep={"seed": [1]},
            parallel_workers=0,
        )


def test_experiment_status_response():
    """Test ExperimentStatusResponse model."""
    response = ExperimentStatusResponse(
        experiment_id="exp-1",
        status="running",
        total_runs=10,
        completed_runs=5,
        successful_runs=4,
        failed_runs=1,
        progress_percentage=50.0,
        start_time=datetime.now(),
    )
    assert response.experiment_id == "exp-1"
    assert response.status == "running"


def test_experiment_results_response():
    """Test ExperimentResultsResponse model."""
    response = ExperimentResultsResponse(
        experiment_id="exp-1",
        status="completed",
        results_summary={"profit": 1000.0},
        individual_run_results=[{"run_id": "run-1"}],
    )
    assert response.results_summary["profit"] == 1000.0
    assert response.individual_run_results[0]["run_id"] == "run-1"


def test_experiment_participant():
    """Test ExperimentParticipant model."""
    participant = ExperimentParticipant(
        agent_id="agent-1",
        role="competitor",
    )
    assert participant.agent_id == "agent-1"
    assert participant.role == "competitor"

    with pytest.raises(ValueError):
        ExperimentParticipant(agent_id="agent-1", role="")


def test_experiment_run_create():
    """Test ExperimentRunCreate model."""
    run_create = ExperimentRunCreate(
        scenario_id="scenario-1",
        participants=[ExperimentParticipant(agent_id="agent-1", role="primary")],
        params={"seed": 42},
    )
    assert run_create.scenario_id == "scenario-1"


def test_experiment_run():
    """Test ExperimentRun model."""
    run = ExperimentRun(
        id="run-1",
        experiment_id="exp-1",
        scenario_id="scenario-1",
        participants=[ExperimentParticipant(agent_id="agent-1", role="primary")],
        status="running",
        started_at=datetime.now(),
        params={"seed": 42},
    )
    assert run.id == "run-1"
    assert run.status == "running"


def test_run_status():
    """Test RunStatus model."""
    status = RunStatus(
        experiment_id="exp-1",
        run_id="run-1",
        status="completed",
        started_at=None,
        updated_at=datetime.now(),
        metrics={"score": 95.0},
    )
    assert status.status == "completed"
    assert status.metrics["score"] == 95.0


def test_run_progress():
    """Test RunProgress model."""
    progress = RunProgress(
        experiment_id="exp-1",
        run_id="run-1",
        current_tick=5,
        total_ticks=10,
        progress_percent=50.0,
        elapsed_time_seconds=12.5,
        current_metrics={"accuracy": 0.9},
    )
    assert progress.current_tick == 5
    assert progress.total_ticks == 10


def test_experiment_run_response():
    """Test ExperimentRunResponse model."""
    response = ExperimentRunResponse(
        run_id="run-1",
        experiment_id="exp-1",
        status="completed",
        message="Run completed",
        created_at=datetime.now(),
        participants_count=1,
    )
    assert response.run_id == "run-1"
    assert response.status == "completed"
