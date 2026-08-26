"""
Integration tests for AstraAgent with LLM Reasoning Engine and Fallback Engine.
"""

from unittest.mock import MagicMock, patch
from src.brain.agent import AstraAgent
from src.brain.llm.mock_provider import MockLLMProvider
from src.brain.models import ExecutionStatus


@patch("subprocess.Popen")
def test_agent_llm_tool_call(mock_popen):
    mock_provider = MockLLMProvider()
    agent = AstraAgent(llm_provider=mock_provider)

    response, result = agent.process_command("Could you please open calculator?")

    assert result.status == ExecutionStatus.SUCCESS
    assert "Calculator opened" in response
    mock_popen.assert_called_once()


def test_agent_llm_clarification():
    mock_provider = MockLLMProvider()
    agent = AstraAgent(llm_provider=mock_provider)

    response, result = agent.process_command("open my project")

    assert result.status == ExecutionStatus.SUCCESS
    assert "Which project" in response


def test_agent_fallback_mode_on_llm_error():
    # Create failing LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_structured.side_effect = RuntimeError("LLM API Network Failure")

    agent = AstraAgent(llm_provider=mock_provider)

    # Should gracefully switch to fallback engine and succeed via RuleBasedIntentRecognizer!
    with patch("subprocess.Popen") as mock_popen:
        response, result = agent.process_command("open calculator")
        assert result.status == ExecutionStatus.SUCCESS
        assert "Calculator opened" in response
