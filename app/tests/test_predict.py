# ============================================================================
# ModelServe — Tests
# ============================================================================
# Integration tests for the inference service.
# ============================================================================

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# Mock the model and feature client before importing main
@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock MLflow model and Feast client for testing."""
    with patch('app.model_loader.ModelLoader.load') as mock_load, \
         patch('app.model_loader.ModelLoader.predict') as mock_predict, \
         patch('app.feature_client.FeatureClient.get_features') as mock_features:
        # Setup mocks
        mock_load.return_value = True

        mock_predict.return_value = {"prediction": 1, "probability": 0.85}

        mock_features.return_value = {
            "amt": 100.0,
            "category_enc": 1,
            "trans_hour": 14,
            "trans_dow": 2,
            "city_pop": 50000,
            "merch_lat": 40.7128,
            "merch_long": -74.0060,
        }

        yield {
            "load": mock_load,
            "predict": mock_predict,
            "features": mock_features,
        }


# Import after mocking
from app.main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
#  Health Endpoint Tests
# ─────────────────────────────────────────────────────────────

def test_health_returns_200():
    """Test /health returns 200 with status and model_version."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "model_version" in data
    assert data["status"] == "healthy"


def test_health_response_format():
    """Test /health response format."""
    response = client.get("/health")
    data = response.json()

    assert isinstance(data["status"], str)
    assert isinstance(data["model_version"], str)


# ─────────────────────────────────────────────────────────────
#  Predict Endpoint Tests
# ─────────────────────────────────────────────────────────────

def test_predict_returns_200():
    """Test /predict returns 200 with valid entity_id."""
    payload = {"entity_id": 1234567890123456}
    response = client.post("/predict", json=payload)
    assert response.status_code == 200


def test_predict_response_format():
    """Test /predict response format."""
    payload = {"entity_id": 1234567890123456}
    response = client.post("/predict", json=payload)
    data = response.json()

    # Check required fields
    assert "prediction" in data
    assert "probability" in data
    assert "model_version" in data
    assert "timestamp" in data

    # Check types
    assert isinstance(data["prediction"], int)
    assert isinstance(data["probability"], float)
    assert isinstance(data["model_version"], str)
    assert isinstance(data["timestamp"], str)


def test_predict_invalid_input():
    """Test /predict returns 422 for invalid input."""
    # Missing entity_id
    response = client.post("/predict", json={})
    assert response.status_code == 422

    # Invalid type
    response = client.post("/predict", json={"entity_id": "not_a_number"})
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
#  Predict GET Endpoint Tests
# ─────────────────────────────────────────────────────────────

def test_predict_get_returns_200():
    """Test GET /predict/{entity_id} returns 200."""
    response = client.get("/predict/1234567890123456")
    assert response.status_code == 200


def test_predict_get_with_explain():
    """Test GET /predict/{entity_id}?explain=true includes features."""
    response = client.get("/predict/1234567890123456?explain=true")
    assert response.status_code == 200

    data = response.json()
    assert "features" in data
    assert data["features"] is not None


def test_predict_get_without_explain():
    """Test GET /predict/{entity_id} without explain param."""
    response = client.get("/predict/1234567890123456")
    assert response.status_code == 200

    data = response.json()
    # features should be None when explain=false
    assert "features" in data


# ─────────────────────────────────────────────────────────────
#  Metrics Endpoint Tests
# ─────────────────────────────────────────────────────────────

def test_metrics_returns_200():
    """Test /metrics returns 200."""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_returns_prometheus_format():
    """Test /metrics returns Prometheus text format."""
    response = client.get("/metrics")
    content = response.text

    # Check for expected metrics
    assert "prediction_requests_total" in content
    assert "prediction_duration_seconds" in content
    assert "prediction_errors_total" in content


# ─────────────────────────────────────────────────────────────
#  Root Endpoint Tests
# ─────────────────────────────────────────────────────────────

def test_root_endpoint():
    """Test root / endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "service" in data
    assert "endpoints" in data
    assert isinstance(data["endpoints"], list)