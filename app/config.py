"""Application settings, read from environment variables."""
import os
import secrets


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/booking_diagnostic"
    )
    # No hardcoded fallback: a known secret string in source control would let
    # anyone forge JWTs. If JWT_SECRET isn't set, generate a random one at
    # startup instead -- tokens just won't survive a process restart.
    jwt_secret: str = os.getenv("JWT_SECRET") or secrets.token_hex(32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # Shared secret the (simulated) payment provider must send back on every
    # webhook call. Unlike JWT_SECRET this one can't be auto-generated -- an
    # external caller needs to know it -- so it has a documented dev default.
    # Set a real value via WEBHOOK_SECRET for anything beyond local testing.
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "local-dev-webhook-secret")


settings = Settings()
