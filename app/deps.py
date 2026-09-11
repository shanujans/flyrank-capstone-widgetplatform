from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_tenant(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Resolves the bearer token to a Tenant row. Any missing/invalid/expired
    token is rejected with 401 — this is what makes every widget/dashboard
    endpoint 'authenticated' per the requirements.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_exception

    tenant = db.query(Tenant).filter(Tenant.email == subject).first()
    if tenant is None:
        raise credentials_exception
    return tenant
