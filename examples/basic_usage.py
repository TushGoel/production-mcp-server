"""
Standalone example — use the guardrail + audit stack without the MCP server.
Run: python examples/basic_usage.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.registry import ToolRegistry, ToolDefinition, RiskLevel
from src.audit import AuditTrail
from src.guardrails import Guardrails, PermissionDeniedError, GuardrailViolationError
from src.tools.example_tools import read_deployment_status, query_metrics


def main():
    # Set up
    registry = ToolRegistry()
    audit = AuditTrail()

    registry.register(ToolDefinition(
        name="deployment_status",
        description="Get deployment status.",
        handler=read_deployment_status,
        required_permissions={"deployments:read"},
        risk_level=RiskLevel.LOW,
    ))
    registry.register(ToolDefinition(
        name="metrics",
        description="Query metrics.",
        handler=query_metrics,
        required_permissions={"metrics:read"},
        risk_level=RiskLevel.LOW,
    ))

    guardrails = Guardrails(registry=registry, audit=audit)

    print("=== Permitted invocations ===")
    result = guardrails.invoke(
        "deployment_status",
        {"deployment_id": "deploy-abc123"},
        caller_id="oncall-agent",
        caller_permissions={"deployments:read", "metrics:read"},
    )
    print(f"Deployment status: {result}")

    result = guardrails.invoke(
        "metrics",
        {"metric_name": "error_rate", "window_minutes": 30},
        caller_id="oncall-agent",
        caller_permissions={"deployments:read", "metrics:read"},
    )
    print(f"Metrics: {result}")

    print("\n=== Denied invocation (missing permission) ===")
    try:
        guardrails.invoke(
            "metrics",
            {"metric_name": "cpu"},
            caller_id="restricted-agent",
            caller_permissions=set(),  # no permissions
        )
    except PermissionDeniedError as e:
        print(f"Blocked: {e}")

    print("\n=== Audit trail ===")
    print(f"Total events: {len(audit)}")
    print(f"Denied requests: {audit.denied_count()}")
    for event in audit.get_events():
        status = "✓" if event.permitted else "✗"
        print(f"  {status} [{event.caller_id}] {event.tool_name} ({event.duration_ms:.1f}ms)")


if __name__ == "__main__":
    main()
