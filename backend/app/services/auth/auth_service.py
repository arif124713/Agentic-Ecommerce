import datetime
from typing import NamedTuple

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core import mfa
from app.core.config import get_settings
from app.core.errors import (
    AccountLockedError,
    EmailAlreadyRegisteredError,
    MfaAlreadyEnabledError,
    MfaInvalidCodeError,
    MfaNotEnabledError,
    MfaRequiredError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.core.mail import send_password_reset_email, send_verification_email
from app.core.security import (
    create_access_token,
    generate_csrf_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    password_policy_errors,
    verify_password,
)
from app.models.auth import EmailVerificationToken, MfaChallengeToken, PasswordResetToken, RefreshToken, User
from app.repositories.auth import (
    LoginAttemptRepository,
    OneTimeTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.schemas.auth import (
    LoginIn,
    MfaDisableIn,
    MfaEnableIn,
    MfaEnableOut,
    MfaLoginVerifyIn,
    MfaSetupOut,
    RegisterIn,
    SessionOut,
    UserOut,
)

logger = structlog.get_logger("blackcart.auth")
settings = get_settings()


class SessionTokens(NamedTuple):
    access_token: str
    refresh_token: str
    csrf_token: str
    refresh_max_age: int | None
    roles: list[str]
    permissions: list[str]


def to_user_out(user: User, roles: list[str], permissions: list[str]) -> UserOut:
    return UserOut(
        public_id=user.public_id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        email_verified_at=user.email_verified_at,
        mfa_enabled=user.mfa_enabled,
        roles=roles,
        permissions=permissions,
    )


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.email_tokens = OneTimeTokenRepository(session, EmailVerificationToken)
        self.reset_tokens = OneTimeTokenRepository(session, PasswordResetToken)
        self.mfa_tokens = OneTimeTokenRepository(session, MfaChallengeToken)
        self.login_attempts = LoginAttemptRepository(session)

    # -- registration & verification -------------------------------------------------

    async def register(self, payload: RegisterIn) -> UserOut:
        errors = password_policy_errors(payload.password, email=payload.email, first_name=payload.first_name)
        if errors:
            raise ValidationAppError(
                "Password does not meet requirements.",
                details=[{"field": "password", "issue": e} for e in errors],
            )

        if await self.users.get_by_email(payload.email) is not None:
            raise EmailAlreadyRegisteredError()

        now = datetime.datetime.now(datetime.UTC)
        user = User(
            public_id=str(ULID()),
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            password_changed_at=now,
            marketing_opt_in=payload.marketing_opt_in,
        )
        self.users.add(user)
        await self.session.flush()  # assign user.id for the role grant + token FK below
        await self.users.assign_role(user_id=user.id, role_code="customer")

        raw_token = generate_opaque_token()
        self.email_tokens.create(
            user_id=user.id, token_hash=hash_token(raw_token), ttl_seconds=settings.email_verification_ttl_seconds
        )
        await self.session.commit()

        send_verification_email(to=user.email, token=raw_token)
        roles, permissions = await self.users.get_roles_and_permissions(user.id)
        return to_user_out(user, roles, permissions)

    async def verify_email(self, token: str) -> None:
        record = await self.email_tokens.get_valid(hash_token(token))
        if record is None:
            raise NotFoundError("This verification link is invalid or has expired.")

        user = await self.users.get_by_id(record.user_id)
        if user is None:
            raise NotFoundError("This verification link is invalid or has expired.")

        record.used_at = datetime.datetime.now(datetime.UTC)
        if user.email_verified_at is None:
            user.email_verified_at = record.used_at
        await self.session.commit()

    async def resend_verification(self, email: str) -> None:
        """Always succeeds from the caller's perspective — no enumeration (spec §10.8 forgot-password
        applies the same principle; resend follows it too since it's rate-limited the same way)."""
        user = await self.users.get_by_email(email)
        if user is None or user.email_verified_at is not None:
            return

        await self.email_tokens.invalidate_all_for_user(user.id)
        raw_token = generate_opaque_token()
        self.email_tokens.create(
            user_id=user.id, token_hash=hash_token(raw_token), ttl_seconds=settings.email_verification_ttl_seconds
        )
        await self.session.commit()
        send_verification_email(to=user.email, token=raw_token)

    # -- login / session lifecycle ----------------------------------------------------

    async def _check_lockout(self, *, email_hash: str, ip: str | None) -> None:
        now = datetime.datetime.now(datetime.UTC)
        failures_1h = await self.login_attempts.count_recent_failures(
            email_hash=email_hash, ip=ip, since=now - datetime.timedelta(hours=1)
        )
        if failures_1h >= 10:
            raise AccountLockedError("Too many failed attempts. Please try again in an hour.")
        failures_15m = await self.login_attempts.count_recent_failures(
            email_hash=email_hash, ip=ip, since=now - datetime.timedelta(minutes=15)
        )
        if failures_15m >= 5:
            raise AccountLockedError("Too many failed attempts. Please try again in 15 minutes.")

    async def _issue_session(
        self,
        user: User,
        *,
        ip: str | None,
        user_agent_hash: str | None,
        remember_me: bool,
        family_id: str | None = None,
        parent_id: int | None = None,
    ) -> SessionTokens:
        roles, permissions = await self.users.get_roles_and_permissions(user.id)
        family = family_id or str(ULID())
        now = datetime.datetime.now(datetime.UTC)
        raw_refresh = generate_opaque_token()

        self.refresh_tokens.add(
            RefreshToken(
                public_id=str(ULID()),
                user_id=user.id,
                token_hash=hash_token(raw_refresh),
                family_id=family,
                parent_id=parent_id,
                ip=ip,
                user_agent_hash=user_agent_hash,
                remember=remember_me,
                expires_at=now + datetime.timedelta(seconds=settings.jwt_refresh_ttl_seconds),
                created_at=now,
            )
        )
        access_token = create_access_token(
            user_public_id=user.public_id, session_id=family, roles=roles, permissions=permissions
        )
        csrf_token = generate_csrf_token()
        refresh_max_age = settings.jwt_refresh_ttl_seconds if remember_me else None
        return SessionTokens(access_token, raw_refresh, csrf_token, refresh_max_age, roles, permissions)

    async def login(
        self, payload: LoginIn, *, ip: str | None, user_agent_hash: str | None
    ) -> tuple[User, UserOut, SessionTokens]:
        email = payload.email.lower()
        email_hash = hash_token(email)
        await self._check_lockout(email_hash=email_hash, ip=ip)

        user = await self.users.get_by_email(email)
        valid_user = user is not None and user.status == "active"
        password_ok = verify_password(payload.password, user.password_hash if user is not None and valid_user else None)

        if user is None or not valid_user or not password_ok:
            self.login_attempts.record(
                email_hash=email_hash, ip=ip, success=False, reason="unknown_email" if not valid_user else "wrong_password"
            )
            await self.session.commit()
            raise UnauthorizedError("Incorrect email or password.")

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(payload.password)

        self.login_attempts.record(email_hash=email_hash, ip=ip, success=True, reason=None)
        user.failed_login_count = 0
        user.last_login_at = datetime.datetime.now(datetime.UTC)
        user.last_login_ip = ip

        if user.mfa_enabled:
            raw_challenge = generate_opaque_token()
            record = self.mfa_tokens.create(
                user_id=user.id,
                token_hash=hash_token(raw_challenge),
                ttl_seconds=settings.mfa_challenge_ttl_seconds,
            )
            record.remember = payload.remember_me
            await self.session.commit()
            raise MfaRequiredError(headers={"X-MFA-Challenge": raw_challenge})

        tokens = await self._issue_session(
            user, ip=ip, user_agent_hash=user_agent_hash, remember_me=payload.remember_me
        )
        await self.session.commit()
        return user, to_user_out(user, tokens.roles, tokens.permissions), tokens

    async def complete_mfa_login(
        self, payload: MfaLoginVerifyIn, *, ip: str | None, user_agent_hash: str | None
    ) -> tuple[User, UserOut, SessionTokens]:
        challenge = await self.mfa_tokens.get_valid(hash_token(payload.challenge_token))
        if challenge is None:
            raise UnauthorizedError("This sign-in attempt has expired. Please sign in again.")

        user = await self.users.get_by_id(challenge.user_id)
        if user is None or user.status != "active" or not user.mfa_enabled:
            raise UnauthorizedError("This sign-in attempt is no longer valid.")

        if not self._verify_mfa_factor(user, code=payload.code, recovery_code=payload.recovery_code):
            raise MfaInvalidCodeError()

        challenge.used_at = datetime.datetime.now(datetime.UTC)
        tokens = await self._issue_session(
            user, ip=ip, user_agent_hash=user_agent_hash, remember_me=challenge.remember
        )
        await self.session.commit()
        return user, to_user_out(user, tokens.roles, tokens.permissions), tokens

    async def refresh(
        self, refresh_raw: str | None, *, ip: str | None, user_agent_hash: str | None
    ) -> tuple[UserOut, SessionTokens]:
        if not refresh_raw:
            raise UnauthorizedError("No active session.")

        token = await self.refresh_tokens.get_by_hash(hash_token(refresh_raw))
        if token is None:
            raise UnauthorizedError("Session is no longer valid.")

        if token.revoked_at is not None:
            if token.revoked_reason == "rotated":
                # This exact token was already exchanged for a newer one and is being replayed —
                # by someone other than the legitimate holder, or by a client that lost the
                # rotation race. Either way, treat the whole family as compromised (spec §11.2).
                logger.warning("session_reuse_detected", user_id=token.user_id, family_id=token.family_id)
                await self.refresh_tokens.revoke_family(token.family_id, reason="reuse_detected")
                await self.session.commit()
                raise UnauthorizedError(
                    "Session reuse detected. All sessions have been signed out for your safety."
                )
            # Revoked for a mundane reason (logout, logout-all, password reset, user-initiated
            # revoke) — just a normal invalid session, not a security event.
            raise UnauthorizedError("Session is no longer valid.")

        now = datetime.datetime.now(datetime.UTC)
        # MySQL DATETIME columns come back tz-naive even though the model declares
        # timezone=True (MySQL has no tz-aware temporal type, unlike Postgres) — compare
        # naive-to-naive rather than crash on "offset-naive and offset-aware".
        if token.expires_at <= now.replace(tzinfo=None):
            raise UnauthorizedError("Session has expired.")

        user = await self.users.get_by_id(token.user_id)
        if user is None or user.status != "active":
            raise UnauthorizedError("Session is no longer valid.")

        await self.refresh_tokens.revoke(token, reason="rotated")
        tokens = await self._issue_session(
            user,
            ip=ip,
            user_agent_hash=user_agent_hash,
            remember_me=token.remember,
            family_id=token.family_id,
            parent_id=token.id,
        )
        await self.session.commit()
        return to_user_out(user, tokens.roles, tokens.permissions), tokens

    async def logout(self, refresh_raw: str | None) -> None:
        if not refresh_raw:
            return
        token = await self.refresh_tokens.get_by_hash(hash_token(refresh_raw))
        if token is not None and token.revoked_at is None:
            await self.refresh_tokens.revoke(token, reason="logout")
            await self.session.commit()

    async def logout_all(self, user: User) -> None:
        await self.refresh_tokens.revoke_all_for_user(user.id, reason="logout_all")
        await self.session.commit()

    # -- password reset -----------------------------------------------------------------

    async def forgot_password(self, email: str) -> None:
        """Always a no-op from the outside for an unknown email (spec §10.8: no enumeration)."""
        user = await self.users.get_by_email(email)
        if user is None:
            return

        await self.reset_tokens.invalidate_all_for_user(user.id)
        raw_token = generate_opaque_token()
        self.reset_tokens.create(
            user_id=user.id, token_hash=hash_token(raw_token), ttl_seconds=settings.password_reset_ttl_seconds
        )
        await self.session.commit()
        send_password_reset_email(to=user.email, token=raw_token)

    async def reset_password(self, token: str, new_password: str) -> None:
        record = await self.reset_tokens.get_valid(hash_token(token))
        if record is None:
            raise NotFoundError("This password reset link is invalid or has expired.")

        user = await self.users.get_by_id(record.user_id)
        if user is None:
            raise NotFoundError("This password reset link is invalid or has expired.")

        errors = password_policy_errors(new_password, email=user.email, first_name=user.first_name)
        if errors:
            raise ValidationAppError(
                "Password does not meet requirements.",
                details=[{"field": "password", "issue": e} for e in errors],
            )

        now = datetime.datetime.now(datetime.UTC)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        record.used_at = now

        # Spec §10.8: password/reset "revokes all sessions" unconditionally.
        await self.refresh_tokens.revoke_all_for_user(user.id, reason="password_reset")
        await self.session.commit()

    # -- MFA (TOTP) ------------------------------------------------------------------------

    def _verify_mfa_factor(self, user: User, *, code: str | None, recovery_code: str | None) -> bool:
        if code:
            if user.mfa_secret is None:
                # mfa_enabled implies mfa_secret is set — a bare crash here would mean that
                # invariant broke, not a bad request from the caller; verification simply fails.
                return False
            secret = mfa.decrypt_secret(user.mfa_secret)
            return mfa.verify_code(secret, code)

        if not recovery_code:
            # Neither a TOTP code nor a recovery code was actually provided — a malformed request,
            # not a match attempt. Without this check, `.strip()` below would raise on None instead
            # of failing the same way every other non-match does.
            return False

        # Recovery codes are single-use: a match consumes it from the stored (hashed) list.
        code_hash = hash_token(recovery_code.strip().lower())
        codes = list(user.mfa_recovery_codes or [])
        if code_hash not in codes:
            return False
        codes.remove(code_hash)
        user.mfa_recovery_codes = codes
        return True

    async def mfa_setup(self, user: User) -> MfaSetupOut:
        """Generates and stores a new (unconfirmed) secret; mfa_enabled stays False until the
        caller proves possession via mfa_enable. Calling this again before enabling just
        replaces the pending secret, so an abandoned setup can't lock a user out of retrying."""
        secret = mfa.generate_secret()
        user.mfa_secret = mfa.encrypt_secret(secret)
        await self.session.commit()
        uri = mfa.provisioning_uri(secret, email=user.email)
        return MfaSetupOut(secret=secret, otpauth_uri=uri, qr_data_uri=mfa.qr_data_uri(uri))

    async def mfa_enable(self, user: User, payload: MfaEnableIn) -> MfaEnableOut:
        if user.mfa_enabled:
            raise MfaAlreadyEnabledError()
        if not user.mfa_secret:
            raise ValidationAppError("Call /mfa/setup before enabling MFA.")

        secret = mfa.decrypt_secret(user.mfa_secret)
        if not mfa.verify_code(secret, payload.code):
            raise MfaInvalidCodeError()

        raw_codes = mfa.generate_recovery_codes()
        user.mfa_recovery_codes = [hash_token(c) for c in raw_codes]
        user.mfa_enabled = True
        await self.session.commit()
        return MfaEnableOut(recovery_codes=raw_codes)

    async def mfa_disable(self, user: User, payload: MfaDisableIn) -> None:
        if not user.mfa_enabled:
            raise MfaNotEnabledError()
        if not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("Incorrect password.")
        if not self._verify_mfa_factor(user, code=payload.code, recovery_code=None):
            raise MfaInvalidCodeError()

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_recovery_codes = None
        await self.session.commit()

    # -- current user / sessions ---------------------------------------------------------

    async def get_user_out(self, user: User) -> UserOut:
        roles, permissions = await self.users.get_roles_and_permissions(user.id)
        return to_user_out(user, roles, permissions)

    async def list_sessions(self, user: User, *, current_family_id: str | None) -> list[SessionOut]:
        tokens = await self.refresh_tokens.list_active_for_user(user.id)
        return [
            SessionOut(
                id=t.public_id,
                device_label=t.device_label,
                ip=t.ip,
                is_current=(t.family_id == current_family_id),
                created_at=t.created_at,
                last_used_at=t.created_at,
            )
            for t in tokens
        ]

    async def revoke_session(self, user: User, session_public_id: str) -> None:
        token = await self.refresh_tokens.get_by_public_id_for_user(session_public_id, user.id)
        if token is None or token.revoked_at is not None:
            raise NotFoundError("Session was not found.")
        await self.refresh_tokens.revoke(token, reason="revoked_by_user")
        await self.session.commit()
