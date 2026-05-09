from datetime import timedelta, timezone

from news import Article
from telegram_client import (
    chunk_article_messages,
    format_article_message,
    format_article_published_time,
    format_articles_message,
)


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


def test_format_articles_message_combines_articles_in_one_message() -> None:
    articles = [
        Article(
            title="First article",
            link="https://example.com/a",
            published="Fri, 08 May 2026 03:33:20 GMT",
            source="Example",
            keyword="Hyundai",
        ),
        Article(
            title="Second article",
            link="https://example.com/b",
            published="Fri, 08 May 2026 03:34:20 GMT",
            source="Example",
            keyword="Samsung",
        ),
    ]

    message = format_articles_message(articles)

    assert message.count("<a href=") == 2
    assert message.count("\n\n") == 1
    assert "[Hyundai][2026-05-08" in message
    assert "[Samsung][2026-05-08" in message


def test_chunk_article_messages_splits_before_length_limit() -> None:
    articles = [
        Article(
            title=f"Article {index}",
            link=f"https://example.com/{index}",
            published="Fri, 08 May 2026 03:33:20 GMT",
            source="Example",
            keyword="Hyundai",
        )
        for index in range(3)
    ]

    chunks = chunk_article_messages(articles, max_length=120)

    assert len(chunks) > 1
    assert sum(len(chunk.articles) for chunk in chunks) == 3
    assert all(len(chunk.text) <= 120 for chunk in chunks)
