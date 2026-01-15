"""Authentication routes for magic link login."""

import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
import resend

from llmstxt_api.config import settings
from llmstxt_api.database import get_db
from llmstxt_api.models import User, MagicLinkToken
from llmstxt_api.schemas import (
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyTokenRequest,
    AuthResponse,
    UserResponse,
)

router = APIRouter()

# Configure Resend
resend.api_key = settings.resend_api_key

# Token expiry
MAGIC_LINK_EXPIRY_MINUTES = 15
JWT_EXPIRY_DAYS = 7


def create_jwt_token(user_id: str, email: str) -> str:
    """Create a JWT token for authenticated user."""
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_jwt_token(token: str) -> dict | None:
    """Verify a JWT token and return payload."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    auth_token: str | None = Cookie(default=None),
) -> User | None:
    """Get current authenticated user from cookie."""
    if not auth_token:
        return None

    payload = verify_jwt_token(auth_token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_uuid))
    return result.scalar_one_or_none()


async def require_auth(
    user: User | None = Depends(get_current_user),
) -> User:
    """Require authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.post("/auth/magic-link", response_model=MagicLinkResponse)
async def send_magic_link(
    request: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a magic link to the user's email.

    Creates or updates user record and sends login link.
    """
    email = request.email.lower().strip()

    # Generate secure token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES)

    # Delete any existing unused tokens for this email
    await db.execute(
        delete(MagicLinkToken).where(
            MagicLinkToken.email == email,
            MagicLinkToken.used == False,
        )
    )

    # Create new token
    magic_token = MagicLinkToken(
        email=email,
        token=token,
        expires_at=expires_at,
    )
    db.add(magic_token)
    await db.commit()

    # Build magic link URL
    magic_link = f"{settings.frontend_url}/auth/verify?token={token}"

    # Send email
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [email],
            "subject": "Your llms.txt login link",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #6366f1;">Log in to llms.txt</h2>
                    <p>Click the button below to log in to your account. This link expires in {MAGIC_LINK_EXPIRY_MINUTES} minutes.</p>
                    <a href="{magic_link}"
                       style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 8px; margin: 16px 0;">
                        Log in to llms.txt
                    </a>
                    <p style="color: #666; font-size: 14px;">
                        If you didn't request this link, you can safely ignore this email.
                    </p>
                    <p style="color: #666; font-size: 12px; margin-top: 32px;">
                        Or copy this link: {magic_link}
                    </p>
                </div>
            """,
        })
    except Exception as e:
        # Log error but don't expose details to user
        print(f"Failed to send magic link email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again.")

    return MagicLinkResponse(
        message="Magic link sent! Check your email.",
        email=email,
    )


@router.post("/auth/verify", response_model=AuthResponse)
async def verify_magic_link(
    request: VerifyTokenRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify magic link token and log user in.

    Creates user if they don't exist, sets auth cookie.
    """
    # Find token
    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.token == request.token,
            MagicLinkToken.used == False,
        )
    )
    magic_token = result.scalar_one_or_none()

    if not magic_token:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    # Check expiry
    if magic_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Link has expired. Please request a new one.")

    # Mark token as used
    magic_token.used = True

    # Find or create user
    user_result = await db.execute(
        select(User).where(User.email == magic_token.email)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        user = User(email=magic_token.email)
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Create JWT token
    jwt_token = create_jwt_token(str(user.id), user.email)

    # Set cookie
    response.set_cookie(
        key="auth_token",
        value=jwt_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * JWT_EXPIRY_DAYS,  # 7 days
    )

    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            created_at=user.created_at,
        ),
        message="Login successful!",
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_auth)):
    """Get current authenticated user."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        created_at=user.created_at,
    )


@router.post("/auth/logout")
async def logout(response: Response):
    """Log out by clearing auth cookie."""
    response.delete_cookie("auth_token")
    return {"message": "Logged out successfully"}


@router.get("/auth/check")
async def check_auth(user: User | None = Depends(get_current_user)):
    """Check if user is authenticated."""
    if user:
        return {
            "authenticated": True,
            "user": UserResponse(
                id=str(user.id),
                email=user.email,
                created_at=user.created_at,
            ),
        }
    return {"authenticated": False, "user": None}
