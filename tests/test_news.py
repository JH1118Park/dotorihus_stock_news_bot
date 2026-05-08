from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from news import (
    Article,
    article_duplicate_key,
    article_keys_are_similar,
    article_published_date,
    build_google_news_rss_url,
    entry_to_article,
    filter_articles_by_published_date,
    filter_articles_published_within,
    find_similar_duplicate_key,
)


def test_build_google_news_rss_url_encodes_quoted_keyword() -> None:
    url = build_google_news_rss_url("Doosan Robotics")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "news.google.com"
    assert query["q"] == ['"Doosan Robotics"']
    assert query["hl"] == ["ko"]
    assert query["gl"] == ["KR"]
    assert query["ceid"] == ["KR:ko"]


def test_entry_to_article_converts_feed_entry() -> None:
    entry = {
        "title": "  Test article  ",
        "link": " https://news.google.com/rss/articles/example ",
        "published": "Fri, 08 May 2026 00:21:22 GMT",
        "source": {"title": "Test News"},
    }

    article = entry_to_article(entry, "Samsung")

    assert article == Article(
        title="Test article",
        link="https://news.google.com/rss/articles/example",
        published="Fri, 08 May 2026 00:21:22 GMT",
        source="Test News",
        keyword="Samsung",
    )


def test_article_published_date_uses_local_timezone() -> None:
    article = Article(
        title="Overnight article",
        link="https://example.com/a",
        published="Thu, 07 May 2026 16:00:00 GMT",
        source="Example",
        keyword="robotics",
    )

    assert article_published_date(
        article,
        local_tz=timezone(timedelta(hours=9)),
    ) == date(2026, 5, 8)


def test_filter_articles_by_published_date_keeps_only_target_date() -> None:
    articles = [
        Article(
            title="Today",
            link="https://example.com/today",
            published="Fri, 08 May 2026 01:00:00 GMT",
            source="Example",
            keyword="robotics",
        ),
        Article(
            title="Yesterday",
            link="https://example.com/yesterday",
            published="Thu, 07 May 2026 01:00:00 GMT",
            source="Example",
            keyword="robotics",
        ),
        Article(
            title="No date",
            link="https://example.com/no-date",
            published=None,
            source="Example",
            keyword="robotics",
        ),
    ]

    assert filter_articles_by_published_date(
        articles,
        date(2026, 5, 8),
        local_tz=timezone.utc,
    ) == [articles[0]]


def test_filter_articles_published_within_keeps_only_recent_articles() -> None:
    now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    articles = [
        Article(
            title="Recent",
            link="https://example.com/recent",
            published="Fri, 08 May 2026 11:30:00 GMT",
            source="Example",
            keyword="robotics",
        ),
        Article(
            title="Boundary",
            link="https://example.com/boundary",
            published="Fri, 08 May 2026 11:00:00 GMT",
            source="Example",
            keyword="robotics",
        ),
        Article(
            title="Old",
            link="https://example.com/old",
            published="Fri, 08 May 2026 10:59:59 GMT",
            source="Example",
            keyword="robotics",
        ),
        Article(
            title="Future",
            link="https://example.com/future",
            published="Fri, 08 May 2026 12:00:01 GMT",
            source="Example",
            keyword="robotics",
        ),
        Article(
            title="No date",
            link="https://example.com/no-date",
            published=None,
            source="Example",
            keyword="robotics",
        ),
    ]

    assert filter_articles_published_within(
        articles,
        now=now,
        window=timedelta(hours=1),
    ) == [articles[0], articles[1]]


def test_article_duplicate_key_ignores_trailing_source_and_spacing() -> None:
    nate_article = Article(
        title="알테오젠, 1분기 매출 716억·영업익 393억 - 네이트",
        link="https://example.com/nate",
        published="Fri, 08 May 2026 04:17:00 GMT",
        source="네이트",
        keyword="알테오젠",
    )
    press_article = Article(
        title="알테오젠, 1분기 매출 716억·영업익 393억 - PRESS9",
        link="https://example.com/press9",
        published="Fri, 08 May 2026 04:24:32 GMT",
        source="PRESS9",
        keyword="알테오젠",
    )

    assert article_duplicate_key(nate_article) == article_duplicate_key(press_article)


def test_article_keys_are_similar_for_same_earnings_story() -> None:
    first = article_duplicate_key(
        Article(
            title="알테오젠, 1분기 매출 716억·영업이익 393억...기술수출 성과 반영 - PRESS9",
            link="https://example.com/press9",
            published="Fri, 08 May 2026 04:17:00 GMT",
            source="PRESS9",
            keyword="알테오젠",
        )
    )
    second = article_duplicate_key(
        Article(
            title="알테오젠, 1분기 매출 716억·영업이익 393억원 ‘동반 감소’ - 코메디닷컴",
            link="https://example.com/kormedi",
            published="Fri, 08 May 2026 05:14:00 GMT",
            source="코메디닷컴",
            keyword="알테오젠",
        )
    )

    assert article_keys_are_similar(first, second)
    assert find_similar_duplicate_key(second, {first}) == first
