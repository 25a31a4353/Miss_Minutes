"""
config/persistence.py - Window Position Persistence & Multi-Monitor Safety.

Guarantees:
- Safely stores and restores window geometry in ~/.miss_minutes/config.json.
- Verifies screen boundaries across all connected monitors.
- Never crashes on missing, unreadable, or corrupted configuration files.
- Never stores credentials, tokens, or audio data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication, QScreen


def get_default_config_path() -> Path:
    """Returns the default configuration path in the user's profile."""
    base_dir = Path.home() / ".miss_minutes"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "config.json"


def load_window_positions(
    config_path: Optional[Path | str] = None,
) -> Dict[str, Dict[str, int]]:
    """
    Loads saved window positions. Returns an empty dict if the file is missing or corrupted.
    """
    path = Path(config_path) if config_path else get_default_config_path()
    if not path.is_file():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError, ValueError):
        # Fail safe: corrupted files must never crash the app
        pass

    return {}


def save_window_positions(
    overlay_pos: Optional[QPoint | Tuple[int, int]] = None,
    controller_pos: Optional[QPoint | Tuple[int, int]] = None,
    reduced_motion: Optional[bool] = None,
    config_path: Optional[Path | str] = None,
) -> bool:
    """
    Persists window positions and safe UI preferences to config.json.
    """
    path = Path(config_path) if config_path else get_default_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = load_window_positions(path)

        if overlay_pos is not None:
            ox = overlay_pos.x() if isinstance(overlay_pos, QPoint) else overlay_pos[0]
            oy = overlay_pos.y() if isinstance(overlay_pos, QPoint) else overlay_pos[1]
            existing["overlay"] = {"x": int(ox), "y": int(oy)}

        if controller_pos is not None:
            cx = controller_pos.x() if isinstance(controller_pos, QPoint) else controller_pos[0]
            cy = controller_pos.y() if isinstance(controller_pos, QPoint) else controller_pos[1]
            existing["controller"] = {"x": int(cx), "y": int(cy)}

        if reduced_motion is not None:
            existing["reduced_motion"] = bool(reduced_motion)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        return True
    except (OSError, TypeError, ValueError):
        return False


def clamp_to_screen_boundaries(
    pos: QPoint,
    window_width: int,
    window_height: int,
    padding: int = 20,
) -> QPoint:
    """
    Ensures that the requested window coordinates are fully visible on at least one
    active monitor. If the saved coordinates lie outside all monitors (e.g. after a display
    is disconnected), clamps safely to the primary monitor workspace.
    """
    screens = QGuiApplication.screens()
    if not screens:
        return pos

    window_rect = QRect(pos.x(), pos.y(), window_width, window_height)

    # 1. Check if the window is substantially visible on any active monitor
    for screen in screens:
        screen_geom = screen.availableGeometry()
        if screen_geom.intersects(window_rect):
            # Clamp within this screen
            clamped_x = max(
                screen_geom.left() + padding,
                min(pos.x(), screen_geom.right() - window_width - padding),
            )
            clamped_y = max(
                screen_geom.top() + padding,
                min(pos.y(), screen_geom.bottom() - window_height - padding),
            )
            return QPoint(int(clamped_x), int(clamped_y))

    # 2. Window is completely off-screen (disconnected monitor). Fall back to primary screen.
    primary = QGuiApplication.primaryScreen() or screens[0]
    p_geom = primary.availableGeometry()
    default_x = p_geom.right() - window_width - 40
    default_y = p_geom.top() + 60
    return QPoint(int(default_x), int(default_y))
