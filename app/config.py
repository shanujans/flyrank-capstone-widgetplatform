"""
Central configuration. Everything secret or environment-specific comes from
env vars (loaded from a .env file in dev) — nothing is hardcoded.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Core ---
    APP_NAME: str = "FlyRank Widget & Lead-Capture Platform"
    ENVIRONMENT: str = "development"

    # --- Database ---
    # Defaults to a local SQLite file. Swap to a Postgres URL
    # (postgresql+psycopg2://user:pass@host:5432/db) with zero code changes.
    DATABASE_URL: str = "sqlite:///./widget_platform.db"

    # --- Auth / JWT ---
    JWT_SECRET: str = "change-me-in-env-this-is-a-dev-only-default"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # --- CORS ---
    # The public endpoints (config, widget.js, submissions) must be reachable
    # from ANY customer site, so we allow all origins there by design.
    # The admin API is separate and requires a bearer token regardless of origin.
    PUBLIC_CORS_ALLOW_ORIGINS: str = "*"

    # --- Rate limiting (in-memory, per-process — see README limitations) ---
    RATE_LIMIT_PER_IP_PER_MINUTE: int = 20
    RATE_LIMIT_PER_WIDGET_PER_MINUTE: int = 60

    # --- Geo enrichment ---
    # When MOCK_GEO=true, provider calls are simulated using the two flags
    # below instead of hitting the real network. This is what makes the
    # fallback-chain proof (Section 7 of the brief) deterministic.
    MOCK_GEO: bool = True
    MOCK_GEO_PROVIDER_A_DOWN: bool = False
    MOCK_GEO_PROVIDER_B_DOWN: bool = False
    GEO_PROVIDER_A_URL: str = "http://ip-api.com/json/{ip}"
    GEO_PROVIDER_B_URL: str = "https://ipapi.co/{ip}/json/"
    GEO_TIMEOUT_SECONDS: float = 3.0

    # --- Side effect (confirmation notification) ---
    # When FORCE_NOTIFY_FAILURE=true, the notify step always raises — used to
    # prove that a broken side effect never breaks the submission (Probe 5).
    FORCE_NOTIFY_FAILURE: bool = False

    # --- Widget bundle version ---
    # Bump this when widget.js changes; it becomes part of the cached URL so
    # old cached copies are never served stale (Section 6.3 / glossary).
    WIDGET_BUNDLE_VERSION: str = "v1"


settings = Settings()
