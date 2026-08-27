"""
ASTRA Centralized Configuration Manager.
Loads settings from environment variables and provides safe allowlists and defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Application configuration container."""

    def __init__(self, env_path: str | Path | None = None):
        if env_path and Path(env_path).exists():
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()

        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.env = os.getenv("ASTRA_ENV", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        log_path_str = os.getenv("LOG_FILE_PATH", "data/logs/astra.log")
        self.log_file = self.root_dir / log_path_str
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Screenshots output directory
        self.screenshots_dir = self.root_dir / "data" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Vision Subsystem Temporary Directory (Phase 8)
        self.temp_vision_dir = self.root_dir / "data" / "temp_vision"
        self.temp_vision_dir.mkdir(parents=True, exist_ok=True)

        self.permissions_mode = os.getenv("PERMISSIONS_MODE", "NORMAL").upper()

        # Application mapping allowlist for Windows
        self.app_allowlist: dict[str, str] = {
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "vscode": "code",
            "code": "code",
            "explorer": "explorer.exe",
            "paint": "mspaint.exe",
            "cmd": "cmd.exe",
        }

        # Safe folder allowlist mapping
        user_profile = Path(os.getenv("USERPROFILE", Path.home()))
        self.folder_allowlist: dict[str, Path] = {
            "downloads": user_profile / "Downloads",
            "documents": user_profile / "Documents",
            "desktop": user_profile / "Desktop",
            "pictures": user_profile / "Pictures",
            "videos": user_profile / "Videos",
            "music": user_profile / "Music",
            "home": user_profile,
        }

        # Project directories
        self.project_dirs: list[Path] = [
            user_profile / "Documents" / "GitHub",
            user_profile / "Projects",
            user_profile / "Desktop",
        ]

        # Safe website URL mapping / shortcuts
        self.website_allowlist: dict[str, str] = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "github": "https://github.com",
            "stack overflow": "https://stackoverflow.com",
            "wikipedia": "https://www.wikipedia.org",
            "reddit": "https://www.reddit.com",
        }

        # Voice Subsystem Configuration (Phase 2)
        self.voice_enabled = os.getenv("VOICE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.stt_provider = os.getenv("STT_PROVIDER", "speech_recognition").lower()
        self.tts_provider = os.getenv("TTS_PROVIDER", "pyttsx3").lower()
        self.microphone_device = os.getenv("MICROPHONE_DEVICE", "default")

        self.listen_timeout = float(os.getenv("LISTEN_TIMEOUT", "10.0"))
        self.silence_timeout = float(os.getenv("SILENCE_TIMEOUT", "2.0"))
        self.minimum_speech_duration = float(os.getenv("MINIMUM_SPEECH_DURATION", "0.5"))

        self.tts_rate = int(os.getenv("TTS_RATE", "175"))
        self.tts_volume = float(os.getenv("TTS_VOLUME", "1.0"))
        self.voice_language = os.getenv("VOICE_LANGUAGE", "en-US")

        # LLM Brain Configuration (Phase 4)
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self.llm_model = os.getenv("LLM_MODEL", "mock-astra-v1")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.llm_max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "512"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "10.0"))
        self.llm_fallback_enabled = os.getenv("LLM_FALLBACK_ENABLED", "true").lower() in ("true", "1", "yes")

        # Filesystem Controls (Phase 5)
        self.max_search_results = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
        self.max_bulk_operations = int(os.getenv("MAX_BULK_OPERATIONS", "50"))

        # Web Intelligence & Research Engine (Phase 6)
        self.web_search_provider = os.getenv("WEB_SEARCH_PROVIDER", "mock").lower()
        self.max_fetch_size_mb = float(os.getenv("MAX_FETCH_SIZE_MB", "1.0"))
        self.max_research_sources = int(os.getenv("MAX_RESEARCH_SOURCES", "8"))
        self.web_cache_ttl_sec = int(os.getenv("WEB_CACHE_TTL_SEC", "3600"))

        # Memory & Personal Context Subsystem (Phase 7)
        db_rel_path = os.getenv("DATABASE_PATH", "data/astra_memory.db")
        self.database_path = self.root_dir / db_rel_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_retrieved_memories = int(os.getenv("MAX_RETRIEVED_MEMORIES", "10"))
        self.memory_expiration_days = int(os.getenv("MEMORY_EXPIRATION_DAYS", "30"))

        # Vision, Screen Understanding & Visual Context (Phase 8)
        self.vision_provider = os.getenv("VISION_PROVIDER", "mock").lower()
        self.ocr_provider = os.getenv("OCR_PROVIDER", "mock").lower()
        self.vision_timeout = float(os.getenv("VISION_TIMEOUT", "10.0"))
        self.max_image_size_mb = float(os.getenv("MAX_IMAGE_SIZE_MB", "5.0"))
        self.visual_context_ttl_sec = int(os.getenv("VISUAL_CONTEXT_TTL_SEC", "300"))

    def is_app_allowed(self, app_name: str) -> bool:
        """Check if an application name is in the allowlist."""
        return app_name.lower().strip() in self.app_allowlist

    def get_app_executable(self, app_name: str) -> str | None:
        """Get executable command for an app name."""
        return self.app_allowlist.get(app_name.lower().strip())

    def get_folder_path(self, folder_name: str) -> Path | None:
        """Get resolved Path for a target folder name."""
        return self.folder_allowlist.get(folder_name.lower().strip())

    def resolve_url(self, target: str) -> str | None:
        """Resolve a website shortcut or raw valid URL."""
        normalized = target.lower().strip()
        if normalized in self.website_allowlist:
            return self.website_allowlist[normalized]
        if target.startswith(("http://", "https://")):
            return target
        if "." in target and not target.startswith(" "):
            return f"https://{target}"
        return None
