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

    # Invalid name
    with pytest.raises(ValueError):
        ExperimentORM(
            id="test-id",
            name="",  # Empty name
            agent_id="agent-1",
            scenario_id="scenario-1",
            params={},
            status="draft",
        )

    # Invalid status
    with pytest.raises(ValueError):
        ExperimentORM(
            id="test-id",
            name="Test",
            agent_id="agent-1",
            scenario_id="scenario-1",
            params={},
            status="invalid_status",
        )


def test_config_template_save():
    """Test ConfigTemplateSave model."""
    template = ConfigTemplateSave(
        config_id="config-1",
        name="Test Config",
        description="Test description",
        config_yaml="key: value",
    )
    assert template.config_id == "config-1"
    assert template.name == "Test Config"

    # Invalid empty name
    with pytest.raises(ValidationError):
        ConfigTemplateSave(
            config_id="config-2",
            name="",
            description="Invalid",
            config_yaml="key: value",
        )


def test_benchmark_config_request():
    """Test BenchmarkConfigRequest model."""
    request = BenchmarkConfigRequest(
        scenario_id="scenario-1",
        agent_id="agent-1",
        params={"iterations": 10},
    )
    assert request.scenario_id == "scenario-1"
    assert request.agent_id == "agent-1"

    # Invalid missing scenario_id
    with pytest.raises(ValidationError):
        BenchmarkConfigRequest(
            agent_id="agent-1",
            params={},
        )


def test_experiment_create_request():
    """Test ExperimentCreateRequest model."""
    request = ExperimentCreateRequest(
        name="New Experiment",
        description="Description",
        agent_id="agent-1",
        scenario_id="scenario-1",
        params={"key": "value"},
    )
    assert request.name == "New Experiment"
    assert request.status == "draft"  # Default

    # Invalid empty name
    with pytest.raises(ValidationError):
        ExperimentCreateRequest(
            name="",
            description="Invalid",
            agent_id="agent-1",
            scenario_id="scenario-1",
            params={},
        )


def test_experiment_status_response():
    """Test ExperimentStatusResponse model."""
    response = ExperimentStatusResponse(
        id="exp-1",
        name="Test Exp",
        status="running",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert response.id == "exp-1"
    assert response.status == "running"


def test_experiment_results_response():
    """Test ExperimentResultsResponse model."""
    response = ExperimentResultsResponse(
        id="exp-1",
        metrics={"profit": 1000.0},
        artifacts=["report.pdf"],
        completed_at=datetime.now(),
    )
    assert response.metrics["profit"] == 1000.0
    assert "report.pdf" in response.artifacts


def test_experiment_participant():
    """Test ExperimentParticipant model."""
    participant = ExperimentParticipant(
        agent_id="agent-1",
        role="competitor",
        performance_score=85.5,
    )
    assert participant.agent_id == "agent-1"
    assert participant.role == "competitor"


def test_experiment_run_create():
    """Test ExperimentRunCreate model."""
    run_create = ExperimentRunCreate(
        experiment_id="exp-1",
        params={"seed": 42},
    )
    assert run_create.experiment_id == "exp-1"


def test_experiment_run():
    """Test ExperimentRun model."""
    run = ExperimentRun(
        id="run-1",
        experiment_id="exp-1",
        status=RunStatusType.running,
        started_at=datetime.now(),
        params={"seed": 42},
    )
    assert run.id == "run-1"
    assert run.status == RunStatusType.running


def test_run_status():
    """Test RunStatus model."""
    status = RunStatus(
        run_id="run-1",
        status=RunStatusType.completed,
        message="Success",
        timestamp=datetime.now(),
    )
    assert status.status == RunStatusType.completed
    assert status.message == "Success"


def test_run_progress():
    """Test RunProgress model."""
    progress = RunProgress(
        run_id="run-1",
        current_step=5,
        total_steps=10,
        metrics={"accuracy": 0.9},
    )
    assert progress.current_step == 5
    assert progress.total_steps == 10


def test_experiment_run_response():
    """Test ExperimentRunResponse model."""
    response = ExperimentRunResponse(
        id="run-1",
        experiment_id="exp-1",
        status=RunStatusType.completed,
        results={"score": 95.0},
        logs="Run logs",
    )
    assert response.id == "run-1"
    assert response.status == RunStatusType.completed
    assert response.results["score"] == 95.0
