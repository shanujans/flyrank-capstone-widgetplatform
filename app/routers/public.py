from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.geo import enrich_ip
from app.models import Submission, Widget
from app.notify import send_confirmation
from app.rate_limit import limiter
from app.schemas import PublicWidgetConfig, SubmissionCreate, SubmissionOut

router = APIRouter(tags=["public"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/widget/{version}/widget.js")
def get_widget_bundle(version: str):
    """
    Versioned + immutable: a customer's browser caches this forever. Ship a
    breaking change as /widget/v2/widget.js and old caches never see it —
    they simply keep loading v1 until the customer updates their snippet.
    """
    bundle_path = STATIC_DIR / f"widget.{version}.js"
    if not bundle_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown widget bundle version")
    return FileResponse(
        bundle_path,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/public/widgets/{widget_id}/config", response_model=PublicWidgetConfig)
def get_widget_config(widget_id: str, response: Response, db: Session = Depends(get_db)):
    widget = db.query(Widget).filter(Widget.id == widget_id).first()
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    # Short cache: config can be edited by the owner at any time, so we keep
    # this fresh-ish (60s) rather than caching it for a year like the bundle.
    response.headers["Cache-Control"] = "public, max-age=60"
    return PublicWidgetConfig(
        widget_id=widget.id,
        type=widget.type,
        title=widget.title,
        description=widget.description,
        button_text=widget.button_text,
        fields=widget.fields,
        display_options=widget.display_options or {},
    )


@router.post(
    "/public/widgets/{widget_id}/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_submission(
    widget_id: str,
    payload: SubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    widget = db.query(Widget).filter(Widget.id == widget_id).first()
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    ip = _client_ip(request)

    # ---- 1. Abuse protection: rate limiting (per IP, then per widget) ----
    allowed, retry_after = limiter.allow(f"ip:{ip}", settings.RATE_LIMIT_PER_IP_PER_MINUTE)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests from this IP. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )
    allowed, retry_after = limiter.allow(f"widget:{widget_id}", settings.RATE_LIMIT_PER_WIDGET_PER_MINUTE)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="This widget is receiving too many submissions right now.",
            headers={"Retry-After": str(retry_after)},
        )

    # ---- 2. Spam control: honeypot ----
    if payload.hp_field.strip():
        # A real visitor never sees this field; a bot filling every input
        # will fill it. Fake a normal success so the bot gets no signal it
        # was caught, but never touch the database.
        return SubmissionOut(
            id=0,
            widget_id=widget.id,
            data={},
            country=None,
            city=None,
            geo_provider=None,
            notified=False,
            created_at=datetime.now(timezone.utc),
        )

    # ---- 3. Boundary validation against this widget's own field defs ----
    errors = []
    for field_def in widget.fields or []:
        name = field_def["name"]
        if field_def.get("required") and not str(payload.data.get(name, "")).strip():
            errors.append(f"'{name}' is required")
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors)

    # ---- 4. Enrichment with provider fallback chain (never blocks) ----
    country, city, geo_provider = await enrich_ip(ip)

    submission = Submission(
        widget_id=widget.id,
        tenant_id=widget.tenant_id,
        data=payload.data,
        ip_address=ip,
        country=country,
        city=city,
        geo_provider=geo_provider,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # ---- 5. Safe side effect: failure must never un-succeed the request ----
    try:
        contact = payload.data.get("email") or ip
        submission.notified = send_confirmation(contact, widget.title)
    except Exception:  # noqa: BLE001 - side effects degrade, they never propagate
        submission.notified = False
    db.commit()
    db.refresh(submission)

    return submission
