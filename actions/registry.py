"""
actions/registry.py - Allowlisted Capability Registry.

Maintains the explicit registry of safe capabilities.
Any capability not registered here is denied by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from actions.schemas import CapabilityType


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Metadata describing a permitted system capability."""
    capability: CapabilityType
    description: str
    requires_confirmation: bool = False
    risk_level: str = "SAFE"  # "SAFE", "MODERATE", "ELEVATED"


class ActionRegistry:
    """
    Registry of all allowlisted capabilities.
    
    Guarantees:
    - Default DENY: Only explicitly registered CapabilityType members exist.
    - No shell, PowerShell, CMD, or arbitrary subprocess execution can be registered.
    """

    def __init__(self):
        self._capabilities: dict[CapabilityType, CapabilityDescriptor] = {}
        self._register_default_capabilities()

    def _register_default_capabilities(self) -> None:
        self.register(CapabilityDescriptor(
            capability=CapabilityType.GET_TIME,
            description="Retrieves current system date and time",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.GET_SYSTEM_STATUS,
            description="Retrieves CPU, memory, and OS uptime",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.GET_BATTERY_STATUS,
            description="Retrieves battery percentage and charging state",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.GET_VOLUME,
            description="Retrieves current master audio volume",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.SEARCH_WEB,
            description="Searches the web using approved default search engine",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.OPEN_WEBSITE,
            description="Opens an allowlisted website URL in default browser",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.SEARCH_YOUTUBE,
            description="Searches YouTube for specified video or topic",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.PLAY_YOUTUBE,
            description="Plays requested media or song on YouTube",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.OPEN_APP,
            description="Launches an approved desktop application",
            requires_confirmation=False,
            risk_level="MODERATE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.SET_VOLUME,
            description="Sets master audio volume level",
            requires_confirmation=True,
            risk_level="MODERATE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.VOLUME_UP,
            description="Increases system volume",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.VOLUME_DOWN,
            description="Decreases system volume",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.VOLUME_MUTE,
            description="Toggles or mutes system volume",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.MEDIA_PLAY_PAUSE,
            description="Toggles media playback play/pause",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.MEDIA_NEXT,
            description="Skips to next media track",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.MEDIA_PREVIOUS,
            description="Returns to previous media track",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.READ_SCREEN,
            description="Reads and inspects on-screen content and active application context",
            requires_confirmation=False,
            risk_level="SAFE",
        ))
        self.register(CapabilityDescriptor(
            capability=CapabilityType.RESEARCH_EXPLAIN,
            description="Conducts thorough real-time research and provides clear explanation",
            requires_confirmation=False,
            risk_level="SAFE",
        ))

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """Registers an approved capability."""
        self._capabilities[descriptor.capability] = descriptor

    def is_registered(self, capability: CapabilityType) -> bool:
        """Checks if the capability is explicitly registered."""
        return capability in self._capabilities

    def get_descriptor(self, capability: CapabilityType) -> Optional[CapabilityDescriptor]:
        """Returns the descriptor for the given capability, or None if unregistered."""
        return self._capabilities.get(capability)

    def list_capabilities(self) -> list[CapabilityDescriptor]:
        """Returns all registered capability descriptors."""
        return list(self._capabilities.values())
