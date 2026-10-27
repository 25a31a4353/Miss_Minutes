"""
actions/mock_executor.py - Deterministic Mock Capability Executor.

Simulates capability execution safely without touching real OS APIs,
subprocesses, or third-party web services.
"""

from __future__ import annotations

import datetime
from typing import Any
from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType


class MockActionExecutor:
    """
    Mock Capability Executor for Phase 4 testing.
    
    Guarantees:
    - Never invokes OS subprocesses, shell commands, or network sockets.
    - Produces realistic, typed simulated outputs.
    - Sets simulated=True on all outputs.
    """

    def __init__(self):
        self.execution_history: list[CapabilityRequest] = []

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        """Executes the capability in safe simulated mock mode."""
        self.execution_history.append(request)
        cap = request.capability

        if cap == CapabilityType.GET_TIME:
            now_str = datetime.datetime.now().strftime("%I:%M %p, %A, %B %d, %Y")
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"time": now_str, "formatted": f"The current time is {now_str}"},
                simulated=True,
            )

        if cap == CapabilityType.GET_SYSTEM_STATUS:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={
                    "cpu_percent": 14.5,
                    "ram_percent": 48.2,
                    "os": "Windows 11",
                    "status": "Nominal",
                },
                simulated=True,
            )

        if cap == CapabilityType.GET_BATTERY_STATUS:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"percent": 88, "charging": True},
                simulated=True,
            )

        if cap == CapabilityType.GET_VOLUME:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"volume": 65, "muted": False},
                simulated=True,
            )

        if cap == CapabilityType.SET_VOLUME:
            target_vol = request.parameters.get("level", 50)
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"previous_volume": 65, "new_volume": target_vol},
                simulated=True,
            )

        if cap == CapabilityType.VOLUME_UP:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "volume_up", "step": 5, "new_volume": 70},
                simulated=True,
            )

        if cap == CapabilityType.VOLUME_DOWN:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "volume_down", "step": 5, "new_volume": 60},
                simulated=True,
            )

        if cap == CapabilityType.VOLUME_MUTE:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "volume_mute", "muted": True},
                simulated=True,
            )

        if cap == CapabilityType.MEDIA_PLAY_PAUSE:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "media_play_pause", "state": "toggled"},
                simulated=True,
            )

        if cap == CapabilityType.MEDIA_NEXT:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "media_next", "track": "next"},
                simulated=True,
            )

        if cap == CapabilityType.MEDIA_PREVIOUS:
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "media_previous", "track": "previous"},
                simulated=True,
            )

        if cap == CapabilityType.PLAY_YOUTUBE:
            query = request.query or request.target or "music"
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={
                    "platform": "YouTube",
                    "action": "play",
                    "query": query,
                    "simulated_url": f"https://www.youtube.com/results?search_query={query}",
                },
                simulated=True,
            )

        if cap == CapabilityType.SEARCH_YOUTUBE:
            query = request.query or "popular videos"
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "search", "query": query},
                simulated=True,
            )

        if cap == CapabilityType.OPEN_WEBSITE:
            target_url = request.target or "https://www.google.com"
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "open_browser", "url": target_url},
                simulated=True,
            )

        if cap == CapabilityType.SEARCH_WEB:
            query = request.query or ""
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"engine": "Google", "query": query},
                simulated=True,
            )

        if cap == CapabilityType.OPEN_APP:
            app = request.target or request.parameters.get("app_name", "Notepad")
            return CapabilityResult(
                request_id=request.request_id,
                capability=cap,
                success=True,
                output={"action": "launch_application", "app": app},
                simulated=True,
            )

        return CapabilityResult(
            request_id=request.request_id,
            capability=cap,
            success=False,
            error_message=f"No mock handler for capability: {cap}",
            simulated=True,
        )
