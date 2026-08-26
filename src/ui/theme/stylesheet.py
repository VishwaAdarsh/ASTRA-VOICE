"""
Qt QSS Stylesheet Generator for ASTRA UI.
"""

from src.ui.theme.tokens import ColorPalette


def generate_stylesheet(p: ColorPalette) -> str:
    """Generate global Qt QSS stylesheet string for the given palette."""
    return f"""
    QMainWindow, QWidget {{
        background-color: {p.bg_main};
        color: {p.text_primary};
        font-family: 'Segoe UI', 'Segoe UI Variable', system-ui, sans-serif;
        font-size: 13px;
    }}

    /* Sidebar Navigation */
    #Sidebar {{
        background-color: {p.bg_sidebar};
        border-right: 1px solid {p.border};
    }}

    #SidebarButton {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        text-align: left;
        font-size: 14px;
        font-weight: 500;
    }}

    #SidebarButton:hover {{
        background-color: {p.bg_hover};
        color: {p.text_primary};
    }}

    #SidebarButton:checked {{
        background-color: {p.bg_card};
        color: {p.accent_blue};
        font-weight: 600;
    }}

    /* Cards & Containers */
    .CardWidget {{
        background-color: {p.bg_card};
        border: 1px solid {p.border};
        border-radius: 12px;
        padding: 16px;
    }}

    /* Input Controls */
    QLineEdit, QTextEdit {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 10px 14px;
        selection-background-color: {p.accent_blue};
    }}

    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {p.accent_blue};
    }}

    /* Primary Action Buttons */
    QPushButton {{
        background-color: {p.accent_blue};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 10px 18px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: {p.bg_hover};
        color: {p.text_primary};
    }}

    QPushButton:pressed {{
        opacity: 0.8;
    }}

    /* Secondary / Icon Buttons */
    QPushButton#IconButton {{
        background-color: {p.bg_card};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 8px;
    }}

    QPushButton#IconButton:hover {{
        background-color: {p.bg_hover};
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
        min-height: 20px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p.text_muted};
    }}

    /* Footer Status Bar */
    #StatusBar {{
        background-color: {p.bg_sidebar};
        border-top: 1px solid {p.border};
        color: {p.text_secondary};
        font-size: 12px;
    }}
    """
