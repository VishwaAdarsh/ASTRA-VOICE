"""
Unit tests for PySide6 UI Pages, MainWindow navigation, and Theme Manager.
"""

from PySide6.QtWidgets import QApplication
from src.brain.agent import AstraAgent
from src.ui.controllers.app_controller import AppController
from src.ui.main_window import MainWindow
from src.ui.theme.manager import ThemeManager
from src.voice.manager import VoiceManager
from src.voice.stt import MockSTTProvider
from src.voice.tts import MockTTSProvider

_app = QApplication.instance() or QApplication([])


def test_main_window_navigation_and_pages():
    agent = AstraAgent()
    voice_manager = VoiceManager(agent=agent, stt_provider=MockSTTProvider(), tts_provider=MockTTSProvider())
    controller = AppController(agent=agent, voice_manager=voice_manager)

    window = MainWindow(controller=controller)
    assert window.windowTitle() == "ASTRA - Personal AI Assistant"
    assert window.page_stack.count() == 9




    # Test navigation switches page stack index
    window._on_page_selected(1)
    assert window.page_stack.currentIndex() == 1

    window._on_page_selected(3)
    assert window.page_stack.currentIndex() == 3


def test_theme_manager_switch():
    tm = ThemeManager()
    tm.set_theme("light")
    assert tm.current_theme == "light"

    tm.set_theme("dark")
    assert tm.current_theme == "dark"


def test_tools_page_dynamic_population():
    agent = AstraAgent()
    voice_manager = VoiceManager(agent=agent, stt_provider=MockSTTProvider(), tts_provider=MockTTSProvider())
    controller = AppController(agent=agent, voice_manager=voice_manager)

    window = MainWindow(controller=controller)
    tools_page = window.tools_page

    # Should dynamically populate grid cards for all registered tools
    assert tools_page.grid.count() == len(agent.registry.list_tools())

