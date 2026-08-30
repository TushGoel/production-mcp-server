"""Tests for the tool registry — explicit registration and @mcp_tool decorator."""

import pytest
from src.registry import ToolRegistry, ToolDefinition, RiskLevel, mcp_tool, set_default_registry


def test_register_and_get():
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="my_tool",
        description="A tool.",
        handler=lambda: "result",
        required_permissions={"data:read"},
        risk_level=RiskLevel.LOW,
    )
    registry.register(tool)
    assert registry.get("my_tool") is tool


def test_duplicate_registration_raises():
    registry = ToolRegistry()
    tool = ToolDefinition(name="t", description="", handler=lambda: None)
    registry.register(tool)
    with pytest.raises(ValueError):
        registry.register(tool)


def test_unknown_tool_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent")


def test_tools_for_permissions():
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="read_tool", description="", handler=lambda: None,
        required_permissions={"data:read"},
    ))
    registry.register(ToolDefinition(
        name="write_tool", description="", handler=lambda: None,
        required_permissions={"data:write"},
    ))
    accessible = registry.tools_for_permissions({"data:read"})
    assert len(accessible) == 1
    assert accessible[0].name == "read_tool"


def test_contains():
    registry = ToolRegistry()
    registry.register(ToolDefinition(name="t", description="", handler=lambda: None))
    assert "t" in registry
    assert "x" not in registry


def test_mcp_tool_decorator_registers():
    registry = ToolRegistry()

    @mcp_tool(permissions={"logs:read"}, risk=RiskLevel.LOW, registry=registry)
    def get_logs(deployment_id: str) -> str:
        return f"logs for {deployment_id}"

    assert "get_logs" in registry
    tool = registry.get("get_logs")
    assert tool.required_permissions == {"logs:read"}
    assert tool.risk_level == RiskLevel.LOW


def test_mcp_tool_decorator_preserves_function():
    registry = ToolRegistry()

    @mcp_tool(registry=registry)
    def my_handler(x: int) -> int:
        return x * 2

    assert my_handler(5) == 10


def test_mcp_tool_decorator_high_risk():
    registry = ToolRegistry()

    @mcp_tool(
        permissions={"ops:write"},
        risk=RiskLevel.HIGH,
        requires_confirmation=True,
        registry=registry,
    )
    def trigger_rollback(deployment_id: str) -> str:
        """Trigger a production rollback."""
        return "rolled back"

    tool = registry.get("trigger_rollback")
    assert tool.risk_level == RiskLevel.HIGH
    assert tool.requires_confirmation is True


def test_mcp_tool_custom_name():
    registry = ToolRegistry()

    @mcp_tool(name="fetch_deployment_logs", registry=registry)
    def get_logs(id: str) -> str:
        return "logs"

    assert "fetch_deployment_logs" in registry
    assert "get_logs" not in registry


def test_default_registry_decorator():
    registry = ToolRegistry()
    set_default_registry(registry)

    @mcp_tool(permissions={"data:read"})
    def read_config(key: str) -> str:
        return "value"

    assert "read_config" in registry
    # Clean up
    set_default_registry(None)
