"""
Autonomous Tasks Page Component (Phase 9).
Native PySide6 view for viewing active tasks, progress steppers, plan previews, event logs, and emergency stop controls.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from src.core.logger import get_logger
from src.task.manager import TaskManager
from src.task.models import Task, TaskResult, TaskStatus

logger = get_logger()


class TasksPage(QWidget):
    """Interactive Autonomous Tasks Center for multi-step goal execution, stepper tracking, and emergency stop."""

    def __init__(self, task_manager: TaskManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.task_manager = task_manager or TaskManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header & Emergency Stop
        header_layout = QHBoxLayout()

        title_lbl = QLabel("⚡ Autonomous Task Execution Center")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #38BDF8;")

        self.stop_btn = QPushButton("🛑 STOP ASTRA")
        self.stop_btn.setFixedHeight(38)
        self.stop_btn.setStyleSheet("background: #DC2626; color: white; font-size: 13px; font-weight: bold; border-radius: 6px; padding: 0 18px;")
        self.stop_btn.clicked.connect(self._on_emergency_stop)

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.stop_btn)

        # Goal Input Bar
        goal_card = QFrame()
        goal_card.setProperty("class", "CardWidget")
        g_layout = QHBoxLayout(goal_card)
        g_layout.setContentsMargins(16, 12, 16, 12)
        g_layout.setSpacing(12)

        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText("Enter high-level goal (e.g. 'Find my project report, summarize it, and save to report_summary.md')...")
        self.goal_input.setStyleSheet("background: #0F172A; border: 1px solid #334155; border-radius: 6px; color: white; padding: 8px 12px; font-size: 13px;")

        start_btn = QPushButton("🚀 Execute Task")
        start_btn.setFixedHeight(36)
        start_btn.setStyleSheet("background: #0284C7; color: white; font-weight: bold; border-radius: 6px; padding: 0 18px;")
        start_btn.clicked.connect(self._on_execute_task)

        g_layout.addWidget(self.goal_input, stretch=1)
        g_layout.addWidget(start_btn)

        # Content Split Layout (Left: Active Task Stepper; Right: Event Audit Log)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Panel (Task Stepper & Plan Preview)
        left_panel = QVBoxLayout()

        task_card = QFrame()
        task_card.setProperty("class", "CardWidget")
        t_layout = QVBoxLayout(task_card)

        self.status_lbl = QLabel("Task Status: IDLE")
        self.status_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #10B981;")

        self.summary_lbl = QLabel("No autonomous task currently running.")
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet("font-size: 13px; color: #94A3B8;")

        t_layout.addWidget(self.status_lbl)
        t_layout.addWidget(self.summary_lbl)

        plan_card = QFrame()
        plan_card.setProperty("class", "CardWidget")
        p_layout = QVBoxLayout(plan_card)

        p_title = QLabel("Execution Plan Stepper")
        p_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38BDF8;")

        self.steps_list = QListWidget()
        self.steps_list.setStyleSheet("background: #0F172A; color: white; border: none; font-size: 13px;")

        p_layout.addWidget(p_title)
        p_layout.addWidget(self.steps_list)

        left_panel.addWidget(task_card)
        left_panel.addWidget(plan_card, stretch=1)

        # Right Panel (Task Audit Log)
        right_panel = QVBoxLayout()

        log_card = QFrame()
        log_card.setProperty("class", "CardWidget")
        l_layout = QVBoxLayout(log_card)

        l_title = QLabel("Task Audit Log")
        l_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #F59E0B;")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Task execution logs and events...")
        self.log_text.setStyleSheet("background: #0F172A; border: none; color: #E2E8F0; font-size: 12px;")

        l_layout.addWidget(l_title)
        l_layout.addWidget(self.log_text)

        right_panel.addWidget(log_card, stretch=1)

        content_layout.addLayout(left_panel, stretch=1)
        content_layout.addLayout(right_panel, stretch=1)

        layout.addLayout(header_layout)
        layout.addWidget(goal_card)
        layout.addLayout(content_layout, stretch=1)

    def _on_execute_task(self):
        goal = self.goal_input.text().strip()
        if not goal:
            return

        self.log_text.append(f"► Starting goal: '{goal}'")
        try:
            res = self.task_manager.create_and_execute_goal(goal)
            self.display_result(res)
        except Exception as e:
            self.status_lbl.setText("Task Status: ERROR")
            self.status_lbl.setStyleSheet("color: #EF4444; font-weight: bold;")
            self.summary_lbl.setText(f"Error: {e}")
            self.log_text.append(f"✖ Task execution error: {e}")

    def display_result(self, res: TaskResult):
        """Populate UI dashboard with TaskResult outcome."""
        self.status_lbl.setText(f"Task Status: {res.status.value}")

        if res.status == TaskStatus.COMPLETED:
            self.status_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
        elif res.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.status_lbl.setStyleSheet("color: #EF4444; font-weight: bold;")
        else:
            self.status_lbl.setStyleSheet("color: #F59E0B; font-weight: bold;")

        self.summary_lbl.setText(res.summary)
        self.log_text.append(f"✔ Goal Completed: {res.summary} ({res.completed_steps}/{res.total_steps} steps)")

        # Update Steps List
        self.steps_list.clear()
        task = self.task_manager.get_active_task()
        if task and task.plan:
            for s in task.plan.steps:
                icon = "✓" if s.status.value == "COMPLETED" else ("✖" if s.status.value == "FAILED" else "○")
                item = QListWidgetItem(f"{icon} Step {s.step_number}: {s.description} ({s.tool_name})")
                self.steps_list.addItem(item)

    def _on_emergency_stop(self):
        self.task_manager.emergency_stop()
        self.status_lbl.setText("Task Status: CANCELLED (EMERGENCY STOP)")
        self.status_lbl.setStyleSheet("color: #DC2626; font-weight: bold;")
        self.summary_lbl.setText("Execution halted by user emergency stop button.")
        self.log_text.append("🛑 EMERGENCY STOP TRIGGERED BY USER!")
