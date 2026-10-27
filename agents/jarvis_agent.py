"""
agents/jarvis_agent.py - Single Authoritative Jarvis Integration.

ARCHITECTURE CONSOLIDATION:
This module consolidates historical references to the single authoritative
Jarvis implementation located in jarvis.py.
COUNT(JARVIS_IMPLEMENTATIONS) = 1.
"""

def __getattr__(name: str):
    if name in ("Jarvis", "JarvisAgent"):
        from jarvis import Jarvis
        return Jarvis
    if name == "get_jarvis":
        from jarvis import get_jarvis
        return get_jarvis
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["Jarvis", "JarvisAgent", "get_jarvis"]
