"""환경 변수 기반 설정. 상대 경로는 저장소 루트 기준이다."""
import os
import secrets
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "database" / "migrations"
SEED_PATH = ROOT / "reference" / "seed" / "seed.json"

TODAY = date(2026, 10, 19)
TODAY_ISO = TODAY.isoformat()


def _path(name: str, default: str) -> Path:
    path = Path(os.environ.get(name) or default)
    return path if path.is_absolute() else ROOT / path


def db_path() -> Path:
    return _path("SHIPYARD_DB_PATH", "database/shipyard.db")


def file_dir() -> Path:
    return _path("SHIPYARD_FILE_DIR", "storage/drawings")


APP_SECRET = os.environ.get("APP_SECRET") or secrets.token_urlsafe(48)


def token_ttl() -> int:
    return int(os.environ.get("TOKEN_TTL") or 28800)


def otp_token_ttl() -> int:
    return int(os.environ.get("OTP_TOKEN_TTL") or 300)


def weather_provider() -> str:
    return os.environ.get("WEATHER_PROVIDER", "")
