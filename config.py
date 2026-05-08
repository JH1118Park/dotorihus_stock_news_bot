from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("config")

MIN_POLL_INTERVAL_SECONDS = 60


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    keywords: list[str]
    poll_interval_seconds: int
    google_news_hl: str
    google_news_gl: str
    google_news_ceid: str
    sent_store_path: Path
    send_existing_on_first_run: bool


def load_settings(env_path: str | Path = ".env") -> Settings:
    env_file = Path(env_path)
    load_dotenv(env_file)

    token = _required_env("TELEGRAM_BOT_TOKEN")
    chat_id = _required_env("TELEGRAM_CHAT_ID")
    keywords = _parse_keywords(os.getenv("NEWS_KEYWORDS", ""))
    poll_interval = _parse_poll_interval(os.getenv("POLL_INTERVAL_SECONDS", "60"))

    settings = Settings(
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        keywords=keywords,
        poll_interval_seconds=poll_interval,
        google_news_hl=os.getenv("GOOGLE_NEWS_HL", "ko").strip() or "ko",
        google_news_gl=os.getenv("GOOGLE_NEWS_GL", "KR").strip() or "KR",
        google_news_ceid=os.getenv("GOOGLE_NEWS_CEID", "KR:ko").strip() or "KR:ko",
        sent_store_path=Path(os.getenv("SENT_STORE_PATH", "sent_articles.json")),
        send_existing_on_first_run=_parse_bool(
            os.getenv("SEND_EXISTING_ON_FIRST_RUN", "false")
        ),
    )

    logger.info("Loaded %s keywords", len(settings.keywords))
    return settings


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} is required. Create a .env file using .env.example as a guide."
        )
    return value


def _parse_keywords(raw: str) -> list[str]:
    keywords = [keyword.strip() for keyword in raw.split(",") if keyword.strip()]
    if not keywords:
        raise ConfigError("NEWS_KEYWORDS must contain at least one keyword.")
    return keywords


def _parse_poll_interval(raw: str) -> int:
    try:
        interval = int(raw)
    except ValueError as exc:
        raise ConfigError("POLL_INTERVAL_SECONDS must be an integer.") from exc

    if interval < MIN_POLL_INTERVAL_SECONDS:
        logger.warning(
            "POLL_INTERVAL_SECONDS=%s is too short. Using minimum %s seconds.",
            interval,
            MIN_POLL_INTERVAL_SECONDS,
        )
        return MIN_POLL_INTERVAL_SECONDS
    return interval


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def mask_secret(value: str, visible: int = 4) -> str:
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * (len(value) - visible)}"
