"""
intents/parser.py - Multilingual Intent Parser for English, Telugu, and Code-Switching.

Parses user speech transcripts into StructuredIntent models.
Supports English, Telugu, and Telugu-English mixed speech without forced translation.
Can operate using an AIProvider (e.g. Gemini) or deterministic fallback rules.
"""

from __future__ import annotations

import re
from typing import Optional

from ai.provider import AIProvider
from ai.prompts import INTENT_EXTRACTION_SYSTEM_PROMPT
from intents.schema import IntentEntities, IntentType, LanguageCode, StructuredIntent
from intents.entities import normalize_app_name, normalize_website_url

# Telugu indicator keywords (written in Roman script or Telugu unicode)
TELUGU_ROMAN_KEYWORDS = {
    "cheyyi", "chesi", "cheyyandi", "choodu", "choodandi",
    "paata", "paatalu", "ante", "enti", "naaku", "oka",
    "cheppu", "ivvu", "undhi", "undi", "ela", "pettuko",
    "pettandi", "aapu", "telusuko", "eppudu", "ippudu",
    "jarugutundi", "jaruguthundi", "samacharam", "samayam",
    "penchu", "tagginchu", "vinipinchu", "teruvu", "kavali",
    "emiti", "entha", "aipoindi", "cheppandi", "pettu",
    "nuvvu", "evaru", "bagunnava", "namaskaram"
}

TELUGU_UNICODE_PATTERN = re.compile(r"[\u0c00-\u0c7f]")


class IntentParser:
    """
    Multilingual Intent Parser capable of extracting structured intent
    from English, Telugu, and Telugu-English mixed speech.
    
    Guarantees:
    - Verbatim raw transcript is always preserved.
    - Code-switching (te-en) is explicitly classified without forcing early translation.
    - Operates with an AI provider when available, or deterministic rules when offline.
    """

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self._provider = ai_provider

    def detect_language(self, transcript: str) -> LanguageCode:
        """
        Detects whether an utterance is English (en), Telugu (te),
        or Telugu-English code-switched (te-en).
        """
        raw = transcript.strip().lower()
        if not raw:
            return LanguageCode.EN

        words = set(re.findall(r"\b\w+\b", raw))
        has_telugu_unicode = bool(TELUGU_UNICODE_PATTERN.search(transcript))
        has_telugu_roman = bool(words.intersection(TELUGU_ROMAN_KEYWORDS))

        # Check for English words
        english_words = {
            "open", "play", "search", "what", "is", "explain", "chrome",
            "youtube", "music", "songs", "quantum", "computing", "time",
            "system", "status", "battery", "volume", "how", "why", "who",
            "sound", "pause", "resume", "mute", "notepad", "calculator",
            "edge", "google"
        }
        has_english = bool(words.intersection(english_words))

        if has_telugu_unicode or has_telugu_roman:
            if has_english:
                return LanguageCode.TE_EN
            return LanguageCode.TE

        return LanguageCode.EN

    def parse(self, transcript: str) -> StructuredIntent:
        """
        Parses a speech/text transcript into a StructuredIntent.
        If an AI provider is active, uses structured generation; otherwise uses deterministic parser.
        """
        clean_text = transcript.strip()
        if not clean_text:
            return StructuredIntent(
                intent=IntentType.UNKNOWN,
                language=LanguageCode.EN,
                raw_transcript="",
                confidence=0.0,
                preferred_agent="miss_minutes",
            )

        # 1. If AI provider is available, attempt structured extraction
        if self._provider and self._provider.is_available():
            try:
                from ai.provider import ModelConfig
                config = ModelConfig(
                    system_instruction=INTENT_EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.1,
                )
                prompt = (
                    f"Analyze this user transcript and extract structured intent.\n"
                    f"Transcript: \"{clean_text}\""
                )
                structured = self._provider.generate_structured(
                    prompt=prompt,
                    response_schema=StructuredIntent,
                    config=config,
                )
                # Ensure raw_transcript matches verbatim
                structured.raw_transcript = clean_text
                if structured.language == LanguageCode.EN or structured.language == LanguageCode.UNKNOWN:
                    detected = self.detect_language(clean_text)
                    if detected != LanguageCode.EN:
                        structured.language = detected
                return structured
            except Exception:
                # Fail gracefully to deterministic fallback
                pass

        # 2. Deterministic rule-based parsing engine
        return self._parse_deterministic(clean_text)

    def _parse_deterministic(self, text: str) -> StructuredIntent:
        """
        Deterministic parser supporting English, Telugu, and Telugu-English utterances.
        Used for tests, offline mode, and zero-API-key environments.
        """
        lang = self.detect_language(text)
        lower = text.lower()
        words = set(re.findall(r"\b\w+\b", lower))

        # 0a. Quiet / Standby command (e.g. "remain quiet", "be quiet", "silent ga undu", "quiet ga undu", "aagu", "paduko")
        quiet_triggers = [
            "remain quiet", "be quiet", "stay quiet", "keep quiet",
            "silent ga undu", "quiet ga undu", "silent ga undandi",
            "matladochu", "matladadhu", "aagu", "paduko", "shut up",
            "don't speak", "stop speaking", "shhh", "quiet please"
        ]
        if any(trig in lower for trig in quiet_triggers) or lower in ("quiet", "silent", "shh"):
            return StructuredIntent(
                intent=IntentType.QUIET_STANDBY,
                language=lang,
                raw_transcript=text,
                confidence=0.98,
                requires_action=True,
                preferred_agent="miss_minutes",
                reasoning="User requested assistant to remain quiet/silent",
            )

        # 0b. Resume / Wake command (e.g. "matladu", "wake up", "start speaking")
        resume_triggers = ["start speaking", "matladu", "matladandi", "wake up", "speak now", "unmute"]
        if any(trig in lower for trig in resume_triggers):
            return StructuredIntent(
                intent=IntentType.RESUME_LISTENING,
                language=lang,
                raw_transcript=text,
                confidence=0.98,
                requires_action=True,
                preferred_agent="miss_minutes",
                reasoning="User requested assistant to resume active conversation",
            )

        # 0c. Screen Reading & Visual Inspection (e.g. "read my screen", "screen meedha emundi", "screen choodu", "explain this screen")
        if (
            "screen meedha" in lower
            or "screen meeda" in lower
            or "screen choodu" in lower
            or "screen scan" in lower
            or "read my screen" in lower
            or "read screen" in lower
            or "look at my screen" in lower
            or "screen lo emundi" in lower
            or ("screen" in words and any(w in lower for w in ("choodu", "read", "scan", "emundi", "explain", "text")))
        ):
            # Extract optional specific question about the screen
            q = re.sub(r"(?:read\s+(?:my\s+)?screen|screen\s+meedha\s+emundi|screen\s+choodu|screen\s+scan\s+cheyyi|screen)", "", lower).strip(" '\",.!?")
            return StructuredIntent(
                intent=IntentType.READ_SCREEN,
                language=lang,
                raw_transcript=text,
                confidence=0.98,
                entities=IntentEntities(query=q if q else "Analyze screen content"),
                requires_action=True,
                preferred_agent="jarvis",
                reasoning="Screen reading and on-screen content analysis request",
            )

        # 1. Media play/pause (e.g. "paata aapu", "pause music", "music aapu", "pause cheyyi", "pause", "resume")
        if (
            "paata aapu" in lower
            or "music aapu" in lower
            or "pause music" in lower
            or "stop music" in lower
            or "resume music" in lower
            or "pause cheyyi" in lower
            or "resume cheyyi" in lower
            or lower in ("pause", "resume", "stop")
        ):
            return StructuredIntent(
                intent=IntentType.MEDIA_PLAY_PAUSE,
                language=lang,
                raw_transcript=text,
                confidence=0.96,
                requires_action=True,
                preferred_agent="jarvis",
                reasoning="Media playback play/pause control request",
            )

        # 2. Volume and Audio Controls (Mute, Up, Down, Set, Get)
        if any(k in lower for k in ("volume", "sound", "mute", "penchu", "tagginchu")):
            # Mute
            if "mute" in lower or "sound aapu" in lower or "volume aapu" in lower:
                return StructuredIntent(
                    intent=IntentType.VOLUME_MUTE,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning="Audio mute request",
                )
            # Volume Up
            if (
                "penchu" in lower
                or "volume up" in lower
                or "sound up" in lower
                or "increase volume" in lower
                or "sound ekkuva" in lower
                or "volume ekkuva" in lower
            ):
                return StructuredIntent(
                    intent=IntentType.VOLUME_UP,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning="Audio volume increase request",
                )
            # Volume Down
            if (
                "tagginchu" in lower
                or "volume down" in lower
                or "sound down" in lower
                or "decrease volume" in lower
                or "sound thakkuva" in lower
                or "volume thakkuva" in lower
            ):
                return StructuredIntent(
                    intent=IntentType.VOLUME_DOWN,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning="Audio volume decrease request",
                )
            # Volume Set (e.g. "volume 50", "set volume to 80")
            vol_match = re.search(r"\b(\d{1,3})\b", text)
            if vol_match:
                vol = max(0, min(100, int(vol_match.group(1))))
                return StructuredIntent(
                    intent=IntentType.SET_VOLUME,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    entities=IntentEntities(volume_level=vol),
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning=f"Set system volume to {vol}%",
                )
            # Volume Get
            if "volume" in lower or "sound entha" in lower:
                return StructuredIntent(
                    intent=IntentType.GET_VOLUME,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.92,
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning="System volume query",
                )

        # 3. System Time / Date (e.g. "samayam entha", "time entha", "what time is it", "time cheppu")
        if (
            "samayam" in lower
            or "time entha" in lower
            or "what time" in lower
            or "time cheppu" in lower
            or "current time" in lower
            or ("time" in words and not any(w in lower for w in ("open", "play", "search", "runtime", "timeline")))
            or "eppudu" in words
        ):
            return StructuredIntent(
                intent=IntentType.GET_TIME,
                language=lang,
                raw_transcript=text,
                confidence=0.96,
                requires_action=True,
                preferred_agent="jarvis",
                reasoning="System time query",
            )

        # 4. Battery Status (e.g. "battery entha undi", "battery percentage", "battery status")
        if "battery" in lower or "charge entha" in lower or "charging entha" in lower:
            return StructuredIntent(
                intent=IntentType.GET_BATTERY_STATUS,
                language=lang,
                raw_transcript=text,
                confidence=0.96,
                requires_action=True,
                preferred_agent="jarvis",
                reasoning="System battery status query",
            )

        # 5. System Status (e.g. "system status", "pc status", "laptop status", "pc ela undi")
        if (
            "system status" in lower
            or "pc status" in lower
            or "laptop status" in lower
            or "pc ela undi" in lower
            or "computer status" in lower
        ):
            return StructuredIntent(
                intent=IntentType.GET_SYSTEM_STATUS,
                language=lang,
                raw_transcript=text,
                confidence=0.95,
                requires_action=True,
                preferred_agent="jarvis",
                reasoning="System health and performance status query",
            )

        # 6. YouTube media playback pattern (e.g. "YouTube open chesi AR Rahman songs play cheyyi" or "Play some music")
        if (
            ("youtube" in lower and any(w in lower for w in ("play", "paata", "songs", "music", "chesi", "pettu", "pettuko")))
            or ("play" in words or "paata" in words or "paatalu" in words or "songs" in words)
        ):
            query = "music"
            m = re.search(r"(?:play|chesi|lo)\s+(.+?)(?:\s+play\s+cheyyi|\s+cheyyi|\s+play|\s+pettu|$)", lower)
            if m:
                query = m.group(1).replace("songs", "").strip() or "songs"
                if "ar rahman" in lower:
                    query = "AR Rahman songs"
            elif "ar rahman" in lower:
                query = "AR Rahman songs"
            elif "oka paata" in lower:
                query = "Telugu songs"

            return StructuredIntent(
                intent=IntentType.PLAY_MEDIA,
                language=lang,
                raw_transcript=text,
                confidence=0.96,
                entities=IntentEntities(
                    target="youtube",
                    query=query,
                    website_url="https://www.youtube.com",
                ),
                requires_action=True,
                preferred_agent="jarvis",
                reasoning="Detected media playback request targeted at YouTube",
            )

        # 7. Open website or application
        # e.g. "Open YouTube", "YouTube open cheyyi", "Chrome open cheyyi", "notepad teruvu", "calculator open cheyyi"
        if "open" in words or ("open" in lower and "cheyyi" in lower) or "teruvu" in words or "teruvandi" in words:
            # Check known web targets
            if "youtube" in lower:
                return StructuredIntent(
                    intent=IntentType.OPEN_WEBSITE,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    entities=IntentEntities(
                        target="youtube",
                        website_url=normalize_website_url("youtube"),
                    ),
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning="Website navigation request for YouTube",
                )
            if "google" in lower:
                return StructuredIntent(
                    intent=IntentType.OPEN_WEBSITE,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    entities=IntentEntities(
                        target="google",
                        website_url=normalize_website_url("google"),
                    ),
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning="Website navigation request for Google",
                )
            # Check known applications
            for known_app in ("whatsapp", "whats app", "wa", "notepad", "chrome", "google chrome", "calculator", "calc", "explorer", "edge", "terminal", "taskmgr", "task manager", "settings", "browser"):
                if known_app in lower:
                    return StructuredIntent(
                        intent=IntentType.OPEN_APP,
                        language=lang,
                        raw_transcript=text,
                        confidence=0.95,
                        entities=IntentEntities(
                            app_name=normalize_app_name(known_app),
                        ),
                        requires_action=True,
                        preferred_agent="jarvis",
                        reasoning=f"Application launch request for {known_app}",
                    )
            # Generic open
            m = re.search(r"(?:open|teruvu)\s+([a-zA-Z0-9_\s]+?)(?:\s+cheyyi|$)", lower)
            target = m.group(1).strip() if m else "unknown"
            return StructuredIntent(
                intent=IntentType.OPEN_APP,
                language=lang,
                raw_transcript=text,
                confidence=0.90,
                entities=IntentEntities(app_name=normalize_app_name(target)),
                requires_action=True,
                preferred_agent="jarvis",
                reasoning=f"Application launch request for {target}",
            )

        # 8. Web Search (e.g. "search web for quantum computing", "search google for python", "Google lo quantum computing search cheyyi")
        if "search" in words or "search" in lower or "vetuku" in words or "vetukandi" in words or "google lo" in lower:
            if "youtube" in lower:
                query = re.sub(r"(?:search\s+(?:on\s+)?youtube\s+for|search\s+for|search|youtube)", "", lower).strip(" '\",.!?") or "music"
                return StructuredIntent(
                    intent=IntentType.PLAY_MEDIA,
                    language=lang,
                    raw_transcript=text,
                    confidence=0.95,
                    entities=IntentEntities(
                        target="youtube",
                        query=query,
                        website_url="https://www.youtube.com",
                    ),
                    requires_action=True,
                    preferred_agent="jarvis",
                    reasoning=f"YouTube search request for '{query}'",
                )

            # Web search query extraction
            clean_query = lower
            for phrase in [
                "search the web for", "search web for", "search google for",
                "search for", "google lo", "search cheyyi", "cheyyi", "search", "vetuku"
            ]:
                clean_query = clean_query.replace(phrase, "")
            extracted_query = clean_query.strip(" '\",.!?") or "information"

            return StructuredIntent(
                intent=IntentType.SEARCH_WEB,
                language=lang,
                raw_transcript=text,
                confidence=0.95,
                entities=IntentEntities(
                    query=extracted_query,
                    target="google",
                    website_url="https://www.google.com",
                ),
                requires_action=True,
                preferred_agent="jarvis",
                reasoning=f"Web search query for '{extracted_query}'",
            )

        # 9. Questions (e.g. "What is quantum computing?", "Quantum computing ante enti?", "Naaku quantum computing explain cheyyi")
        if (
            "ante enti" in lower
            or "enti" in words
            or "what is" in lower
            or "explain" in lower
            or "cheppu" in words
            or lower.endswith("?")
        ):
            # Extract query subject
            query = lower
            for phrase in ["what is", "explain", "naaku", "explain cheyyi", "ante enti", "enti", "?"]:
                query = query.replace(phrase, "")
            query = query.strip() or text.strip()

            return StructuredIntent(
                intent=IntentType.QUESTION,
                language=lang,
                raw_transcript=text,
                confidence=0.92,
                entities=IntentEntities(query=query),
                requires_action=False,
                preferred_agent="miss_minutes",
                reasoning="Information query suitable for conversational explanation",
            )

        # 10. Default to CHAT (greetings, chit-chat, Telugu or English conversation)
        return StructuredIntent(
            intent=IntentType.CHAT,
            language=lang,
            raw_transcript=text,
            confidence=0.88,
            requires_action=False,
            preferred_agent="miss_minutes",
            reasoning="General conversational utterance",
        )
