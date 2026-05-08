import json

from storage import SentArticleState, SentArticleStore


def test_load_returns_empty_set_when_file_missing(tmp_path) -> None:
    store = SentArticleStore(tmp_path / "missing.json")

    assert store.load() == set()


def test_save_and_load_links(tmp_path) -> None:
    path = tmp_path / "sent_articles.json"
    store = SentArticleStore(path)

    store.save({"https://example.com/a", "https://example.com/b"})

    assert store.load() == {"https://example.com/a", "https://example.com/b"}


def test_load_handles_corrupted_json(tmp_path) -> None:
    path = tmp_path / "sent_articles.json"
    path.write_text("{not-json", encoding="utf-8")
    store = SentArticleStore(path)

    assert store.load() == set()


def test_save_writes_expected_shape(tmp_path) -> None:
    path = tmp_path / "sent_articles.json"
    store = SentArticleStore(path)

    store.save({"https://example.com/a"})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "sent_article_keys_by_date": {},
        "sent_links": ["https://example.com/a"],
    }


def test_save_and_load_state_with_article_keys_by_date(tmp_path) -> None:
    path = tmp_path / "sent_articles.json"
    store = SentArticleStore(path)

    store.save_state(
        SentArticleState(
            links={"https://example.com/a"},
            keys_by_date={"2026-05-08": {"normalized-title"}},
        )
    )
    state = store.load_state()

    assert state.links == {"https://example.com/a"}
    assert state.keys_for_date("2026-05-08") == {"normalized-title"}
    assert state.keys_for_date("2026-05-09") == set()


def test_load_ignores_legacy_global_article_keys(tmp_path) -> None:
    path = tmp_path / "sent_articles.json"
    path.write_text(
        json.dumps(
            {
                "sent_links": ["https://example.com/a"],
                "sent_article_keys": ["old-global-title"],
            }
        ),
        encoding="utf-8",
    )
    store = SentArticleStore(path)

    state = store.load_state()

    assert state.links == {"https://example.com/a"}
    assert state.keys_by_date == {}
