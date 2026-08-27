"""
Animated Custom Voice Orb Widget (Stitch Design System Integration).
Primary visual motif of the ASTRA assistant ("Living Light" radial gradient sphere with expanding outer rings).
"""

import math
from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget
from src.ui.theme.tokens import DARK_PALETTE
from src.voice.models import VoiceState


class VoiceOrb(QWidget):
    """Custom painted animated orb visualizer for ASTRA voice state."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self.state = VoiceState.IDLE
        self._pulse_phase = 0.0

        # Animation timer (~30 fps)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_animate)
        self._timer.start(30)

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
        step = 0.08 if self.state in (VoiceState.LISTENING, VoiceState.SPEAKING) else 0.03
        self._pulse_phase = (self._pulse_phase + step) % (2 * math.pi)
        self.update()

    def _get_state_colors(self) -> tuple[QColor, QColor]:
        p = DARK_PALETTE
        if self.state == VoiceState.LISTENING:
            return QColor(p.orb_listening), QColor(p.accent_violet)
        elif self.state == VoiceState.PROCESSING:
            return QColor(p.orb_processing), QColor(p.accent_tertiary)
        elif self.state == VoiceState.SPEAKING:
            return QColor(p.orb_speaking), QColor(p.accent_violet_container)
        elif self.state == VoiceState.ERROR:
            return QColor(p.orb_error), QColor("#ef4444")
        else:
            return QColor(p.orb_idle), QColor(p.bg_card_high)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        center_x = w / 2.0
        center_y = h / 2.0
        base_radius = min(w, h) / 3.2

        c_primary, c_outer = self._get_state_colors()

        # Dynamic pulse offset based on state
        pulse_scale = 1.0 + (math.sin(self._pulse_phase) * (0.08 if self.state != VoiceState.IDLE else 0.03))
        radius = base_radius * pulse_scale

        # 1. Outer Diffused Radial Halo
        halo_gradient = QRadialGradient(center_x, center_y, radius * 1.8)
        c_halo = QColor(c_primary)
        c_halo.setAlpha(60 if self.state != VoiceState.IDLE else 30)
        halo_gradient.setColorAt(0.0, c_halo)
        halo_gradient.setColorAt(0.7, QColor(c_primary.red(), c_primary.green(), c_primary.blue(), 15))
        halo_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(halo_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(center_x - radius * 1.8, center_y - radius * 1.8, radius * 3.6, radius * 3.6))

        # 2. Main Glowing Core Sphere
        core_gradient = QRadialGradient(center_x - radius * 0.2, center_y - radius * 0.2, radius * 1.2)
        c_center = QColor(c_primary)
        c_center.setAlpha(255)
        core_gradient.setColorAt(0.0, QColor("#FFFFFF"))
        core_gradient.setColorAt(0.4, c_center)
        core_gradient.setColorAt(1.0, c_outer)

        painter.setBrush(core_gradient)
        painter.drawEllipse(QRectF(center_x - radius, center_y - radius, radius * 2.0, radius * 2.0))

        # 3. Plus Jakarta Sans State Label
        painter.setPen(QColor("#e2e2e3"))
        font = QFont("Plus Jakarta Sans", 11, QFont.Bold)
        painter.setFont(font)
        state_text = self.state.value.capitalize()
        painter.drawText(QRectF(0, center_y + radius + 10, w, 30), Qt.AlignCenter, state_text)
