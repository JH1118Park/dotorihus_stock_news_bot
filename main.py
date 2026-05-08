from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import ConfigError, Settings, load_settings, mask_secret
from news import Article, fetch_articles, filter_articles_published_within
from storage import SentArticleStore
from telegram_client import TelegramClient


LOG_DIR = Path("docs") / "logs"
ARTICLE_LOOKBACK_WINDOW = timedelta(hours=1)


def configure_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"news_bot_{started_at}.log"
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler],
        force=True,
    )
    return log_path


logger = logging.getLogger("main")


def run_once(
    settings: Settings,
    store: SentArticleStore,
    telegram: TelegramClient,
    *,
    is_first_run: bool,
) -> None:
    sent_links = store.load()
    new_sent_links: set[str] = set()
    search_time = datetime.now().astimezone()

    for keyword in settings.keywords:
        articles = fetch_articles(
            keyword,
            hl=settings.google_news_hl,
            gl=settings.google_news_gl,
            ceid=settings.google_news_ceid,
        )
        recent_articles = filter_articles_published_within(
            articles,
            now=search_time,
            window=ARTICLE_LOOKBACK_WINDOW,
        )
        skipped_count = len(articles) - len(recent_articles)
        if skipped_count:
            logger.info(
                "Skipped %s article(s) not published within 1 hour of %s for keyword: %s",
                skipped_count,
                search_time.isoformat(timespec="seconds"),
                keyword,
            )

        seen_links = sent_links | new_sent_links
        fresh_articles = [
            article for article in recent_articles if article.link not in seen_links
        ]

        if is_first_run and not settings.send_existing_on_first_run:
            new_sent_links.update(article.link for article in fresh_articles)
            logger.info(
                "First run: stored %s existing article(s) without sending for keyword: %s",
                len(fresh_articles),
                keyword,
            )
            continue

        for article in fresh_articles:
            if _send_and_record(article, telegram):
                new_sent_links.add(article.link)

    if new_sent_links:
        sent_links.update(new_sent_links)
        store.save(sent_links)


def run_forever(settings: Settings) -> None:
    logger.info("Starting bot with token %s", mask_secret(settings.telegram_bot_token))
    store = SentArticleStore(settings.sent_store_path)
    telegram = TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )

    is_first_run = not settings.sent_store_path.exists()

    while True:
        try:
            run_once(settings, store, telegram, is_first_run=is_first_run)
            is_first_run = False
        except Exception:
            logger.exception("Unexpected error in main loop")

        time.sleep(settings.poll_interval_seconds)


def _send_and_record(article: Article, telegram: TelegramClient) -> bool:
    return telegram.send_article(article)


def main() -> int:
    log_path = configure_logging()
    logger.info("Writing runtime log to %s", log_path)
    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.error("%s", exc)
        return 1

    run_forever(settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
