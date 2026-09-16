"""
Integration & Contract tests for FastAPI & WebSocket Communication Server (Phase V2-03).
Tests dynamic runtime config, readiness probes, request correlation, idempotency protection,
WebSocket heartbeat/lifecycle, error normalization, and CORS policy.
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.brain.agent import AstraAgent
from src.brain.llm.errors import LLMAuthError, LLMQuotaExhaustedError
from src.brain.models import ExecutionStatus, ToolResult


@pytest.fixture
def mock_agent():
    """Mock AstraAgent for fast API testing."""
    agent = MagicMock()
    agent.config = MagicMock()
    agent.config.voice_enabled = False

    health_mgr = MagicMock()
    healthy_sub = MagicMock()
    healthy_sub.status.value = "HEALTHY"
    healthy_sub.message = "OK"
    health_mgr.get_all_health.return_value = {"LLM": healthy_sub}
    health_mgr.is_overall_healthy.return_value = True
    agent.health_manager = health_mgr

    result = ToolResult(
        status=ExecutionStatus.SUCCESS,
        message="Calculator opened.",
        data={"tool_name": "open_application"},
        execution_time_ms=120.0,
    )
    result.tool_name = "open_application"
    agent.process_command.return_value = ("Calculator opened successfully.", result)
    return agent


@pytest.fixture
def client(mock_agent):
    """FastAPI TestClient bound to mock agent with custom runtime config."""
    runtime_cfg = {
        "apiBaseUrl": "http://127.0.0.1:8005/api/v1",
        "wsUrl": "ws://127.0.0.1:8005/api/v1/ws",
        "host": "127.0.0.1:8005",
        "port": 8005,
        "version": "1.0.0",
        "environment": "test",
        "capabilities": ["text", "voice", "tools"],
    }
    app = create_app(
        agent=mock_agent,
        port=8005,
        host="127.0.0.1",
        runtime_config=runtime_cfg,
    )
    return TestClient(app)


# ============================================================================
# 1. RUNTIME CONFIGURATION & READINESS
# ============================================================================

def test_runtime_config_endpoint(client):
    """GET /api/v1/config returns sanitized runtime configuration without secrets."""
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    data = res.json()
    assert data["port"] == 8005
    assert data["apiBaseUrl"] == "http://127.0.0.1:8005/api/v1"
    assert data["wsUrl"] == "ws://127.0.0.1:8005/api/v1/ws"
    assert "capabilities" in data
    # Ensure no secrets or API keys are exposed
    assert "api_key" not in data
    assert "secret" not in data


def test_readiness_probe(client):
    """GET /api/v1/ready verifies both server and agent readiness."""
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["ready"] is True
    assert data["status"] == "READY"
    assert data["subsystems_ready"] is True
    assert data["agent_initialized"] is True


def test_health_diagnostics(client):
    """GET /api/v1/health exposes operational subsystem states."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert "LLM" in data["subsystems"]
    assert data["subsystems"]["LLM"]["status"] == "HEALTHY"


# ============================================================================
# 2. COMMAND EXECUTION, REQUEST CORRELATION & IDEMPOTENCY
# ============================================================================

def test_command_execution_with_request_id(client, mock_agent):
    """POST /api/v1/command returns standardized envelope with propagated request_id."""
    req_id = "test-req-12345"
    res = client.post("/api/v1/command", json={"input": "open calculator", "request_id": req_id})
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["request_id"] == req_id
    assert data["status"] == "SUCCESS"
    assert "Calculator opened" in data["response"]
    assert data["tool_used"] == "open_application"
    assert "timestamp" in data
    mock_agent.process_command.assert_called_once_with("open calculator")


def test_idempotency_duplicate_protection(client, mock_agent):
    """Submitting the same request_id twice returns cached result without re-executing."""
    req_id = "idempotent-unique-99"
    res1 = client.post("/api/v1/command", json={"input": "open calculator", "request_id": req_id})
    assert res1.status_code == 200

    # Second call with same request_id
    res2 = client.post("/api/v1/command", json={"input": "open calculator", "request_id": req_id})
    assert res2.status_code == 200
    assert res2.json()["request_id"] == req_id

    # process_command was called ONLY ONCE
    assert mock_agent.process_command.call_count == 1


# ============================================================================
# 3. ERROR NORMALIZATION
# ============================================================================

def test_error_normalization_quota_exhausted(client, mock_agent):
    """Typed LLMQuotaExhaustedError maps to 429 and structured error envelope."""
    mock_agent.process_command.side_effect = LLMQuotaExhaustedError("Daily quota limit exceeded")

    res = client.post("/api/v1/command", json={"input": "write poem", "request_id": "req-quota-1"})
    assert res.status_code == 429
    data = res.json()

    assert data["success"] is False
    assert data["error"]["code"] == "LLM_QUOTA_EXHAUSTED"
    assert "quota" in data["error"]["message"].lower()
    assert data["request_id"] == "req-quota-1"


def test_error_normalization_auth_failed(client, mock_agent):
    """Typed LLMAuthError maps to 401 and structured error envelope."""
    mock_agent.process_command.side_effect = LLMAuthError("Invalid Gemini API key", status_code=401)

    res = client.post("/api/v1/command", json={"input": "search web", "request_id": "req-auth-1"})
    assert res.status_code == 401
    data = res.json()

    assert data["success"] is False
    assert data["error"]["code"] == "LLM_AUTH_FAILED"
    assert "authentication failed" in data["error"]["message"].lower()


# ============================================================================
# 4. WEBSOCKET REAL-TIME CONTRACT & HEARTBEAT
# ============================================================================

def test_websocket_heartbeat_and_events(client):
    """WebSocket handles PING/PONG heartbeat and receives initial state."""
    with client.websocket_connect("/api/v1/ws") as ws:
        # Initial health snapshot
        initial_msg = ws.receive_json()
        assert initial_msg["type"] == "HEALTH_CHANGED"

        # Client sends PING with timestamp
        ws.send_json({"type": "PING", "timestamp": 123456789})

        # Server responds with PONG
        pong_msg = ws.receive_json()
        assert pong_msg["type"] == "PONG"
        assert pong_msg["client_timestamp"] == 123456789
        assert "timestamp" in pong_msg


# ============================================================================
# 5. LOCALHOST CORS SECURITY
# ============================================================================

def test_cors_allows_localhost_and_dev_origins(client):
    """CORS permits local WebEngine and development server origins."""
    headers = {"Origin": "http://127.0.0.1:5173"}
    res = client.options("/api/v1/command", headers=headers)
    assert res.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"

    headers_desktop = {"Origin": "http://127.0.0.1:8005"}
    res2 = client.options("/api/v1/command", headers=headers_desktop)
    assert res2.headers.get("access-control-allow-origin") == "http://127.0.0.1:8005"


def test_cors_blocks_external_origins(client):
    """CORS does NOT reflect arbitrary untrusted external origins."""
    headers = {"Origin": "http://malicious-website.com"}
    res = client.options("/api/v1/command", headers=headers)
    # The external origin must not be granted access
    assert res.headers.get("access-control-allow-origin") != "http://malicious-website.com"
