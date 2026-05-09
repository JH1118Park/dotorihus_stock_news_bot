from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import ConfigError, Settings, load_settings, mask_secret
from news import (
    Article,
    article_duplicate_key,
    article_published_date,
    fetch_articles,
    find_similar_duplicate_key,
    filter_articles_published_within,
)
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
    sent_state = store.load_state()
    new_sent_links: set[str] = set()
    candidate_article_keys_by_date: dict[str, set[str]] = {}
    new_sent_article_keys_by_date: dict[str, set[str]] = {}
    articles_to_send: list[Article] = []
    search_time = datetime.now().astimezone()
    digest_mode = is_nightly_digest_collection_time(settings, search_time)

    if flush_pending_digest_if_due(settings, sent_state, store, telegram, search_time):
        sent_state = store.load_state()

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
        allowed_articles = filter_articles_by_banned_keywords(
            recent_articles,
            settings.banned_keywords,
        )
        skipped_count = len(articles) - len(recent_articles)
        if skipped_count:
            logger.info(
                "Skipped %s article(s) not published within 1 hour of %s for keyword: %s",
                skipped_count,
                search_time.isoformat(timespec="seconds"),
                keyword,
            )
        banned_count = len(recent_articles) - len(allowed_articles)
        if banned_count:
            logger.info(
                "Skipped %s article(s) matching banned keywords for keyword: %s",
                banned_count,
                keyword,
            )

        seen_links = sent_state.links | _pending_article_links(sent_state) | new_sent_links
        fresh_articles: list[Article] = []
        duplicate_count = 0

        for article in allowed_articles:
            article_key = article_duplicate_key(article)
            article_date_key = _article_date_key(article, search_time)
            seen_article_keys = sent_state.keys_for_date(article_date_key) | (
                candidate_article_keys_by_date.get(article_date_key, set())
            )
            seen_article_keys |= _pending_article_keys_for_date(
                sent_state,
                article_date_key,
                search_time,
            )
            is_duplicate_link = article.link in seen_links
            similar_article_key = find_similar_duplicate_key(article_key, seen_article_keys)
            is_duplicate_title = similar_article_key is not None
            if is_duplicate_link or is_duplicate_title:
                duplicate_count += 1
                duplicate_reason = "link" if is_duplicate_link else "title"
                logger.info(
                    "Skipped duplicate article by %s for keyword '%s': title='%s', "
                    "source='%s', link='%s', duplicate_key='%s'",
                    duplicate_reason,
                    keyword,
                    article.title,
                    article.source or "unknown",
                    article.link,
                    similar_article_key or article_key,
                )
                continue

            fresh_articles.append(article)
            seen_links.add(article.link)
            candidate_article_keys_by_date.setdefault(article_date_key, set()).add(article_key)

        if duplicate_count:
            logger.info(
                "Skipped %s duplicate article(s) for keyword: %s",
                duplicate_count,
                keyword,
            )

        if is_first_run and not settings.send_existing_on_first_run:
            new_sent_links.update(article.link for article in fresh_articles)
            for article in fresh_articles:
                article_date_key = _article_date_key(article, search_time)
                new_sent_article_keys_by_date.setdefault(article_date_key, set()).add(
                    article_duplicate_key(article)
                )
            logger.info(
                "First run: stored %s existing article(s) without sending for keyword: %s",
                len(fresh_articles),
                keyword,
            )
            continue

        if digest_mode:
            sent_state.pending_articles.extend(_article_to_stored(article) for article in fresh_articles)
            for article in fresh_articles:
                article_date_key = _article_date_key(article, search_time)
                candidate_article_keys_by_date.setdefault(article_date_key, set()).add(
                    article_duplicate_key(article)
                )
            logger.info(
                "Nightly digest: queued %s article(s) without sending for keyword: %s",
                len(fresh_articles),
                keyword,
            )
            continue

        articles_to_send.extend(fresh_articles)

    if articles_to_send:
        if telegram.send_articles(articles_to_send):
            for article in articles_to_send:
                new_sent_links.add(article.link)
                article_date_key = _article_date_key(article, search_time)
                new_sent_article_keys_by_date.setdefault(article_date_key, set()).add(
                    article_duplicate_key(article)
                )
        else:
            logger.warning(
                "Skipped saving %s article(s) because Telegram batch send failed",
                len(articles_to_send),
            )

    if new_sent_links or new_sent_article_keys_by_date:
        sent_state.links.update(new_sent_links)
        for date_key, article_keys in new_sent_article_keys_by_date.items():
            sent_state.keys_for_date(date_key).update(article_keys)
        store.save_state(sent_state)
    elif digest_mode:
        store.save_state(sent_state)


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


def _article_date_key(article: Article, search_time: datetime) -> str:
    published_date = article_published_date(article, local_tz=search_time.tzinfo)
    if published_date is None:
        published_date = search_time.date()
    return published_date.isoformat()


def filter_articles_by_banned_keywords(
    articles: list[Article],
    banned_keywords: list[str],
) -> list[Article]:
    if not banned_keywords:
        return articles

    normalized_banned_keywords = [
        banned_keyword.casefold()
        for banned_keyword in banned_keywords
        if banned_keyword.strip()
    ]
    if not normalized_banned_keywords:
        return articles

    allowed_articles: list[Article] = []
    for article in articles:
        searchable_text = " ".join(
            value
            for value in (
                article.title,
                article.source or "",
                article.keyword,
            )
            if value
        ).casefold()
        matched_keyword = next(
            (
                banned_keyword
                for banned_keyword in normalized_banned_keywords
                if banned_keyword in searchable_text
            ),
            None,
        )
        if matched_keyword:
            logger.info(
                "Skipped article by banned keyword '%s': title='%s', source='%s', link='%s'",
                matched_keyword,
                article.title,
                article.source or "unknown",
                article.link,
            )
            continue
        allowed_articles.append(article)

    return allowed_articles


def is_nightly_digest_collection_time(settings: Settings, now: datetime) -> bool:
    if not settings.nightly_digest_enabled:
        return False

    start_hour = settings.nightly_digest_start_hour
    send_hour = settings.nightly_digest_send_hour
    current_hour = now.hour

    if start_hour == send_hour:
        return False
    if start_hour < send_hour:
        return start_hour <= current_hour < send_hour
    return current_hour >= start_hour or current_hour < send_hour


def flush_pending_digest_if_due(
    settings: Settings,
    sent_state,
    store: SentArticleStore,
    telegram: TelegramClient,
    now: datetime,
) -> bool:
    if not settings.nightly_digest_enabled:
        return False
    if is_nightly_digest_collection_time(settings, now):
        return False
    if now.hour < settings.nightly_digest_send_hour:
        return False
    if not sent_state.pending_articles:
        return False

    articles = [_stored_to_article(article) for article in sent_state.pending_articles]
    logger.info("Sending nightly digest with %s article(s)", len(articles))
    if not telegram.send_articles(articles):
        logger.warning(
            "Keeping %s nightly digest article(s) queued because Telegram send failed",
            len(articles),
        )
        return False

    for article in articles:
        sent_state.links.add(article.link)
        sent_state.keys_for_date(_article_date_key(article, now)).add(
            article_duplicate_key(article)
        )
    sent_state.pending_articles = []
    store.save_state(sent_state)
    return True


def _article_to_stored(article: Article) -> dict[str, str | None]:
    return {
        "title": article.title,
        "link": article.link,
        "published": article.published,
        "source": article.source,
        "keyword": article.keyword,
    }


def _stored_to_article(article: dict[str, str | None]) -> Article:
    return Article(
        title=str(article["title"]),
        link=str(article["link"]),
        published=article.get("published"),
        source=article.get("source"),
        keyword=str(article["keyword"]),
    )


def _pending_article_links(sent_state) -> set[str]:
    return {article["link"] for article in sent_state.pending_articles}


def _pending_article_keys_for_date(
    sent_state,
    date_key: str,
    search_time: datetime,
) -> set[str]:
    return {
        article_duplicate_key(_stored_to_article(article))
        for article in sent_state.pending_articles
        if _article_date_key(_stored_to_article(article), search_time) == date_key
    }


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
