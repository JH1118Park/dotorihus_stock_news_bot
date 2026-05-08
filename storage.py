from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("storage")


class SentArticleStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logger.warning("Sent store is corrupted. Starting with an empty store: %s", self.path)
            return set()
        except OSError:
            logger.exception("Failed to read sent store: %s", self.path)
            return set()

        sent_links = data.get("sent_links", [])
        if not isinstance(sent_links, list):
            logger.warning("Invalid sent store format. Starting with an empty store: %s", self.path)
            return set()

        return {link for link in sent_links if isinstance(link, str) and link}

    def save(self, sent_links: Iterable[str]) -> None:
        unique_links = sorted(set(sent_links))
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(
                    {"sent_links": unique_links},
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            logger.exception("Failed to write sent store: %s", self.path)
            return

        logger.info("Saved %s sent links", len(unique_links))

    def add(self, links: Iterable[str]) -> set[str]:
        sent_links = self.load()
        before_count = len(sent_links)
        sent_links.update(link for link in links if link)
        self.save(sent_links)
        logger.info("Saved %s new sent link(s)", len(sent_links) - before_count)
        return sent_links
