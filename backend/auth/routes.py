import os
import secrets
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from db import get_session
from rate_limit import limiter
from auth.deps import get_current_user
from auth.email import send_otp_email
from auth.google import build_authorize_url, exchange_code_for_id_token
from auth.otp import can_resend, generate_otp, verify_otp
from auth.schemas import (
    ForgotPasswordRequest,
    RefreshRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    SigninRequest,
    SignupRequest,
    SignupResponse,
    TokenPair,
    UserRead,
    VerifyOtpRequest,
)
from auth.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hashpwd,
    verifypwd,
)
from auth.tables import Auth_provider, User


router = APIRouter(prefix="/auth", tags=["auth"])

FRONTEND_REDIRECT_URL = os.getenv("FRONTEND_REDIRECT_URL", "http://localhost:3000/auth/callback")
GOOGLE_STATE_COOKIE = "google_oauth_state"


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def signup(request: Request, req: SignupRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == req.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    user = User(
        email=req.email,
        hashed_password=hashpwd(req.password),
        provider=Auth_provider.LOCAL,
        is_verified=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    code = generate_otp(user.id)
    try:
        send_otp_email(user.email, code)
    except Exception as exc:
        # Don't fail signup if SMTP is misconfigured in dev — just log.
        print(f"[warn] failed to send OTP email to {user.email}: {exc}")
        print(f"[dev] OTP for {user.email}: {code}")

    return SignupResponse(user_id=user.id, email=user.email)


@router.post("/verify-otp", response_model=TokenPair)
@limiter.limit("10/minute")
def verify_otp_route(request: Request, req: VerifyOtpRequest, session: Session = Depends(get_session)):
    user = session.get(User, req.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    if not verify_otp(req.user_id, req.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired code")

    if not user.is_verified:
        user.is_verified = True
        session.add(user)
        session.commit()

    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/resend-otp")
@limiter.limit("3/minute")
def resend_otp(request: Request, req: ResendOtpRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == req.email)).first()
    # Always return 200 to avoid email enumeration.
    if user is None or user.is_verified:
        return {"message": "if eligible, a new code has been sent"}

    if not can_resend(user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="please wait before requesting another code",
        )

    code = generate_otp(user.id)
    try:
        send_otp_email(user.email, code)
    except Exception as exc:
        print(f"[warn] failed to send OTP email to {user.email}: {exc}")
        print(f"[dev] OTP for {user.email}: {code}")

    return {"message": "if eligible, a new code has been sent"}


@router.post("/signin", response_model=TokenPair)
@limiter.limit("10/minute")
def signin(request: Request, req: SigninRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == req.email)).first()
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if user is None or user.hashed_password is None:
        raise invalid
    if not verifypwd(req.password, user.hashed_password):
        raise invalid
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email not verified")

    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
def forgot_password(request: Request, req: ForgotPasswordRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == req.email)).first()
    if user is not None:
        reset_token = create_password_reset_token(user.id)
        # TODO: email the token to the user. For dev, print it.
        print(f"[dev] password reset token for {user.email}: {reset_token}")
    return {"message": "if that email exists, a reset link has been sent"}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, session: Session = Depends(get_session)):
    try:
        payload = decode_token(req.token, expected_type="access")
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    user.hashed_password = hashpwd(req.new_password)
    session.add(user)
    session.commit()
    return {"message": "password updated"}


@router.post("/refresh-token", response_model=TokenPair)
def refresh_token(req: RefreshRequest, session: Session = Depends(get_session)):
    try:
        payload = decode_token(req.refresh_token, expected_type="refresh")
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")

    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    return {"message": "logged out"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/google/login")
def google_login():
    state = secrets.token_urlsafe(32)
    redirect_url = build_authorize_url(state)
    resp = RedirectResponse(redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    resp.set_cookie(
        key=GOOGLE_STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=False,  # set True in prod (HTTPS)
        samesite="lax",
    )
    return resp


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    session: Session = Depends(get_session),
):
    cookie_state = request.cookies.get(GOOGLE_STATE_COOKIE)
    if not code or not state or not cookie_state or state != cookie_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid oauth state")

    try:
        claims = await exchange_code_for_id_token(code)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google token exchange failed")

    google_sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified", False)
    if not google_sub or not email or not email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google account missing verified email")

    user = session.exec(select(User).where(User.google_sub == google_sub)).first()
    if user is None:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                email=email,
                hashed_password=None,
                provider=Auth_provider.GOOGLE,
                google_sub=google_sub,
                is_verified=True,
            )
            session.add(user)
        else:
            user.google_sub = google_sub
            user.provider = Auth_provider.GOOGLE
            user.is_verified = True
            session.add(user)
        session.commit()
        session.refresh(user)

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    redirect = RedirectResponse(
        f"{FRONTEND_REDIRECT_URL}?access_token={access}&refresh_token={refresh}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    redirect.delete_cookie(GOOGLE_STATE_COOKIE)
    return redirect
