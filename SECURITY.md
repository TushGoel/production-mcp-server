# Security Model

This document describes the security principles embedded in the production-mcp-server design.

## Threat Model

When AI agents gain tool access, the primary threats are:

| Threat | Example | Mitigation |
|--------|---------|-----------|
| **Privilege escalation** | Agent calls a tool it isn't authorized for | Permission enforcement layer — every call checked before execution |
| **Blast-radius explosion** | Agent triggers a rollback affecting 50 services instead of 1 | HIGH risk tools require `confirmed=True` — cannot be called accidentally |
| **Prompt injection via tools** | Malicious data in a tool response tricks the agent | Tool results truncated to 500 chars before logging; output validation against injected content is not yet implemented |
| **Path traversal** | Agent passes `../../etc/passwd` to a file-reading tool | Input validation layer blocks traversal patterns before handler runs |
| **SQL injection** | Agent constructs a destructive query | Destructive SQL pattern detection (`DROP TABLE`, `DELETE FROM`, `TRUNCATE`) |
| **Replay attacks** | Old audit events used to reconstruct agent behavior | Timestamps and immutable append-only audit trail |
| **Credential exposure** | Agent inadvertently logs secrets | Audit trail logs full tool arguments, untruncated — callers must never pass credentials as tool arguments |

## Design Principles Applied

### Principle of Least Privilege
Every agent identity holds only the permissions required for its specific workflow. Read-only agents cannot hold write permissions. The registry makes this explicit and auditable.

```python
# Oncall triage agent — read-only
CALLER_PERMISSIONS = {"deployments:read", "metrics:read", "database:read"}
# deployments:write intentionally absent — agent cannot trigger rollbacks
```

### Defense in Depth
Four independent layers between an agent request and tool execution:
1. Permission check (authorization)
2. Blast-radius guard (risk classification — enforced automatically for HIGH risk tools, not opt-in)
3. Input validation (injection prevention)
4. Execution timeout (bounds how long a handler can run)

Any single layer failing does not bypass the others.

### Immutable Audit Trail
Every tool call — permitted or denied — is recorded with: caller identity, arguments, result, timestamp, duration. Audit records are append-only and cannot be modified after creation. In production, emit to your SIEM.

### Fail Closed
When in doubt, deny. Unknown tool → KeyError. Missing permission → PermissionDeniedError. Invalid input → GuardrailViolationError. The agent never silently degrades to a lower-security path.

### Workload Identity
Caller identity is passed explicitly on every invocation — not inferred from environment. In production, derive from your OAuth token, service account, or SPIFFE/SPIRE workload identity.

## Compliance Considerations

This pattern supports compliance requirements in environments governed by:

- **SOC 2 Type II** — complete audit trail of every privileged action
- **ISO 27001** — access control, least privilege, audit logging
- **GDPR / CCPA** — tool results are truncated to 500 chars before logging; arguments are logged in full, so PII/credentials must never be passed as tool arguments
- **NIST AI RMF** — risk classification per tool (LOW/MEDIUM/HIGH), mandatory confirmation gate for HIGH-risk actions (see README's Human-in-the-loop section for what `confirmed=True` does and does not guarantee)

## Reporting Security Issues

If you find a security issue in this reference implementation, open a GitHub issue with the label `security`.
