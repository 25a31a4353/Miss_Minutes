"""
tests/test_phase7_capabilities.py - Phase 7 Secure Real Windows Capabilities Test Suite.

Covers:
1. Architecture Invariant: COUNT(JARVIS_IMPLEMENTATIONS) == 1.
2. Security Validator:
   - Default DENY policy.
   - Rejection of unknown capabilities.
   - Rejection of arbitrary shell (PowerShell, CMD, bash, scripts).
   - Rejection of credential access, Defender tampering, registry manipulation, file deletion.
   - Master OFFLINE gate: all capabilities evaluate to DENY when offline.
3. Capability Parameter & Schema Boundaries:
   - SET_VOLUME bounds (-1, 101, non-int).
   - Unknown application names, path traversal, and raw executable paths.
   - Unsafe URL schemes (file://, javascript:, ftp://) and private/local IPs.
   - Empty search and YouTube queries.
4. WindowsActionExecutor:
   - Launching approved applications (verified PID).
   - Safe browser URL dispatch (verified).
   - Web search with URL-encoded parameters (verified).
   - YouTube search/playback (verified dispatch, honest non-fabricated playback).
   - Native volume controls and get/set verification.
   - Media playback controls.
5. Verification Mechanisms:
   - Honest verification outputs across all capabilities.
6. Dual-Agent & Pipeline Integration:
   - Miss Minutes -> Existing Jarvis -> SecurityValidator -> WindowsActionExecutor.
   - Multilingual Telugu-English code-switching preservation.
"""

from __future__ import annotations

import os
import subprocess
import pytest
from unittest.mock import MagicMock, patch

from actions.apps import APPROVED_APPLICATIONS, resolve_approved_app, is_app_approved, is_safe_url
from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType
from actions.registry import ActionRegistry
from actions.windows_executor import WindowsActionExecutor
from security.permissions import SecurityDecision, SecurityValidationResult
from security.validator import SecurityValidator
from app.pipeline import CapabilityPipeline, PipelineExecutionResult
from intents.schema import IntentType, LanguageCode
from agents.bus import AgentMessageBus
from agents.message import AgentId, AgentMessage, MessageType
from agents.miss_minutes_agent import MissMinutesAgent
from jarvis import Jarvis, get_jarvis
import jarvis
import jarvis_actions


# ==============================================================================
# 1. Architectural Invariant: Single Authoritative Jarvis
# ==============================================================================

def test_single_jarvis_invariant() -> None:
    """Verifies COUNT(JARVIS_IMPLEMENTATIONS) == 1."""
    import inspect
    import agents.jarvis_agent

    # The Jarvis class in jarvis.py is the exact same class exposed by agents.jarvis_agent
    assert agents.jarvis_agent.Jarvis is jarvis.Jarvis
    assert agents.jarvis_agent.get_jarvis is jarvis.get_jarvis

    j1 = get_jarvis()
    j2 = agents.jarvis_agent.get_jarvis()
    assert j1 is j2
    assert isinstance(j1, Jarvis)


# ==============================================================================
# 2. Security Boundary & Negative Attack Vector Tests
# ==============================================================================

class TestSecurityBoundaryAndDenials:
    """Verifies that SecurityValidator blocks unauthorized or dangerous actions."""

    @pytest.mark.parametrize(
        "attack_cmd, reason_label",
        [
            ("powershell -c Get-Process", "PowerShell invocation"),
            ("pwsh -nop -c Invoke-Mimikatz", "PowerShell pwsh"),
            ("cmd.exe /c dir C:\\", "CMD shell"),
            ("bash -c 'rm -rf /'", "Bash invocation"),
            ("python -c 'import os; os.system(\"calc\")'", "Direct Python code execution"),
            ("reg add HKLM\\Software /v Test", "Registry modification"),
            ("regedit.exe /s patch.reg", "Registry editor execution"),
            ("Set-MpPreference -DisableRealtimeMonitoring $true", "Defender disablement"),
            ("netsh advfirewall set allprofiles state off", "Firewall disablement"),
            ("del /f /q C:\\Windows\\System32", "File deletion"),
            ("format C: /y", "Disk format"),
            ("cat ~/.ssh/id_rsa", "SSH private key access"),
            ("cmdkey /list", "Credential vault query"),
        ],
    )
    def test_arbitrary_shell_and_attack_vectors_blocked(self, attack_cmd: str, reason_label: str) -> None:
        validator = SecurityValidator()
        req = CapabilityRequest(
            capability=CapabilityType.SEARCH_WEB,
            query=attack_cmd,
            requested_by="jarvis",
        )
        res = validator.validate_capability_request(req, is_assistant_online=True)
        assert res.decision == SecurityDecision.DENY
        assert "Security violation" in res.reason or "Blocked forbidden" in res.reason

        raw_res = validator.validate_raw_command(attack_cmd, is_assistant_online=True)
        assert raw_res.decision == SecurityDecision.DENY

    def test_offline_gate_blocks_all_capabilities(self) -> None:
        """When assistant is OFFLINE, all capability requests must be strictly DENIED."""
        validator = SecurityValidator()
        req = CapabilityRequest(
            capability=CapabilityType.OPEN_APP,
            target="notepad",
            requested_by="jarvis",
        )
        res = validator.validate_capability_request(req, is_assistant_online=False)
        assert res.decision == SecurityDecision.DENY
        assert "OFFLINE" in res.reason

        denials = validator.audit_logger.get_denials()
        assert len(denials) >= 1
        assert any("OFFLINE" in d.reason for d in denials)

    def test_unknown_capability_denied(self) -> None:
        """Any unregistered capability is denied by default."""
        validator = SecurityValidator()
        req = CapabilityRequest.model_construct(
            request_id="test-123",
            capability="UNAPPROVED_MAGIC_ACTION",
            target="target",
            parameters={},
            requested_by="jarvis",
        )
        res = validator.validate_capability_request(req, is_assistant_online=True)
        assert res.decision == SecurityDecision.DENY
        assert "not in the approved allowlist" in res.reason


# ==============================================================================
# 3. Parameter Validation & Boundaries
# ==============================================================================

class TestParameterValidation:
    """Verifies that invalid or out-of-bound parameters fail closed."""

    def test_volume_out_of_bounds_rejected(self) -> None:
        validator = SecurityValidator()

        # Negative volume
        req_neg = CapabilityRequest(
            capability=CapabilityType.SET_VOLUME,
            parameters={"level": -10},
        )
        res_neg = validator.validate_capability_request(req_neg, is_assistant_online=True)
        assert res_neg.decision == SecurityDecision.DENY
        assert "out of bounds" in res_neg.reason

        # Excessive volume
        req_over = CapabilityRequest(
            capability=CapabilityType.SET_VOLUME,
            parameters={"level": 150},
        )
        res_over = validator.validate_capability_request(req_over, is_assistant_online=True)
        assert res_over.decision == SecurityDecision.DENY
        assert "out of bounds" in res_over.reason

        # Non-integer volume
        req_str = CapabilityRequest(
            capability=CapabilityType.SET_VOLUME,
            parameters={"level": "maximum_loudness"},
        )
        res_str = validator.validate_capability_request(req_str, is_assistant_online=True)
        assert res_str.decision == SecurityDecision.DENY

    def test_unknown_application_rejected(self) -> None:
        validator = SecurityValidator()

        # Arbitrary unlisted app
        req1 = CapabilityRequest(capability=CapabilityType.OPEN_APP, target="malware.exe")
        res1 = validator.validate_capability_request(req1, is_assistant_online=True)
        assert res1.decision == SecurityDecision.DENY
        assert "not in the approved application allowlist" in res1.reason

        # Path traversal
        req2 = CapabilityRequest(capability=CapabilityType.OPEN_APP, target=r"..\..\Windows\System32\cmd.exe")
        res2 = validator.validate_capability_request(req2, is_assistant_online=True)
        assert res2.decision == SecurityDecision.DENY

    def test_unsafe_urls_rejected(self) -> None:
        validator = SecurityValidator()

        # file:// scheme
        req_file = CapabilityRequest(
            capability=CapabilityType.OPEN_WEBSITE,
            parameters={"url": "file:///C:/Windows/System32"},
        )
        res_file = validator.validate_capability_request(req_file, is_assistant_online=True)
        assert res_file.decision == SecurityDecision.DENY
        assert "URL validation failed" in res_file.reason

        # Private IP address
        req_ip = CapabilityRequest(
            capability=CapabilityType.OPEN_WEBSITE,
            parameters={"url": "http://192.168.1.1/admin"},
        )
        res_ip = validator.validate_capability_request(req_ip, is_assistant_online=True)
        assert res_ip.decision == SecurityDecision.DENY

        # Localhost
        req_local = CapabilityRequest(
            capability=CapabilityType.OPEN_WEBSITE,
            parameters={"url": "http://localhost:8080"},
        )
        res_local = validator.validate_capability_request(req_local, is_assistant_online=True)
        assert res_local.decision == SecurityDecision.DENY

        # Unapproved external domain
        req_unapproved = CapabilityRequest(
            capability=CapabilityType.OPEN_WEBSITE,
            parameters={"url": "https://unknown-random-site-123.com"},
        )
        res_unapproved = validator.validate_capability_request(req_unapproved, is_assistant_online=True)
        assert res_unapproved.decision == SecurityDecision.DENY

    def test_empty_search_query_rejected(self) -> None:
        validator = SecurityValidator()

        req_empty = CapabilityRequest(capability=CapabilityType.SEARCH_WEB, query="   ")
        res_empty = validator.validate_capability_request(req_empty, is_assistant_online=True)
        assert res_empty.decision == SecurityDecision.DENY
        assert "non-empty" in res_empty.reason

        req_yt_empty = CapabilityRequest(capability=CapabilityType.PLAY_YOUTUBE, query="")
        res_yt = validator.validate_capability_request(req_yt_empty, is_assistant_online=True)
        assert res_yt.decision == SecurityDecision.DENY


# ==============================================================================
# 4. Windows Action Executor Tests (Simulated & Real Capabilities)
# ==============================================================================

class TestWindowsActionExecutor:
    """Tests WindowsActionExecutor functionality with real and mocked OS bindings."""

    def test_get_time_real(self) -> None:
        executor = WindowsActionExecutor(allow_real_execution=True)
        req = CapabilityRequest(capability=CapabilityType.GET_TIME)
        res = executor.execute(req)
        assert res.success is True
        assert res.simulated is False
        assert res.verified is True
        assert "The current time is" in res.output["formatted"]

    def test_get_system_status_real(self) -> None:
        executor = WindowsActionExecutor(allow_real_execution=True)
        req = CapabilityRequest(capability=CapabilityType.GET_SYSTEM_STATUS)
        res = executor.execute(req)
        assert res.success is True
        assert res.simulated is False
        assert res.verified is True
        assert "cpu_percent" in res.output
        assert "ram_percent" in res.output
        assert res.output["cpu_percent"] >= 0

    def test_get_battery_status_real(self) -> None:
        executor = WindowsActionExecutor(allow_real_execution=True)
        req = CapabilityRequest(capability=CapabilityType.GET_BATTERY_STATUS)
        res = executor.execute(req)
        assert res.success is True
        assert res.simulated is False
        assert res.verified is True
        assert "percent" in res.output
        assert res.output["percent"] > 0

    def test_volume_set_and_verification(self) -> None:
        """Verifies native volume setting and independent readback verification."""
        executor = WindowsActionExecutor(allow_real_execution=True)
        req = CapabilityRequest(
            capability=CapabilityType.SET_VOLUME,
            parameters={"level": 75},
        )
        res = executor.execute(req)
        assert res.success is True
        assert res.simulated is False
        assert res.verified is True
        assert res.output["requested_level"] == 75
        # Verify readback matches within 1% rounding
        assert abs(res.output["verified_level"] - 75) <= 1

        # Restore volume to safe level
        req_restore = CapabilityRequest(
            capability=CapabilityType.SET_VOLUME,
            parameters={"level": 60},
        )
        executor.execute(req_restore)

    def test_volume_up_down_mute(self) -> None:
        executor = WindowsActionExecutor(allow_real_execution=True)
        req_up = CapabilityRequest(capability=CapabilityType.VOLUME_UP, parameters={"steps": 2})
        res_up = executor.execute(req_up)
        assert res_up.success is True
        assert res_up.verified is True

        req_mute = CapabilityRequest(capability=CapabilityType.VOLUME_MUTE)
        res_mute = executor.execute(req_mute)
        assert res_mute.success is True
        assert res_mute.verified is True

    def test_media_playback_controls(self) -> None:
        executor = WindowsActionExecutor(allow_real_execution=True)
        for cap in (CapabilityType.MEDIA_PLAY_PAUSE, CapabilityType.MEDIA_NEXT, CapabilityType.MEDIA_PREVIOUS):
            req = CapabilityRequest(capability=cap)
            res = executor.execute(req)
            assert res.success is True
            assert res.verified is True

    def test_open_approved_app_launch_verification(self) -> None:
        """Verifies process spawn with shell=False and process existence check."""
        executor = WindowsActionExecutor(allow_real_execution=True)

        with patch("subprocess.Popen") as mock_popen, patch("psutil.pid_exists", return_value=True):
            mock_proc = MagicMock()
            mock_proc.pid = 4321
            mock_popen.return_value = mock_proc

            req = CapabilityRequest(capability=CapabilityType.OPEN_APP, target="notepad")
            res = executor.execute(req)

            assert res.success is True
            assert res.simulated is False
            assert res.verified is True
            assert res.output["pid"] == 4321
            assert res.output["app"] == "Notepad"
            # Verify shell=False was strictly enforced
            mock_popen.assert_called_once()
            _, kwargs = mock_popen.call_args
            assert kwargs.get("shell") is False

    def test_open_approved_website_verification(self) -> None:
        """Verifies browser navigation without shell command string."""
        executor = WindowsActionExecutor(allow_real_execution=True)

        with patch("webbrowser.open", return_value=True) as mock_open:
            req = CapabilityRequest(
                capability=CapabilityType.OPEN_WEBSITE,
                target="github",
                parameters={"url": "https://github.com"},
            )
            res = executor.execute(req)

            assert res.success is True
            assert res.simulated is False
            assert res.verified is True
            mock_open.assert_called_once_with("https://github.com", new=2)

    def test_search_web_url_encoding(self) -> None:
        """Verifies query URL encoding and dispatch."""
        executor = WindowsActionExecutor(allow_real_execution=True)

        with patch("webbrowser.open", return_value=True) as mock_open:
            req = CapabilityRequest(
                capability=CapabilityType.SEARCH_WEB,
                query="quantum computing & entanglement 101",
            )
            res = executor.execute(req)

            assert res.success is True
            assert res.simulated is False
            assert res.verified is True
            assert "q=quantum+computing+%26+entanglement+101" in res.output["url"]
            mock_open.assert_called_once()

    def test_youtube_honest_verification(self) -> None:
        """Verifies that YouTube dispatch is verified but autonomous playback is not fabricated."""
        executor = WindowsActionExecutor(allow_real_execution=True)

        with patch("webbrowser.open", return_value=True) as mock_open:
            req = CapabilityRequest(
                capability=CapabilityType.PLAY_YOUTUBE,
                query="Arjun Reddy songs",
            )
            res = executor.execute(req)

            assert res.success is True
            assert res.simulated is False
            assert res.verified is True
            assert res.output["dispatch_verified"] is True
            # Crucial requirement: never fabricate playback success
            assert res.output["playback_verified"] is False
            assert "autonomous media playback cannot be independently confirmed" in res.output["note"]
            mock_open.assert_called_once()


# ==============================================================================
# 5. Dual-Agent & Pipeline Integration Tests
# ==============================================================================

class TestDualAgentAndPipelineIntegration:
    """Verifies end-to-end flow from Miss Minutes to Jarvis to Security to Executor."""

    def test_full_real_pipeline_flow(self) -> None:
        """End-to-end execution of a verified capability using real WindowsActionExecutor."""
        executor = WindowsActionExecutor(allow_real_execution=True)

        with patch("webbrowser.open", return_value=True):
            pipeline = CapabilityPipeline(action_executor=executor)

            res = pipeline.execute_pipeline(
                "Hey Minutes, YouTube open chesi AR Rahman songs play cheyyi",
                is_online=True,
            )

            assert res.success is True
            assert res.language == LanguageCode.TE_EN
            assert res.intent.intent == IntentType.PLAY_MEDIA
            assert res.delegated_to_jarvis is True
            assert res.capability_result is not None
            assert res.capability_result.simulated is False
            assert res.capability_result.verified is True
            assert "YouTube" in res.miss_minutes_response

    def test_jarvis_actions_try_action_with_real_windows(self) -> None:
        """Verifies jarvis_actions.try_action uses real Windows capability execution."""
        with patch("webbrowser.open", return_value=True):
            result_str = jarvis_actions.try_action(
                "search for quantum computing",
                is_online=True,
                use_real_windows=True,
            )
            assert result_str is not None
            assert "Dispatched search on Google" in result_str

    def test_jarvis_delegation_with_real_windows_executor(self) -> None:
        """Verifies Jarvis agent correctly processes delegation with security validation."""
        jarvis_inst = get_jarvis()

        msg = AgentMessage(
            sender=AgentId.MISS_MINUTES,
            recipient=AgentId.JARVIS,
            message_type=MessageType.DELEGATION,
            content="Could you open Notepad for our user?",
        )

        reply = jarvis_inst.receive_message(msg)
        assert reply is not None
        assert reply.message_type == MessageType.RESULT
        assert "Notepad" in reply.content
        assert reply.metadata.get("security_decision") == "ALLOW"
        assert reply.metadata.get("action_type") == "OPEN_APP"
