from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_tenant
from app.models import Submission, Tenant, Widget
from app.schemas import DashboardOverview, SubmissionOut, WidgetStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _owned_widget_or_404(db: Session, widget_id: str, tenant: Tenant) -> Widget:
    widget = db.query(Widget).filter(Widget.id == widget_id, Widget.tenant_id == tenant.id).first()
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widget


@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), tenant: Tenant = Depends(get_current_tenant)):
    total_widgets = db.query(Widget).filter(Widget.tenant_id == tenant.id).count()
    total_submissions = db.query(Submission).filter(Submission.tenant_id == tenant.id).count()
    since = datetime.now(timezone.utc) - timedelta(days=7)
    recent = (
        db.query(Submission)
        .filter(Submission.tenant_id == tenant.id, Submission.created_at >= since)
        .count()
    )
    return DashboardOverview(
        total_widgets=total_widgets,
        total_submissions=total_submissions,
        submissions_last_7_days=recent,
    )


@router.get("/widgets/{widget_id}/submissions", response_model=list[SubmissionOut])
def widget_submissions(
    widget_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    widget = _owned_widget_or_404(db, widget_id, tenant)
    return (
        db.query(Submission)
        .filter(Submission.widget_id == widget.id)
        .order_by(Submission.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )


@router.get("/widgets/{widget_id}/stats", response_model=WidgetStats)
def widget_stats(widget_id: str, db: Session = Depends(get_db), tenant: Tenant = Depends(get_current_tenant)):
    widget = _owned_widget_or_404(db, widget_id, tenant)
    submissions = db.query(Submission).filter(Submission.widget_id == widget.id).all()

    by_day: Counter = Counter()
    countries: Counter = Counter()
    for s in submissions:
        by_day[s.created_at.strftime("%Y-%m-%d")] += 1
        if s.country:
            countries[s.country] += 1

    return WidgetStats(
        widget_id=widget.id,
        total_submissions=len(submissions),
        submissions_by_day=dict(sorted(by_day.items())),
        top_countries=dict(countries.most_common(10)),
    )
