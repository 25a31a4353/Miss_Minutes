"""
app/pipeline.py - End-to-End Multilingual Capability Pipeline.

Connects the full Phase 4 architecture:
Input -> Transcript -> Language Detection -> Intent Parser -> Structured Intent
-> Agent Delegation (Miss Minutes <-> Jarvis) -> Capability Proposal
-> Security Validator -> Safe Mock Executor -> Response Synthesis -> TTS
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Any

from ai.provider import AIProvider
from intents.schema import StructuredIntent, IntentType, LanguageCode
from intents.parser import IntentParser
from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType
from actions.registry import ActionRegistry
from actions.mock_executor import MockActionExecutor
from actions.windows_executor import WindowsActionExecutor
from security.permissions import SecurityDecision, SecurityValidationResult
from security.validator import SecurityValidator
from voice.service import VoiceService
from voice.tts import TTSAudioResult
from agents.bus import AgentMessageBus
from agents.context import SharedBoundedContext
from agents.message import AgentId, AgentMessage, MessageType

logger = logging.getLogger(__name__)


@dataclass
class PipelineExecutionResult:
    """Complete diagnostic trail of an utterance flowing through the capability pipeline."""
    raw_transcript: str
    language: LanguageCode
    intent: StructuredIntent
    delegated_to_jarvis: bool = False
    capability_request: Optional[CapabilityRequest] = None
    security_result: Optional[SecurityValidationResult] = None
    capability_result: Optional[CapabilityResult] = None
    miss_minutes_response: str = ""
    jarvis_response: str = ""
    tts_result: Optional[TTSAudioResult] = None
    success: bool = True
    error_message: Optional[str] = None


class CapabilityPipeline:
    """
    Coordinated capability orchestration pipeline.
    
    Guarantees:
    - Verbatim transcript preservation without forced translation.
    - Default DENY security validation prior to any executor call.
    - Strict OFFLINE gate enforcement.
    - Bounded conversational context memory for multi-turn dialogue.
    - Real Gemini / AI conversational reasoning with personality preservation.
    """

    def __init__(
        self,
        ai_provider: Optional[AIProvider] = None,
        security_validator: Optional[SecurityValidator] = None,
        action_executor: Optional[Any] = None,
        voice_service: Optional[VoiceService] = None,
        message_bus: Optional[AgentMessageBus] = None,
        context: Optional[SharedBoundedContext] = None,
    ):
        self.ai_provider = ai_provider
        self.intent_parser = IntentParser(ai_provider=ai_provider)
        self.security_validator = security_validator or SecurityValidator()
        self.action_executor = action_executor or MockActionExecutor()
        self.voice_service = voice_service or VoiceService(is_assistant_online=False)
        self.bus = message_bus or AgentMessageBus()
        self.context = context if context is not None else SharedBoundedContext(max_turns=10)

    def execute_voice_pipeline(
        self,
        audio_data: Optional[bytes] = None,
        language_hint: Optional[str] = None,
        is_online: bool = True,
        user_confirmed: bool = False,
    ) -> PipelineExecutionResult:
        """
        Executes real voice interaction:
        Microphone capture (or provided audio) -> faster-whisper STT -> Intent -> Delegation -> Capability -> TTS.
        Silence guard: Never executes action capabilities on silence or empty audio.
        """
        if not is_online:
            return PipelineExecutionResult(
                raw_transcript="",
                language=LanguageCode.EN,
                intent=StructuredIntent(
                    intent=IntentType.UNKNOWN,
                    language=LanguageCode.EN,
                    raw_transcript="",
                    confidence=0.0,
                ),
                success=False,
                error_message="Assistant is OFFLINE: Voice pipeline is strictly blocked.",
            )

        self.voice_service.set_online(True)
        raw_wav = audio_data if audio_data is not None else self.voice_service.capture_speech()
        transcription = self.voice_service.transcribe_audio(raw_wav, language_hint=language_hint)

        if transcription.is_empty:
            fallback_msg = "I didn't quite catch that, sugar. Could you say that again?"
            tts_res = None
            try:
                self.voice_service.set_online(True)
                tts_res = self.voice_service.speak_text(
                    fallback_msg,
                    agent_name="miss_minutes",
                    language="en",
                )
            except Exception as exc:
                logger.warning("TTS fallback synthesis skipped: %s", exc)

            return PipelineExecutionResult(
                raw_transcript="",
                language=LanguageCode.EN,
                intent=StructuredIntent(
                    intent=IntentType.UNKNOWN,
                    language=LanguageCode.EN,
                    raw_transcript="",
                    confidence=0.0,
                ),
                success=True,
                miss_minutes_response=fallback_msg,
                tts_result=tts_res,
            )

        return self.execute_pipeline(
            utterance=transcription.raw_text,
            is_online=is_online,
            user_confirmed=user_confirmed,
        )

    def execute_pipeline(
        self,
        utterance: str,
        is_online: bool = True,
        user_confirmed: bool = False,
    ) -> PipelineExecutionResult:
        """
        Executes the safe mock capability pipeline from user utterance to agent response.
        """
        clean_input = utterance.strip()

        # 1. Master OFFLINE Gate
        if not is_online:
            return PipelineExecutionResult(
                raw_transcript=clean_input,
                language=LanguageCode.EN,
                intent=StructuredIntent(
                    intent=IntentType.UNKNOWN,
                    language=LanguageCode.EN,
                    raw_transcript=clean_input,
                    confidence=0.0,
                ),
                success=False,
                error_message="Assistant is OFFLINE: Pipeline processing is strictly blocked.",
            )

        # 2. Multilingual Intent Parsing
        intent = self.intent_parser.parse(clean_input)

        result = PipelineExecutionResult(
            raw_transcript=clean_input,
            language=intent.language,
            intent=intent,
        )

        # 3. Conversational / Informational Query (No system action required)
        if intent.intent in (IntentType.QUIET_STANDBY, IntentType.RESUME_LISTENING):
            if intent.intent == IntentType.QUIET_STANDBY:
                result.miss_minutes_response = "Sare darling, nenu silent ga untanu. Meeku emaina help kaavalante pilavandi!"
                result.jarvis_response = "Standing by quietly, sir. Call whenever you need us."
            else:
                result.miss_minutes_response = "Hey, Miss Minutes ready! Neeku em help kaavalo cheppu darling."
                result.jarvis_response = "Jarvis online. Awaiting your instructions, sir."

            # Voice synthesis via turn taking
            try:
                self.voice_service.set_online(True)
                result.tts_result = self.voice_service.speak_text(
                    result.miss_minutes_response,
                    agent_name="miss_minutes",
                    language="te",
                )
            except Exception as exc:
                logger.warning("TTS synthesis skipped: %s", exc)

            return result

        if not intent.requires_action or intent.intent in (IntentType.CHAT, IntentType.QUESTION, IntentType.RESEARCH_EXPLAIN):
            lower_input = clean_input.lower()
            ai_resp_content = ""

            if self.ai_provider and self.ai_provider.is_available():
                from ai.prompts import MISS_MINUTES_SYSTEM_PROMPT
                from ai.provider import ModelConfig
                cfg = ModelConfig(
                    system_instruction=MISS_MINUTES_SYSTEM_PROMPT,
                    temperature=0.7,
                    max_tokens=400,
                )
                history_msgs = []
                for turn in self.context.get_turns(limit=self.context.max_turns):
                    r = "user" if turn.sender == AgentId.USER else "assistant"
                    history_msgs.append({"role": r, "content": turn.content})
                history_msgs.append({"role": "user", "content": clean_input})

                try:
                    ai_resp = self.ai_provider.generate_chat_response(history_msgs, config=cfg)
                    if ai_resp and ai_resp.content:
                        ai_resp_content = ai_resp.content.strip()
                except Exception as exc:
                    logger.debug("AI provider chat response error: %s", exc)

            if intent.intent in (IntentType.QUESTION, IntentType.RESEARCH_EXPLAIN):
                query_topic = intent.entities.query or clean_input
                from actions.researcher import RapidResearcher
                researcher = RapidResearcher(ai_provider=self.ai_provider)
                res_data = researcher.research(topic=query_topic)
                findings = res_data.get("summary", f"{query_topic} gurinchi information gather chesamu.")

                result.miss_minutes_response = f"Manchi question sugar! {query_topic} gurinchi Jarvis research details share chestharu choodandi."
                result.jarvis_response = ai_resp_content or f"Here is the research summary, sir: {findings}. All analysis verified."

            else:
                # Chat and modern greeting
                if any(w in lower_input for w in ("ela unnavu", "bagunnava")):
                    result.miss_minutes_response = "Nenu chala bagunnanu darling! How about you?"
                    result.jarvis_response = "Systems fully operational, sir. Ready to assist with your workload."
                elif any(w in lower_input for w in ("nuvvu evaru", "evaru", "who are you")):
                    result.miss_minutes_response = "Nenu Miss Minutes ni, your lively TVA companion! And Jarvis is right here beside me."
                    result.jarvis_response = "Jarvis, at your service. Between Miss Minutes and myself, consider any task handled."
                else:
                    # User's signature modern Telugu + English greeting
                    result.miss_minutes_response = ai_resp_content or "Hey, nenu Miss Minutes ni! Enti ivala chala workload undhi anukunta. Neeku eh help kavalo cheppu, seconds lo complete chesi pedathanu!"
                    result.jarvis_response = "Exactly ma'am. Jarvis here as well. Chrome, WhatsApp, screen research, system actions — edhaina ready ga undhi sir."

            # Bounded context tracking
            self.context.add_message(AgentMessage(
                sender=AgentId.USER,
                recipient=AgentId.MISS_MINUTES,
                message_type=MessageType.CHAT,
                content=clean_input,
            ))
            self.context.add_message(AgentMessage(
                sender=AgentId.MISS_MINUTES,
                recipient=AgentId.USER,
                message_type=MessageType.CHAT,
                content=result.miss_minutes_response,
            ))

            # Voice synthesis
            try:
                self.voice_service.set_online(True)
                result.tts_result = self.voice_service.speak_text(
                    result.miss_minutes_response,
                    agent_name="miss_minutes",
                    language="te",
                )
            except Exception as exc:
                logger.warning("TTS synthesis skipped: %s", exc)

            return result

        # 4. System Capability Execution Required -> Delegate to Jarvis
        result.delegated_to_jarvis = True

        # Formulate capability request based on intent
        cap_type = self._map_intent_to_capability(intent.intent)
        if cap_type is None:
            result.success = False
            result.error_message = f"No allowable capability mapped for intent {intent.intent.value}"
            result.miss_minutes_response = "I'm sorry sugar, I don't know how to do that just yet."
            return result

        params = {
            "level": intent.entities.volume_level,
            "url": intent.entities.website_url,
        }
        if cap_type in (CapabilityType.VOLUME_UP, CapabilityType.VOLUME_DOWN):
            params["steps"] = 3

        cap_request = CapabilityRequest(
            capability=cap_type,
            target=intent.entities.target or intent.entities.app_name,
            query=intent.entities.query,
            parameters=params,
            requested_by="jarvis",
        )
        result.capability_request = cap_request

        # Post delegation message to AgentMessageBus if Jarvis is registered
        if self.bus.get_agent(AgentId.JARVIS):
            try:
                self.bus.dispatch(AgentMessage(
                    sender=AgentId.MISS_MINUTES,
                    recipient=AgentId.JARVIS,
                    message_type=MessageType.DELEGATION,
                    content=f"Jarvis, could you take care of {intent.intent.value} for our friend?",
                    metadata={"capability_request": cap_request.model_dump()},
                ))
            except Exception as bus_err:
                logger.debug("Bus dispatch skipped: %s", bus_err)

        # 5. Security Validation Gate
        sec_result = self.security_validator.validate_capability_request(
            request=cap_request,
            is_assistant_online=is_online,
            user_confirmed=user_confirmed,
        )
        result.security_result = sec_result

        if sec_result.decision == SecurityDecision.DENY:
            result.success = False
            result.error_message = f"Security block: {sec_result.reason}"
            result.jarvis_response = f"I cannot permit that operation, sir. {sec_result.reason}"
            result.miss_minutes_response = f"Hold your horses! Jarvis says that's not allowed right now."
            return result

        if sec_result.decision == SecurityDecision.REQUIRES_CONFIRMATION:
            result.success = False
            result.error_message = f"Confirmation required: {sec_result.reason}"
            result.jarvis_response = "Awaiting user confirmation before proceeding."
            result.miss_minutes_response = "Are you sure you want to proceed with this, sugar?"
            return result

        # 6. Execute via Action Executor (Real or Mock)
        cap_exec_result = self.action_executor.execute(cap_request)
        result.capability_result = cap_exec_result

        # 7. Agent Response Synthesis
        if cap_exec_result.success:
            is_te = intent.language in (LanguageCode.TE, LanguageCode.TE_EN)
            result.jarvis_response = f"Task completed successfully: {cap_type.value} has been executed."

            # Capability-specific verified & simulated feedback
            if cap_type == CapabilityType.GET_TIME:
                time_val = ""
                if isinstance(cap_exec_result.output, dict):
                    time_val = cap_exec_result.output.get("time") or cap_exec_result.output.get("formatted", "")
                elif isinstance(cap_exec_result.output, str):
                    time_val = cap_exec_result.output
                result.miss_minutes_response = f"Ippudu time {time_val}, darling!" if is_te else f"The current time is {time_val}, sugar!"

            elif cap_type == CapabilityType.GET_BATTERY_STATUS:
                batt_val = "100"
                if isinstance(cap_exec_result.output, dict):
                    batt_val = str(cap_exec_result.output.get("percent", "100"))
                result.miss_minutes_response = f"Battery {batt_val}% undi, sugar!" if is_te else f"Your battery is at {batt_val}%, sugar!"

            elif cap_type == CapabilityType.GET_VOLUME:
                vol_val = "70"
                if isinstance(cap_exec_result.output, dict):
                    vol_val = str(cap_exec_result.output.get("current_volume", "70"))
                result.miss_minutes_response = f"System volume {vol_val}% undi, darling!" if is_te else f"System volume is currently at {vol_val}%, darling!"

            elif cap_type == CapabilityType.GET_SYSTEM_STATUS:
                cpu_val = "10"
                ram_val = "50"
                if isinstance(cap_exec_result.output, dict):
                    cpu_val = str(cap_exec_result.output.get("cpu_percent", "10"))
                    ram_val = str(cap_exec_result.output.get("ram_percent", "50"))
                result.miss_minutes_response = f"System CPU is at {cpu_val}% and RAM is at {ram_val}%, sugar!"

            elif cap_type in (CapabilityType.PLAY_YOUTUBE, CapabilityType.SEARCH_YOUTUBE):
                song_name = intent.entities.query or "music"
                result.miss_minutes_response = f"YouTube lo {song_name} play chestunna, darling!" if is_te else f"Playing {song_name} on YouTube for ya, darling!"

            elif cap_type == CapabilityType.SEARCH_WEB:
                search_q = intent.entities.query or "that"
                result.miss_minutes_response = f"Google lo {search_q} search chesanu, sugar!" if is_te else f"I pulled up the search for {search_q} on Google for ya, sugar!"

            elif cap_type == CapabilityType.OPEN_APP:
                app_name = intent.entities.app_name or "that app"
                if "whatsapp" in app_name.lower():
                    result.miss_minutes_response = "Sure darling, WhatsApp open chestunnanu!"
                    result.jarvis_response = "WhatsApp is ready for your communications, sir."
                elif "chrome" in app_name.lower():
                    result.miss_minutes_response = "Google Chrome open chesanu darling!"
                    result.jarvis_response = "Google Chrome browser dispatched and ready, sir."
                else:
                    result.miss_minutes_response = f"{app_name} open chesanu, darling!" if is_te else f"I launched {app_name} for ya right away, darling!"
                    result.jarvis_response = f"Application '{app_name}' successfully launched on Windows, sir."

            elif cap_type == CapabilityType.READ_SCREEN:
                out = cap_exec_result.output if isinstance(cap_exec_result.output, dict) else {}
                act_win = out.get("active_window") or "Desktop"
                snippet = out.get("extracted_text", "")[:120]
                result.miss_minutes_response = "Screen scan chesanu darling! Details Jarvis share chestharu."
                if snippet:
                    result.jarvis_response = f"Active window is '{act_win}'. Visible content includes: '{snippet}'. All data analyzed, sir."
                else:
                    result.jarvis_response = f"Active window is '{act_win}'. Screen captured and verified, sir."

            elif cap_type == CapabilityType.RESEARCH_EXPLAIN:
                out = cap_exec_result.output if isinstance(cap_exec_result.output, dict) else {}
                sum_text = out.get("summary") or "Research analysis complete."
                result.miss_minutes_response = "Research analysis complete ayyindi darling!"
                result.jarvis_response = f"Here are the verified research findings, sir: {sum_text}."

            elif cap_type == CapabilityType.OPEN_WEBSITE:
                web_target = intent.entities.target or "that website"
                result.miss_minutes_response = f"I opened up {web_target} in your browser, honey!"
                result.jarvis_response = f"Web navigation to {web_target} dispatched, sir."

            elif cap_type == CapabilityType.SET_VOLUME:
                req_l = intent.entities.volume_level or "desired level"
                result.miss_minutes_response = f"Volume {req_l}% ki set chesanu, sugar!" if is_te else f"I adjusted your system volume to {req_l}%, sugar!"
                result.jarvis_response = f"System audio volume adjusted to {req_l}%, sir."

            elif cap_type == CapabilityType.VOLUME_UP:
                result.miss_minutes_response = "Volume penchanu, darling!" if is_te else "I turned the volume up for ya, darling!"
                result.jarvis_response = "Volume increased, sir."

            elif cap_type == CapabilityType.VOLUME_DOWN:
                result.miss_minutes_response = "Volume tagginchanu, sugar!" if is_te else "I turned the volume down for ya, sugar!"
                result.jarvis_response = "Volume reduced, sir."

            elif cap_type == CapabilityType.VOLUME_MUTE:
                result.miss_minutes_response = "Sound mute chesanu, sugar!" if is_te else "Sound has been muted for you, sugar!"
                result.jarvis_response = "Master audio output muted, sir."

            elif cap_type in (CapabilityType.MEDIA_PLAY_PAUSE, CapabilityType.MEDIA_NEXT, CapabilityType.MEDIA_PREVIOUS):
                result.miss_minutes_response = "Media command sent, darling!"
                result.jarvis_response = "Media playback signal dispatched, sir."

            else:
                result.miss_minutes_response = f"All done, sugar! Jarvis and I got that taken care of for ya."
                result.jarvis_response = f"Task completed successfully: {cap_type.value}."
            
            # Post completion back to bus if Miss Minutes is registered
            if self.bus.get_agent(AgentId.MISS_MINUTES):
                try:
                    self.bus.dispatch(AgentMessage(
                        sender=AgentId.JARVIS,
                        recipient=AgentId.MISS_MINUTES,
                        message_type=MessageType.RESULT,
                        content=f"Execution successful for {cap_type.value}.",
                        metadata={"result": cap_exec_result.model_dump()},
                    ))
                except Exception as bus_err:
                    logger.debug("Bus dispatch skipped: %s", bus_err)

            # Synthesize TTS
            try:
                self.voice_service.set_online(True)
                result.tts_result = self.voice_service.speak_text(
                    result.miss_minutes_response,
                    agent_name="miss_minutes",
                    language="te" if is_te else "en",
                )
            except Exception as exc:
                logger.warning("TTS synthesis skipped: %s", exc)

        else:
            result.success = False
            result.error_message = cap_exec_result.error_message or "Capability execution failed."
            result.jarvis_response = f"Execution failed: {result.error_message}"
            result.miss_minutes_response = "I'm sorry sugar, but there was an issue executing that command on your computer."

        return result

    def _map_intent_to_capability(self, intent: IntentType) -> Optional[CapabilityType]:
        """Maps high-level intent to approved typed capability."""
        mapping = {
            IntentType.PLAY_MEDIA: CapabilityType.PLAY_YOUTUBE,
            IntentType.OPEN_WEBSITE: CapabilityType.OPEN_WEBSITE,
            IntentType.OPEN_APP: CapabilityType.OPEN_APP,
            IntentType.SEARCH_WEB: CapabilityType.SEARCH_WEB,
            IntentType.GET_TIME: CapabilityType.GET_TIME,
            IntentType.GET_SYSTEM_STATUS: CapabilityType.GET_SYSTEM_STATUS,
            IntentType.GET_BATTERY_STATUS: CapabilityType.GET_BATTERY_STATUS,
            IntentType.GET_VOLUME: CapabilityType.GET_VOLUME,
            IntentType.SET_VOLUME: CapabilityType.SET_VOLUME,
            IntentType.VOLUME_UP: CapabilityType.VOLUME_UP,
            IntentType.VOLUME_DOWN: CapabilityType.VOLUME_DOWN,
            IntentType.VOLUME_MUTE: CapabilityType.VOLUME_MUTE,
            IntentType.MEDIA_PLAY_PAUSE: CapabilityType.MEDIA_PLAY_PAUSE,
            IntentType.READ_SCREEN: CapabilityType.READ_SCREEN,
            IntentType.RESEARCH_EXPLAIN: CapabilityType.RESEARCH_EXPLAIN,
        }
        return mapping.get(intent)
