from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, tzinfo
from html import escape
from typing import Iterable

import requests

from news import Article, article_published_at

logger = logging.getLogger("telegram")

TELEGRAM_MAX_MESSAGE_LENGTH = 3900
ARTICLE_SEPARATOR = "\n\n"


class TelegramError(RuntimeError):
    """Raised when Telegram does not accept a message."""


@dataclass(frozen=True)
class TelegramClient:
    bot_token: str
    chat_id: str
    timeout: int = 10

    @property
    def send_message_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_article(self, article: Article) -> bool:
        return self.send_articles([article])

    def send_articles(self, articles: Iterable[Article]) -> bool:
        article_list = list(articles)
        if not article_list:
            return True

        chunks = chunk_article_messages(article_list)
        if len(chunks) > 1:
            logger.info(
                "Split %s article(s) into %s Telegram messages to stay under length limit",
                len(article_list),
                len(chunks),
            )

        for chunk_index, chunk in enumerate(chunks, start=1):
            if not self._send_text(chunk.text, len(chunk.articles), chunk_index, len(chunks)):
                return False

        for article in article_list:
            logger.info(
                "Sent article: keyword='%s', title='%s', source='%s', published='%s', link='%s'",
                article.keyword,
                article.title,
                article.source or "unknown",
                format_article_published_time(article),
                article.link,
            )
        return True

    def _send_text(
        self,
        text: str,
        article_count: int,
        chunk_index: int,
        chunk_count: int,
    ) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                self.send_message_url,
                data=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response else "unknown"
            if status_code == 429:
                logger.warning(
                    "Telegram rate limit hit while sending %s article(s)",
                    article_count,
                )
                return False
            logger.error(
                "Telegram API error %s while sending %s article(s)",
                status_code,
                article_count,
            )
            return False
        except requests.RequestException:
            logger.exception(
                "Telegram request failed while sending %s article(s)",
                article_count,
            )
            return False

        if chunk_count == 1:
            logger.info("Sent %s article(s) in one Telegram message", article_count)
        else:
            logger.info(
                "Sent %s article(s) in Telegram message %s/%s",
                article_count,
                chunk_index,
                chunk_count,
            )
        return True


def format_article_message(article: Article) -> str:
    return format_articles_message([article])


def format_articles_message(articles: Iterable[Article]) -> str:
    return ARTICLE_SEPARATOR.join(format_article_link(article) for article in articles)


@dataclass(frozen=True)
class ArticleMessageChunk:
    text: str
    articles: list[Article]


def chunk_article_messages(
    articles: Iterable[Article],
    *,
    max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> list[ArticleMessageChunk]:
    chunks: list[ArticleMessageChunk] = []
    current_parts: list[str] = []
    current_articles: list[Article] = []

    for article in articles:
        article_text = format_article_link(article)
        candidate_parts = [*current_parts, article_text]
        candidate_text = ARTICLE_SEPARATOR.join(candidate_parts)

        if current_parts and len(candidate_text) > max_length:
            chunks.append(
                ArticleMessageChunk(
                    text=ARTICLE_SEPARATOR.join(current_parts),
                    articles=current_articles,
                )
            )
            current_parts = [article_text]
            current_articles = [article]
        else:
            current_parts = candidate_parts
            current_articles.append(article)

    if current_parts:
        chunks.append(
            ArticleMessageChunk(
                text=ARTICLE_SEPARATOR.join(current_parts),
                articles=current_articles,
            )
        )

    return chunks


def format_article_link(article: Article) -> str:
    published = format_article_published_time(article, include_timezone=False)
    title = escape(f"[{article.keyword}][{published}] {article.title}")
    link = escape(article.link, quote=True)

    return f'<a href="{link}">{title}</a>'


def format_article_published_time(
    article: Article,
    *,
    local_tz: tzinfo | None = None,
    include_timezone: bool = True,
) -> str:
    published_at = article_published_at(article)
    if published_at is None:
        return article.published or "알 수 없음"

    target_tz = local_tz or datetime.now().astimezone().tzinfo
    local_published_at = published_at.astimezone(target_tz)
    formatted = f"{local_published_at:%Y-%m-%d %H:%M:%S}"
    if not include_timezone:
        return formatted

    timezone_name = local_published_at.tzname() or "local"
    return f"{formatted} {timezone_name}"
