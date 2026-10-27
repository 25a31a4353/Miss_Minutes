"""
voice/voices.py - Distinct Voice Configurations for Miss Minutes and Jarvis.

Defines distinct voice profiles for both agents across English and Telugu.
The system explicitly enforces separate voice identities for Miss Minutes and Jarvis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AgentVoiceProfile:
    """Voice profile attributes for an individual agent."""
    agent_name: str
    gender: str
    primary_en_voice: str
    primary_te_voice: str
    pitch: str = "+0Hz"
    rate: str = "+0%"
    description: str = ""

    def get_voice_for_language(self, language_code: str) -> str:
        """Returns the appropriate voice identifier based on language."""
        lang = language_code.strip().lower()
        if lang in ("te", "te-en", "telugu"):
            return self.primary_te_voice
        return self.primary_en_voice


# Miss Minutes: Female, playful, warm, slightly Southern / lively
MISS_MINUTES_VOICE_PROFILE = AgentVoiceProfile(
    agent_name="miss_minutes",
    gender="female",
    primary_en_voice="en-US-JennyNeural",
    primary_te_voice="te-IN-ShrutiNeural",
    pitch="+5Hz",
    rate="+5%",
    description="Miss Minutes: Warm, cheerful, witted, southern-tinged clock companion",
)

# Jarvis: Male, calm, British/formal or professional, composed
JARVIS_VOICE_PROFILE = AgentVoiceProfile(
    agent_name="jarvis",
    gender="male",
    primary_en_voice="en-GB-RyanNeural",
    primary_te_voice="te-IN-MohanNeural",
    pitch="-2Hz",
    rate="+0%",
    description="Jarvis: Composed, dry wit, impeccable professional co-pilot",
)

AGENT_VOICE_REGISTRY: dict[str, AgentVoiceProfile] = {
    "miss_minutes": MISS_MINUTES_VOICE_PROFILE,
    "jarvis": JARVIS_VOICE_PROFILE,
}


def get_voice_profile(agent_name: str) -> AgentVoiceProfile:
    """Returns the voice profile for the specified agent, defaulting to Miss Minutes."""
    key = agent_name.strip().lower()
    return AGENT_VOICE_REGISTRY.get(key, MISS_MINUTES_VOICE_PROFILE)
