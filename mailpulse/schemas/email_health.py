from pydantic import BaseModel


class EmailHealthChecks(BaseModel):
    mx_records_found: bool
    mx_resolves: bool
    smtp_reachable: bool
    smtp_handshake_ok: bool


class EmailHealthResponse(BaseModel):
    domain: str
    healthy: bool
    status: str
    reason: str | None
    checks: EmailHealthChecks
