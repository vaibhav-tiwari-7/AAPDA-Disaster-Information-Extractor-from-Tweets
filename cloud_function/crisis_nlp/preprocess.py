from __future__ import annotations

import re
from typing import Iterable, List


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@\w+")
_HASHTAG_RE = re.compile(r"#(\w+)")
_NON_WORD_RE = re.compile(r"[^\w\s]")
_MULTISPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    t = text.lower()
    t = _URL_RE.sub(" ", t)
    t = _MENTION_RE.sub(" ", t)
    t = _HASHTAG_RE.sub(r"\1", t)
    t = _NON_WORD_RE.sub(" ", t)
    t = _MULTISPACE_RE.sub(" ", t).strip()
    return t


def normalize_many(texts: Iterable[str]) -> List[str]:
    return [normalize_text(t) for t in texts]

