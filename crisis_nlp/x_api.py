from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import requests


class XApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class XTweety:
    tweet_id: str
    text: str
    created_at: Optional[datetime]
    author_id: Optional[str]


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # ex: 2026-03-13T10:00:00.000Z
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_recent_tweets(
    *,
    query: str,
    max_results: int = 50,
    bearer_token: Optional[str] = None,
    lang: Optional[str] = "en",
) -> List[XTweety]:
    """
    Fetch recent tweets via X API v2 recent search.

    Requires an X Developer account + Bearer Token.
    """
    token = bearer_token or os.environ.get("X_BEARER_TOKEN", "")
    if not token:
        raise XApiError("Missing X Bearer Token. Set env var X_BEARER_TOKEN.")

    q = query.strip()
    if not q:
        raise XApiError("Query is empty.")

    if lang:
        # X query syntax supports `lang:en`
        q = f"({q}) lang:{lang}"

    url = "https://api.x.com/2/tweets/search/recent"
    params = {
        "query": q,
        "max_results": max(10, min(int(max_results), 100)),
        "tweet.fields": "created_at,lang,author_id",
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:2000]}
        raise XApiError(f"X API error {resp.status_code}: {body}")

    data = resp.json()
    rows = data.get("data") or []
    out: List[XTweety] = []
    for r in rows:
        out.append(
            XTweety(
                tweet_id=str(r.get("id", "")),
                text=str(r.get("text", "")),
                created_at=_parse_dt(r.get("created_at")),
                author_id=(str(r.get("author_id")) if r.get("author_id") is not None else None),
            )
        )
    return out

