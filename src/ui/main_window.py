"""
Main Application Window Component for ASTRA UI.
Integrates Sidebar Navigation, Page Stack, Status Bar, and AppController signals.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget
from src.ui.components.notification import NotificationToast
from src.ui.components.sidebar import SidebarNav
from src.ui.components.status_bar import StatusBar
from src.ui.controllers.app_controller import AppController
from src.ui.pages.activity import ActivityPage
from src.ui.pages.assistant import AssistantPage
from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.memory import MemoryPage
from src.ui.pages.settings import SettingsPage
from src.ui.pages.tasks import TasksPage
from src.ui.pages.tools import ToolsPage
from src.ui.pages.vision import VisionPage


class MainWindow(QMainWindow):
    """Main Desktop GUI Window."""

    def __init__(self, controller: AppController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller

        self.setWindowTitle("ASTRA - Personal AI Assistant")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        # Main Central Widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content Split Layout (Sidebar + Stacked Pages)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar Navigation
        self.sidebar = SidebarNav()
        self.sidebar.sig_page_selected.connect(self._on_page_selected)
        content_layout.addWidget(self.sidebar)

        # Page Stack
        self.page_stack = QStackedWidget()

        self.dashboard_page = DashboardPage(self.controller)
        self.dashboard_page.sig_quick_action.connect(self._on_quick_action)

        self.assistant_page = AssistantPage(self.controller)
        self.activity_page = ActivityPage(self.controller)
        self.tools_page = ToolsPage(self.controller)
        self.memory_page = MemoryPage(memory_manager=self.controller.agent.memory_manager)
        self.vision_page = VisionPage(vision_manager=self.controller.agent.vision_manager)
        self.tasks_page = TasksPage(task_manager=self.controller.agent.task_manager)
        self.settings_page = SettingsPage(self.controller)

        self.page_stack.addWidget(self.dashboard_page)  # Index 0
        self.page_stack.addWidget(self.assistant_page)  # Index 1
        self.page_stack.addWidget(self.activity_page)   # Index 2
        self.page_stack.addWidget(self.tools_page)      # Index 3
        self.page_stack.addWidget(self.memory_page)     # Index 4
        self.page_stack.addWidget(self.vision_page)     # Index 5
        self.page_stack.addWidget(self.tasks_page)      # Index 6
        self.page_stack.addWidget(self.settings_page)   # Index 7



        content_layout.addWidget(self.page_stack)
        main_layout.addLayout(content_layout)

        # Footer Status Bar
        tool_count = len(self.controller.agent.registry.list_tools())
        self.status_bar_widget = StatusBar(tool_count=tool_count)
        main_layout.addWidget(self.status_bar_widget)

        # Connect controller signals
        self.controller.sig_voice_state_changed.connect(self.status_bar_widget.set_voice_state)
        self.controller.sig_notification.connect(self.show_notification)

    def _on_page_selected(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)

    def _on_quick_action(self, command_text: str) -> None:
        """Handle quick action button clicked from Dashboard."""
        self.sidebar.select_page(1)
        self.page_stack.setCurrentIndex(1)
        self.controller.submit_text_command(command_text)

    def show_notification(self, level: str, message: str) -> None:
        """Show toast notification banner."""
        toast = NotificationToast(level, message, self)
        toast.move(self.width() - toast.width() - 20, 20)
        toast.show()
