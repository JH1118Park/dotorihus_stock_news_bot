import json

from storage import SentArticleStore


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
        "sent_links": ["https://example.com/a"]
    }
