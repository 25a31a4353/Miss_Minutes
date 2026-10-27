"""
intents/__init__.py - Multilingual Intent Understanding Package.

Exports intent models, entities, and the multilingual IntentParser.
"""

from intents.schema import IntentEntities, IntentType, LanguageCode, StructuredIntent
from intents.entities import normalize_app_name, normalize_website_url, APPLICATION_ALIASES, WEBSITE_ALIASES
from intents.parser import IntentParser

__all__ = [
    "IntentEntities",
    "IntentType",
    "LanguageCode",
    "StructuredIntent",
    "normalize_app_name",
    "normalize_website_url",
    "APPLICATION_ALIASES",
    "WEBSITE_ALIASES",
    "IntentParser",
]
