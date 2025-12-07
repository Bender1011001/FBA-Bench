from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.fba_bench_api.server.app_factory import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestMedusaEndpoints:
    @pytest.fixture
    def mock_subprocess(self):
        mock_popen = Mock()
        mock_popen.poll.return_value = None
        mock_popen.pid = 1234
        return mock_popen

    @pytest.fixture
    def mock_file_exists(self):
        with patch("pathlib.Path.exists") as mock:
            mock.return_value = True
            yield mock

    @pytest.fixture
    def mock_file_read(self):
        with patch("pathlib.Path.read_text") as mock:
            mock.return_value = "Mocked log content"
            yield mock

    def test_start_medusa_trainer_success(self, client, mock_subprocess):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_subprocess
            response = client.post("/api/v1/medusa/start")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["message"] == "Medusa trainer started with PID: 1234"

    def test_start_medusa_trainer_already_running(self, client):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock(poll=lambda: None)
            response = client.post("/api/v1/medusa/start")
        assert response.status_code == 409
        assert response.json()["detail"] == "Medusa trainer is already running."

    def test_stop_medusa_trainer_success(self, client):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock(poll=lambda: None)
            mock_popen.terminate = Mock()
            mock_popen.kill = Mock()
            response = client.post("/api/v1/medusa/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"
        assert "stopped" in data["message"]

    def test_stop_medusa_trainer_not_running(self, client):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock(poll=lambda: 0)
            response = client.post("/api/v1/medusa/stop")
        assert response.status_code == 404
        assert response.json()["detail"] == "Medusa trainer is not running."

    def test_get_medusa_status_running(self, client):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock(poll=lambda: None)
            response = client.get("/api/v1/medusa/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["pid"] == 1234

    def test_get_medusa_status_stopped(self, client):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = Mock(poll=lambda: 0)
            response = client.get("/api/v1/medusa/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"
        assert data["pid"] is None

    def test_get_medusa_logs_success(self, client, mock_file_exists, mock_file_read):
        response = client.get("/api/v1/medusa/logs")
        assert response.status_code == 200
        assert response.text == "Mocked log content"

    def test_get_medusa_logs_not_found(self, client, mock_file_exists):
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            response = client.get("/api/v1/medusa/logs")
        assert response.status_code == 200
        assert response.text == "Log file not found. The trainer may not have run yet."

    def test_get_medusa_analysis_success(self, client):
        with patch(
            "medusa_experiments.medusa_analyzer.MedusaAnalyzer"
        ) as mock_analyzer:
            mock_instance = Mock()
            mock_instance.analyze_medusa_run.return_value = {"mock": "analysis"}
            mock_analyzer.return_value = mock_instance
            response = client.get("/api/v1/medusa/analysis")
        assert response.status_code == 200
        data = response.json()
        assert data == {"mock": "analysis"}

    def test_get_medusa_analysis_failure(self, client):
        with patch(
            "medusa_experiments.medusa_analyzer.MedusaAnalyzer"
        ) as mock_analyzer:
            mock_instance = Mock()
            mock_instance.analyze_medusa_run.side_effect = Exception("Analysis failed")
            mock_analyzer.return_value = mock_instance
            response = client.get("/api/v1/medusa/analysis")
        assert response.status_code == 500
        assert "Failed to generate Medusa analysis report" in response.json()["detail"]
