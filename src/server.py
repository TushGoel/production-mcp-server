"""
Production MCP Server entry point.

Wires together the tool registry, guardrails, and audit trail into a
running MCP server. Agents connect via the MCP protocol and can only
invoke tools they are explicitly authorized for.
"""

from mcp.server.fastmcp import FastMCP
from .registry import ToolRegistry, ToolDefinition, RiskLevel
from .guardrails import Guardrails
from .audit import AuditTrail
from .tools.example_tools import (
    read_deployment_status,
    query_metrics,
    run_database_query,
    trigger_rollback,
)

# ── Infrastructure ────────────────────────────────────────────────────────────

audit = AuditTrail()
registry = ToolRegistry()

# Register tools with explicit permissions and risk classification
registry.register(ToolDefinition(
    name="read_deployment_status",
    description="Fetch the current health and status of a deployment by ID.",
    handler=read_deployment_status,
    required_permissions={"deployments:read"},
    risk_level=RiskLevel.LOW,
))

registry.register(ToolDefinition(
    name="query_metrics",
    description="Retrieve metric values for a given metric name and time window.",
    handler=query_metrics,
    required_permissions={"metrics:read"},
    risk_level=RiskLevel.LOW,
))

registry.register(ToolDefinition(
    name="run_database_query",
    description="Execute a read-only SELECT query against the database replica.",
    handler=run_database_query,
    required_permissions={"database:read"},
    risk_level=RiskLevel.MEDIUM,
))

registry.register(ToolDefinition(
    name="trigger_rollback",
    description="Initiate a deployment rollback. HIGH risk — requires explicit confirmation.",
    handler=trigger_rollback,
    required_permissions={"deployments:write", "deployments:rollback"},
    risk_level=RiskLevel.HIGH,
    requires_confirmation=True,
))

# ── Example caller identity (replace with your auth layer) ───────────────────
# In production: derive from the MCP session context, OAuth token, or workload identity.
CALLER_ID = "oncall-agent-v1"
CALLER_PERMISSIONS = {"deployments:read", "metrics:read", "database:read"}
# Note: deployments:write intentionally excluded — agent cannot trigger rollback

guardrails = Guardrails(registry=registry, audit=audit)

# ── MCP Server ────────────────────────────────────────────────────────────────

mcp = FastMCP("production-mcp-server")


@mcp.tool()
def deployment_status(deployment_id: str) -> dict:
    """Get deployment health and status."""
    return guardrails.invoke(
        tool_name="read_deployment_status",
        arguments={"deployment_id": deployment_id},
        caller_id=CALLER_ID,
        caller_permissions=CALLER_PERMISSIONS,
    )


@mcp.tool()
def metrics(metric_name: str, window_minutes: int = 60) -> dict:
    """Retrieve metric values for analysis."""
    return guardrails.invoke(
        tool_name="query_metrics",
        arguments={"metric_name": metric_name, "window_minutes": window_minutes},
        caller_id=CALLER_ID,
        caller_permissions=CALLER_PERMISSIONS,
    )


@mcp.tool()
def database_query(query: str, database: str = "readonly_replica") -> list:
    """Run a read-only database query."""
    return guardrails.invoke(
        tool_name="run_database_query",
        arguments={"query": query, "database": database},
        caller_id=CALLER_ID,
        caller_permissions=CALLER_PERMISSIONS,
    )


if __name__ == "__main__":
    mcp.run()
