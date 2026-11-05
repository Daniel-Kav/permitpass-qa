"""Authentication routes and the current-user dependency."""
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import UserRow
from .schemas import LoginIn, TokenOut, User
from .security import DUMMY_HASH, create_access_token, decode_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> UserRow:
    if creds is None:
        raise _unauthorized("Not authenticated")
    try:
        claims = decode_access_token(creds.credentials)
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid or expired token") from None
    user = db.get(UserRow, claims["sub"])
    # The database, not the token, is the authority on role and whether the account is still active
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(UserRow).where(UserRow.email == body.email.strip().lower()))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not (user and ok and user.is_active):
        raise _unauthorized("Incorrect email or password")  # same message for every failure
    return TokenOut(
        access_token=create_access_token(user.id, user.role.value),
        expires_in=config.ACCESS_TOKEN_MINUTES * 60,
        role=user.role,
    )


@router.get("/me", response_model=User)
def me(user: UserRow = Depends(current_user)) -> UserRow:
    return user
