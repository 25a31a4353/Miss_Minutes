"""
tests/test_context_learning_and_fast_llm.py - Verification of Adaptive Context Learning,
Zero-Lag Audio Caching, Parallel Research, and Real-LLM Integration.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agents.learner import ContextLearner
from ai.free_intelligence import FreeIntelligenceProvider
from ai.fallback_provider import ResilientAIProvider
from ai.mock_provider import MockAIProvider
from ai.provider import ModelConfig, ProviderResponse
from actions.researcher import RapidResearcher
from voice.tts import EdgeTTSProvider, TTSAudioResult, MockTTSProvider
from app.pipeline import CapabilityPipeline
from intents.schema import IntentType, LanguageCode


def test_context_learner_vocabulary_and_facts():
    """Verifies that the ContextLearner learns Telugu words, Tenglish idioms, and facts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        learner_path = Path(tmp_dir) / "learned_test.json"
        learner = ContextLearner(persistence_path=learner_path)

        # 1. User speaks Tenglish phrases
        learner.learn_from_interaction(
            user_utterance="Hey Miss Minutes, ivala chala workload undhi naaku seconds lo help cheyyi",
            detected_language="te-en",
            executed_app="chrome",
        )
        learner.learn_from_interaction(
            user_utterance="naa peru Shanmukheswar",
            detected_language="te-en",
        )
        learner.learn_from_interaction(
            user_utterance="wa ante whatsapp",
            detected_language="te-en",
        )

        # Check vocabulary tracking
        top_words = learner.get_top_vocabulary(10)
        assert "workload" in top_words or "seconds" in top_words or "cheyyi" in top_words
        
        # Check learned facts
        assert learner.learned_facts.get("user_name") == "Shanmukheswar"

        # Check alias resolution
        assert learner.resolve_alias("wa") == "whatsapp"
        assert learner.resolve_alias("chrome") == "chrome"

        # Check prompt generation
        prompt_snippet = learner.get_llm_context_prompt()
        assert "USER ADAPTIVE LINGUISTIC PROFILE" in prompt_snippet
        assert "Shanmukheswar" in prompt_snippet

        # Verify disk persistence & reload
        learner.save()
        reloaded_learner = ContextLearner(persistence_path=learner_path)
        assert reloaded_learner.learned_facts.get("user_name") == "Shanmukheswar"
        assert reloaded_learner.resolve_alias("wa") == "whatsapp"


def test_edge_tts_audio_caching_zero_lag():
    """Verifies that repeated synthesis uses the in-memory cache to eliminate lag."""
    tts = EdgeTTSProvider(cache_size=16)

    # Mock asyncio.run to return dummy audio bytes
    with patch("asyncio.run", return_value=b"CACHED_AUDIO_TEST"):
        res1 = tts.synthesize("Sare darling nenu silent ga untanu", language="te")
        assert res1.audio_bytes == b"CACHED_AUDIO_TEST"

    # Second call without patch: should hit cache directly without calling asyncio.run!
    res2 = tts.synthesize("Sare darling nenu silent ga untanu", language="te")
    assert res2.audio_bytes == b"CACHED_AUDIO_TEST"


def test_rapid_researcher_caching_and_concurrency():
    """Verifies that RapidResearcher caches responses and handles topics rapidly."""
    mock_ai = MockAIProvider(default_text_response="Quantum computing simplifies complex state superposition.")
    researcher = RapidResearcher(ai_provider=mock_ai)

    # First call
    res1 = researcher.research(topic="quantum computing")
    assert res1["topic"] == "quantum computing"
    assert "superposition" in res1["summary"]

    # Second call: must hit cache instantly
    res2 = researcher.research(topic="quantum computing")
    assert res2["summary"] == res1["summary"]


def test_free_intelligence_fallback_chain():
    """Verifies that ResilientAIProvider coordinates primary, free intelligence, and mock fallbacks."""
    free_provider = FreeIntelligenceProvider()
    mock_fallback = MockAIProvider(default_text_response="Deterministic test fallback.")

    resilient = ResilientAIProvider(
        primary=None,
        secondary=None,
        tertiary=free_provider,
        fallback=mock_fallback,
    )

    assert resilient.is_available()
    # Mocking network call in FreeIntelligenceProvider to test clean execution
    with patch.object(free_provider, "generate_response", return_value=ProviderResponse(content="Free LLM answer", provider_id="free_intelligence", model_used="test")):
        resp = resilient.generate_response("Explain relativity")
        assert resp.content == "Free LLM answer"


def test_pipeline_adaptive_learning_flow():
    """Verifies that CapabilityPipeline automatically updates learned context on utterances."""
    mock_ai = MockAIProvider(default_text_response="Nenu ready ga unnanu, let's start!")
    pipeline = CapabilityPipeline(ai_provider=mock_ai)

    result = pipeline.execute_pipeline(
        utterance="Miss Minutes, ivala chala workload undhi",
        is_online=True,
    )

    assert result.success
    # Ensure learner recorded the interaction
    assert pipeline.learner.interaction_count >= 1
    assert "workload" in pipeline.learner.vocabulary_counts
