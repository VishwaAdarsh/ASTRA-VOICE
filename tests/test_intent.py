"""
Unit tests for ASTRA Intent Recognition Engine.
"""

from src.brain.intent import RuleBasedIntentRecognizer
from src.brain.models import Command, IntentType


def test_intent_open_application():
    recognizer = RuleBasedIntentRecognizer()

    cmd1 = Command(raw_text="open calculator", normalized_text="open calculator")
    intent1 = recognizer.recognize(cmd1)
    assert intent1.intent_type == IntentType.OPEN_APPLICATION
    assert intent1.parameters.get("app_name") == "calculator"

    cmd2 = Command(raw_text="launch notepad", normalized_text="launch notepad")
    intent2 = recognizer.recognize(cmd2)
    assert intent2.intent_type == IntentType.OPEN_APPLICATION
    assert intent2.parameters.get("app_name") == "notepad"


def test_intent_open_folder():
    recognizer = RuleBasedIntentRecognizer()

    cmd = Command(raw_text="open downloads", normalized_text="open downloads")
    intent = recognizer.recognize(cmd)
    assert intent.intent_type == IntentType.OPEN_FOLDER
    assert intent.parameters.get("folder_name") == "downloads"


def test_intent_open_website():
    recognizer = RuleBasedIntentRecognizer()

    cmd1 = Command(raw_text="open youtube", normalized_text="open youtube")
    intent1 = recognizer.recognize(cmd1)
    assert intent1.intent_type == IntentType.OPEN_WEBSITE
    assert intent1.parameters.get("target") == "youtube"

    cmd2 = Command(raw_text="open https://github.com", normalized_text="open https://github.com")
    intent2 = recognizer.recognize(cmd2)
    assert intent2.intent_type == IntentType.OPEN_WEBSITE
    assert intent2.parameters.get("target") == "https://github.com"


def test_intent_system_information():
    recognizer = RuleBasedIntentRecognizer()

    cmd1 = Command(raw_text="show system information", normalized_text="show system information")
    intent1 = recognizer.recognize(cmd1)
    assert intent1.intent_type == IntentType.SYSTEM_INFORMATION

    cmd2 = Command(raw_text="system info", normalized_text="system info")
    intent2 = recognizer.recognize(cmd2)
    assert intent2.intent_type == IntentType.SYSTEM_INFORMATION


def test_intent_unknown_command():
    recognizer = RuleBasedIntentRecognizer()

    cmd = Command(raw_text="do something completely unsupported", normalized_text="do something completely unsupported")
    intent = recognizer.recognize(cmd)
    assert intent.intent_type == IntentType.UNKNOWN
    assert intent.confidence == 0.0
