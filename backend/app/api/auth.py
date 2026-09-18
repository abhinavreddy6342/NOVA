from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional

import bcrypt
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core import models
from app.core.database import get_db


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# ============================================================
# CONFIGURATION
# ============================================================

JWT_SECRET = os.getenv(
    "NOVA_JWT_SECRET",
    "nova-local-development-secret-change-this",
)

JWT_ALGORITHM = "HS256"

JWT_EXPIRE_SECONDS = int(
    os.getenv(
        "NOVA_JWT_EXPIRE_SECONDS",
        "86400",
    )
)

COOKIE_NAME = "nova_session"


# ============================================================
# SCHEMAS
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=128,
    )
    remember_me: bool = False


class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None


# ============================================================
# EMAIL
# ============================================================

def _normalize_email(
    email: str,
) -> str:
    return str(
        email or ""
    ).strip().lower()


def _is_gmail(
    email: str,
) -> bool:
    normalized = _normalize_email(email)

    return (
        normalized.count("@") == 1
        and normalized.endswith("@gmail.com")
    )


# ============================================================
# PASSWORD
# ============================================================

def _validate_password(
    password: str,
) -> None:
    value = str(
        password or ""
    )

    if not 8 <= len(value) <= 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must contain "
                "8 to 128 characters."
            ),
        )

    if not any(
        character.isupper()
        for character in value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must contain "
                "an uppercase letter."
            ),
        )

    if not any(
        character.islower()
        for character in value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must contain "
                "a lowercase letter."
            ),
        )

    if not any(
        character.isdigit()
        for character in value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must contain "
                "a number."
            ),
        )

    if not any(
        not character.isalnum()
        for character in value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must contain "
                "a special character."
            ),
        )


# ============================================================
# BCRYPT
# ============================================================

def _hash_password(
    password: str,
) -> str:
    password_bytes = password.encode(
        "utf-8"
    )

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return hashed.decode(
        "utf-8"
    )


def _verify_password(
    password: str,
    password_hash: str,
) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        return False


# ============================================================
# JWT
# ============================================================

def _base64url_encode(
    value: bytes,
) -> str:
    return (
        base64.urlsafe_b64encode(value)
        .rstrip(b"=")
        .decode("utf-8")
    )


def _base64url_decode(
    value: str,
) -> bytes:
    padding = "=" * (
        (-len(value)) % 4
    )

    return base64.urlsafe_b64decode(
        value + padding
    )


def _create_jwt(
    user_id: int,
) -> str:
    issued_at = int(
        time.time()
    )

    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": (
            issued_at
            + JWT_EXPIRE_SECONDS
        ),
    }

    header = {
        "alg": JWT_ALGORITHM,
        "typ": "JWT",
    }

    encoded_header = _base64url_encode(
        json.dumps(
            header,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    encoded_payload = _base64url_encode(
        json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    unsigned_token = (
        f"{encoded_header}."
        f"{encoded_payload}"
    )

    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        unsigned_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    encoded_signature = _base64url_encode(
        signature
    )

    return (
        f"{unsigned_token}."
        f"{encoded_signature}"
    )


def _decode_jwt(
    token: str,
) -> Optional[int]:
    try:
        parts = token.split(".")

        if len(parts) != 3:
            return None

        encoded_header = parts[0]
        encoded_payload = parts[1]
        encoded_signature = parts[2]

        unsigned_token = (
            f"{encoded_header}."
            f"{encoded_payload}"
        )

        expected_signature = hmac.new(
            JWT_SECRET.encode("utf-8"),
            unsigned_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        submitted_signature = (
            _base64url_decode(
                encoded_signature
            )
        )

        if not hmac.compare_digest(
            expected_signature,
            submitted_signature,
        ):
            return None

        header = json.loads(
            _base64url_decode(
                encoded_header
            ).decode("utf-8")
        )

        if (
            header.get("alg")
            != JWT_ALGORITHM
        ):
            return None

        if (
            header.get("typ")
            != "JWT"
        ):
            return None

        payload = json.loads(
            _base64url_decode(
                encoded_payload
            ).decode("utf-8")
        )

        expires_at = int(
            payload.get(
                "exp",
                0,
            )
        )

        if (
            expires_at
            <= int(time.time())
        ):
            return None

        user_id = payload.get(
            "sub"
        )

        if user_id is None:
            return None

        return int(
            user_id
        )

    except Exception:
        return None


# ============================================================
# USER SERIALIZATION
# ============================================================

def _serialize_user(
    user: Any,
) -> UserResponse:
    return UserResponse(
        id=int(user.id),
        email=str(user.email),
        name=getattr(
            user,
            "name",
            None,
        ),
    )


# ============================================================
# CURRENT USER DEPENDENCY
# ============================================================

def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(
        default=None
    ),
    nova_session: Optional[str] = Cookie(
        default=None,
        alias=COOKIE_NAME,
    ),
):
    token: Optional[str] = None

    # Bearer token support is retained for
    # existing authenticated API clients.
    if authorization:
        scheme, _, value = (
            authorization.partition(" ")
        )

        if (
            scheme.lower()
            == "bearer"
            and value.strip()
        ):
            token = value.strip()

    # HTTP-only NOVA session cookie is preferred.
    if nova_session:
        token = nova_session

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    user_id = _decode_jwt(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid.",
        )

    user = (
        db.query(models.User)
        .filter(
            models.User.id == user_id
        )
        .first()
    )

    if (
        user is None
        or not bool(
            user.is_active
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return user


# ============================================================
# REGISTER
# ============================================================

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = _normalize_email(
        str(payload.email)
    )

    if not _is_gmail(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only Gmail addresses are "
                "allowed for NOVA accounts."
            ),
        )

    _validate_password(
        payload.password
    )

    existing_user = (
        db.query(models.User)
        .filter(
            models.User.email == email
        )
        .first()
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account with this Gmail "
                "address already exists."
            ),
        )

    password_hash = _hash_password(
        payload.password
    )

    user = models.User(
        email=email,
        password_hash=password_hash,
        name=email.split("@")[0],
        role="user",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_jwt(
        user.id
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_EXPIRE_SECONDS,
        path="/",
    )

    return AuthResponse(
        success=True,
        message="Account created successfully.",
        user=_serialize_user(user),
    )


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = _normalize_email(
        str(payload.email)
    )

    if not _is_gmail(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only Gmail addresses are "
                "allowed for NOVA accounts."
            ),
        )

    user = (
        db.query(models.User)
        .filter(
            models.User.email == email
        )
        .first()
    )

    if (
        user is None
        or not bool(
            user.is_active
        )
        or not _verify_password(
            payload.password,
            str(
                user.password_hash
            ),
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = _create_jwt(
        user.id
    )

    cookie_kwargs = {
        "key": COOKIE_NAME,
        "value": token,
        "httponly": True,
        "secure": False,
        "samesite": "lax",
        "path": "/",
    }

    if payload.remember_me:
        cookie_kwargs[
            "max_age"
        ] = JWT_EXPIRE_SECONDS

    response.set_cookie(
        **cookie_kwargs
    )

    return AuthResponse(
        success=True,
        message="Login successful.",
        user=_serialize_user(user),
    )


# ============================================================
# CURRENT USER
# ============================================================

@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    user: models.User = Depends(
        get_current_user
    ),
):
    return _serialize_user(user)


# ============================================================
# LOGOUT
# ============================================================

@router.post(
    "/logout",
)
def logout(
    response: Response,
):
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )

    return {
        "success": True,
        "message": "Logged out successfully.",
    }