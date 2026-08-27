"""
Vision & Screen Understanding Page Component (Phase 8).
Native PySide6 view for capturing, viewing, inspecting OCR text, and analyzing desktop visuals.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from src.core.logger import get_logger
from src.vision.context.manager import VisionManager
from src.vision.types import VisualContext


logger = get_logger()


class VisionPage(QWidget):
    """Interactive Vision Dashboard for screen capture, active window analysis, OCR, and element view."""

    def __init__(self, vision_manager: VisionManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.vision_manager = vision_manager or VisionManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header & Action Buttons
        header_layout = QHBoxLayout()

        title_lbl = QLabel("👁️ Vision & Screen Understanding")
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #38BDF8;")

        mode_lbl = QLabel("Mode: Perception Only (No Auto-Click)")
        mode_lbl.setStyleSheet("font-size: 12px; color: #10B981; font-weight: bold; background: #064E3B; padding: 4px 8px; border-radius: 4px;")

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(mode_lbl)

        # Toolbar Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        win_btn = QPushButton("📷 Analyze Active Window")
        win_btn.setFixedHeight(36)
        win_btn.setStyleSheet("background: #0284C7; color: white; font-weight: bold; border-radius: 6px; padding: 0 16px;")
        win_btn.clicked.connect(self._on_analyze_window)

        screen_btn = QPushButton("🖥️ Analyze Full Screen")
        screen_btn.setFixedHeight(36)
        screen_btn.setStyleSheet("background: #6366F1; color: white; font-weight: bold; border-radius: 6px; padding: 0 16px;")
        screen_btn.clicked.connect(self._on_analyze_screen)

        img_btn = QPushButton("📁 Open Image File")
        img_btn.setFixedHeight(36)
        img_btn.setStyleSheet("background: #334155; color: white; font-weight: bold; border-radius: 6px; padding: 0 16px;")
        img_btn.clicked.connect(self._on_open_image)

        btn_layout.addWidget(win_btn)
        btn_layout.addWidget(screen_btn)
        btn_layout.addWidget(img_btn)
        btn_layout.addStretch()

        # Content Split Layout (Left: Preview & Summary; Right: OCR & Elements)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Panel (Preview Thumbnail & Description)
        left_panel = QVBoxLayout()

        preview_card = QFrame()
        preview_card.setProperty("class", "CardWidget")
        p_layout = QVBoxLayout(preview_card)

        p_title = QLabel("Screenshot Preview")
        p_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #94A3B8;")

        self.img_lbl = QLabel("No visual capture loaded")
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setMinimumSize(320, 200)
        self.img_lbl.setStyleSheet("border: 1px dashed #475569; border-radius: 8px; color: #64748B;")

        p_layout.addWidget(p_title)
        p_layout.addWidget(self.img_lbl)

        desc_card = QFrame()
        desc_card.setProperty("class", "CardWidget")
        d_layout = QVBoxLayout(desc_card)

        d_title = QLabel("Visual Findings")
        d_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #38BDF8;")

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setPlaceholderText("Visual analysis output will appear here...")
        self.desc_text.setStyleSheet("background: #0F172A; border: none; color: #F8FAFC; font-size: 13px;")

        d_layout.addWidget(d_title)
        d_layout.addWidget(self.desc_text)

        left_panel.addWidget(preview_card)
        left_panel.addWidget(desc_card, stretch=1)

        # Right Panel (OCR Text & Detected UI Elements Table)
        right_panel = QVBoxLayout()

        ocr_card = QFrame()
        ocr_card.setProperty("class", "CardWidget")
        o_layout = QVBoxLayout(ocr_card)

        o_title = QLabel("Extracted OCR Text")
        o_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #F59E0B;")

        self.ocr_text = QTextEdit()
        self.ocr_text.setReadOnly(True)
        self.ocr_text.setPlaceholderText("OCR extracted text...")
        self.ocr_text.setStyleSheet("background: #0F172A; border: none; color: #E2E8F0; font-size: 12px;")

        o_layout.addWidget(o_title)
        o_layout.addWidget(self.ocr_text)

        elem_card = QFrame()
        elem_card.setProperty("class", "CardWidget")
        e_layout = QVBoxLayout(elem_card)

        e_title = QLabel("Detected UI Elements")
        e_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #10B981;")

        self.elem_table = QTableWidget(0, 3)
        self.elem_table.setHorizontalHeaderLabels(["Type", "Label", "Bounds"])
        self.elem_table.setStyleSheet("QTableWidget { background: #0F172A; color: white; border: none; gridline-color: #334155; }")

        e_layout.addWidget(e_title)
        e_layout.addWidget(self.elem_table)

        right_panel.addWidget(ocr_card)
        right_panel.addWidget(elem_card, stretch=1)

        content_layout.addLayout(left_panel, stretch=1)
        content_layout.addLayout(right_panel, stretch=1)

        layout.addLayout(header_layout)
        layout.addLayout(btn_layout)
        layout.addLayout(content_layout, stretch=1)

    def display_context(self, context: VisualContext):
        """Populate UI dashboard with VisualContext data."""
        self.desc_text.setText(f"App: {context.app_name}\nWindow: {context.window_title}\n\nDescription:\n{context.description}")

        if context.detected_errors:
            self.desc_text.append("\nDetected Errors:\n" + "\n".join([f"• {e}" for e in context.detected_errors]))

        self.ocr_text.setText(context.ocr.full_text)

        # Populate Elements Table
        self.elem_table.setRowCount(len(context.elements))
        for idx, elem in enumerate(context.elements):
            self.elem_table.setItem(idx, 0, QTableWidgetItem(elem.element_type.value))
            self.elem_table.setItem(idx, 1, QTableWidgetItem(elem.label))
            bounds_str = f"({elem.bounds.x1}, {elem.bounds.y1}) to ({elem.bounds.x2}, {elem.bounds.y2})"
            self.elem_table.setItem(idx, 2, QTableWidgetItem(bounds_str))

        # Thumbnail Preview
        pixmap = QPixmap(context.screenshot.file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_lbl.setPixmap(scaled)

    def _on_analyze_window(self):
        context = self.vision_manager.analyze_active_window()
        self.display_context(context)

    def _on_analyze_screen(self):
        context = self.vision_manager.analyze_screen()
        self.display_context(context)

    def _on_open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            context = self.vision_manager.analyze_image_file(file_path)
            self.display_context(context)
