from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LCS Freight Forwarding API"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+asyncpg://freight:freight@localhost:5432/freight",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")
    redis_socket_timeout_seconds: float = Field(default=3.0, alias="REDIS_SOCKET_TIMEOUT_SECONDS")
    redis_socket_connect_timeout_seconds: float = Field(default=2.0, alias="REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS")
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")

    # Response caching (read-through, PostgreSQL remains authoritative).
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_key_prefix: str = Field(default="lcs", alias="CACHE_KEY_PREFIX")
    cache_ttl_reference_seconds: int = Field(default=300, alias="CACHE_TTL_REFERENCE_SECONDS")
    cache_ttl_dashboard_seconds: int = Field(default=30, alias="CACHE_TTL_DASHBOARD_SECONDS")
    cache_ttl_report_seconds: int = Field(default=60, alias="CACHE_TTL_REPORT_SECONDS")
    cache_ttl_permissions_seconds: int = Field(default=300, alias="CACHE_TTL_PERMISSIONS_SECONDS")

    jwt_secret_key: str = Field(
        default="change-me-in-production-use-a-32-byte-minimum-secret", alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    # Access JWT lifetime. Defaults to a full day (1440 minutes).
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    # Persistent ("Remember me") refresh session lifetime. Rotating a refresh
    # token never extends this absolute deadline.
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    # Non-persistent (browser-session) refresh session lifetime. The refresh
    # cookie has no Max-Age, and the server enforces this absolute deadline.
    session_refresh_token_expire_hours: int = Field(default=12, alias="SESSION_REFRESH_TOKEN_EXPIRE_HOURS")
    password_reset_code_expire_minutes: int = 15
    password_min_length: int = Field(default=8, alias="PASSWORD_MIN_LENGTH")
    password_max_length: int = Field(default=128, alias="PASSWORD_MAX_LENGTH")
    auth_return_tokens: bool = Field(default=True, alias="AUTH_RETURN_TOKENS")
    csrf_secret_key: str | None = Field(default=None, alias="CSRF_SECRET_KEY")
    field_encryption_key: str | None = Field(default=None, alias="FIELD_ENCRYPTION_KEY")

    cors_origins: str = Field(default="http://localhost:3000,http://localhost:3001", alias="CORS_ORIGINS")
    allowed_hosts: str = Field(default="localhost,127.0.0.1,testserver", alias="ALLOWED_HOSTS")

    access_cookie_name: str = Field(default="access_token", alias="ACCESS_COOKIE_NAME")
    refresh_cookie_name: str = Field(default="refresh_token", alias="REFRESH_COOKIE_NAME")
    csrf_cookie_name: str = Field(default="XSRF-TOKEN", alias="CSRF_COOKIE_NAME")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    csrf_header_name: str = Field(default="X-CSRF-Token", alias="CSRF_HEADER_NAME")

    # Background Google Sheets backup scheduler (in-process asyncio loop).
    backup_scheduler_enabled: bool = Field(default=True, alias="BACKUP_SCHEDULER_ENABLED")
    backup_scheduler_tick_seconds: int = Field(default=60, alias="BACKUP_SCHEDULER_TICK_SECONDS")

    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")
    storage_local_path: str = Field(default="./storage", alias="STORAGE_LOCAL_PATH")
    storage_public_base_url: str = Field(default="/api/v1/attachments/file", alias="STORAGE_PUBLIC_BASE_URL")

    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_public_endpoint_url: str | None = Field(default=None, alias="S3_PUBLIC_ENDPOINT_URL")
    s3_access_key: str = Field(default="minioadmin", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="minioadmin", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="freight-attachments", alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_use_ssl: bool = Field(default=False, alias="S3_USE_SSL")

    storage_presigned_uploads_enabled: bool = Field(default=True, alias="STORAGE_PRESIGNED_UPLOADS_ENABLED")
    upload_max_size_mb: int = Field(default=20, alias="UPLOAD_MAX_SIZE_MB")
    upload_allowed_extensions: str = Field(
        default="pdf,png,jpg,jpeg,gif,webp,txt,csv,xlsx,docx",
        alias="UPLOAD_ALLOWED_EXTENSIONS",
    )
    presigned_url_expire_seconds: int = Field(default=300, alias="PRESIGNED_URL_EXPIRE_SECONDS")

    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")
    database_pool_recycle_seconds: int = Field(default=1800, alias="DATABASE_POOL_RECYCLE_SECONDS")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.lower() != "production":
            return self

        errors: list[str] = []
        default_secret = "change-me-in-production-use-a-32-byte-minimum-secret"
        if self.jwt_secret_key == default_secret or len(self.jwt_secret_key) < 32:
            errors.append("JWT_SECRET_KEY must be a unique secret of at least 32 characters")
        if not self.csrf_secret_key or len(self.csrf_secret_key) < 32:
            errors.append("CSRF_SECRET_KEY must be a unique secret of at least 32 characters")
        if not self.field_encryption_key or len(self.field_encryption_key) < 32:
            errors.append("FIELD_ENCRYPTION_KEY must be a unique secret of at least 32 characters")
        configured_secrets = [
            self.jwt_secret_key,
            self.csrf_secret_key,
            self.field_encryption_key,
        ]
        if len(set(configured_secrets)) != len(configured_secrets):
            errors.append("JWT, CSRF and field-encryption secrets must all be different")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true")
        if self.auth_return_tokens:
            errors.append("AUTH_RETURN_TOKENS must be false for browser cookie authentication")
        if self.access_token_expire_minutes > 30:
            errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must not exceed 30")
        if self.password_min_length < 8:
            errors.append("PASSWORD_MIN_LENGTH must be at least 8")
        if self.password_max_length < self.password_min_length:
            errors.append("PASSWORD_MAX_LENGTH must not be lower than PASSWORD_MIN_LENGTH")
        if not self.rate_limit_enabled:
            errors.append("RATE_LIMIT_ENABLED must be true")
        origins = self.cors_origin_list
        if not origins or any(
            (parsed := urlsplit(origin)).scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            for origin in origins
        ):
            errors.append("CORS_ORIGINS must contain only explicit production HTTPS origins")
        if any(value in self.allowed_hosts for value in ("*", "localhost", "127.0.0.1")):
            errors.append("ALLOWED_HOSTS must contain only explicit production hostnames")
        if self.cookie_domain:
            errors.append("COOKIE_DOMAIN must be empty so cookies remain host-only")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def upload_allowed_extension_set(self) -> set[str]:
        return {value.strip().lower().lstrip(".") for value in self.upload_allowed_extensions.split(",") if value.strip()}

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
