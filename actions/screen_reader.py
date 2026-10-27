"""
actions/screen_reader.py - Screen Capture and Intelligent Content Reader.

Allows Miss Minutes and Jarvis to:
1. Capture the user's screen cleanly via PySide6 or Windows GDI.
2. Identify the active foreground application / browser tab.
3. Extract visible text using Windows built-in OCR / Windows.Media.Ocr.
4. Support Gemini multimodal visual analysis when available.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_foreground_window_title() -> str:
    """Returns the title of the currently focused / active desktop window."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except Exception as exc:
        logger.debug("Failed to get foreground window: %s", exc)
        return ""


def capture_screen_image() -> Optional[str]:
    """
    Captures the primary monitor screen and saves it as a temporary PNG.
    Returns the path to the saved image file, or None if failed.
    """
    try:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            pix = screen.grabWindow(0)
            if not pix.isNull():
                tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tf_path = tf.name
                tf.close()
                pix.save(tf_path, "PNG")
                return tf_path
    except Exception as exc:
        logger.debug("PySide6 screen grab attempt failed: %s", exc)

    # Fallback via PowerShell screen copy
    try:
        tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tf_path = tf.name
        tf.close()
        ps_cmd = (
            f"[Reflection.Assembly]::LoadWithPartialName('System.Drawing') | Out-Null; "
            f"$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            f"$bmp = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height; "
            f"$g = [Drawing.Graphics]::FromImage($bmp); "
            f"$g.CopyFromScreen($bounds.Location, [Drawing.Point]::Empty, $bounds.Size); "
            f"$bmp.Save('{tf_path}', [Drawing.Imaging.ImageFormat]::Png); "
            f"$g.Dispose(); $bmp.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True, timeout=5)
        if os.path.exists(tf_path) and os.path.getsize(tf_path) > 1000:
            return tf_path
    except Exception as exc:
        logger.warning("Fallback screen grab failed: %s", exc)

    return None


def ocr_image_windows(image_path: str) -> str:
    """
    Runs Windows.Media.Ocr on the captured screenshot via PowerShell.
    Extracts visible text cleanly and rapidly without third-party external dependencies.
    """
    if not image_path or not os.path.exists(image_path):
        return ""

    escaped_path = image_path.replace("'", "''")
    ps_script = f"""
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

    async function Do-Ocr {{
        $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync('{escaped_path}').AsTask().GetAwaiter().GetResult()
        $stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).AsTask().GetAwaiter().GetResult()
        $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).AsTask().GetAwaiter().GetResult()
        $bmp = $decoder.GetSoftwareBitmapAsync().AsTask().GetAwaiter().GetResult()
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
        if (-not $engine) {{
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
        }}
        $res = $engine.RecognizeAsync($bmp).AsTask().GetAwaiter().GetResult()
        return $res.Text
    }}
    Do-Ocr
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return proc.stdout.strip()
    except Exception as exc:
        logger.warning("Windows OCR execution failed: %s", exc)
        return ""


class ScreenReaderService:
    """Service to capture and analyze screen contents for Miss Minutes & Jarvis."""

    def __init__(self, ai_provider: Optional[Any] = None):
        self._ai_provider = ai_provider

    def read_screen(self, user_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Reads the user's screen, identifies active context, extracts text,
        and generates an insightful answer in modern Telugu + English.
        """
        active_window = get_foreground_window_title()
        image_path = capture_screen_image()

        ocr_text = ""
        if image_path:
            ocr_text = ocr_image_windows(image_path)
            # Cleanup temp file
            try:
                os.remove(image_path)
            except OSError:
                pass

        # Prepare summary of visible content
        cleaned_text = " ".join(ocr_text.split())[:1200]
        context_desc = f"Active window: '{active_window}'."
        if cleaned_text:
            context_desc += f" Visible screen text: {cleaned_text}"

        return {
            "active_window": active_window,
            "extracted_text": cleaned_text,
            "context_description": context_desc,
        }
