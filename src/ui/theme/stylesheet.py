"""
Qt QSS Stylesheet Generator for ASTRA UI (Stitch Design System Integration).
Generates Qt QSS matching the Google Stitch "Calm Presence" aesthetic.
"""

from src.ui.theme.tokens import ColorPalette


def generate_stylesheet(p: ColorPalette) -> str:
    """Generate global Qt QSS stylesheet string for the Stitch design system."""
    return f"""
    QMainWindow, QWidget {{
        background-color: {p.bg_main};
        color: {p.text_primary};
        font-family: 'Plus Jakarta Sans', 'Segoe UI', system-ui, sans-serif;
        font-size: 14px;
        line-height: 1.5;
    }}

    /* Sidebar Navigation (Stitch Glassmorphism Container) */
    #Sidebar {{
        background-color: {p.bg_sidebar};
        border-right: 1px solid {p.border};
        padding: 16px 8px;
    }}

    #SidebarButton {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-radius: 20px;
        padding: 12px 18px;
        text-align: left;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 4px;
    }}

    #SidebarButton:hover {{
        background-color: {p.bg_hover};
        color: {p.text_primary};
    }}

    #SidebarButton:checked {{
        background-color: {p.bg_card};
        color: {p.accent_violet};
        font-weight: 600;
        border: 1px solid rgba(124, 92, 254, 0.35);
    }}

    /* Cards & Containers (Stitch Glassmorphic Tonal Surface) */
    .CardWidget {{
        background-color: {p.bg_card};
        border: 1px solid {p.border};
        border-radius: 16px;
        padding: 20px;
    }}

    /* Input Controls (Stitch Pill Rounded Fields) */
    QLineEdit, QTextEdit {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 28px;
        padding: 14px 22px;
        font-size: 15px;
        selection-background-color: {p.accent_violet};
    }}

    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {p.accent_violet};
        background-color: {p.bg_card};
    }}

    /* Primary Action Buttons (Stitch Pill Buttons) */
    QPushButton {{
        background-color: {p.accent_violet};
        color: #FFFFFF;
        border: none;
        border-radius: 28px;
        padding: 12px 24px;
        font-size: 15px;
        font-weight: 600;
        min-height: 44px;
    }}

    QPushButton:hover {{
        background-color: {p.accent_violet_container};
        color: #FFFFFF;
    }}

    QPushButton:pressed {{
        background-color: {p.accent_violet};
        opacity: 0.9;
    }}

    /* Secondary / Icon Buttons */
    QPushButton#IconButton {{
        background-color: {p.bg_card};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 20px;
        padding: 10px;
        min-height: 40px;
    }}

    QPushButton#IconButton:hover {{
        background-color: {p.bg_hover};
        border-color: {p.accent_violet};
    }}

    /* Quick Action Chips (Stitch Rounded Pill Chips) */
    QPushButton#ChipButton {{
        background-color: {p.bg_card_high};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 20px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }}

    QPushButton#ChipButton:hover {{
        background-color: {p.bg_card_highest};
        border-color: {p.accent_violet};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {p.bg_main};
        width: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: {p.border};
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p.text_muted};
    }}

    /* Footer Status Bar */
    #StatusBar {{
        background-color: {p.bg_sidebar};
        border-top: 1px solid {p.border};
        color: {p.text_secondary};
        font-size: 13px;
        padding: 6px 16px;
    }}
    """
