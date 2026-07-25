from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_cart_session_cookie,
    get_client_ip,
    get_current_session_id,
    get_current_user,
    get_db,
    get_refresh_cookie,
    get_user_agent_hash,
    verify_csrf,
)
from app.core.cookies import clear_auth_cookies, clear_cart_session_cookie, set_auth_cookies
from app.core.rate_limit import rate_limit
from app.models.auth import User
from app.schemas.auth import (
    EmailResendIn,
    EmailVerifyIn,
    ForgotPasswordIn,
    LoginIn,
    RegisterIn,
    ResetPasswordIn,
    SessionOut,
    UserOut,
)
from app.services.auth.auth_service import AuthService
from app.services.cart_service import CartService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    dependencies=[Depends(rate_limit("register", limit=5, window_seconds=3600))],
)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).register(payload)


@router.post(
    "/login",
    response_model=UserOut,
    dependencies=[Depends(rate_limit("login", limit=20, window_seconds=900))],
)
async def login(
    payload: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
    ip: str | None = Depends(get_client_ip),
    ua_hash: str | None = Depends(get_user_agent_hash),
    guest_cart_token: str | None = Depends(get_cart_session_cookie),
):
    user, user_out, tokens = await AuthService(db).login(payload, ip=ip, user_agent_hash=ua_hash)
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=tokens.csrf_token,
        refresh_max_age=tokens.refresh_max_age,
    )
    if guest_cart_token:
        await CartService(db).merge_guest_into_user(session_token=guest_cart_token, user=user)
        clear_cart_session_cookie(response)
    return user_out


@router.post("/refresh", response_model=UserOut)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_raw: str | None = Depends(get_refresh_cookie),
    ip: str | None = Depends(get_client_ip),
    ua_hash: str | None = Depends(get_user_agent_hash),
):
    user_out, tokens = await AuthService(db).refresh(refresh_raw, ip=ip, user_agent_hash=ua_hash)
    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=tokens.csrf_token,
        refresh_max_age=tokens.refresh_max_age,
    )
    return user_out


@router.post("/logout", status_code=204, dependencies=[Depends(verify_csrf)])
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_raw: str | None = Depends(get_refresh_cookie),
):
    await AuthService(db).logout(refresh_raw)
    clear_auth_cookies(response)
    return Response(status_code=204)


@router.post("/logout-all", status_code=204, dependencies=[Depends(verify_csrf)])
async def logout_all(
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await AuthService(db).logout_all(user)
    clear_auth_cookies(response)
    return Response(status_code=204)


@router.post("/email/verify", status_code=204)
async def verify_email(payload: EmailVerifyIn, db: AsyncSession = Depends(get_db)):
    await AuthService(db).verify_email(payload.token)
    return Response(status_code=204)


@router.post(
    "/email/resend",
    status_code=202,
    dependencies=[Depends(rate_limit("email_resend", limit=5, window_seconds=3600))],
)
async def resend_verification(payload: EmailResendIn, db: AsyncSession = Depends(get_db)):
    await AuthService(db).resend_verification(payload.email)
    return {"status": "accepted"}


@router.post(
    "/password/forgot",
    status_code=202,
    dependencies=[Depends(rate_limit("password_forgot", limit=5, window_seconds=3600))],
)
async def forgot_password(payload: ForgotPasswordIn, db: AsyncSession = Depends(get_db)):
    await AuthService(db).forgot_password(payload.email)
    return {"status": "accepted"}


@router.post(
    "/password/reset",
    status_code=204,
    dependencies=[Depends(rate_limit("password_reset", limit=10, window_seconds=3600))],
)
async def reset_password(payload: ResetPasswordIn, db: AsyncSession = Depends(get_db)):
    await AuthService(db).reset_password(payload.token, payload.password)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
async def me(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await AuthService(db).get_user_out(user)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    current_family_id: str | None = Depends(get_current_session_id),
):
    return await AuthService(db).list_sessions(user, current_family_id=current_family_id)


@router.delete("/sessions/{session_id}", status_code=204, dependencies=[Depends(verify_csrf)])
async def revoke_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await AuthService(db).revoke_session(user, session_id)
    return Response(status_code=204)
