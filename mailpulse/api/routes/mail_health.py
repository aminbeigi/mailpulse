from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from mailpulse.schemas.mail_health import MailHealthResponse
from mailpulse.services.mail_health import check_mail_health

router = APIRouter(tags=["mail-health"])


@router.get("/mail-health", response_model=MailHealthResponse)
async def get_mail_health(email: str = Query(..., min_length=1)) -> MailHealthResponse:
    try:
        # Blocking DNS work runs in a thread pool so the asyncio loop stays responsive.
        return await run_in_threadpool(check_mail_health, email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
