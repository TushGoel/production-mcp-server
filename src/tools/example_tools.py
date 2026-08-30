"""
Example tool handlers demonstrating production MCP patterns.

These are illustrative implementations — swap with your real data sources.
Every handler is a plain Python function; the registry + guardrails layer
wraps them with permission enforcement and audit logging.
"""

from typing import Any


def read_deployment_status(deployment_id: str) -> dict[str, Any]:
    """Read-only: fetch deployment status by ID."""
    # In production: call your deployment API / DynamoDB table
    return {
        "deployment_id": deployment_id,
        "status": "healthy",
        "last_updated": "2026-08-26T12:00:00Z",
    }


def query_metrics(metric_name: str, window_minutes: int = 60) -> dict[str, Any]:
    """Read-only: retrieve metric values for a given window."""
    # In production: call CloudWatch / Prometheus / Datadog API
    return {
        "metric": metric_name,
        "window_minutes": window_minutes,
        "value": 42.0,
        "unit": "Count",
    }


def run_database_query(query: str, database: str = "readonly_replica") -> list[dict]:
    """Read-only: execute a SELECT query against the read replica."""
    # In production: execute against your read-only DB connection
    # Guardrails already blocked DROP/DELETE/TRUNCATE before reaching here
    return [{"result": f"Simulated result for: {query} on {database}"}]


def trigger_rollback(deployment_id: str, reason: str) -> dict[str, Any]:
    """HIGH risk: initiate a deployment rollback. Requires confirmation."""
    # In production: call your deployment orchestration API
    return {
        "deployment_id": deployment_id,
        "action": "rollback_initiated",
        "reason": reason,
        "status": "pending",
    }
