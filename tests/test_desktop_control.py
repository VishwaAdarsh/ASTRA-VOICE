"""
Comprehensive Test Suite for ASTRA Desktop Control & Automation.
Covers:
- Safe Application Launcher (allowlist, executable resolution, already-running checks, launch verification)
- File and Folder Search (approved roots, traversal rejection, depth bounding, timeout bounding, error tolerance)
- Clipboard Operations (read, write, secret scrubbing, empty handling, logging protection)
- Capability Registry & Agent Integration
"""

import os
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from src.brain.agent import AstraAgent
from src.brain.models import ExecutionStatus, PermissionLevel, ToolRequest
from src.core.config import Config
from src.core.exceptions import PathSecurityError
from src.execution.executor import ToolExecutor
from src.tools.applications.aliases import ApplicationRegistry
from src.tools.applications.launcher import OpenApplicationTool
from src.tools.applications.status import ApplicationStatusTool
from src.tools.filesystem.paths import PathResolver
from src.tools.filesystem.search import SearchFilesTool
from src.tools.registry import ToolRegistry
from src.tools.system.clipboard import (
    ReadClipboardTool,
    WriteClipboardTool,
    _get_win32_clipboard_text,
    _set_win32_clipboard_text,
)
from src.voice.tts import sanitize_text_for_speech


# =====================================================================
# 1. APPLICATION LAUNCHER TESTS
# =====================================================================

def test_launcher_allowlist_validation():
    """Verify allowlisted apps are accepted and non-allowlisted apps are rejected."""
    config = Config()
    tool = OpenApplicationTool(config=config)

    # Allowed apps
    for app in ["notepad", "calculator", "settings", "browser", "vscode", "paint", "cmd"]:
        assert tool.validate({"app_name": app}) is True

    # Disallowed apps
    for bad_app in ["malicious.exe", "powershell.exe", "regedit", "format.com", "unknown_trojan"]:
        assert tool.validate({"app_name": bad_app}) is False

        res = tool.execute({"app_name": bad_app})
        assert res.status == ExecutionStatus.INVALID_REQUEST
        assert "not in the allowlist" in res.message


def test_launcher_browser_resolution():
    """Verify dynamic browser resolution prioritizes available browsers."""
    reg = ApplicationRegistry()
    resolved = reg.resolve_executable("browser")
    assert resolved is not None
    assert any(b in resolved.lower() for b in ["chrome", "msedge", "brave", "firefox"])


def test_launcher_settings_uri_resolution():
    """Verify Windows Settings resolves to ms-settings: URI."""
    reg = ApplicationRegistry()
    assert reg.resolve_executable("settings") == "ms-settings:"
    assert reg.resolve_executable("windows settings") == "ms-settings:"


@patch("os.startfile", create=True)
def test_launcher_opens_settings_safely(mock_startfile):
    """Verify settings opens via native os.startfile without shell invocation."""
    config = Config()
    tool = OpenApplicationTool(config=config)

    res = tool.execute({"app_name": "settings"})
    assert res.status == ExecutionStatus.SUCCESS
    assert "Settings opened" in res.message
    assert res.data["executable"] == "ms-settings:"
    assert res.verified is True
    mock_startfile.assert_called_once_with("ms-settings:")


@patch("subprocess.Popen")
def test_launcher_executes_with_safe_arguments(mock_popen):
    """Verify normal apps launch via safe argument list with shell=False."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 9999
    mock_popen.return_value = mock_proc

    config = Config()
    tool = OpenApplicationTool(config=config)

    res = tool.execute({"app_name": "notepad"})
    assert res.status == ExecutionStatus.SUCCESS
    assert "Notepad opened" in res.message
    assert res.data["pid"] == 9999
    assert res.verified is True

    # Ensure Popen was called with list args, not a shell string
    called_args, called_kwargs = mock_popen.call_args
    assert isinstance(called_args[0], list)
    assert "shell" not in called_kwargs or called_kwargs["shell"] is False


def test_launcher_already_running_check():
    """Verify honest reporting when an app is already running and check is requested."""
    config = Config()
    mock_status = MagicMock()
    mock_status.is_process_running.return_value = (True, 12345)

    tool = OpenApplicationTool(config=config, status_tool=mock_status)

    res = tool.execute({"app_name": "calculator", "check_already_running": True})
    assert res.status == ExecutionStatus.SUCCESS
    assert "is already running" in res.message
    assert res.data["is_already_running"] is True
    assert res.data["launched"] is False
    assert res.data["pid"] == 12345


def test_launcher_missing_application_honest_failure():
    """Verify non-existent executable returns honest NOT_FOUND."""
    config = Config()
    mock_registry = MagicMock()
    mock_registry.resolve_executable.return_value = r"C:\NonExistent\Folder\phantom.exe"

    tool = OpenApplicationTool(config=config, app_registry=mock_registry)
    with patch.object(config, "is_app_allowed", return_value=True):
        res = tool.execute({"app_name": "phantom"})
        assert res.status == ExecutionStatus.NOT_FOUND
        assert "not installed or executable not found" in res.message


# =====================================================================
# 2. APPLICATION STATUS TOOL TESTS
# =====================================================================

def test_application_status_psutil_inspection():
    """Verify ApplicationStatusTool correctly inspects process status without shell."""
    tool = ApplicationStatusTool()

    # Query calculator (standard Windows test)
    res = tool.execute({"app_name": "calculator"})
    assert res.status == ExecutionStatus.SUCCESS
    assert "status" in res.data
    assert isinstance(res.data["is_running"], bool)


def test_application_status_not_running():
    """Verify application status reports not running for inactive app."""
    tool = ApplicationStatusTool()
    res = tool.execute({"app_name": "non_existent_app_xyz"})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["is_running"] is False
    assert res.data["status"] == "NOT_RUNNING"


# =====================================================================
# 3. FILE AND FOLDER SEARCH TESTS
# =====================================================================

def test_search_files_approved_roots_success(tmp_path):
    """Verify search succeeds within approved sandbox or allowlisted folder."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    # Populate test files
    (tmp_path / "report_2026.pdf").write_text("dummy report", encoding="utf-8")
    (tmp_path / "invoice_march.pdf").write_text("dummy invoice", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("some notes", encoding="utf-8")

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)

    # Search by query
    res = search_tool.execute({"query": "invoice", "location": str(tmp_path)})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["count"] == 1
    assert res.data["results"][0]["name"] == "invoice_march.pdf"
    assert "Found 1 file matching 'invoice'" in res.message

    # Search by extension
    res_ext = search_tool.execute({"extension": ".pdf", "location": str(tmp_path)})
    assert res_ext.status == ExecutionStatus.SUCCESS
    assert res_ext.data["count"] == 2


def test_search_files_rejects_unapproved_roots(tmp_path):
    """Verify search explicitly denies traversal outside approved roots."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)

    # Attempt to search restricted Windows system directory
    res_sys = search_tool.execute({"location": r"C:\Windows\System32"})
    assert res_sys.status == ExecutionStatus.DENIED

    # Attempt to search outside sandbox root
    unapproved = tmp_path.parent / "unapproved_random_dir_123"
    unapproved.mkdir(exist_ok=True)
    try:
        res_unapproved = search_tool.execute({"location": str(unapproved)})
        assert res_unapproved.status == ExecutionStatus.DENIED
        assert "outside approved search roots" in res_unapproved.message
    finally:
        if unapproved.exists():
            unapproved.rmdir()


def test_search_files_depth_bounding(tmp_path):
    """Verify file search strictly bounds traversal depth to max_depth=3."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    # Create nested tree: depth 1, 2, 3, 4
    d1 = tmp_path / "level1"
    d2 = d1 / "level2"
    d3 = d2 / "level3"
    d4 = d3 / "level4"
    d4.mkdir(parents=True)

    (tmp_path / "root_file.txt").write_text("root", encoding="utf-8")
    (d1 / "level1_file.txt").write_text("l1", encoding="utf-8")
    (d2 / "level2_file.txt").write_text("l2", encoding="utf-8")
    (d3 / "level3_file.txt").write_text("l3", encoding="utf-8")
    (d4 / "level4_file.txt").write_text("l4", encoding="utf-8")

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)

    # Search bounded to depth 2
    res_d2 = search_tool.execute({"location": str(tmp_path), "max_depth": 2})
    found_names = [f["name"] for f in res_d2.data["results"]]
    assert "root_file.txt" in found_names
    assert "level1_file.txt" in found_names
    assert "level2_file.txt" in found_names
    # Depth 3 and 4 must NOT be reached
    assert "level3_file.txt" not in found_names
    assert "level4_file.txt" not in found_names


def test_search_files_result_capping(tmp_path):
    """Verify file search strictly caps results at max 20 even if higher limit requested."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    # Create 30 test files
    for i in range(30):
        (tmp_path / f"doc_{i:02d}.txt").write_text(f"content {i}", encoding="utf-8")

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)

    # Request limit of 100
    res = search_tool.execute({"location": str(tmp_path), "limit": 100})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["count"] <= 20
    assert len(res.data["results"]) <= 20


def test_search_files_permission_error_tolerance(tmp_path):
    """Verify search gracefully tolerates unreadable directories without crashing."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    (tmp_path / "valid.txt").write_text("valid file", encoding="utf-8")

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)

    # Simulate permission error on os.walk
    with patch("os.walk") as mock_walk:
        mock_walk.side_effect = PermissionError("Access is denied")
        res = search_tool.execute({"location": str(tmp_path)})
        # Must not raise an unhandled exception
        assert res.status == ExecutionStatus.SUCCESS
        assert res.data["count"] == 0


def test_search_files_metadata_only(tmp_path):
    """Verify file search returns metadata only without file contents."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)

    sensitive_content = "SECRET_DATABASE_PASSWORD_XYZ_123"
    (tmp_path / "sensitive.env").write_text(sensitive_content, encoding="utf-8")

    search_tool = SearchFilesTool(config=config, path_resolver=resolver)
    res = search_tool.execute({"location": str(tmp_path)})

    assert res.status == ExecutionStatus.SUCCESS
    for item in res.data["results"]:
        assert "content" not in item
        assert sensitive_content not in str(item)
        assert "name" in item
        assert "path" in item
        assert "size" in item
        assert "modified" in item


# =====================================================================
# 4. CLIPBOARD OPERATIONS TESTS
# =====================================================================

def test_clipboard_write_and_read():
    """Verify writing to and reading from clipboard."""
    writer = WriteClipboardTool()
    reader = ReadClipboardTool()

    test_payload = "ASTRA Voice Assistant Desktop Control"
    write_res = writer.execute({"text": test_payload})
    assert write_res.status == ExecutionStatus.SUCCESS
    assert write_res.data["char_count"] == len(test_payload)

    read_res = reader.execute({})
    assert read_res.status == ExecutionStatus.SUCCESS
    assert read_res.data["text"] == test_payload
    assert read_res.data["is_empty"] is False


def test_clipboard_secret_scrubbing():
    """Verify sensitive tokens and API keys are redacted upon clipboard read."""
    writer = WriteClipboardTool()
    reader = ReadClipboardTool()

    sensitive_payload = "Here is my secret token: sk_live_1234567890abcdef and password: secret_password_123"
    writer.execute({"text": sensitive_payload})

    read_res = reader.execute({})
    assert read_res.status == ExecutionStatus.SUCCESS
    assert "sk_live_1234567890abcdef" not in read_res.data["text"]
    assert "secret_password_123" not in read_res.data["text"]
    assert "[REDACTED]" in read_res.data["text"]
    assert read_res.data["was_redacted"] is True


def test_clipboard_empty_handling():
    """Verify reading an empty clipboard returns clean empty status."""
    writer = WriteClipboardTool()
    reader = ReadClipboardTool()

    # Clear clipboard
    writer.execute({"text": ""})

    read_res = reader.execute({})
    assert read_res.status == ExecutionStatus.SUCCESS
    assert read_res.data["is_empty"] is True
    assert "empty" in read_res.message.lower()


def test_clipboard_write_validation():
    """Verify write_clipboard validates input parameter."""
    writer = WriteClipboardTool()

    assert writer.validate({"text": "valid"}) is True
    assert writer.validate({}) is False
    assert writer.validate({"text": 123}) is False

    res = writer.execute({"invalid_key": "bad"})
    assert res.status == ExecutionStatus.INVALID_REQUEST


# =====================================================================
# 5. INTEGRATION & PIPELINE TESTS
# =====================================================================

def test_agent_registers_desktop_control_tools():
    """Verify AstraAgent registers all desktop control tools with CapabilityRegistry."""
    agent = AstraAgent()
    tools = agent.registry.list_tools()

    assert "open_application" in tools
    assert "application_status" in tools
    assert "search_files" in tools
    assert "read_clipboard" in tools
    assert "write_clipboard" in tools


def test_executor_executes_clipboard_and_search(tmp_path):
    """Verify ToolExecutor handles clipboard and search requests through pipeline."""
    config = Config()
    resolver = PathResolver(config=config, sandbox_root=tmp_path)
    (tmp_path / "invoice.pdf").write_text("pdf data", encoding="utf-8")

    registry = ToolRegistry()
    registry.register(SearchFilesTool(config=config, path_resolver=resolver))
    registry.register(WriteClipboardTool(config=config))
    registry.register(ReadClipboardTool(config=config))

    executor = ToolExecutor(registry=registry, config=config)

    # 1. Execute search
    req_search = ToolRequest(tool_name="search_files", parameters={"query": "invoice", "location": str(tmp_path)})
    res_search = executor.execute(req_search)
    assert res_search.status == ExecutionStatus.SUCCESS
    assert res_search.data["count"] == 1

    # 2. Execute clipboard write
    req_clip_write = ToolRequest(tool_name="write_clipboard", parameters={"text": "Copied summary"})
    res_clip_write = executor.execute(req_clip_write)
    assert res_clip_write.status == ExecutionStatus.SUCCESS

    # 3. Execute clipboard read
    req_clip_read = ToolRequest(tool_name="read_clipboard", parameters={})
    res_clip_read = executor.execute(req_clip_read)
    assert res_clip_read.status == ExecutionStatus.SUCCESS
    assert res_clip_read.data["text"] == "Copied summary"


def test_speech_sanitization_for_desktop_responses():
    """Verify desktop control response messages sanitize cleanly for TTS."""
    responses = [
        "Found 3 files matching 'invoice' in Documents.",
        "Calculator opened.",
        "Notepad is already running.",
        "Clipboard contains: Hello world.",
        "Access denied: Location is outside approved search roots.",
    ]
    for msg in responses:
        speech = sanitize_text_for_speech(msg)
        assert isinstance(speech, str)
        assert len(speech) > 0
        assert not speech.startswith("http")
