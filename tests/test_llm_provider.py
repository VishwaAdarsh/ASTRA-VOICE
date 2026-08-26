"""
Unit tests for LLM Provider Subsystem.
"""

from src.brain.llm.client import LLMClient
from src.brain.llm.factory import LLMProviderFactory
from src.brain.llm.mock_provider import MockLLMProvider
from src.brain.llm.models import DecisionType, ModelConfig


def test_mock_llm_provider_decisions():
    config = ModelConfig(provider="mock")
    provider = LLMProviderFactory.create(config)

    assert isinstance(provider, MockLLMProvider)

    # 1. Tool Call decision
    d1 = provider.generate_structured("open calculator")
    assert d1.decision_type == DecisionType.TOOL_CALL
    assert d1.tool_name == "open_application"
    assert d1.arguments == {"app_name": "calculator"}

    # 2. Clarification decision
    d2 = provider.generate_structured("open my project")
    assert d2.decision_type == DecisionType.CLARIFICATION
    assert "Which project" in d2.message

    # 3. Response decision
    d3 = provider.generate_structured("hello")
    assert d3.decision_type == DecisionType.RESPONSE


def test_llm_client_execution():
    config = ModelConfig(provider="mock", retry_count=2)
    client = LLMClient(config=config)

    decision = client.generate_decision("open downloads")
    assert decision.decision_type == DecisionType.TOOL_CALL
    assert decision.tool_name == "open_folder"
    assert decision.arguments == {"folder_name": "downloads"}
