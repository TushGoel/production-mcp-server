"""
Guardrail layer — permission enforcement, pre-action validation,
blast-radius controls, and execution timeout before any tool runs.
"""

import threading
import time
from typing import Any, Optional
from .registry import ToolRegistry, RiskLevel
from .audit import AuditTrail, AuditEvent


class PermissionDeniedError(Exception):
    pass


class GuardrailViolationError(Exception):
    pass


class ToolTimeoutError(Exception):
    pass


class Guardrails:
    """
    Enforces four layers of protection on every tool invocation:

    1. Permission check — caller must hold all permissions the tool requires.
    2. Blast-radius guard — HIGH risk tools require explicit confirmation flag.
    3. Argument validation — tool-specific pre-conditions (e.g. no path traversal).
    4. Execution timeout — tool handler must complete within timeout_seconds.

    No tool handler runs unless layers 1-3 pass. Layer 4 enforces that even
    permitted tools cannot hang indefinitely — critical for agentic loops where
    a stalled tool call blocks the entire workflow.
    """

    DEFAULT_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        registry: ToolRegistry,
        audit: AuditTrail,
        default_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._registry = registry
        self._audit = audit
        self._default_timeout = default_timeout_seconds

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        caller_id: str,
        caller_permissions: set[str],
        confirmed: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        tool = self._registry.get(tool_name)
        start = time.monotonic()
        event = AuditEvent(
            tool_name=tool_name,
            caller_id=caller_id,
            arguments=arguments,
        )

        try:
            # Layer 1: permission enforcement
            missing = tool.required_permissions - caller_permissions
            if missing:
                event.permitted = False
                event.error = f"Missing permissions: {missing}"
                raise PermissionDeniedError(
                    f"Caller '{caller_id}' lacks permissions {missing} for tool '{tool_name}'"
                )

            # Layer 2: blast-radius guard for HIGH risk tools
            if tool.risk_level == RiskLevel.HIGH and tool.requires_confirmation and not confirmed:
                event.permitted = False
                event.error = "HIGH risk tool requires confirmed=True"
                raise GuardrailViolationError(
                    f"Tool '{tool_name}' has HIGH risk level. Pass confirmed=True to proceed."
                )

            # Layer 3: argument validation
            self._validate_arguments(tool_name, arguments)

            # Layer 4: execute with timeout
            deadline = timeout_seconds if timeout_seconds is not None else self._default_timeout
            result = self._execute_with_timeout(tool.handler, arguments, deadline, tool_name)
            event.result = str(result)[:500]  # truncate for log safety
            return result

        except (PermissionDeniedError, GuardrailViolationError, ToolTimeoutError):
            raise
        except Exception as exc:
            event.error = str(exc)
            raise
        finally:
            event.duration_ms = (time.monotonic() - start) * 1000
            self._audit.record(event)

    def _execute_with_timeout(
        self,
        handler: Any,
        arguments: dict[str, Any],
        timeout_seconds: float,
        tool_name: str,
    ) -> Any:
        """Run handler in a thread with a timeout. Raises ToolTimeoutError if exceeded."""
        result_box: list[Any] = [None]
        error_box: list[Optional[Exception]] = [None]

        def run() -> None:
            try:
                result_box[0] = handler(**arguments)
            except Exception as exc:
                error_box[0] = exc

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=timeout_seconds)

        if t.is_alive():
            raise ToolTimeoutError(
                f"Tool '{tool_name}' exceeded timeout of {timeout_seconds:.1f}s. "
                "The tool handler is still running in the background — "
                "check for blocking I/O or infinite loops in the handler."
            )

        if error_box[0] is not None:
            raise error_box[0]

        return result_box[0]

    def _validate_arguments(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Tool-specific pre-condition checks — extend per tool as needed."""
        if "path" in arguments:
            path = str(arguments["path"])
            if ".." in path:
                raise GuardrailViolationError(f"Path traversal detected in tool '{tool_name}'")
        if "query" in arguments:
            query = str(arguments["query"]).lower()
            if any(kw in query for kw in ("drop table", "delete from", "truncate")):
                raise GuardrailViolationError(
                    f"Destructive SQL pattern detected in tool '{tool_name}'"
                )
