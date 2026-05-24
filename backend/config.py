import os
from urllib.parse import urlsplit, urlunsplit

from core.env import load_env_file


load_env_file()


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default):
    value = os.environ.get(name)
    if not value:
        return default
    return [normalize_origin(item) for item in value.split(",") if item.strip()]


def normalize_origin(value):
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


APP_ENV = os.environ.get("PLANLY_ENV", "development").strip().lower()
HOST = os.environ.get("PLANLY_HOST", "127.0.0.1" if APP_ENV == "development" else "0.0.0.0")
PORT = int(os.environ.get("PLANLY_PORT") or os.environ.get("PORT", "8000"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
ADMIN_EMAIL = os.environ.get("PLANLY_ADMIN_EMAIL", "").strip()
ADMIN_PASSWORD = os.environ.get("PLANLY_ADMIN_PASSWORD", "")
SESSION_COOKIE_NAME = os.environ.get("PLANLY_SESSION_COOKIE_NAME", "planly_session")
SESSION_TTL_HOURS = int(os.environ.get("PLANLY_SESSION_TTL_HOURS", "12"))
SESSION_COOKIE_SAMESITE = os.environ.get("PLANLY_SESSION_COOKIE_SAMESITE", "Lax")
COOKIE_SECURE = env_bool("PLANLY_COOKIE_SECURE", False)
PUBLIC_ERROR_DETAILS = env_bool("PLANLY_PUBLIC_ERROR_DETAILS", False)
REQUIRE_CSRF = env_bool("PLANLY_REQUIRE_CSRF", True)
MAX_REQUEST_BYTES = int(os.environ.get("PLANLY_MAX_REQUEST_BYTES", str(256 * 1024)))
ALLOW_SQLITE_IN_PRODUCTION = env_bool("PLANLY_ALLOW_SQLITE_IN_PRODUCTION", False)
ALLOWED_ORIGINS = env_list(
    "PLANLY_ALLOWED_ORIGINS",
    ["http://127.0.0.1:5173", "http://localhost:5173"],
)
ROLES = {"admin", "planner", "client"}
PAYMENT_METHODS = {"pix", "debito", "credito", "dinheiro"}


def is_production():
    return APP_ENV == "production"


def validate_production_config(db_path):
    if not is_production():
        return
    errors = []
    if not ALLOWED_ORIGINS:
        errors.append("PLANLY_ALLOWED_ORIGINS deve conter o dominio do frontend.")
    if any(origin == "*" or "localhost" in origin or "127.0.0.1" in origin for origin in ALLOWED_ORIGINS):
        errors.append("PLANLY_ALLOWED_ORIGINS nao pode usar localhost, 127.0.0.1 ou * em producao.")
    if not COOKIE_SECURE:
        errors.append("PLANLY_COOKIE_SECURE=true e obrigatorio em producao.")
    if SESSION_COOKIE_SAMESITE.lower() == "none" and not COOKIE_SECURE:
        errors.append("SameSite=None exige cookie Secure.")
    if PUBLIC_ERROR_DETAILS:
        errors.append("PLANLY_PUBLIC_ERROR_DETAILS=false e obrigatorio em producao.")
    if ADMIN_PASSWORD and len(ADMIN_PASSWORD) < 14:
        errors.append("PLANLY_ADMIN_PASSWORD deve ter pelo menos 14 caracteres em producao.")
    if not DATABASE_URL and str(db_path).endswith((".db", ".sqlite", ".sqlite3")) and not ALLOW_SQLITE_IN_PRODUCTION:
        errors.append("SQLite local nao e recomendado em producao. Use Postgres ou defina PLANLY_ALLOW_SQLITE_IN_PRODUCTION=true conscientemente.")
    if errors:
        raise RuntimeError("Configuracao insegura para producao: " + " ".join(errors))
