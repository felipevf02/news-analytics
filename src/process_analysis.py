"""Persist analyses for articles not yet processed by the current analyzer."""

from datetime import datetime, timezone

from supabase import Client

from src.analyze import analyze_text


def analyze_unprocessed(client: Client) -> int:
    articles = (
        client.table("articles")
        .select("id,title,description,content_excerpt")
        .order("published_at", desc=True)
        .limit(5000)
        .execute()
        .data
        or []
    )
    completed = (
        client.table("article_analyses")
        .select("article_id")
        .execute()
        .data
        or []
    )
    completed_ids = {row["article_id"] for row in completed}

    rows = []
    analyzed_at = datetime.now(timezone.utc).isoformat()
    for article in articles:
        if article["id"] in completed_ids:
            continue
        metrics = analyze_text(
            article.get("title"),
            article.get("description"),
            article.get("content_excerpt"),
        )
        rows.append(
            {
                "article_id": article["id"],
                **metrics,
                "analyzed_at": analyzed_at,
            }
        )

    if rows:
        client.table("article_analyses").upsert(
            rows, on_conflict="article_id"
        ).execute()
    return len(rows)
