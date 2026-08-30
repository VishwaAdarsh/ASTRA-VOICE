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
        self.performance_logging = os.getenv("PERFORMANCE_LOGGING", "true").lower() in ("true", "1", "yes")


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

        # Primary ASTRA API Key & Subsystem Credential Integration
        self.astra_api_key = os.getenv("ASTRA_API_KEY", "")
        self.voice_api_key = os.getenv("VOICE_API_KEY", self.astra_api_key)
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", self.voice_api_key)




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
        self.llm_api_key = os.getenv("LLM_API_KEY", self.astra_api_key)
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.llm_max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "512"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "10.0"))
        self.llm_retry_count = int(os.getenv("LLM_RETRY_COUNT", "2"))
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

        # Advanced Autonomous Task Execution Engine (Phase 9 & 21)
        self.agent_max_steps = int(os.getenv("AGENT_MAX_STEPS", "20"))
        self.agent_max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))
        self.agent_max_tool_calls = int(os.getenv("AGENT_MAX_TOOL_CALLS", "30"))
        self.agent_max_replans = int(os.getenv("AGENT_MAX_REPLANS", "5"))
        self.agent_max_retries = int(os.getenv("AGENT_MAX_RETRIES", "3"))
        self.agent_timeout = float(os.getenv("AGENT_TIMEOUT", "30.0"))
        self.agent_autonomy_level = os.getenv("AGENT_AUTONOMY_LEVEL", "LEVEL_3").upper()


        # Proactive Personal Assistant & Automation (Phase 10)
        self.proactive_enabled = os.getenv("PROACTIVE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.max_automations = int(os.getenv("MAX_AUTOMATIONS", "50"))
        self.max_active_automations = int(os.getenv("MAX_ACTIVE_AUTOMATIONS", "20"))
        self.quiet_hours_enabled = os.getenv("QUIET_HOURS_ENABLED", "true").lower() in ("true", "1", "yes")
        self.quiet_hours_start = os.getenv("QUIET_HOURS_START", "23:00")
        self.quiet_hours_end = os.getenv("QUIET_HOURS_END", "07:00")
        self.max_notifications_per_automation_per_day = int(os.getenv("MAX_NOTIFICATIONS_PER_AUTOMATION_PER_DAY", "10"))

        # Security, Reliability & Production Hardening (Phase 11)
        self.max_file_size_mb = float(os.getenv("MAX_FILE_SIZE_MB", "10.0"))
        self.network_timeout = float(os.getenv("NETWORK_TIMEOUT", "15.0"))
        self.log_max_bytes = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5MB
        self.log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "3"))

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
