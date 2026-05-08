from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("storage")


class SentArticleState:
    def __init__(
        self,
        links: Iterable[str] | None = None,
        keys_by_date: dict[str, Iterable[str]] | None = None,
    ) -> None:
        self.links = set(links or [])
        self.keys_by_date = {
            date_key: set(keys)
            for date_key, keys in (keys_by_date or {}).items()
            if date_key
        }

    def keys_for_date(self, date_key: str) -> set[str]:
        return self.keys_by_date.setdefault(date_key, set())


class SentArticleStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> set[str]:
        return self.load_state().links

    def load_state(self) -> SentArticleState:
        if not self.path.exists():
            return SentArticleState()

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logger.warning("Sent store is corrupted. Starting with an empty store: %s", self.path)
            return SentArticleState()
        except OSError:
            logger.exception("Failed to read sent store: %s", self.path)
            return SentArticleState()

        sent_links = data.get("sent_links", [])
        sent_article_keys_by_date = data.get("sent_article_keys_by_date", {})
        if not isinstance(sent_links, list):
            logger.warning("Invalid sent store format. Starting with an empty store: %s", self.path)
            return SentArticleState()
        if not isinstance(sent_article_keys_by_date, dict):
            sent_article_keys_by_date = {}

        return SentArticleState(
            links={link for link in sent_links if isinstance(link, str) and link},
            keys_by_date={
                str(date_key): {
                    key for key in keys if isinstance(key, str) and key
                }
                for date_key, keys in sent_article_keys_by_date.items()
                if isinstance(keys, list)
            },
        )

    def save(self, sent_links: Iterable[str]) -> None:
        self.save_state(SentArticleState(links=sent_links))

    def save_state(self, state: SentArticleState) -> None:
        unique_links = sorted(state.links)
        unique_keys_by_date = {
            date_key: sorted(keys)
            for date_key, keys in sorted(state.keys_by_date.items())
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(
                    {
                        "sent_links": unique_links,
                        "sent_article_keys_by_date": unique_keys_by_date,
                    },
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            logger.exception("Failed to write sent store: %s", self.path)
            return

        logger.info(
            "Saved %s sent links and %s sent article keys",
            len(unique_links),
            sum(len(keys) for keys in unique_keys_by_date.values()),
        )

    def add(self, links: Iterable[str]) -> set[str]:
        state = self.load_state()
        before_count = len(state.links)
        state.links.update(link for link in links if link)
        self.save_state(state)
        logger.info("Saved %s new sent link(s)", len(state.links) - before_count)
        return state.links
