"""Shared configuration helpers."""


def normalize_supabase_url(url: str) -> str:
    """Accept either the project URL or its REST API URL."""
    return url.rstrip("/").removesuffix("/rest/v1")
