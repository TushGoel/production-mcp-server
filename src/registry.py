"""Tool registry — metadata, permissions, and risk classification for every tool."""

import functools
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Optional


class RiskLevel(str, Enum):
    LOW = "low"        # read-only, no side effects
    MEDIUM = "medium"  # writes to bounded scope
    HIGH = "high"      # destructive, external calls, or broad scope


@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any]
    required_permissions: set[str] = field(default_factory=set)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False  # blast-radius guard for HIGH risk tools


# Module-level default registry — used by @mcp_tool decorator
_default_registry: Optional["ToolRegistry"] = None


def set_default_registry(registry: "ToolRegistry") -> None:
    """Set the registry that @mcp_tool decorators auto-register into."""
    global _default_registry
    _default_registry = registry


def mcp_tool(
    name: Optional[str] = None,
    description: str = "",
    permissions: Optional[set] = None,
    risk: RiskLevel = RiskLevel.LOW,
    requires_confirmation: bool = False,
    registry: Optional["ToolRegistry"] = None,
) -> Callable:
    """
    Decorator that registers a function as an MCP tool.

    Usage:
        registry = ToolRegistry()
        set_default_registry(registry)

        @mcp_tool(permissions={"logs:read"}, risk=RiskLevel.LOW)
        def get_deployment_logs(deployment_id: str) -> str:
            return fetch_logs(deployment_id)

        # Equivalent to:
        # registry.register(ToolDefinition(
        #     name="get_deployment_logs",
        #     description="",
        #     handler=get_deployment_logs,
        #     required_permissions={"logs:read"},
        #     risk_level=RiskLevel.LOW,
        # ))
    """
    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        tool_description = description or (fn.__doc__ or "").strip().split("\n")[0]
        tool_perms = permissions or set()

        definition = ToolDefinition(
            name=tool_name,
            description=tool_description,
            handler=fn,
            required_permissions=tool_perms,
            risk_level=risk,
            requires_confirmation=requires_confirmation,
        )

        target = registry or _default_registry
        if target is not None:
            target.register(definition)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        wrapper._mcp_tool_definition = definition
        return wrapper

    return decorator


class ToolRegistry:
    """
    Central registry for all MCP tools.

    Tools are registered with explicit permission requirements and risk
    classification. The guardrail layer enforces these at invocation time —
    agents cannot call tools they are not explicitly authorized for.

    Two registration styles:

    1. Explicit (original):
        registry.register(ToolDefinition(name="get_logs", ...))

    2. Decorator (new):
        @mcp_tool(permissions={"logs:read"}, risk=RiskLevel.LOW)
        def get_logs(deployment_id: str) -> str: ...
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Unknown tool: '{name}'")
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def tools_for_permissions(self, permissions: set[str]) -> list[ToolDefinition]:
        """Return tools the caller is authorized to invoke."""
        return [t for t in self._tools.values() if t.required_permissions <= permissions]

    def __contains__(self, name: str) -> bool:
        return name in self._tools
