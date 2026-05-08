from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests

from utils import clean_text, normalize_link

logger = logging.getLogger("news")

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
RSS_TIMEOUT_SECONDS = 10
TRAILING_SOURCE_PATTERN = re.compile(r"\s[-–—]\s[^-–—]{1,40}$")
ARTICLE_KEY_PATTERN = re.compile(r"[^0-9a-z가-힣]+")


@dataclass(frozen=True)
class Article:
    title: str
    link: str
    published: str | None
    source: str | None
    keyword: str


def build_google_news_rss_url(
    keyword: str,
    *,
    hl: str = "ko",
    gl: str = "KR",
    ceid: str = "KR:ko",
) -> str:
    query = quote_plus(f'"{keyword}"')
    return f"{GOOGLE_NEWS_RSS_URL}?q={query}&hl={hl}&gl={gl}&ceid={ceid}"


def fetch_articles(
    keyword: str,
    *,
    hl: str = "ko",
    gl: str = "KR",
    ceid: str = "KR:ko",
) -> list[Article]:
    url = build_google_news_rss_url(keyword, hl=hl, gl=gl, ceid=ceid)

    try:
        response = requests.get(url, timeout=RSS_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("RSS request failed for keyword: %s", keyword)
        return []

    try:
        feed = feedparser.parse(response.content)
    except Exception:
        logger.exception("Failed to parse RSS for keyword: %s", keyword)
        return []

    if getattr(feed, "bozo", False):
        logger.warning("RSS parse warning for keyword %s: %s", keyword, feed.bozo_exception)

    entries = getattr(feed, "entries", [])
    if not entries:
        logger.info("No articles found for keyword: %s", keyword)
        return []

    articles = [article for entry in entries if (article := entry_to_article(entry, keyword))]
    logger.info("Fetched %s articles for keyword: %s", len(articles), keyword)
    return articles


def entry_to_article(entry: Any, keyword: str) -> Article | None:
    title = clean_text(_get_value(entry, "title"))
    link = normalize_link(_get_value(entry, "link"))

    if not title or not link:
        logger.debug("Skipping RSS entry without title or link for keyword: %s", keyword)
        return None

    published = clean_text(
        _get_value(entry, "published")
        or _get_value(entry, "updated")
        or _get_value(entry, "created")
    )
    source = _extract_source(entry)

    return Article(
        title=title,
        link=link,
        published=published or None,
        source=source,
        keyword=keyword,
    )


def filter_articles_by_published_date(
    articles: list[Article],
    target_date: date,
    *,
    local_tz: tzinfo | None = None,
) -> list[Article]:
    return [
        article
        for article in articles
        if article_published_date(article, local_tz=local_tz) == target_date
    ]


def filter_articles_published_within(
    articles: list[Article],
    *,
    now: datetime,
    window: timedelta,
) -> list[Article]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    oldest_allowed = now - window
    return [
        article
        for article in articles
        if (
            published_at := article_published_at(article)
        )
        and oldest_allowed <= published_at.astimezone(now.tzinfo) <= now
    ]


def article_duplicate_key(article: Article) -> str:
    title = TRAILING_SOURCE_PATTERN.sub("", article.title)
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return ARTICLE_KEY_PATTERN.sub("", normalized)


def article_published_date(
    article: Article,
    *,
    local_tz: tzinfo | None = None,
) -> date | None:
    published_at = article_published_at(article)
    if published_at is None:
        return None

    target_tz = local_tz or datetime.now().astimezone().tzinfo
    return published_at.astimezone(target_tz).date()


def article_published_at(article: Article) -> datetime | None:
    if not article.published:
        return None

    try:
        published_at = parsedate_to_datetime(article.published)
    except (TypeError, ValueError):
        logger.warning(
            "Could not parse published date for article, skipping date match: %s",
            article.title,
        )
        return None

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    return published_at


def _extract_source(entry: Any) -> str | None:
    source = _get_value(entry, "source")
    if isinstance(source, dict):
        return clean_text(source.get("title")) or None

    source_detail = _get_value(entry, "source_detail")
    if isinstance(source_detail, dict):
        return clean_text(source_detail.get("title")) or None

    return None


def _get_value(entry: Any, key: str) -> Any:
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key, None)
