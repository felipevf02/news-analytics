"""Fetch Brazilian Portuguese AI news and store articles in Supabase."""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from supabase import Client, create_client

from src.config import normalize_supabase_url

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"
SEARCH_QUERY = '"inteligência artificial" OR "IA generativa" OR "aprendizado de máquina"'


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_articles(api_key: str) -> list[dict]:
    # The free GNews plan has a delay; a 36-hour lookback gives the daily job
    # room to catch delayed items. Database upsert makes overlapping runs safe.
    since = datetime.now(timezone.utc) - timedelta(hours=36)
    since_iso = since.isoformat(timespec="seconds").replace("+00:00", "Z")
    response = requests.get(
        GNEWS_SEARCH_URL,
        params={
            "q": SEARCH_QUERY,
            "lang": "pt",
            "country": "br",
            "max": 10,
            "from": since_iso,
        },
        headers={"X-Api-Key": api_key},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"GNews returned HTTP {response.status_code}: {response.text}"
        )
    return response.json().get("articles", [])


def store_articles(client: Client, articles: list[dict]) -> int:
    rows = []
    for item in articles:
        url = item.get("url")
        if not url:
            continue
        source = item.get("source") or {}
        rows.append(
            {
                "url": url,
                "title": item.get("title") or "",
                "description": item.get("description"),
                "content_excerpt": item.get("content"),
                "image_url": item.get("image"),
                "source_name": source.get("name"),
                "source_url": source.get("url"),
                "published_at": item.get("publishedAt"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": item,
            }
        )
    if not rows:
        return 0
    result = client.table("articles").upsert(rows, on_conflict="url").execute()
    return len(result.data or [])


def main() -> int:
    load_dotenv()
    api_key = required_env("GNEWS_API_KEY")
    client = create_client(
        normalize_supabase_url(required_env("SUPABASE_URL")),
        required_env("SUPABASE_SECRET_KEY"),
    )
    articles = get_articles(api_key)
    saved = store_articles(client, articles)
    print(f"Received {len(articles)} articles; upserted {saved}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
