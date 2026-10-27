"""
main.py - Primary Unified Application Entry Point for Miss Minutes + Existing Jarvis.

PHASE 8: PRODUCTION CONSOLIDATION & DESKTOP READINESS.

This is the single primary entry point for the entire application:
    python main.py

User Experience:
- Double-click or single command launches the complete unified system:
  Miss Minutes Mascot UI + Voice Pipeline + Gemini Intelligence +
  Existing Jarvis Co-Pilot + Security Validator + Real Windows Capabilities.
- No separate background consoles or multiple processes needed.

CLI Options:
    python main.py                # Standard desktop launch (IDLE or saved state)
    python main.py --offline      # Launch forced into OFFLINE state
    python main.py --diagnostics  # Run headless production diagnostics and exit
    python main.py --jarvis       # Run Jarvis developer mode
    python main.py --version      # Print system version info
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Suppress harmless HuggingFace Windows symlink cache warning
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

APP_VERSION = "2.5.0"
APP_TITLE = "Miss Minutes & Jarvis AI Desktop Assistant"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def run_diagnostics() -> int:
    """Runs a fast headless diagnostic check of all consolidated components."""
    output_lines: list[str] = []

    def log_line(msg: str = "") -> None:
        output_lines.append(msg)
        try:
            print(msg)
        except Exception:
            pass

    log_line("=" * 65)
    log_line(f" {APP_TITLE}")
    log_line(f" Version: {APP_VERSION} | Production Diagnostics")
    log_line("=" * 65)

    checks_passed = 0
    total_checks = 6

    # 1. Check Settings & Persistence
    try:
        from config.settings import load_settings
        from config.persistence import load_window_positions
        settings = load_settings()
        prefs = load_window_positions()
        log_line(f"[OK] 1/6 Config & Persistence: App='{settings.app_name}', StartState={settings.start_state}")
        checks_passed += 1
    except Exception as e:
        log_line(f"[FAIL] 1/6 Config & Persistence: {e}")

    # 2. Check Security Validator
    try:
        from security.validator import SecurityValidator
        from security.permissions import SecurityDecision
        from actions.schemas import CapabilityRequest, CapabilityType
        validator = SecurityValidator()
        # Verify default-deny and dangerous pattern blocking
        bad_req = CapabilityRequest(
            capability=CapabilityType.OPEN_APP,
            parameters={"app_name": "powershell.exe"},
        )
        res = validator.validate_capability_request(bad_req, is_assistant_online=True)
        assert res.decision == SecurityDecision.DENY, f"Expected DENY, got {res.decision}"
        log_line("[OK] 2/6 Security Validator: Default-DENY & dangerous pattern blocking verified")
        checks_passed += 1
    except Exception as e:
        log_line(f"[FAIL] 2/6 Security Validator: {e}")

    # 3. Check Authoritative Single Jarvis
    try:
        from jarvis import Jarvis, get_jarvis
        jarvis_inst = get_jarvis()
        assert isinstance(jarvis_inst, Jarvis)
        # Verify COUNT(JARVIS_IMPLEMENTATIONS) = 1
        from agents.jarvis_agent import Jarvis as ProxyJarvis
        assert ProxyJarvis is Jarvis
        log_line(f"[OK] 3/6 Single Jarvis Invariant: Verified authoritative singleton {jarvis_inst.name}")
        checks_passed += 1
    except Exception as e:
        log_line(f"[FAIL] 3/6 Single Jarvis Invariant: {e}")

    # 4. Check AI Providers & Failover
    try:
        import jarvis_brain
        provider = jarvis_brain.get_ai_provider()
        provider_name = provider.provider_name if hasattr(provider, "provider_name") else type(provider).__name__
        log_line(f"[OK] 4/6 AI Intelligence Layer: Provider='{provider_name}'")
        checks_passed += 1
    except Exception as e:
        log_line(f"[FAIL] 4/6 AI Intelligence Layer: {e}")

    # 5. Check Windows Capability Registry & Apps
    try:
        from actions.apps import APPROVED_APPLICATIONS, is_safe_url
        from actions.registry import ActionRegistry
        reg = ActionRegistry()
        capabilities = reg.list_capabilities()
        apps = APPROVED_APPLICATIONS
        assert "notepad" in apps
        is_safe, _ = is_safe_url("https://www.youtube.com")
        assert is_safe
        log_line(f"[OK] 5/6 Windows Capabilities: {len(capabilities)} registered, {len(apps)} approved apps")
        checks_passed += 1
    except Exception as e:
        log_line(f"[FAIL] 5/6 Windows Capabilities: {e}")

    # 6. Check Dual-Agent Message Bus
    try:
        from agents import AgentMessageBus, SharedBoundedContext, MissMinutesAgent
        from ui.state_machine import AppStateMachine, AssistantState
        sm = AppStateMachine(initial_state=AssistantState.IDLE)
        ctx = SharedBoundedContext(max_turns=10)
        bus = AgentMessageBus(state_machine=sm, context=ctx)
        mm = MissMinutesAgent()
        bus.register_agent(mm)
        bus.register_agent(jarvis_inst)
        log_line("[OK] 6/6 Dual-Agent Foundation: Miss Minutes & Jarvis registered on message bus")
        checks_passed += 1
    except Exception as e:
        log_line(f"[FAIL] 6/6 Dual-Agent Foundation: {e}")

    log_line("-" * 65)
    log_line(f"Diagnostics Result: {checks_passed}/{total_checks} subsystems operational.")
    log_line("=" * 65)

    # Persist diagnostics log to user data directory
    try:
        from pathlib import Path
        diag_log = Path.home() / ".miss_minutes" / "diagnostics.log"
        diag_log.parent.mkdir(parents=True, exist_ok=True)
        with open(diag_log, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines) + "\n")
    except Exception:
        pass

    return 0 if checks_passed == total_checks else 1


def run_jarvis_developer_mode(args: list[str]) -> int:
    """Direct developer access to authoritative Jarvis backend."""
    from jarvis import get_jarvis
    jarvis = get_jarvis()

    print("=" * 65)
    print(f" JARVIS AI CO-PILOT — Developer / Debug Interface")
    print(f" Invariant: COUNT(JARVIS_IMPLEMENTATIONS) = 1")
    print("=" * 65)

    if not args:
        print("Jarvis is ready. Enter queries (or 'exit' to quit):")
        try:
            while True:
                prompt = input("\nJarvis> ").strip()
                if not prompt or prompt.lower() in ("exit", "quit"):
                    break
                response = jarvis.think(prompt)
                print(f"Jarvis: {response}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Jarvis developer mode.")
        return 0

    query = " ".join(args)
    print(f"Query: {query}")
    response = jarvis.think(query)
    print(f"Response: {response}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Primary application coordinator entry point."""
    if argv is None:
        argv = sys.argv[1:]

    # Attach parent console if invoked with CLI flags from terminal in Windows windowed mode
    if any(arg in argv for arg in ("--help", "-h", "--version", "--diagnostics", "--jarvis")):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.AttachConsole(-1)
                if sys.stdout is None:
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                if sys.stderr is None:
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8")
            except Exception:
                pass

    parser = argparse.ArgumentParser(
        prog="MissMinutes",
        description="Miss Minutes & Jarvis AI Desktop Assistant",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_TITLE} v{APP_VERSION}",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Start assistant forced into OFFLINE state",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Run comprehensive headless diagnostic verification and exit",
    )
    parser.add_argument(
        "--jarvis",
        nargs="*",
        metavar="QUERY",
        help="Run existing Jarvis in direct developer/debug mode",
    )

    args = parser.parse_args(argv)

    if args.diagnostics:
        return run_diagnostics()

    if args.jarvis is not None:
        return run_jarvis_developer_mode(args.jarvis)

    # Standard Desktop UI Launch
    try:
        from PySide6.QtWidgets import QApplication
        from app.main import MissMinutesApp
        from config.settings import load_settings
    except ImportError as e:
        logger.error("Failed to import desktop UI dependencies: %s", e)
        print(f"\n[ERROR] Missing required GUI dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("MissMinutes")
    app.setOrganizationName("MissMinutes")

    # Set application icon if available
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    icon_candidates = [
        os.path.join(base_dir, "packaging", "MissMinutes.ico"),
        os.path.join(base_dir, "MissMinutes.ico"),
    ]
    for ic in icon_candidates:
        if os.path.exists(ic):
            from PySide6.QtGui import QIcon
            app.setWindowIcon(QIcon(ic))
            break

    settings = load_settings()
    import dataclasses
    if args.offline:
        settings = dataclasses.replace(settings, start_state="OFFLINE")
    else:
        settings = dataclasses.replace(settings, start_state="IDLE")

    from actions.windows_executor import WindowsActionExecutor
    miss_minutes = MissMinutesApp(
        settings=settings,
        action_executor=WindowsActionExecutor(allow_real_execution=True),
        qapp=app,
    )
    miss_minutes.show()

    logger.info("Miss Minutes application started successfully.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
