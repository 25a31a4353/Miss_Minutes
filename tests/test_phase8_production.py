"""
tests/test_phase8_production.py - Production Consolidation, Integration & Desktop Readiness Tests.

Validates Phase 8 requirements:
1. Single application entry point (main.py) and CLI flags.
2. Clean lifecycle startup and shutdown without orphaned resources.
3. Strict invariant enforcement: COUNT(JARVIS_IMPLEMENTATIONS) = 1.
4. Miss Minutes -> Jarvis delegation across typed message bus.
5. Jarvis -> SecurityValidator capability gating.
6. SecurityValidator -> Windows executor boundary.
7. OFFLINE master authority: zero background execution when assistant is OFFLINE.
8. End-to-end representative capability workflows:
   - OPEN_APP (Notepad)
   - OPEN_WEBSITE (YouTube)
   - SEARCH_WEB (Multilingual / English)
   - SEARCH_YOUTUBE
   - SET_VOLUME
   - Dangerous command blocking (injection / shell)
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from actions.mock_executor import MockActionExecutor
from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType
from agents import (
    AgentId,
    AgentMessage,
    AgentMessageBus,
    MessageType,
    MissMinutesAgent,
    SharedBoundedContext,
)
from ai.mock_provider import MockAIProvider
from config.settings import AppSettings
from jarvis import Jarvis, get_jarvis
from security.permissions import SecurityDecision
from security.validator import SecurityValidator
from ui.state_machine import AppStateMachine, AssistantState


class TestPhase8SingleJarvisInvariant(unittest.TestCase):
    """Verifies the core architectural mandate: COUNT(JARVIS_IMPLEMENTATIONS) = 1."""

    def test_single_jarvis_invariant(self):
        """Validates that exactly one Jarvis class exists and is a singleton."""
        import jarvis
        import agents.jarvis_agent as proxy_module

        # 1. Instance from get_jarvis is an instance of jarvis.Jarvis
        j1 = get_jarvis()
        j2 = get_jarvis()
        self.assertIs(j1, j2)
        self.assertIsInstance(j1, jarvis.Jarvis)

        # 2. agents.jarvis_agent is purely a proxy to jarvis.Jarvis
        self.assertIs(proxy_module.Jarvis, jarvis.Jarvis)
        self.assertIs(proxy_module.get_jarvis, jarvis.get_jarvis)

    def test_jarvis_has_no_duplicated_engine(self):
        """Confirms jarvis.py uses jarvis_brain, jarvis_actions, and jarvis_market directly."""
        j = get_jarvis()
        import jarvis_actions
        import jarvis_brain
        import jarvis_market

        self.assertIs(j.brain, jarvis_brain)
        self.assertIs(j.actions, jarvis_actions)
        self.assertIs(j.market, jarvis_market)

    def test_jarvis_direct_developer_mode(self):
        """Verifies developer direct access in jarvis.py executes without duplicate logic."""
        j = get_jarvis()
        res = j.think("status diagnostics")
        self.assertIn("Nominal", res)


class TestPhase8EntryPointAndCLI(unittest.TestCase):
    """Verifies the primary application entry point (main.py) and CLI options."""

    def test_diagnostics_cli_option(self):
        """Tests that 'python main.py --diagnostics' completes with exit code 0."""
        from main import main
        exit_code = main(["--diagnostics"])
        self.assertEqual(exit_code, 0)

    def test_jarvis_developer_cli_option(self):
        """Tests that 'python main.py --jarvis <query>' returns exit code 0."""
        from main import main
        exit_code = main(["--jarvis", "check", "system", "status"])
        self.assertEqual(exit_code, 0)

    def test_version_cli_option(self):
        """Tests that 'python main.py --version' displays version and raises SystemExit(0)."""
        from main import main
        with self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_app_main_delegates_to_root_main(self):
        """Verifies app/main.py main() cleanly delegates to root main.py with zero competing lifecycle."""
        with patch("main.main", return_value=42) as mock_root:
            from app.main import main as app_main
            exit_code = app_main()
            self.assertEqual(exit_code, 42)
            mock_root.assert_called_once()


class TestPhase8LifecycleAndShutdown(unittest.TestCase):
    """Verifies clean application lifecycle startup, state binding, and shutdown."""

    def setUp(self):
        from PySide6.QtWidgets import QApplication
        self.qapp = QApplication.instance() or QApplication(sys.argv)

    def test_clean_startup_and_shutdown(self):
        """Tests that MissMinutesApp initializes all subsystems cleanly and shuts down without leaks."""
        from app.main import MissMinutesApp

        settings = AppSettings(
            app_name="MissMinutesTest",
            start_state="OFFLINE",
            always_on_top=False,
        )
        mock_executor = MockActionExecutor()
        app = MissMinutesApp(settings=settings, qapp=self.qapp, action_executor=mock_executor)

        # Verify initial state is OFFLINE
        self.assertEqual(app.state_machine.current_state, AssistantState.OFFLINE)
        self.assertFalse(app.state_machine.is_online)

        # Turn ON
        app.state_machine.turn_on()
        self.assertEqual(app.state_machine.current_state, AssistantState.IDLE)
        self.assertTrue(app.state_machine.is_online)

        # Verify Dual-Agent Registration
        self.assertIsNotNone(app.bus.get_agent(AgentId.MISS_MINUTES))
        self.assertIsNotNone(app.bus.get_agent(AgentId.JARVIS))

        # Verify Clean Shutdown
        app.shutdown()
        self.assertEqual(app.state_machine.current_state, AssistantState.OFFLINE)
        self.assertFalse(app.state_machine.is_online)


class TestPhase8DelegationAndSecurityGate(unittest.TestCase):
    """Verifies Miss Minutes -> Jarvis delegation and strict SecurityValidator enforcement."""

    def setUp(self):
        self.state_machine = AppStateMachine(initial_state=AssistantState.IDLE)
        self.context = SharedBoundedContext(max_turns=10)
        self.bus = AgentMessageBus(state_machine=self.state_machine, context=self.context)
        self.miss_minutes = MissMinutesAgent()
        self.jarvis = get_jarvis()
        self.bus.register_agent(self.miss_minutes)
        self.bus.register_agent(self.jarvis)
        self.validator = SecurityValidator()
        self.mock_executor = MockActionExecutor()

    def test_miss_minutes_to_jarvis_delegation(self):
        """Verifies structured task delegation from Miss Minutes to Jarvis."""
        msg = AgentMessage(
            sender=AgentId.MISS_MINUTES,
            recipient=AgentId.JARVIS,
            message_type=MessageType.DELEGATION,
            content="Could you check system diagnostics?",
        )
        reply = self.bus.dispatch(msg)
        self.assertIsNotNone(reply)
        self.assertEqual(reply.sender, AgentId.JARVIS)
        self.assertEqual(reply.message_type, MessageType.RESULT)
        self.assertIn("GET_SYSTEM_STATUS", reply.content)
        self.assertEqual(reply.metadata.get("action_type"), "GET_SYSTEM_STATUS")
        self.assertEqual(reply.metadata.get("security_decision"), "ALLOW")

    def test_jarvis_action_planning_passes_through_security_gate(self):
        """Verifies that an action planned by Jarvis must be validated by SecurityValidator."""
        delegation_msg = AgentMessage(
            sender=AgentId.MISS_MINUTES,
            recipient=AgentId.JARVIS,
            message_type=MessageType.DELEGATION,
            content="Could you open Notepad for our user?",
        )
        req = self.jarvis.plan_capability_request(delegation_msg)
        self.assertIsNotNone(req)
        self.assertEqual(req.capability, CapabilityType.OPEN_APP)

        # Gated by SecurityValidator
        val_result = self.validator.validate_capability_request(req, is_assistant_online=True)
        self.assertEqual(val_result.decision, SecurityDecision.ALLOW)

        # Dispatched to Executor
        exec_result = self.mock_executor.execute(req)
        self.assertTrue(exec_result.success)
        self.assertEqual(exec_result.capability, CapabilityType.OPEN_APP)

    def test_dangerous_request_denied_by_security_validator(self):
        """Verifies injection payloads and shell commands are blocked and never executed."""
        dangerous_req = CapabilityRequest(
            capability=CapabilityType.OPEN_APP,
            parameters={"app_name": "cmd.exe /c format c:"},
            requested_by="attacker",
        )
        val_result = self.validator.validate_capability_request(dangerous_req, is_assistant_online=True)
        self.assertEqual(val_result.decision, SecurityDecision.DENY)
        self.assertIn("Security violation", val_result.reason)

        # Ensure MockExecutor was NOT called for dangerous action
        self.assertEqual(len(self.mock_executor.execution_history), 0)


class TestPhase8OfflineAbsoluteAuthority(unittest.TestCase):
    """Verifies that OFFLINE state strictly shuts down all execution."""

    def setUp(self):
        self.state_machine = AppStateMachine(initial_state=AssistantState.OFFLINE)
        self.validator = SecurityValidator()
        self.mock_executor = MockActionExecutor()

    def test_offline_denies_all_capabilities(self):
        """Verifies that every capability is denied when assistant is OFFLINE."""
        req = CapabilityRequest(
            capability=CapabilityType.OPEN_APP,
            parameters={"app_name": "notepad"},
        )
        val_result = self.validator.validate_capability_request(
            req,
            is_assistant_online=self.state_machine.is_online,  # False
        )
        self.assertEqual(val_result.decision, SecurityDecision.DENY)
        self.assertIn("OFFLINE", val_result.reason)

        # Volume change also denied in OFFLINE
        vol_req = CapabilityRequest(
            capability=CapabilityType.SET_VOLUME,
            parameters={"level": 50},
        )
        vol_result = self.validator.validate_capability_request(
            vol_req,
            is_assistant_online=self.state_machine.is_online,  # False
        )
        self.assertEqual(vol_result.decision, SecurityDecision.DENY)
        self.assertIn("OFFLINE", vol_result.reason)


class TestPhase8RepresentativeWorkflows(unittest.TestCase):
    """Tests end-to-end representative workflows through the unified CapabilityPipeline."""

    def setUp(self):
        self.state_machine = AppStateMachine(initial_state=AssistantState.IDLE)
        self.context = SharedBoundedContext(max_turns=10)
        self.bus = AgentMessageBus(state_machine=self.state_machine, context=self.context)
        self.mock_ai = MockAIProvider(default_text_response="I'm on it! Let's get that done for you.")
        self.miss_minutes = MissMinutesAgent(ai_provider=self.mock_ai)
        self.jarvis = get_jarvis()
        self.bus.register_agent(self.miss_minutes)
        self.bus.register_agent(self.jarvis)
        self.mock_executor = MockActionExecutor()

        from app.pipeline import CapabilityPipeline
        self.pipeline = CapabilityPipeline(
            ai_provider=self.mock_ai,
            action_executor=self.mock_executor,
            message_bus=self.bus,
            context=self.context,
        )

    def test_workflow_open_app(self):
        """User: 'Hey Minutes, open Notepad' -> OPEN_APP dispatched and verified."""
        res = self.pipeline.execute_pipeline("open notepad", is_online=True)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.capability_result)
        self.assertEqual(res.capability_result.capability, CapabilityType.OPEN_APP)

    def test_workflow_open_website(self):
        """User: 'Hey Minutes, open YouTube' -> OPEN_WEBSITE dispatched and verified."""
        res = self.pipeline.execute_pipeline("open youtube", is_online=True)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.capability_result)
        self.assertEqual(res.capability_result.capability, CapabilityType.OPEN_WEBSITE)

    def test_workflow_search_web(self):
        """User: 'Search Google for quantum computing' -> SEARCH_WEB dispatched and verified."""
        res = self.pipeline.execute_pipeline("search web for quantum computing", is_online=True)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.capability_result)
        self.assertEqual(res.capability_result.capability, CapabilityType.SEARCH_WEB)

    def test_workflow_search_youtube(self):
        """User: 'Search youtube for Telugu songs' -> SEARCH_YOUTUBE dispatched and verified."""
        res = self.pipeline.execute_pipeline("search youtube for Telugu songs", is_online=True)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.capability_result)
        self.assertIn(res.capability_result.capability, (CapabilityType.SEARCH_YOUTUBE, CapabilityType.PLAY_YOUTUBE))

    def test_workflow_set_volume(self):
        """User: 'Set volume to 50' -> REQUIRES_CONFIRMATION gate without confirmation, executed when confirmed."""
        # Unconfirmed: stops at confirmation gate
        unconf_res = self.pipeline.execute_pipeline("set volume to 50", is_online=True, user_confirmed=False)
        self.assertFalse(unconf_res.success)
        self.assertEqual(unconf_res.security_result.decision, SecurityDecision.REQUIRES_CONFIRMATION)

        # Confirmed: executes through security gate
        conf_res = self.pipeline.execute_pipeline("set volume to 50", is_online=True, user_confirmed=True)
        self.assertTrue(conf_res.success)
        self.assertIsNotNone(conf_res.capability_result)
        self.assertEqual(conf_res.capability_result.capability, CapabilityType.SET_VOLUME)

    def test_workflow_blocked_unsafe(self):
        """User: 'delete all files in c:/windows' -> BLOCKED at security gate, 0 actions executed."""
        res = self.pipeline.execute_pipeline("delete all files in c:/windows", is_online=True)
        # Unsafe command should either fail or not execute capability
        self.assertIsNone(res.capability_result)
        # Mock executor should have zero records of unsafe capability
        self.assertEqual(len(self.mock_executor.execution_history), 0)


if __name__ == "__main__":
    unittest.main()
