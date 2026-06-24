from __future__ import annotations

import os
from typing import Any

import httpx

from backend.app.core.logging import log_event


async def fetch_news_articles(config: dict[str, Any]) -> list[dict[str, Any]]:
    news_config = config.get("news", {})
    api_key_env = news_config.get("api_key_env", "NEWS_API_KEY")
    api_key = os.getenv(api_key_env)
    if not api_key:
        return list(news_config.get("demo_articles", []))

    params = {
        "q": news_config.get("query", "gold"),
        "language": news_config.get("language", "en"),
        "pageSize": news_config.get("page_size", 10),
        "apiKey": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(news_config["endpoint"], params=params)
            response.raise_for_status()
            payload = response.json()
        return list(payload.get("articles", []))
    except Exception as exc:
        log_event(30, "news_fetch_failed", error=str(exc))
        return list(news_config.get("demo_articles", []))
