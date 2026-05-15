from pydantic import BaseModel


class MailHealthChecks(BaseModel):
    mx_records_found: bool
    mx_resolves: bool
    smtp_reachable: bool
    smtp_handshake_ok: bool


class MailHealthResponse(BaseModel):
    domain: str
    healthy: bool
    status: str
    reason: str | None
    checks: MailHealthChecks
