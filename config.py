import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from the project .env file.
load_dotenv(os.path.join(BASE_DIR, ".env"))

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

SECRET_KEY = os.getenv("SECRET_KEY")

# Keep local development easy to run, but never allow the fallback in production.
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY must be set in the environment before production starts."
        )
    SECRET_KEY = "development-only-key-do-not-use-in-production"


class Config:
    SECRET_KEY = SECRET_KEY

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" +
        os.path.join(BASE_DIR, "instance", "home_finance.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Browser session security.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("SESSION_COOKIE_SECURE", "true" if IS_PRODUCTION else "false")
        .strip()
        .lower() == "true"
    )

    # Flask-Login remember-cookie security (remember-me is not enabled by default).
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Configure this to a Redis URL for production/multi-worker deployments.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
