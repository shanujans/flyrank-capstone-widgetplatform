from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ---------- Auth ----------


class TenantCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TenantOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Widgets ----------

ALLOWED_WIDGET_TYPES = {"signup_form", "cta", "popover"}
ALLOWED_FIELD_TYPES = {"text", "email", "textarea", "tel", "checkbox"}


class WidgetField(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    type: str = "text"
    required: bool = False

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in ALLOWED_FIELD_TYPES:
            raise ValueError(f"field type must be one of {sorted(ALLOWED_FIELD_TYPES)}")
        return v


class WidgetBase(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    button_text: str = Field(default="Submit", max_length=64)
    fields: list[WidgetField] = Field(min_length=1, max_length=20)
    display_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def check_widget_type(cls, v: str) -> str:
        if v not in ALLOWED_WIDGET_TYPES:
            raise ValueError(f"type must be one of {sorted(ALLOWED_WIDGET_TYPES)}")
        return v


class WidgetCreate(WidgetBase):
    pass


class WidgetUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    button_text: Optional[str] = Field(default=None, max_length=64)
    fields: Optional[list[WidgetField]] = None
    display_options: Optional[dict[str, Any]] = None


class WidgetOut(BaseModel):
    id: str
    type: str
    title: str
    description: str
    button_text: str
    fields: list[WidgetField]
    display_options: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WidgetEmbedOut(BaseModel):
    widget_id: str
    snippet: str


# ---------- Public config ----------


class PublicWidgetConfig(BaseModel):
    widget_id: str
    type: str
    title: str
    description: str
    button_text: str
    fields: list[WidgetField]
    display_options: dict[str, Any]


# ---------- Submissions ----------

# Public submissions carry arbitrary field values keyed by field name, plus an
# honeypot value that a real visitor will always leave blank.
MAX_FIELD_VALUE_LENGTH = 2000
MAX_FIELDS_IN_SUBMISSION = 30


class SubmissionCreate(BaseModel):
    data: dict[str, Any]
    # Hidden honeypot field. Any real widget renders this off-screen; a
    # scripted bot filling every input will fill it too.
    hp_field: str = Field(default="", max_length=500)

    @field_validator("data")
    @classmethod
    def bound_payload_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > MAX_FIELDS_IN_SUBMISSION:
            raise ValueError(f"too many fields (max {MAX_FIELDS_IN_SUBMISSION})")
        for key, value in v.items():
            if not isinstance(key, str) or len(key) > 64:
                raise ValueError("invalid field name")
            if isinstance(value, str) and len(value) > MAX_FIELD_VALUE_LENGTH:
                raise ValueError(f"field '{key}' exceeds max length ({MAX_FIELD_VALUE_LENGTH})")
        return v


class SubmissionOut(BaseModel):
    id: int
    widget_id: str
    data: dict[str, Any]
    country: Optional[str]
    city: Optional[str]
    geo_provider: Optional[str]
    notified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Dashboard ----------


class WidgetStats(BaseModel):
    widget_id: str
    total_submissions: int
    submissions_by_day: dict[str, int]
    top_countries: dict[str, int]


class DashboardOverview(BaseModel):
    total_widgets: int
    total_submissions: int
    submissions_last_7_days: int
