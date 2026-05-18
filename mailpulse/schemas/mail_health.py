from pydantic import BaseModel


class MailHealthChecks(BaseModel):
    mx_records_found: bool
    mx_resolves: bool


class MailHealthResponse(BaseModel):
    domain: str
    healthy: bool
    status: str
    reason: str | None
    checks: MailHealthChecks
