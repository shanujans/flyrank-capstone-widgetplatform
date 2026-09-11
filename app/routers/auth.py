from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant
from app.schemas import TenantCreate, TenantOut, Token
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def register(payload: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    tenant = Tenant(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm's "username" field carries the tenant's email.
    tenant = db.query(Tenant).filter(Tenant.email == form_data.username).first()
    if not tenant or not verify_password(form_data.password, tenant.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return Token(access_token=create_access_token(subject=tenant.email))
