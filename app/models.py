import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    """
    A customer of the platform. Kept intentionally simple (email + password)
    since auth itself isn't the point of this capstone — tenant isolation is.
    """

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utc_now)

    widgets = relationship("Widget", back_populates="tenant", cascade="all, delete-orphan")


class Widget(Base):
    """
    One embeddable widget belonging to exactly one tenant.
    `id` is a random hex string (not a sequential int) so widget ids are not
    guessable/enumerable from the public embed snippet.
    """

    __tablename__ = "widgets"

    id = Column(String, primary_key=True, default=_uuid, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    type = Column(String, nullable=False)  # "signup_form" | "cta" | "popover"
    title = Column(String, nullable=False)
    description = Column(String, default="")
    button_text = Column(String, default="Submit")
    fields = Column(JSON, nullable=False)  # e.g. [{"name": "email", "label": "Email", "type": "email", "required": true}]
    display_options = Column(JSON, default=dict)  # e.g. {"position": "bottom-right", "delay_seconds": 0}

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    tenant = relationship("Tenant", back_populates="widgets")
    submissions = relationship("Submission", back_populates="widget", cascade="all, delete-orphan")


class Submission(Base):
    """
    A single visitor submission. `tenant_id` is denormalized onto the row so
    every dashboard/tenant-isolation query can filter without an extra join —
    and so isolation is enforced even if a widget_id were guessed.
    """

    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    widget_id = Column(String, ForeignKey("widgets.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    data = Column(JSON, nullable=False)  # the validated form field values
    ip_address = Column(String, nullable=True)

    # Enrichment (nullable — enrichment is best-effort, never blocking)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    geo_provider = Column(String, nullable=True)  # "provider_a" | "provider_b" | None

    notified = Column(Boolean, default=False)  # did the side-effect succeed?

    created_at = Column(DateTime, default=_utc_now, index=True)

    widget = relationship("Widget", back_populates="submissions")
