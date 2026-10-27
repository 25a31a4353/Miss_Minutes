"""
ui/theme.py - Visual Theme & Design Tokens for Miss Minutes.

Palette:
- Original retro-futuristic timeline & clock motifs.
- Warm amber, gold, vintage cream, and espresso tones.
- High contrast, intentional spacing, readable typography.
"""

from PySide6.QtGui import QColor, QFont


class Theme:
    """Color tokens, fonts, and stylesheets for Miss Minutes UI."""

    # Brand & Accent Colors
    AMBER_PRIMARY = QColor("#f59e0b")
    AMBER_LIGHT = QColor("#fbbf24")
    AMBER_DARK = QColor("#b45309")
    CREAM_FACE = QColor("#fbf6ec")
    CREAM_DARK = QColor("#ede2cb")
    VINTAGE_BORDER = QColor("#78350f")

    # Dark Backgrounds
    BG_DARK = QColor("#141210")
    BG_CARD = QColor("#221c17")
    BG_HOVER = QColor("#302720")
    TEXT_MAIN = QColor("#fdf8f0")
    TEXT_MUTED = QColor("#a89f91")
    BORDER_SUBTLE = QColor("#44382d")

    # State Status Colors
    STATE_OFFLINE = QColor("#645d56")
    STATE_ONLINE = QColor("#10b981")
    STATE_WORKING = QColor("#f59e0b")
    STATE_SUCCESS = QColor("#10b981")
    STATE_ERROR = QColor("#ef4444")
    STATE_BLOCKED = QColor("#dc2626")

    # Font definitions
    FONT_FAMILY = "Segoe UI"
    FONT_MONO = "Consolas"

    @classmethod
    def get_title_font(cls, size: int = 12) -> QFont:
        return QFont(cls.FONT_FAMILY, size, QFont.Weight.Bold)

    @classmethod
    def get_body_font(cls, size: int = 9) -> QFont:
        return QFont(cls.FONT_FAMILY, size, QFont.Weight.Normal)

    @classmethod
    def get_mono_font(cls, size: int = 9) -> QFont:
        return QFont(cls.FONT_MONO, size, QFont.Weight.DemiBold)

    @classmethod
    def controller_stylesheet(cls) -> str:
        """Qt StyleSheet for the refined control panel."""
        return """
        QWidget#ControllerWindow {
            background-color: #171310;
            border: 2px solid #4a3c2e;
            border-radius: 14px;
        }
        QLabel {
            color: #f7f1e6;
            font-family: 'Segoe UI', sans-serif;
        }
        QLabel#HeaderTitle {
            font-size: 14px;
            font-weight: 700;
            color: #fbbf24;
            letter-spacing: 0.6px;
        }
        QLabel#HeaderStatusDot {
            font-size: 11px;
            font-weight: 600;
        }
        QFrame#StatusCard {
            background-color: #221a14;
            border: 1px solid #423425;
            border-radius: 10px;
            padding: 8px 10px;
        }
        QLabel#StateBadge {
            font-family: 'Consolas', monospace;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 5px;
        }
        QPushButton#PowerButton {
            font-family: 'Segoe UI', sans-serif;
            font-size: 12px;
            font-weight: 700;
            border-radius: 8px;
            padding: 9px 16px;
            border: none;
            letter-spacing: 0.4px;
        }
        QPushButton#PowerButton[online="true"] {
            background-color: #d97706;
            color: #ffffff;
        }
        QPushButton#PowerButton[online="true"]:hover {
            background-color: #b45309;
        }
        QPushButton#PowerButton[online="false"] {
            background-color: #059669;
            color: #ffffff;
        }
        QPushButton#PowerButton[online="false"]:hover {
            background-color: #047857;
        }
        QPushButton#StateGridBtn {
            background-color: #271f18;
            color: #f7f1e6;
            border: 1px solid #423425;
            border-radius: 6px;
            padding: 6px 4px;
            font-size: 10px;
            font-weight: 600;
        }
        QPushButton#StateGridBtn:hover {
            background-color: #3d3023;
            border-color: #f59e0b;
            color: #fbbf24;
        }
        QPushButton#StateGridBtn:disabled {
            background-color: #1a1511;
            color: #574b3e;
            border-color: #2b221a;
        }
        QPushButton#BottomToolBtn {
            background-color: #221b15;
            color: #d6ccbe;
            border: 1px solid #3d3124;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 10px;
            font-weight: 600;
        }
        QPushButton#BottomToolBtn:hover {
            background-color: #382c20;
            color: #f59e0b;
            border-color: #f59e0b;
        }
        QPushButton#CloseButton {
            background-color: transparent;
            color: #a89a88;
            border: none;
            font-size: 13px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
        }
        QPushButton#CloseButton:hover {
            background-color: #7f1d1d;
            color: #ffffff;
        }
        """
