# -*- mode: python ; coding: utf-8 -*-
"""
packaging/MissMinutes.spec - Production PyInstaller Specification for Miss Minutes.

Build Mode: onedir
Target Platform: Windows 10/11 (64-bit)
Window Mode: --windowed (console=False)
Icon: packaging/MissMinutes.ico
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Determine project root cleanly
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "main.py")
ICO_PATH = os.path.join(PROJECT_ROOT, "packaging", "MissMinutes.ico")
PNG_PATH = os.path.join(PROJECT_ROOT, "packaging", "MissMinutes.png")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env.example")

# Hidden imports to ensure dynamic reflection/submodule loading resolves cleanly
hidden_imports = [
    # PySide6 Qt bindings
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    # Pydantic v2
    "pydantic",
    # AI SDKs
    "google.genai",
    # Core Application Submodules
    "actions",
    "actions.apps",
    "actions.registry",
    "actions.schemas",
    "actions.windows_executor",
    "actions.mock_executor",
    "agents",
    "agents.base",
    "agents.bus",
    "agents.context",
    "agents.message",
    "agents.miss_minutes_agent",
    "agents.jarvis_agent",
    "agents.audit_log",
    "agents.personalities",
    "ai",
    "ai.provider",
    "ai.gemini",
    "ai.groq",
    "ai.mock_provider",
    "ai.provider_router",
    "app",
    "app.main",
    "app.pipeline",
    "config",
    "config.settings",
    "config.persistence",
    "intents",
    "intents.extractor",
    "intents.parser",
    "security",
    "security.permissions",
    "security.validator",
    "security.audit",
    "ui",
    "ui.overlay",
    "ui.controller",
    "ui.state_machine",
    "voice",
    "voice.service",
    "voice.stt",
    "voice.tts",
    "voice.wake",
    "voice.microphone",
    "voice.device",
    "voice.audio_player",
    # Authoritative Single Jarvis
    "jarvis",
    "jarvis_brain",
    "jarvis_actions",
    "jarvis_voice",
    "jarvis_market",
]

# Collect any additional submodules
hidden_imports += collect_submodules("pydantic")

# Collect package data files
datas = [
    (ICO_PATH, "packaging"),
    (PNG_PATH, "packaging"),
    (ENV_PATH, "."),
]

try:
    datas += collect_data_files("google.genai")
except Exception:
    pass

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "_pytest",
        "unittest",
        "IPython",
        "tkinter",
        "matplotlib",
        "numpy.testing",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MissMinutes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed GUI mode (no persistent terminal window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICO_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MissMinutes",
)
