import ssl
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Single source of runtime configuration. No module reads os.environ directly."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    # >=32 bytes even as a placeholder: RFC 7518 §3.2 recommends an HMAC-SHA256 key be at least
    # as long as the hash output (32 bytes) — pyjwt started warning about this at runtime after
    # the 2.13.0 upgrade (spec §22.7's dependency-audit checklist), and the old 20-byte default
    # ("dev-secret-change-me") triggered it on every single token issued in dev/test.
    app_secret_key: str = Field(default="dev-secret-change-me-please-32bytes", alias="APP_SECRET_KEY")
    # spec §11.5: admin API keys are stored as argon2(key + pepper) — a pepper distinct from
    # APP_SECRET_KEY so a leaked JWT signing key alone can't be used to forge/verify API keys too.
    admin_api_key_pepper: str = Field(default="dev-pepper-change-me-please-32bytes", alias="ADMIN_API_KEY_PEPPER")
    # HMAC secret for the simulated payment webhook (spec §12.5) — a separate secret from
    # APP_SECRET_KEY/ADMIN_API_KEY_PEPPER, same "must be changed in production" fail-fast pattern.
    payment_webhook_secret: str = Field(
        default="dev-webhook-secret-change-me-please-32b", alias="PAYMENT_WEBHOOK_SECRET"
    )
    app_base_url: str = Field(default="http://localhost:5173", alias="APP_BASE_URL")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    # Distinct from app_base_url (the frontend's origin, used for email links): this is the
    # backend's OWN origin, used to build absolute /media URLs an <img> tag can fetch directly —
    # cross-port image loads don't need CORS the way fetch/XHR would, so no proxy config needed.
    backend_base_url: str = Field(default="http://127.0.0.1:8000", alias="BACKEND_BASE_URL")

    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="mysql_password")
    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_db: str = Field(default="blackcart", alias="MYSQL_DB")
    # Managed MySQL providers (Aiven and similar) require TLS and reject plaintext connections
    # outright — "DISABLED" (the native-Windows-dev default) skips SSL entirely; "REQUIRED" wraps
    # the connection in an SSL context, optionally pinned to a specific CA (mysql_ssl_ca, the PEM
    # content itself rather than a file path, since env vars are the only config channel on Vercel).
    mysql_ssl_mode: str = Field(default="DISABLED", alias="MYSQL_SSL_MODE")
    mysql_ssl_ca: str | None = Field(default=None, alias="MYSQL_SSL_CA")

    kaggle_api_key: str | None = Field(default=None, alias="kaggle_api_key")

    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=5, alias="DATABASE_MAX_OVERFLOW")
    # Managed MySQL providers commonly close idle connections well under an hour — recycling
    # proactively avoids "MySQL server has gone away" on a connection pulled from the pool after
    # sitting idle, the classic failure mode of a fixed pool talking to someone else's DB server.
    database_pool_recycle_seconds: int = Field(default=280, alias="DATABASE_POOL_RECYCLE_SECONDS")

    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    blob_read_write_token: str | None = Field(default=None, alias="BLOB_READ_WRITE_TOKEN")

    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    jwt_access_ttl_seconds: int = Field(default=900, alias="JWT_ACCESS_TTL_SECONDS")
    jwt_refresh_ttl_seconds: int = Field(default=1_209_600, alias="JWT_REFRESH_TTL_SECONDS")
    email_verification_ttl_seconds: int = Field(default=86_400, alias="EMAIL_VERIFICATION_TTL_SECONDS")
    password_reset_ttl_seconds: int = Field(default=3_600, alias="PASSWORD_RESET_TTL_SECONDS")
    mfa_challenge_ttl_seconds: int = Field(default=300, alias="MFA_CHALLENGE_TTL_SECONDS")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    mail_backend: str = Field(default="console", alias="MAIL_BACKEND")

    guest_cart_cookie_ttl_seconds: int = Field(default=30 * 24 * 3600, alias="GUEST_CART_COOKIE_TTL_SECONDS")
    tax_rate_percent: str = Field(default="0", alias="TAX_RATE_PERCENT")
    free_shipping_threshold: str = Field(default="2000", alias="FREE_SHIPPING_THRESHOLD")
    shipping_flat_fee: str = Field(default="60", alias="SHIPPING_FLAT_FEE")
    cod_surcharge: str = Field(default="20", alias="COD_SURCHARGE")
    delivery_min_days: int = Field(default=3, alias="DELIVERY_MIN_DAYS")
    delivery_max_days: int = Field(default=6, alias="DELIVERY_MAX_DAYS")
    delivery_simulator_minutes_per_hour: float = Field(
        default=0.05,
        alias="DELIVERY_SIMULATOR_MINUTES_PER_HOUR",
        description="Real minutes per spec-hour of the delivery timeline — e.g. 0.05 compresses "
        "the 34-hour T+0..T+34h schedule (spec §13.1) into ~1.7 real minutes.",
    )
    payment_simulator_success_rate: float = Field(default=0.9, alias="PAYMENT_SIMULATOR_SUCCESS_RATE")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def sync_database_url(self) -> str:
        """Used by Alembic, which runs migrations synchronously."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        """False in local dev so cookies still work over plain http://localhost."""
        return self.is_production


def get_mysql_ssl_connect_args(settings: Settings) -> dict:
    """`connect_args` for both the async (aiomysql) and sync (pymysql) engines — SSL params go
    through DBAPI connect kwargs, not the connection URL, so both `db/session.py` and
    `alembic/env.py` share this rather than each hand-rolling it. Managed providers like Aiven
    typically sign their MySQL endpoint's certificate with a well-known CA, so the default system
    trust store (`ssl.create_default_context()`) validates it without `mysql_ssl_ca`; that setting
    exists for providers that hand out a private/self-signed CA instead."""
    if settings.mysql_ssl_mode == "DISABLED":
        return {}
    ctx = ssl.create_default_context()
    if settings.mysql_ssl_ca:
        ctx.load_verify_locations(cadata=settings.mysql_ssl_ca)
    return {"ssl": ctx}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production:
        if settings.app_secret_key.startswith("dev-secret-change-me"):
            raise RuntimeError("APP_SECRET_KEY must be set in production")
        if len(settings.app_secret_key.encode("utf-8")) < 32:
            # RFC 7518 §3.2 — an HS256 key shorter than the hash output (32 bytes) is weak
            # regardless of whether it's the placeholder; pyjwt itself warns about this at
            # sign/verify time (spec §22.7's dependency audit surfaced it), so failing fast here
            # catches a misconfigured production secret before the first token is ever issued.
            raise RuntimeError("APP_SECRET_KEY must be at least 32 bytes long in production")
        if settings.admin_api_key_pepper.startswith("dev-pepper-change-me"):
            raise RuntimeError("ADMIN_API_KEY_PEPPER must be set in production")
        if settings.payment_webhook_secret.startswith("dev-webhook-secret-change-me"):
            raise RuntimeError("PAYMENT_WEBHOOK_SECRET must be set in production")
    return settings
