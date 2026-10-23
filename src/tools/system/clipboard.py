"""
Windows Clipboard Operations Tools.
Safe read and write clipboard capabilities with secret redaction and no disk logging.
"""

import ctypes
from ctypes import wintypes
import os
import sys
import time
from typing import Any

from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import SecretRedactionFilter, get_logger
from src.tools.base import BaseTool

logger = get_logger()

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# Internal fallback buffer for non-Windows / test simulation
_mock_clipboard_buffer: str | None = None


def _get_win32_clipboard_text() -> str | None:
    """Read text from Windows clipboard via ctypes."""
    if sys.platform != "win32":
        return _mock_clipboard_buffer

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Define function signatures for 64-bit Windows safety
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    # Attempt to open clipboard with retry (in case another process has it open)
    opened = False
    for _ in range(5):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.05)

    if not opened:
        return _mock_clipboard_buffer

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None

        h_mem = user32.GetClipboardData(CF_UNICODETEXT)
        if not h_mem:
            return None

        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            return None

        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(h_mem)
    finally:
        user32.CloseClipboard()


def _set_win32_clipboard_text(text: str) -> bool:
    """Write text to Windows clipboard via ctypes."""
    global _mock_clipboard_buffer
    _mock_clipboard_buffer = text

    if sys.platform != "win32":
        return True

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    opened = False
    for _ in range(5):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.05)

    if not opened:
        return False

    try:
        user32.EmptyClipboard()
        if not text:
            return True

        encoded = (text + "\0").encode("utf-16le")
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h_mem:
            return False

        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            return False

        ctypes.memmove(ptr, encoded, len(encoded))
        kernel32.GlobalUnlock(h_mem)

        res = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        return res is not None
    finally:
        user32.CloseClipboard()


class ReadClipboardTool(BaseTool):
    """Tool for reading text from the Windows clipboard safely."""

    name = "read_clipboard"
    description = "Reads text currently on the clipboard with sensitive secret scrubbing (API keys, passwords, tokens)."
    permission_level = PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def validate(self, parameters: dict[str, Any]) -> bool:
        return isinstance(parameters, dict)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        try:
            raw_text = _get_win32_clipboard_text()

            if not raw_text or not raw_text.strip():
                logger.info("Clipboard read: empty or non-text content.")
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Clipboard is empty or contains non-text data.",
                    data={"text": "", "char_count": 0, "is_empty": True},
                    execution_time_ms=(time.time() - start_time) * 1000,
                    verified=True,
                )

            # Scrub credentials, API keys, passwords, and bearer tokens
            sanitized = SecretRedactionFilter.redact(raw_text)

            # Never log raw clipboard text to disk or logger
            logger.info(f"Clipboard read successfully ({len(sanitized)} characters, redacted={sanitized != raw_text}).")

            # Format natural voice-friendly summary
            if len(sanitized) <= 60 and "\n" not in sanitized:
                voice_msg = f"Clipboard contains: {sanitized}"
            else:
                voice_msg = f"Read {len(sanitized)} characters from clipboard."

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=voice_msg,
                data={
                    "text": sanitized,
                    "char_count": len(sanitized),
                    "is_empty": False,
                    "was_redacted": sanitized != raw_text,
                },
                execution_time_ms=(time.time() - start_time) * 1000,
                verified=True,
            )
        except Exception as e:
            logger.error(f"Failed to read clipboard: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to read clipboard: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )


class WriteClipboardTool(BaseTool):
    """Tool for copying text to the Windows clipboard."""

    name = "write_clipboard"
    description = "Copies user-supplied text to the Windows clipboard."
    permission_level = PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text content to copy to the clipboard.",
            }
        },
        "required": ["text"],
    }

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def validate(self, parameters: dict[str, Any]) -> bool:
        if not isinstance(parameters, dict):
            return False
        return "text" in parameters and isinstance(parameters["text"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        if not self.validate(parameters):
            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message="Missing or invalid 'text' parameter for write_clipboard.",
                error="Invalid parameter: text must be a string.",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        text = parameters["text"]
        try:
            success = _set_win32_clipboard_text(text)
            if not success:
                return ToolResult(
                    status=ExecutionStatus.FAILED,
                    message="Failed to write to clipboard.",
                    error="Clipboard API returned failure",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # Never log raw clipboard text to disk or logger
            logger.info(f"Clipboard written successfully ({len(text)} characters).")

            if not text:
                msg = "Clipboard cleared."
            else:
                msg = "Text copied to clipboard."

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={
                    "char_count": len(text),
                    "success": True,
                },
                execution_time_ms=(time.time() - start_time) * 1000,
                verified=True,
            )
        except Exception as e:
            logger.error(f"Failed to write clipboard: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to copy to clipboard: {e}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
