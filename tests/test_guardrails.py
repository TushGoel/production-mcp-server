"""Tests for the guardrail layer — permission enforcement, blast-radius controls, and timeouts."""

import time
import pytest
from src.registry import ToolRegistry, ToolDefinition, RiskLevel
from src.audit import AuditTrail
from src.guardrails import Guardrails, PermissionDeniedError, GuardrailViolationError, ToolTimeoutError


def _make_stack(handler=None):
    registry = ToolRegistry()
    audit = AuditTrail()
    handler = handler or (lambda **kwargs: "ok")
    registry.register(ToolDefinition(
        name="test_tool",
        description="A test tool.",
        handler=handler,
        required_permissions={"data:read"},
        risk_level=RiskLevel.LOW,
    ))
    registry.register(ToolDefinition(
        name="high_risk_tool",
        description="A high risk tool.",
        handler=lambda reason="": f"rolled back: {reason}",
        required_permissions={"ops:write"},
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True,
    ))
    guardrails = Guardrails(registry=registry, audit=audit)
    return guardrails, audit


def test_permitted_invocation():
    guardrails, audit = _make_stack()
    result = guardrails.invoke(
        tool_name="test_tool",
        arguments={},
        caller_id="agent-1",
        caller_permissions={"data:read"},
    )
    assert result == "ok"
    assert len(audit) == 1
    assert audit.get_events()[0].permitted is True


def test_permission_denied():
    guardrails, audit = _make_stack()
    with pytest.raises(PermissionDeniedError):
        guardrails.invoke(
            tool_name="test_tool",
            arguments={},
            caller_id="agent-1",
            caller_permissions=set(),  # missing data:read
        )
    assert audit.denied_count() == 1


def test_high_risk_requires_confirmation():
    guardrails, audit = _make_stack()
    with pytest.raises(GuardrailViolationError):
        guardrails.invoke(
            tool_name="high_risk_tool",
            arguments={"reason": "test"},
            caller_id="agent-1",
            caller_permissions={"ops:write"},
            confirmed=False,
        )


def test_high_risk_passes_with_confirmation():
    guardrails, audit = _make_stack()
    result = guardrails.invoke(
        tool_name="high_risk_tool",
        arguments={"reason": "incident-123"},
        caller_id="agent-1",
        caller_permissions={"ops:write"},
        confirmed=True,
    )
    assert "rolled back" in result


def test_path_traversal_blocked():
    guardrails, audit = _make_stack(handler=lambda path="": path)
    guardrails._registry._tools["test_tool"].required_permissions = set()
    with pytest.raises(GuardrailViolationError):
        guardrails.invoke(
            tool_name="test_tool",
            arguments={"path": "../../etc/passwd"},
            caller_id="agent-1",
            caller_permissions=set(),
        )


def test_destructive_sql_blocked():
    guardrails, audit = _make_stack(handler=lambda query="": query)
    guardrails._registry._tools["test_tool"].required_permissions = set()
    with pytest.raises(GuardrailViolationError):
        guardrails.invoke(
            tool_name="test_tool",
            arguments={"query": "DROP TABLE users"},
            caller_id="agent-1",
            caller_permissions=set(),
        )


def test_audit_records_all_events():
    guardrails, audit = _make_stack()
    try:
        guardrails.invoke("test_tool", {}, "agent-1", set())
    except PermissionDeniedError:
        pass
    guardrails.invoke("test_tool", {}, "agent-1", {"data:read"})
    assert len(audit) == 2
    assert audit.denied_count() == 1


def test_tool_timeout_raises():
    registry = ToolRegistry()
    audit = AuditTrail()

    def slow_handler(**kwargs):
        time.sleep(10)  # intentionally hangs
        return "never reached"

    registry.register(ToolDefinition(
        name="slow_tool",
        description="A slow tool.",
        handler=slow_handler,
        required_permissions=set(),
        risk_level=RiskLevel.LOW,
    ))
    guardrails = Guardrails(registry=registry, audit=audit, default_timeout_seconds=0.1)
    with pytest.raises(ToolTimeoutError):
        guardrails.invoke("slow_tool", {}, "agent-1", set())


def test_fast_tool_completes_within_timeout():
    guardrails, audit = _make_stack()
    # Default timeout is 30s — a fast tool should complete immediately
    result = guardrails.invoke("test_tool", {}, "agent-1", {"data:read"}, timeout_seconds=5.0)
    assert result == "ok"


def test_timeout_is_logged_in_audit():
    registry = ToolRegistry()
    audit = AuditTrail()

    def blocking_handler(**kwargs):
        time.sleep(10)
        return "done"

    registry.register(ToolDefinition(
        name="blocking_tool",
        description="Blocks.",
        handler=blocking_handler,
        required_permissions=set(),
        risk_level=RiskLevel.LOW,
    ))
    guardrails = Guardrails(registry=registry, audit=audit, default_timeout_seconds=0.05)
    try:
        guardrails.invoke("blocking_tool", {}, "agent-1", set())
    except ToolTimeoutError:
        pass
    # Audit still records the attempt even on timeout
    assert len(audit) == 1
