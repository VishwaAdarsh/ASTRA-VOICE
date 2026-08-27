"""
ASTRA Design Tokens (Stitch Design System Integration).
Official Design Tokens extracted from Google Stitch Project: Astra Voice Assistant Design System (projects/2218653904695225469).
Theme Philosophy: "Calm Presence" (Minimalism + Glassmorphism + Dark-Mode-First).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    """Color palette tokens aligned with Stitch 'Calm Presence' design system."""

    bg_main: str                  # #121415 Deep Dark Canvas
    bg_card: str                  # #1e2021 Surface Container
    bg_card_low: str              # #1a1c1d Surface Container Low
    bg_card_high: str             # #282a2b Surface Container High
    bg_card_highest: str          # #333536 Surface Container Highest
    bg_sidebar: str               # #0c0e0f Surface Container Lowest
    bg_hover: str                 # #282a2b Surface Container High
    bg_input: str                 # #1a1c1d Surface Container Low
    border: str                   # #484555 Outline Variant
    border_focus: str             # #7c5cfc Primary Violet Accent
    text_primary: str             # #e2e2e3 On Surface
    text_secondary: str           # #c9c4d8 On Surface Variant
    text_muted: str               # #938ea1 Outline Muted
    accent_violet: str            # #7c5cfc Living Violet Light Primary
    accent_violet_container: str  # #947dff Primary Container
    accent_tertiary: str          # #cebdff Soft Violet Accent
    accent_emerald: str           # #34d399 Emerald Green (Success)
    accent_amber: str             # #fbbf24 Amber Yellow (Warning)
    accent_rose: str              # #ffb4ab Soft Rose (Error)
    orb_idle: str                 # #7c5cfc 20% opacity violet pulse
    orb_listening: str            # #947dff Living violet glow
    orb_processing: str           # #cebdff Rotating gradient blob
    orb_speaking: str             # #b794fc Pulsing waveform
    orb_error: str                # #ffb4ab Soft rose glow


DARK_PALETTE = ColorPalette(
    bg_main="#121415",
    bg_card="#1e2021",
    bg_card_low="#1a1c1d",
    bg_card_high="#282a2b",
    bg_card_highest="#333536",
    bg_sidebar="#0c0e0f",
    bg_hover="#282a2b",
    bg_input="#1a1c1d",
    border="#484555",
    border_focus="#7c5cfc",
    text_primary="#e2e2e3",
    text_secondary="#c9c4d8",
    text_muted="#938ea1",
    accent_violet="#7c5cfc",
    accent_violet_container="#947dff",
    accent_tertiary="#cebdff",
    accent_emerald="#34d399",
    accent_amber="#fbbf24",
    accent_rose="#ffb4ab",
    orb_idle="#7c5cfc",
    orb_listening="#947dff",
    orb_processing="#cebdff",
    orb_speaking="#b794fc",
    orb_error="#ffb4ab",
)

LIGHT_PALETTE = ColorPalette(
    bg_main="#121415",            # Stitch design system is strictly Dark Mode First
    bg_card="#1e2021",
    bg_card_low="#1a1c1d",
    bg_card_high="#282a2b",
    bg_card_highest="#333536",
    bg_sidebar="#0c0e0f",
    bg_hover="#282a2b",
    bg_input="#1a1c1d",
    border="#484555",
    border_focus="#7c5cfc",
    text_primary="#e2e2e3",
    text_secondary="#c9c4d8",
    text_muted="#938ea1",
    accent_violet="#7c5cfc",
    accent_violet_container="#947dff",
    accent_tertiary="#cebdff",
    accent_emerald="#34d399",
    accent_amber="#fbbf24",
    accent_rose="#ffb4ab",
    orb_idle="#7c5cfc",
    orb_listening="#947dff",
    orb_processing="#cebdff",
    orb_speaking="#b794fc",
    orb_error="#ffb4ab",
)
