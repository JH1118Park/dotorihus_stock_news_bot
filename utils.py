from __future__ import annotations


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def normalize_link(value: object) -> str:
    return clean_text(value)
