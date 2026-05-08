from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, tzinfo

import requests

from news import Article, article_published_at

logger = logging.getLogger("telegram")


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
        message = format_article_message(article)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
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
                logger.warning("Telegram rate limit hit while sending: %s", article.title)
                return False
            logger.error("Telegram API error %s while sending: %s", status_code, article.title)
            return False
        except requests.RequestException:
            logger.exception("Telegram request failed while sending: %s", article.title)
            return False

        logger.info("Sent article: %s", article.title)
        return True


def format_article_message(article: Article) -> str:
    source = article.source or "알 수 없음"
    published = format_article_published_time(article)
    return (
        f"[{article.keyword}] {article.title}\n\n"
        f"언론사: {source}\n"
        f"시간: {published}\n\n"
        f"{article.link}"
    )


def format_article_published_time(
    article: Article,
    *,
    local_tz: tzinfo | None = None,
) -> str:
    published_at = article_published_at(article)
    if published_at is None:
        return article.published or "알 수 없음"

    target_tz = local_tz or datetime.now().astimezone().tzinfo
    local_published_at = published_at.astimezone(target_tz)
    timezone_name = local_published_at.tzname() or "local"
    return f"{local_published_at:%Y-%m-%d %H:%M:%S} {timezone_name}"
