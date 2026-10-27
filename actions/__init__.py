"""
actions/__init__.py - Typed Capabilities and Execution Package.

Exports capability schemas, allowlist registry, and executors.
"""

from actions.schemas import CapabilityRequest, CapabilityResult, CapabilityType
from actions.registry import ActionRegistry, CapabilityDescriptor
from actions.mock_executor import MockActionExecutor
from actions.windows_executor import WindowsActionExecutor
from actions.apps import APPROVED_APPLICATIONS, resolve_approved_app, is_safe_url, is_app_approved

__all__ = [
    "CapabilityRequest",
    "CapabilityResult",
    "CapabilityType",
    "ActionRegistry",
    "CapabilityDescriptor",
    "MockActionExecutor",
    "WindowsActionExecutor",
    "APPROVED_APPLICATIONS",
    "resolve_approved_app",
    "is_safe_url",
    "is_app_approved",
]
