from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from main import is_nightly_digest_collection_time


def _settings(
    *,
    enabled: bool = True,
    start_hour: int = 22,
    send_hour: int = 7,
) -> Settings:
    return Settings(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        keywords=["robotics"],
        poll_interval_seconds=60,
        google_news_hl="ko",
        google_news_gl="KR",
        google_news_ceid="KR:ko",
        sent_store_path=Path("sent_articles.json"),
        send_existing_on_first_run=False,
        nightly_digest_enabled=enabled,
        nightly_digest_start_hour=start_hour,
        nightly_digest_send_hour=send_hour,
    )


def test_nightly_digest_collection_time_spans_midnight() -> None:
    settings = _settings()

    assert is_nightly_digest_collection_time(
        settings,
        datetime(2026, 5, 8, 22, 0, tzinfo=timezone.utc),
    )
    assert is_nightly_digest_collection_time(
        settings,
        datetime(2026, 5, 9, 6, 59, tzinfo=timezone.utc),
    )
    assert not is_nightly_digest_collection_time(
        settings,
        datetime(2026, 5, 9, 7, 0, tzinfo=timezone.utc),
    )


def test_nightly_digest_collection_time_can_be_disabled() -> None:
    assert not is_nightly_digest_collection_time(
        _settings(enabled=False),
        datetime(2026, 5, 8, 23, 0, tzinfo=timezone.utc),
    )
