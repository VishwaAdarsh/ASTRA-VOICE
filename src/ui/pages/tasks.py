"""
Autonomous Tasks Page Component (Stitch Design System Integration).
Aligns with Stitch "Tasks & Notes" design screen.
Connects to Phase 9 TaskManager for multi-step goal execution, plan steppers, and emergency stop.
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
from src.task.models import TaskResult, TaskStatus

logger = get_logger()


class TasksPage(QWidget):
    """Interactive Autonomous Tasks Center matching Stitch design system."""

    def __init__(self, task_manager: TaskManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.task_manager = task_manager or TaskManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header & Emergency Stop
        header_layout = QHBoxLayout()

        title_lbl = QLabel("⚡ Autonomous Task Execution")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: 700; color: #e2e2e3;")

        self.stop_btn = QPushButton("🛑 STOP ASTRA")
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.setStyleSheet("background: #ffb4ab; color: #690005; font-size: 14px; font-weight: 700; border-radius: 22px; padding: 0 22px;")
        self.stop_btn.clicked.connect(self._on_emergency_stop)

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.stop_btn)

        # Goal Input Bar (Stitch Pill Input)
        goal_card = QFrame()
        goal_card.setProperty("class", "CardWidget")
        g_layout = QHBoxLayout(goal_card)
        g_layout.setContentsMargins(16, 12, 16, 12)
        g_layout.setSpacing(12)

        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText("Enter goal (e.g. 'Find project report, summarize it, and save to report_summary.md')...")

        start_btn = QPushButton("🚀 Execute Task")
        start_btn.setFixedHeight(44)
        start_btn.clicked.connect(self._on_execute_task)

        g_layout.addWidget(self.goal_input, stretch=1)
        g_layout.addWidget(start_btn)

        # Content Split Layout (Left: Task Stepper; Right: Audit Log)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Left Panel (Task Stepper & Status)
        left_panel = QVBoxLayout()

        task_card = QFrame()
        task_card.setProperty("class", "CardWidget")
        t_layout = QVBoxLayout(task_card)

        self.status_lbl = QLabel("Task Status: IDLE")
        self.status_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #34d399;")

        self.summary_lbl = QLabel("No autonomous task currently executing.")
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet("font-size: 14px; color: #c9c4d8;")

        t_layout.addWidget(self.status_lbl)
        t_layout.addWidget(self.summary_lbl)

        plan_card = QFrame()
        plan_card.setProperty("class", "CardWidget")
        p_layout = QVBoxLayout(plan_card)

        p_title = QLabel("Execution Plan Stepper")
        p_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #7c5cfc;")

        self.steps_list = QListWidget()
        self.steps_list.setStyleSheet("background: #1a1c1d; color: #e2e2e3; border: none; border-radius: 12px; font-size: 14px; padding: 8px;")

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
        l_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #fbbf24;")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Task execution logs and events...")
        self.log_text.setStyleSheet("background: #1a1c1d; border: none; border-radius: 12px; color: #c9c4d8; font-size: 13px; padding: 12px;")

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
            self.status_lbl.setStyleSheet("color: #ffb4ab; font-weight: 700;")
            self.summary_lbl.setText(f"Error: {e}")
            self.log_text.append(f"✖ Task execution error: {e}")

    def display_result(self, res: TaskResult):
        """Populate UI dashboard with TaskResult outcome."""
        self.status_lbl.setText(f"Task Status: {res.status.value}")

        if res.status == TaskStatus.COMPLETED:
            self.status_lbl.setStyleSheet("color: #34d399; font-weight: 700;")
        elif res.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.status_lbl.setStyleSheet("color: #ffb4ab; font-weight: 700;")
        else:
            self.status_lbl.setStyleSheet("color: #fbbf24; font-weight: 700;")

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
        self.status_lbl.setStyleSheet("color: #ffb4ab; font-weight: 700;")
        self.summary_lbl.setText("Execution halted by user emergency stop button.")
        self.log_text.append("🛑 EMERGENCY STOP TRIGGERED BY USER!")
