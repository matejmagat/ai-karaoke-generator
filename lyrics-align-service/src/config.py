from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    genius_access_token: str
    genius_timeout_seconds: int
    genius_retries: int
    genius_sleep_time_seconds: float


def load_settings() -> Settings:
    """
    Loads local .env values when present.

    Existing operating-system / Docker environment variables are preserved,
    because override=False is the default.
    """
    load_dotenv(dotenv_path=DOTENV_PATH, override=False)

    genius_access_token = os.getenv("GENIUS_ACCESS_TOKEN")

    if not genius_access_token:
        raise RuntimeError(
            "GENIUS_ACCESS_TOKEN is required. "
            "Set it in worker/.env for local development or provide it "
            "as an environment variable in Docker/production."
        )

    return Settings(
        genius_access_token=genius_access_token,
        genius_timeout_seconds=_read_int(
            "GENIUS_TIMEOUT_SECONDS",
            default=15,
        ),
        genius_retries=_read_int(
            "GENIUS_RETRIES",
            default=2,
        ),
        genius_sleep_time_seconds=_read_float(
            "GENIUS_SLEEP_TIME_SECONDS",
            default=0.2,
        ),
    )


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as error:
        raise RuntimeError(
            f"{name} must be an integer, got {raw_value!r}."
        ) from error


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError as error:
        raise RuntimeError(
            f"{name} must be a number, got {raw_value!r}."
        ) from error