from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from mailpulse.schemas.email_health import EmailHealthResponse
from mailpulse.services.email_health import check_email_health

router = APIRouter(prefix="/v1", tags=["mail-health"])


@router.get("/mail-health", response_model=EmailHealthResponse)
async def get_mail_health(email: str = Query(..., min_length=1)) -> EmailHealthResponse:
    try:
        # Blocking DNS/SMTP work runs in a thread pool so the asyncio loop stays responsive.
        return await run_in_threadpool(check_email_health, email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
