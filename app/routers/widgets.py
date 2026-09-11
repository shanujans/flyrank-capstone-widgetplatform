from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_tenant
from app.models import Tenant, Widget
from app.schemas import WidgetCreate, WidgetEmbedOut, WidgetOut, WidgetUpdate

router = APIRouter(prefix="/widgets", tags=["widgets"])


def _get_owned_widget_or_404(db: Session, widget_id: str, tenant: Tenant) -> Widget:
    widget = db.query(Widget).filter(Widget.id == widget_id).first()
    # Same 404 whether the id doesn't exist at all or belongs to a different
    # tenant — this is the actual enforcement of tenant isolation: tenant A
    # can't even learn that tenant B's widget id exists.
    if widget is None or widget.tenant_id != tenant.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widget


@router.post("", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
def create_widget(
    payload: WidgetCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    widget = Widget(
        tenant_id=tenant.id,
        type=payload.type,
        title=payload.title,
        description=payload.description,
        button_text=payload.button_text,
        fields=[f.model_dump() for f in payload.fields],
        display_options=payload.display_options,
    )
    db.add(widget)
    db.commit()
    db.refresh(widget)
    return widget


@router.get("", response_model=list[WidgetOut])
def list_widgets(db: Session = Depends(get_db), tenant: Tenant = Depends(get_current_tenant)):
    return (
        db.query(Widget)
        .filter(Widget.tenant_id == tenant.id)
        .order_by(Widget.created_at.desc())
        .all()
    )


@router.get("/{widget_id}", response_model=WidgetOut)
def get_widget(widget_id: str, db: Session = Depends(get_db), tenant: Tenant = Depends(get_current_tenant)):
    return _get_owned_widget_or_404(db, widget_id, tenant)


@router.patch("/{widget_id}", response_model=WidgetOut)
def update_widget(
    widget_id: str,
    payload: WidgetUpdate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    widget = _get_owned_widget_or_404(db, widget_id, tenant)
    update_data = payload.model_dump(exclude_unset=True)  # nested models -> dicts already
    for key, value in update_data.items():
        setattr(widget, key, value)
    db.commit()
    db.refresh(widget)
    return widget


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(widget_id: str, db: Session = Depends(get_db), tenant: Tenant = Depends(get_current_tenant)):
    widget = _get_owned_widget_or_404(db, widget_id, tenant)
    db.delete(widget)
    db.commit()
    return None


@router.get("/{widget_id}/embed", response_model=WidgetEmbedOut)
def get_embed_snippet(
    widget_id: str,
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    The one line the customer pastes into their site. Everything it needs —
    config fetch, rendering, submission wiring — flows from the ?id= param,
    which the bundle reads via document.currentScript.
    """
    widget = _get_owned_widget_or_404(db, widget_id, tenant)
    base_url = str(request.base_url).rstrip("/")
    snippet = (
        f'<script src="{base_url}/widget/{settings.WIDGET_BUNDLE_VERSION}/widget.js'
        f'?id={widget.id}" async></script>'
    )
    return WidgetEmbedOut(widget_id=widget.id, snippet=snippet)
