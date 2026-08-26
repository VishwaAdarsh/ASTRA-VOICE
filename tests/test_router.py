"""
Unit tests for ASTRA Intent Router.
"""

import pytest
from src.brain.models import Intent, IntentType
from src.brain.router import IntentRouter
from src.core.exceptions import IntentRecognitionError


def test_router_maps_open_application():
    router = IntentRouter()
    intent = Intent(intent_type=IntentType.OPEN_APPLICATION, confidence=0.9, parameters={"app_name": "calculator"})
    request = router.route(intent)

    assert request.tool_name == "open_application"
    assert request.parameters == {"app_name": "calculator"}


def test_router_maps_open_folder():
    router = IntentRouter()
    intent = Intent(intent_type=IntentType.OPEN_FOLDER, confidence=0.9, parameters={"folder_name": "downloads"})
    request = router.route(intent)

    assert request.tool_name == "open_folder"
    assert request.parameters == {"folder_name": "downloads"}


def test_router_maps_open_website():
    router = IntentRouter()
    intent = Intent(intent_type=IntentType.OPEN_WEBSITE, confidence=0.9, parameters={"target": "youtube"})
    request = router.route(intent)

    assert request.tool_name == "open_website"
    assert request.parameters == {"target": "youtube"}


def test_router_maps_system_information():
    router = IntentRouter()
    intent = Intent(intent_type=IntentType.SYSTEM_INFORMATION, confidence=1.0, parameters={})
    request = router.route(intent)

    assert request.tool_name == "system_information"


def test_router_raises_on_unknown_intent():
    router = IntentRouter()
    intent = Intent(intent_type=IntentType.UNKNOWN, confidence=0.0, raw_command="unknown cmd")

    with pytest.raises(IntentRecognitionError):
        router.route(intent)
