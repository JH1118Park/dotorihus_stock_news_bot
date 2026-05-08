from datetime import timedelta, timezone

from news import Article
from telegram_client import format_article_message, format_article_published_time


def test_format_article_published_time_converts_gmt_to_kst() -> None:
    article = Article(
        title="Hyundai article",
        link="https://example.com/a",
        published="Fri, 08 May 2026 03:33:20 GMT",
        source="Example",
        keyword="Hyundai",
    )

    assert (
        format_article_published_time(article, local_tz=timezone(timedelta(hours=9), "KST"))
        == "2026-05-08 12:33:20 KST"
    )


def test_format_article_message_omits_news_prefix_and_uses_local_time() -> None:
    article = Article(
        title="Hyundai article",
        link="https://example.com/a",
        published="Fri, 08 May 2026 03:33:20 GMT",
        source="Example",
        keyword="Hyundai",
    )

    message = format_article_message(article)

    assert message.startswith("[Hyundai] Hyundai article")
    assert not message.startswith("뉴스 ")
    assert "언론사: Example" in message
    assert "Fri, 08 May 2026 03:33:20 GMT" not in message
