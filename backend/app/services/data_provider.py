from __future__ import annotations

import asyncio
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from backend.app.core.config import get_by_path
from backend.app.core.logging import log_event
from backend.app.services.validation import PriceTick


class MarketDataError(RuntimeError):
    pass


class PriceProvider:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._demo_counter = 0
        self._prices_by_source: dict[str, list[float]] = {}

    @property
    def prices(self) -> list[float]:
        return self.price_history()

    def price_history(self, source_name: Optional[str] = None) -> list[float]:
        return list(self._prices_by_source.get(self._source_key(source_name), []))

    async def latest_tick(self, source_name: Optional[str] = None) -> PriceTick:
        history_key = self._source_key(source_name)
        source_config = self.source_config(source_name)
        try:
            tick = await self._fetch_with_retry(source_config)
        except Exception:
            fallback_config = self.fallback_source_config()
            if not fallback_config:
                raise
            tick = await self._fetch_with_retry(fallback_config)
        self._append_price(history_key, tick.price)
        return tick

    def _append_price(self, source_key: str, price: float) -> None:
        prices = self._prices_by_source.setdefault(source_key, [])
        prices.append(price)
        self._prices_by_source[source_key] = prices[-240:]

    async def _fetch_with_retry(self, source_config: dict[str, Any]) -> PriceTick:
        retry_config = self.config.get("retry", {})
        max_attempts = int(retry_config.get("max_attempts", 3))
        base_delay = float(retry_config.get("base_delay_seconds", 0.2))
        multiplier = float(retry_config.get("multiplier", 2))
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                if source_config.get("type") == "http":
                    return await self._fetch_http(source_config)
                return self._fetch_demo(source_config)
            except Exception as exc:
                last_error = exc
                log_event(
                    30,
                    "market_data_fetch_failed",
                    source=source_config.get("type"),
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < max_attempts:
                    await asyncio.sleep(base_delay * (multiplier ** (attempt - 1)))

        raise MarketDataError(f"failed to fetch market data after {max_attempts} attempts: {last_error}")

    def source_config(self, source_name: Optional[str] = None) -> dict[str, Any]:
        sources = self.config.get("data_sources", {})
        selected = source_name or sources.get("active", "demo")
        price_sources = sources.get("price", {})
        if selected not in price_sources:
            raise MarketDataError(f"unknown price source: {selected}")
        config = dict(price_sources[selected])
        config["_key"] = selected
        return config

    def _active_source_config(self) -> dict[str, Any]:
        return self.source_config()

    def _source_key(self, source_name: Optional[str] = None) -> str:
        return self.source_config(source_name).get("_key", source_name or "demo")

    def fallback_source_config(self) -> Optional[dict[str, Any]]:
        sources = self.config.get("data_sources", {})
        fallback = sources.get("fallback")
        if not fallback:
            return None
        price_sources = sources.get("price", {})
        if fallback not in price_sources:
            raise MarketDataError(f"unknown fallback price source: {fallback}")
        config = dict(price_sources[fallback])
        config["_key"] = fallback
        return config

    def _fetch_demo(self, source_config: dict[str, Any]) -> PriceTick:
        base_price = float(source_config.get("base_price", 4018.77))
        volatility = float(source_config.get("volatility", 8.0))
        self._demo_counter += 1
        drift = math.sin(self._demo_counter / 3) * volatility
        micro_move = math.cos(self._demo_counter / 5) * (volatility / 2)
        price = round(base_price + drift + micro_move + (self._demo_counter * 0.18), 2)
        return PriceTick(
            symbol=source_config.get("symbol", "XAUUSD"),
            price=price,
            timestamp=datetime.now(timezone.utc),
            source=source_config.get("name", "demo"),
        )

    async def _fetch_http(self, source_config: dict[str, Any]) -> PriceTick:
        endpoint = source_config["endpoint"]
        api_key_env = source_config.get("api_key_env") or ""
        api_key = os.getenv(api_key_env) if api_key_env else None
        headers = dict(source_config.get("headers", {}))
        if api_key:
            headers[source_config.get("auth_header", "Authorization")] = api_key

        timeout_seconds = float(source_config.get("timeout_seconds", 5))
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            payload = _parse_response_payload(response.text, source_config.get("response_format", "json"))

        price_path = source_config.get("json_paths", {}).get("price", "price")
        timestamp_path = source_config.get("json_paths", {}).get("timestamp", "timestamp")
        price = get_by_path(payload, price_path)
        timestamp_value = get_by_path(payload, timestamp_path)
        if price is None:
            raise MarketDataError(f"price path not found: {price_path}")

        timestamp = _parse_timestamp(timestamp_value)
        return PriceTick(
            symbol=source_config.get("symbol", "XAUUSD"),
            price=float(price),
            timestamp=timestamp,
            source=source_config.get("name", source_config.get("type", "http")),
        )


def _parse_response_payload(text: str, response_format: str) -> dict[str, Any]:
    if response_format == "jsonp":
        match = re.match(r"^[\w$]+\((.*)\)\s*;?\s*$", text.strip(), re.DOTALL)
        if not match:
            raise MarketDataError("invalid JSONP market data response")
        return json.loads(match.group(1))
    return json.loads(text)


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    raise MarketDataError(f"unsupported timestamp value: {value}")
