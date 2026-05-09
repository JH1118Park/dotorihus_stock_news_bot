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


def test_format_article_message_links_title_with_time_and_omits_time_line() -> None:
    article = Article(
        title="Hyundai & Atlas article",
        link="https://example.com/a?x=1&y=2",
        published="Fri, 08 May 2026 03:33:20 GMT",
        source="Example <News>",
        keyword="Hyundai",
    )

    message = format_article_message(article)

    assert message.startswith(
        '<a href="https://example.com/a?x=1&amp;y=2">[Hyundai]['
    )
    assert "Hyundai &amp; Atlas article</a>" in message
    assert "언론사:" not in message
    assert "\n시간:" not in message
    assert "\n\n" not in message
    assert "Fri, 08 May 2026 03:33:20 GMT" not in message
    assert "\n\nhttps://example.com/a" not in message
