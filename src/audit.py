"""Structured audit trail for every MCP tool invocation."""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    tool_name: str
    caller_id: str
    arguments: dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    permitted: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditTrail:
    """
    Immutable, append-only audit log for all tool invocations.

    Every call — permitted or denied — is recorded with caller identity,
    arguments, result, and timing. In production, emit to your SIEM or
    log aggregation pipeline.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)
        level = logging.WARNING if not event.permitted or event.error else logging.INFO
        logger.log(level, "AUDIT %s", event.to_json())

    def get_events(
        self,
        tool_name: Optional[str] = None,
        caller_id: Optional[str] = None,
        permitted_only: bool = False,
    ) -> list[AuditEvent]:
        events = self._events
        if tool_name:
            events = [e for e in events if e.tool_name == tool_name]
        if caller_id:
            events = [e for e in events if e.caller_id == caller_id]
        if permitted_only:
            events = [e for e in events if e.permitted]
        return events

    def denied_count(self) -> int:
        return sum(1 for e in self._events if not e.permitted)

    def __len__(self) -> int:
        return len(self._events)
