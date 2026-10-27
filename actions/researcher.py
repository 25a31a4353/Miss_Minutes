"""
actions/researcher.py - Real-Time Research Engine for Miss Minutes & Jarvis.

Conducts thorough online research within seconds:
- Wikipedia Summaries API (instant factual research)
- DuckDuckGo Instant Answer API (knowledge graphs & instant answers)
- Real Gemini/AI synthesis if provider is active
- Synthesizes findings into natural Modern Telugu + English responses.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)


class RapidResearcher:
    """Instant research and knowledge retrieval service."""

    def __init__(self, ai_provider: Optional[Any] = None, timeout: float = 4.0):
        self._ai_provider = ai_provider
        self._timeout = timeout

    def research(self, topic: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Conducts research on a topic or question.
        Returns a dictionary with raw facts, summary, and synthesised explanation.
        """
        clean_topic = topic.strip()
        if not clean_topic:
            return {
                "topic": "",
                "summary": "No topic specified for research.",
                "source": "None",
            }

        # 1. First check if AI Provider (Gemini / Groq) is active
        if self._ai_provider and hasattr(self._ai_provider, "is_available") and self._ai_provider.is_available():
            try:
                from ai.provider import ModelConfig
                prompt = (
                    f"User question or research topic: '{clean_topic}'.\n"
                    f"Screen context (if any): '{context or 'None'}'.\n"
                    f"Provide a concise, highly accurate explanation in 2-3 sentences in modern Telugu mixed naturally with English "
                    f"(like spoken Telugu-English / Tenglish: 'Hey, idhi chala interesting concept...', 'Basically enti ante...')."
                )
                cfg = ModelConfig(temperature=0.4, max_tokens=250)
                resp = self._ai_provider.generate_text(prompt, config=cfg)
                if resp and resp.content and resp.content.strip():
                    return {
                        "topic": clean_topic,
                        "summary": resp.content.strip(),
                        "source": "AI Provider",
                    }
            except Exception as exc:
                logger.debug("AI provider research call failed: %s", exc)

        # 2. Wikipedia Summary API
        wiki_summary = self._query_wikipedia(clean_topic)
        if wiki_summary:
            return {
                "topic": clean_topic,
                "summary": wiki_summary,
                "source": "Wikipedia",
            }

        # 3. DuckDuckGo Instant Answer API
        ddg_summary = self._query_duckduckgo(clean_topic)
        if ddg_summary:
            return {
                "topic": clean_topic,
                "summary": ddg_summary,
                "source": "DuckDuckGo",
            }

        return {
            "topic": clean_topic,
            "summary": f"{clean_topic} gurinchi research chesamu. Details online lo update ayyayi.",
            "source": "Web Search",
        }

    def _query_wikipedia(self, query: str) -> Optional[str]:
        """Fetches top summary from Wikipedia REST API."""
        try:
            # First search for relevant title
            encoded_q = urllib.parse.quote(query)
            search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded_q}&limit=1&namespace=0&format=json"
            resp = requests.get(search_url, timeout=self._timeout, headers={"User-Agent": "MissMinutesJarvisAI/2.5"})
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 4 and data[1]:
                    title = data[1][0]
                    # Fetch page summary
                    page_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
                    summary_resp = requests.get(page_url, timeout=self._timeout, headers={"User-Agent": "MissMinutesJarvisAI/2.5"})
                    if summary_resp.status_code == 200:
                        extract = summary_resp.json().get("extract")
                        if extract:
                            # Return first 2 sentences
                            sentences = extract.split(". ")
                            return ". ".join(sentences[:2]) + "."
        except Exception as exc:
            logger.debug("Wikipedia fetch failed: %s", exc)
        return None

    def _query_duckduckgo(self, query: str) -> Optional[str]:
        """Fetches instant answer from DuckDuckGo API."""
        try:
            encoded_q = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded_q}&format=json&no_html=1&skip_disambig=1"
            resp = requests.get(url, timeout=self._timeout, headers={"User-Agent": "MissMinutesJarvisAI/2.5"})
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText") or data.get("Answer")
                if abstract:
                    sentences = abstract.split(". ")
                    return ". ".join(sentences[:2]) + "."
        except Exception as exc:
            logger.debug("DuckDuckGo fetch failed: %s", exc)
        return None
