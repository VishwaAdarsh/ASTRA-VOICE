"""
ASTRA Design Tokens.
Defines cohesive color palettes, typography scales, spacing metrics, and radiuses.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    """Color palette tokens for Dark and Light themes."""

    bg_main: str
    bg_card: str
    bg_sidebar: str
    bg_hover: str
    bg_input: str
    border: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent_blue: str
    accent_emerald: str
    accent_amber: str
    accent_rose: str
    orb_idle: str
    orb_listening: str
    orb_processing: str
    orb_speaking: str
    orb_error: str


DARK_PALETTE = ColorPalette(
    bg_main="#0F172A",       # Slate 900
    bg_card="#1E293B",       # Slate 800
    bg_sidebar="#020617",    # Slate 950
    bg_hover="#334155",      # Slate 700
    bg_input="#1E293B",      # Slate 800
    border="#334155",        # Slate 700
    text_primary="#F8FAFC",  # Slate 50
    text_secondary="#94A3B8",# Slate 400
    text_muted="#64748B",    # Slate 500
    accent_blue="#38BDF8",   # Sky 400
    accent_emerald="#10B981",# Emerald 500
    accent_amber="#F59E0B",  # Amber 500
    accent_rose="#F43F5E",   # Rose 500
    orb_idle="#38BDF8",      # Sky Blue
    orb_listening="#10B981", # Emerald Green
    orb_processing="#F59E0B",# Amber Yellow
    orb_speaking="#A855F7",  # Purple
    orb_error="#F43F5E",     # Rose Red
)

LIGHT_PALETTE = ColorPalette(
    bg_main="#F8FAFC",       # Slate 50
    bg_card="#FFFFFF",       # White
    bg_sidebar="#F1F5F9",    # Slate 100
    bg_hover="#E2E8F0",      # Slate 200
    bg_input="#FFFFFF",      # White
    border="#CBD5E1",        # Slate 300
    text_primary="#0F172A",  # Slate 900
    text_secondary="#475569",# Slate 600
    text_muted="#94A3B8",    # Slate 400
    accent_blue="#0284C7",   # Sky 600
    accent_emerald="#059669",# Emerald 600
    accent_amber="#D97706",  # Amber 600
    accent_rose="#E11D48",   # Rose 600
    orb_idle="#0284C7",
    orb_listening="#059669",
    orb_processing="#D97706",
    orb_speaking="#7E22CE",
    orb_error="#E11D48",
)
