"""
agents/learner.py - Adaptive Context & Language Learning Engine for Miss Minutes & Jarvis.

Enables Miss Minutes and Jarvis to:
1. Dynamically learn the user's speech habits, colloquialisms, and code-switched Telugu+English ("Tenglish") phrasing.
2. Track user preferences, frequent entities, custom aliases, and conversational facts.
3. Inject the learned profile into LLM reasoning and system prompts so the assistants adapt their speaking style to the user.
4. Persist learned context across desktop restarts in ~/.miss_minutes/learned_context.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

TELUGU_UNICODE_PATTERN = re.compile(r"[\u0c00-\u0c7f]+")
WORD_PATTERN = re.compile(r"\b[a-zA-Z\u0c00-\u0c7f']+\b")

COMMON_TELUGU_WORDS = {
    "cheyyi", "chesi", "cheyyandi", "choodu", "choodandi", "paata", "paatalu",
    "ante", "enti", "naaku", "oka", "cheppu", "ivvu", "undhi", "undi", "ela",
    "pettuko", "pettandi", "aapu", "telusuko", "eppudu", "ippudu", "jarugutundi",
    "samacharam", "samayam", "penchu", "tagginchu", "vinipinchu", "teruvu", "kavali",
    "emiti", "entha", "aipoindi", "cheppandi", "pettu", "nuvvu", "evaru", "bagunnava",
    "namaskaram", "workload", "seconds", "lo", "darling", "sugar", "babu", "anna",
    "garu", "kudarledha", "kudurtunda", "ayindha", "inkenti", "ala", "ila", "mari"
}


class ContextLearner:
    """
    Adaptive contextual language learning engine.
    Continuously observes user interactions, analyzes vocabulary and phrasing,
    stores facts, and dynamically tunes the LLM prompt.
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        if persistence_path:
            self._path = Path(persistence_path)
        else:
            data_dir = Path(os.environ.get("APP_DATA_DIR", Path.home() / ".miss_minutes"))
            self._path = data_dir / "learned_context.json"

        # In-memory learning state
        self.vocabulary_counts: Counter[str] = Counter()
        self.preferred_language_mix: Dict[str, int] = {"te": 0, "en": 0, "te-en": 0}
        self.learned_facts: Dict[str, str] = {}
        self.custom_aliases: Dict[str, str] = {}
        self.frequent_apps: Counter[str] = Counter()
        self.interaction_count: int = 0
        self.last_updated: float = time.time()

        self._load()

    def _load(self) -> None:
        """Loads learned context from persistent storage."""
        if not self._path.is_file():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.vocabulary_counts = Counter(data.get("vocabulary_counts", {}))
            self.preferred_language_mix = data.get("preferred_language_mix", {"te": 0, "en": 0, "te-en": 0})
            self.learned_facts = data.get("learned_facts", {})
            self.custom_aliases = data.get("custom_aliases", {})
            self.frequent_apps = Counter(data.get("frequent_apps", {}))
            self.interaction_count = data.get("interaction_count", 0)
            self.last_updated = data.get("last_updated", time.time())
            logger.info("Loaded learned context (%d vocabulary tokens, %d facts)", len(self.vocabulary_counts), len(self.learned_facts))
        except Exception as exc:
            logger.warning("Could not read learned context from %s: %s", self._path, exc)

    def save(self) -> None:
        """Persists current learned context to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "vocabulary_counts": dict(self.vocabulary_counts.most_common(200)),
                "preferred_language_mix": self.preferred_language_mix,
                "learned_facts": self.learned_facts,
                "custom_aliases": self.custom_aliases,
                "frequent_apps": dict(self.frequent_apps.most_common(50)),
                "interaction_count": self.interaction_count,
                "last_updated": time.time(),
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Could not persist learned context to %s: %s", self._path, exc)

    def learn_from_interaction(
        self,
        user_utterance: str,
        detected_language: str = "te-en",
        executed_app: Optional[str] = None,
    ) -> None:
        """
        Extracts vocabulary, patterns, facts, and updates user profile statistics.
        """
        raw = user_utterance.strip()
        if not raw:
            return

        self.interaction_count += 1
        lang_key = detected_language if detected_language in self.preferred_language_mix else "te-en"
        self.preferred_language_mix[lang_key] = self.preferred_language_mix.get(lang_key, 0) + 1

        if executed_app:
            self.frequent_apps[executed_app.lower()] += 1

        # Tokenize and extract Telugu / Tenglish words
        tokens = [w.lower() for w in WORD_PATTERN.findall(raw)]
        for token in tokens:
            if len(token) > 1 and (token in COMMON_TELUGU_WORDS or TELUGU_UNICODE_PATTERN.search(token)):
                self.vocabulary_counts[token] += 1

        # Detect explicit fact learning patterns:
        # e.g. "naa peru Shanmukh", "my name is X", "gurthupettuko X", "remember X"
        lower = raw.lower()
        if "naa peru " in lower:
            name = raw.split("naa peru ", 1)[1].split()[0]
            self.learned_facts["user_name"] = name
        elif "my name is " in lower:
            name = raw.split("my name is ", 1)[1].split()[0]
            self.learned_facts["user_name"] = name
        elif "gurthupettuko " in lower or "remember " in lower:
            prefix = "gurthupettuko " if "gurthupettuko " in lower else "remember "
            fact = raw.split(prefix, 1)[1].strip()
            if fact:
                self.learned_facts[f"fact_{len(self.learned_facts)+1}"] = fact

        # Detect custom alias creation: "X ante Y" (e.g. "wa ante whatsapp")
        alias_match = re.search(r"(\w+)\s+ante\s+(\w+)", lower)
        if alias_match:
            alias, real = alias_match.groups()
            self.custom_aliases[alias] = real

        self.last_updated = time.time()

        # Periodically save updates (every 3 interactions)
        if self.interaction_count % 3 == 0:
            self.save()

    def register_custom_alias(self, alias: str, target: str) -> None:
        """Explicitly registers a user shortcut or nickname."""
        self.custom_aliases[alias.lower().strip()] = target.lower().strip()
        self.save()

    def resolve_alias(self, name: str) -> str:
        """Resolves a user shortcut to its target if registered."""
        return self.custom_aliases.get(name.lower().strip(), name)

    def get_top_vocabulary(self, limit: int = 15) -> List[str]:
        """Returns the user's most frequently spoken Telugu and Tenglish words."""
        return [word for word, _ in self.vocabulary_counts.most_common(limit)]

    def get_dominant_language(self) -> str:
        """Determines the user's most frequent language mode."""
        if not self.preferred_language_mix:
            return "te-en"
        return max(self.preferred_language_mix, key=self.preferred_language_mix.get)

    def get_llm_context_prompt(self) -> str:
        """
        Builds a rich, adaptive context injection block to insert into LLM system prompts.
        This guides Miss Minutes & Jarvis to naturally reflect the user's unique speech style.
        """
        top_words = self.get_top_vocabulary(12)
        top_apps = [app for app, _ in self.frequent_apps.most_common(5)]
        
        lines = [
            "--- USER ADAPTIVE LINGUISTIC PROFILE & CONTEXT ---",
            f"- Primary Communication Mode: Telugu + English code-switching (Tenglish).",
            f"- Dominant Tone: Modern, conversational, highly collaborative, fast-paced.",
        ]
        
        if top_words:
            lines.append(f"- User's Frequently Spoken Vocabulary & Idioms: {', '.join(top_words)}.")
            lines.append("  -> (Use these idioms and conversational style naturally in your responses to mirror how the user speaks).")

        if self.learned_facts:
            facts_str = "; ".join(f"{k}: {v}" for k, v in self.learned_facts.items())
            lines.append(f"- Learned User Facts & Preferences: {facts_str}.")

        if top_apps:
            lines.append(f"- Frequently Used Applications: {', '.join(top_apps)}.")

        lines.append("- Instruction: Speak naturally in modern Telugu mixed with English. Never sound robotic or formal. Keep responses snappy and responsive.")
        lines.append("--------------------------------------------------")

        return "\n".join(lines)
