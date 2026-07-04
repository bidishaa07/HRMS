"""Password, JWT-cookie, and Google OAuth authentication."""

from datetime import UTC, date, datetime
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import AuditLog, Department, Employee, User
from .security import create_token, decode_token, hash_password, token_hash, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    password: str = Field(min_length=8, max_length=72)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: str | None = Field(default=None, pattern="^(admin|employee|hr)$")


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=40)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


def company_prefix(company_name: str) -> str:
    words = ["".join(character for character in word if character.isalnum()) for word in company_name.split()]
    words = [word for word in words if word]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return words[0][:2].upper() if words else "AU"


def name_prefix(name: str) -> str:
    parts = [part for part in name.split() if part]
    first = parts[0][:2] if parts else "US"
    last = parts[-1][:2] if len(parts) > 1 else first
    return f"{first}{last}".upper()


async def generate_login_id(db: AsyncSession, company_name: str, name: str, joining_year: int) -> str:
    base = f"{company_prefix(company_name)}{name_prefix(name)}{joining_year}"
    count = await db.scalar(select(func.count(User.id)).where(User.login_id.like(f"{base}%")))
    return f"{base}{int(count or 0) + 1:04d}"


def user_payload(user: User) -> dict:
    employee = user.employee
    return {
        "id": str(user.id),
        "email": user.email,
        "login_id": user.login_id,
        "name": user.name,
        "company_name": user.company_name,
        "phone": user.phone,
        "role": user.role,
        "oauth_provider": user.oauth_provider,
        "employee_id": str(employee.id) if employee else None,
        "employee_code": employee.employee_code if employee else None,
    }


def set_session_cookies(response: Response, access: str, refresh: str) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.set_cookie("aurora_access", access, max_age=settings.access_token_minutes * 60, **common)
    response.set_cookie("aurora_refresh", refresh, max_age=settings.refresh_token_days * 86400, **common)


def clear_session_cookies(response: Response) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.delete_cookie("aurora_access", **common)
    response.delete_cookie("aurora_refresh", **common)


async def issue_session(db: AsyncSession, user: User, response: Response) -> dict:
    access = create_token(str(user.id), user.role)
    refresh = create_token(str(user.id), user.role, "refresh")
    user.refresh_token_hash = token_hash(refresh)
    await db.commit()
    set_session_cookies(response, access, refresh)
    return {"user": user_payload(user), "access_expires_in": settings.access_token_minutes * 60}


async def get_current_user(
    request: Request,
    db: DbSession,
    aurora_access: Annotated[str | None, Cookie()] = None,
) -> User:
    token = aurora_access
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        claims = decode_token(token, "access")
        user_id = UUID(claims["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired session") from None
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    async def role_guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return user

    return role_guard


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, response: Response, db: DbSession) -> dict:
    existing = await db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="An account already exists for this email")
    company_exists = await db.scalar(
        select(func.count(User.id)).where(func.lower(User.company_name) == payload.company_name.lower())
    )
    role = "admin" if not company_exists else "employee"
    login_id = await generate_login_id(db, payload.company_name, payload.name, date.today().year)
    department = await db.scalar(select(Department).where(Department.name == "Unassigned"))
    if not department:
        department = Department(name="Unassigned", description="New employees awaiting assignment")
        db.add(department)
        await db.flush()
    user = User(
        email=payload.email.lower(),
        login_id=login_id,
        name=payload.name.strip(),
        company_name=payload.company_name.strip(),
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    await db.flush()
    employee = Employee(
        user_id=user.id,
        employee_code=login_id,
        department_id=department.id,
        title="Company Administrator" if role == "admin" else "Team Member",
        joining_date=date.today(),
        profile_completion=75,
    )
    db.add(employee)
    db.add(AuditLog(actor_id=user.id, action="auth.register", entity_type="user", entity_id=user.id))
    await db.flush()
    await db.refresh(user, ["employee"])
    return await issue_session(db, user, response)


@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: DbSession) -> dict:
    normalized = payload.login.strip().lower()
    user = await db.scalar(
        select(User).where(or_(func.lower(User.email) == normalized, func.lower(User.login_id) == normalized))
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login ID/email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive")
    if payload.role and user.role != payload.role:
        raise HTTPException(status_code=403, detail="This account is not authorized for the selected role")
    db.add(AuditLog(actor_id=user.id, action="auth.login", entity_type="user", entity_id=user.id))
    await db.refresh(user, ["employee"])
    return await issue_session(db, user, response)


@router.get("/me")
async def me(user: CurrentUser, db: DbSession) -> dict:
    await db.refresh(user, ["employee"])
    return user_payload(user)


@router.patch("/me")
async def update_me(payload: ProfileUpdate, user: CurrentUser, db: DbSession) -> dict:
    user.name = payload.name.strip()
    user.phone = payload.phone.strip()
    db.add(AuditLog(actor_id=user.id, action="profile.update", entity_type="user", entity_id=user.id))
    await db.commit()
    await db.refresh(user, ["employee"])
    return user_payload(user)


@router.post("/change-password", status_code=204)
async def change_password(payload: PasswordChange, user: CurrentUser, db: DbSession) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.refresh_token_hash = None
    db.add(AuditLog(actor_id=user.id, action="auth.password_change", entity_type="user", entity_id=user.id))
    await db.commit()


@router.get("/providers")
async def provider_status() -> dict[str, bool]:
    return {
        "google": bool(settings.google_client_id and settings.google_client_secret),
    }


@router.post("/refresh")
async def refresh_session(
    response: Response,
    db: DbSession,
    aurora_refresh: Annotated[str | None, Cookie()] = None,
) -> dict:
    if not aurora_refresh:
        raise HTTPException(status_code=401, detail="Refresh session is missing")
    try:
        claims = decode_token(aurora_refresh, "refresh")
        user = await db.scalar(select(User).where(User.id == UUID(claims["sub"])))
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Refresh session is invalid") from None
    if not user or user.refresh_token_hash != token_hash(aurora_refresh):
        raise HTTPException(status_code=401, detail="Refresh session has been revoked")
    await db.refresh(user, ["employee"])
    return await issue_session(db, user, response)


@router.post("/logout", status_code=204)
async def logout(response: Response, db: DbSession, request: Request) -> Response:
    token = request.cookies.get("aurora_access")
    user_id = None
    if token:
        try:
            claims = decode_token(token, "access")
            user_id = UUID(claims["sub"])
        except (ValueError, KeyError):
            user_id = None
    if user_id:
        user = await db.scalar(select(User).where(User.id == user_id))
        if user:
            user.refresh_token_hash = None
            db.add(AuditLog(actor_id=user.id, action="auth.logout", entity_type="user", entity_id=user.id))
            await db.commit()
    clear_session_cookies(response)
    return response


OAUTH = {
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "profile": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
}


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str) -> dict[str, str]:
    if provider not in OAUTH:
        raise HTTPException(status_code=404, detail="Unsupported OAuth provider")
    client_id = getattr(settings, f"{provider}_client_id")
    if not client_id:
        raise HTTPException(status_code=503, detail=f"{provider.title()} OAuth is not configured")
    redirect_uri = getattr(settings, f"{provider}_redirect_uri")
    state_token = create_token("oauth", "anonymous", "oauth_state", provider=provider)
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": OAUTH[provider]["scope"],
            "state": state_token,
            "prompt": "select_account",
        }
    )
    return {"authorization_url": f"{OAUTH[provider]['authorize']}?{query}"}


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str, db: DbSession) -> RedirectResponse:
    if provider not in OAUTH:
        raise HTTPException(status_code=404, detail="Unsupported OAuth provider")
    try:
        claims = decode_token(state, "oauth_state")
        if claims.get("provider") != provider:
            raise ValueError("Provider mismatch")
    except ValueError:
        return RedirectResponse(f"{settings.frontend_url}/login?error=invalid_oauth_state")
    redirect_uri = getattr(settings, f"{provider}_redirect_uri")
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            OAUTH[provider]["token"],
            data={
                "client_id": getattr(settings, f"{provider}_client_id"),
                "client_secret": getattr(settings, f"{provider}_client_secret"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if token_response.is_error:
            return RedirectResponse(f"{settings.frontend_url}/login?error=oauth_exchange_failed")
        access_token = token_response.json()["access_token"]
        profile_response = await client.get(
            OAUTH[provider]["profile"], headers={"Authorization": f"Bearer {access_token}"}
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    email = (profile.get("email") or profile.get("mail") or profile.get("userPrincipalName", "")).lower()
    name = profile.get("name") or profile.get("displayName") or email.split("@")[0]
    if not email:
        return RedirectResponse(f"{settings.frontend_url}/login?error=email_not_available")
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not user:
        login_id = await generate_login_id(db, "Aurora HR", name, datetime.now(UTC).year)
        department = await db.scalar(select(Department).where(Department.name == "Unassigned"))
        if not department:
            department = Department(name="Unassigned")
            db.add(department)
            await db.flush()
        user = User(
            email=email,
            login_id=login_id,
            name=name,
            company_name="Aurora HR",
            role="employee",
            oauth_provider=provider,
        )
        db.add(user)
        await db.flush()
        db.add(
            Employee(user_id=user.id, employee_code=login_id, department_id=department.id, joining_date=date.today())
        )
        await db.flush()
    else:
        user.oauth_provider = provider
    await db.refresh(user, ["employee"])
    response = RedirectResponse(settings.frontend_url)
    await issue_session(db, user, response)
    return response
