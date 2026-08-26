"""
Animated Custom Voice Orb Widget.
Uses QPainter to render smooth pulsating glowing rings representing ASTRA voice states.
"""

import math
from PySide6.QtCore import QPropertyAnimation, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget
from src.ui.theme.tokens import DARK_PALETTE
from src.voice.models import VoiceState


class VoiceOrb(QWidget):
    """Custom painted animated orb visualizer for voice state."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self.state = VoiceState.IDLE
        self._pulse_phase = 0.0

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_animate)
        self._timer.start(30)  # ~33 fps

    def set_state(self, state: VoiceState | str) -> None:
        """Update voice state and refresh visual rendering."""
        if isinstance(state, str):
            try:
                state = VoiceState(state.upper())
            except ValueError:
                state = VoiceState.IDLE

        self.state = state
        self.update()

    def _on_animate(self) -> None:
        """Pulse animation frame callback."""
        self._pulse_phase = (self._pulse_phase + 0.05) % (2 * math.pi)
        self.update()

    def _get_state_color(self) -> QColor:
        p = DARK_PALETTE
        if self.state == VoiceState.LISTENING:
            return QColor(p.orb_listening)
        elif self.state == VoiceState.PROCESSING:
            return QColor(p.orb_processing)
        elif self.state == VoiceState.SPEAKING:
            return QColor(p.orb_speaking)
        elif self.state == VoiceState.ERROR:
            return QColor(p.orb_error)
        else:
            return QColor(p.orb_idle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0
        base_radius = min(width, height) / 3.0

        base_color = self._get_state_color()

        # Dynamic pulse offset
        pulse = math.sin(self._pulse_phase) * 4.0 if self.state != VoiceState.IDLE else 0.0
        radius = base_radius + pulse

        # 1. Outer Soft Glow Ring
        glow_color = QColor(base_color)
        glow_color.setAlpha(40)
        painter.setBrush(glow_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(center_x - radius - 12, center_y - radius - 12, (radius + 12) * 2, (radius + 12) * 2))

        # 2. Main Central Orb Circle
        painter.setBrush(base_color)
        painter.drawEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))

        # 3. State Text Label in center
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        state_label = self.state.value.capitalize()
        painter.drawText(QRectF(0, 0, width, height), Qt.AlignCenter, state_label)
