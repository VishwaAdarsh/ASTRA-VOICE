"""
Memory Dashboard Page Component (Stitch Design System Integration).
Connects to Phase 7 MemoryManager for managing, searching, editing, and deleting long-term memories.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from src.core.logger import get_logger
from src.memory.manager import MemoryManager
from src.memory.models import MemoryItem, MemoryType

logger = get_logger()


class MemoryCardWidget(QFrame):
    """Widget card representing an individual MemoryItem record."""

    delete_requested = Signal(int)
    edit_requested = Signal(int, str)

    def __init__(self, item: MemoryItem, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self.setProperty("class", "CardWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        # Title & Content
        content_lbl = QLabel(item.content)
        content_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e2e3;")
        content_lbl.setWordWrap(True)

        meta_str = f"Type: {item.type.value} | Source: {item.source.value} | Created: {item.created_at[:10]}"
        meta_lbl = QLabel(meta_str)
        meta_lbl.setStyleSheet("font-size: 12px; color: #938ea1;")

        info_layout.addWidget(content_lbl)
        info_layout.addWidget(meta_lbl)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(65, 32)
        edit_btn.setStyleSheet("background: #7c5cfc; color: white; border-radius: 16px; font-weight: 600; font-size: 13px;")
        edit_btn.clicked.connect(self._on_edit)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(70, 32)
        del_btn.setStyleSheet("background: #ffb4ab; color: #690005; border-radius: 16px; font-weight: 700; font-size: 13px;")
        del_btn.clicked.connect(self._on_delete)

        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)

        layout.addLayout(info_layout, stretch=1)
        layout.addLayout(btn_layout)

    def _on_delete(self):
        if self.item.id:
            self.delete_requested.emit(self.item.id)

    def _on_edit(self):
        if self.item.id:
            self.edit_requested.emit(self.item.id, self.item.content)


class MemoryPage(QWidget):
    """Interactive Memory Dashboard matching Stitch design system."""

    def __init__(self, memory_manager: MemoryManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.memory_manager = memory_manager or MemoryManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header Section
        header_layout = QHBoxLayout()

        title_lbl = QLabel("🧠 Memory Subsystem")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: 700; color: #e2e2e3;")

        self.stats_lbl = QLabel("Total Memories: 0")
        self.stats_lbl.setStyleSheet("font-size: 13px; color: #7c5cfc; font-weight: 700;")

        add_btn = QPushButton("+ Add Memory")
        add_btn.setFixedSize(130, 40)
        add_btn.setStyleSheet("background: #7c5cfc; color: white; font-weight: 700; border-radius: 20px;")
        add_btn.clicked.connect(self._on_add_memory)

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.stats_lbl)
        header_layout.addWidget(add_btn)

        # Search Bar Section (Stitch Pill Input)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search stored memories...")
        self.search_input.textChanged.connect(self.refresh_memories)

        # Scrollable Cards Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.scroll_area.setWidget(self.cards_container)

        layout.addLayout(header_layout)
        layout.addWidget(self.search_input)
        layout.addWidget(self.scroll_area, stretch=1)

        self.refresh_memories()

    def refresh_memories(self):
        """Re-query memories and populate card widgets."""
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_input.text().strip()
        if query:
            items = self.memory_manager.search(query=query)
        else:
            items = self.memory_manager.list_all()

        stats = self.memory_manager.get_stats()
        self.stats_lbl.setText(f"Total Memories: {stats['total']} | Prefs: {stats['USER_PREFERENCE']} | Projects: {stats['PROJECT']}")

        if not items:
            empty_lbl = QLabel("No memory records found.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("font-size: 15px; color: #938ea1; margin-top: 40px;")
            self.cards_layout.addWidget(empty_lbl)
            return

        for item in items:
            card = MemoryCardWidget(item)
            card.delete_requested.connect(self._handle_delete)
            card.edit_requested.connect(self._handle_edit)
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def _handle_delete(self, memory_id: int):
        self.memory_manager.forget(memory_id)
        self.refresh_memories()

    def _handle_edit(self, memory_id: int, current_text: str):
        new_text, ok = QInputDialog.getText(self, "Edit Memory", "Update memory content:", QLineEdit.Normal, current_text)
        if ok and new_text.strip():
            item = self.memory_manager.repository.get_by_id(memory_id)
            if item:
                item.content = new_text.strip()
                self.memory_manager.repository.update(item)
                self.refresh_memories()

    def _on_add_memory(self):
        text, ok = QInputDialog.getText(self, "Add Memory", "Enter new memory item:")
        if ok and text.strip():
            self.memory_manager.remember(content=text.strip(), memory_type=MemoryType.USER_FACT)
            self.refresh_memories()
