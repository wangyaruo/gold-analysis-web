from __future__ import annotations

import asyncio
import json
import math
import os
import re
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from backend.app.core.config import get_by_path
from backend.app.core.logging import log_event
from backend.app.services.validation import PriceTick

SHANGHAI_TZ = timezone(timedelta(hours=8))


class MarketDataError(RuntimeError):
    pass


class PriceProvider:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._demo_counter = 0
        self._prices_by_source: dict[str, list[float]] = {}
        self._daily_ranges_by_source: dict[str, dict[str, float | str]] = {}

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
        include_observed_range = source_config.get("day_range_mode", "observed") != "reported"
        self._append_price(
            history_key,
            tick.price,
            tick.timestamp,
            day_low=tick.day_low,
            day_high=tick.day_high,
            include_observed_range=include_observed_range,
        )
        return tick

    def _append_price(
        self,
        source_key: str,
        price: float,
        timestamp: Optional[datetime] = None,
        *,
        day_low: Optional[float] = None,
        day_high: Optional[float] = None,
        include_observed_range: bool = True,
    ) -> None:
        prices = self._prices_by_source.setdefault(source_key, [])
        prices.append(price)
        self._prices_by_source[source_key] = prices[-240:]
        self._update_today_range(
            source_key,
            price,
            timestamp or datetime.now(timezone.utc),
            day_low,
            day_high,
            include_observed_range=include_observed_range,
        )

    def _update_today_range(
        self,
        source_key: str,
        price: float,
        timestamp: datetime,
        day_low: Optional[float],
        day_high: Optional[float],
        *,
        include_observed_range: bool = True,
    ) -> None:
        date_key = timestamp.astimezone(SHANGHAI_TZ).date().isoformat()
        candidates = [float(price)] if include_observed_range else []
        if day_low is not None:
            candidates.append(float(day_low))
        if day_high is not None:
            candidates.append(float(day_high))
        if not candidates:
            return

        current = self._daily_ranges_by_source.get(source_key)
        if not current or current.get("date") != date_key:
            self._daily_ranges_by_source[source_key] = {
                "date": date_key,
                "low": min(candidates),
                "high": max(candidates),
            }
            return

        current["low"] = min(float(current["low"]), *candidates)
        current["high"] = max(float(current["high"]), *candidates)

    def today_range(self, source_name: Optional[str] = None) -> Optional[dict[str, float | str]]:
        source_key = self._source_key(source_name)
        current = self._daily_ranges_by_source.get(source_key)
        if not current:
            return None
        return dict(current)

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
        verify_option = _httpx_verify_option(source_config)
        async with httpx.AsyncClient(timeout=timeout_seconds, verify=verify_option) as client:
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
            day_low = _optional_float(get_by_path(payload, "latest.low_price"))
            day_high = _optional_float(get_by_path(payload, "latest.high_price"))
            if (day_low is None or day_high is None) and source_config.get("day_range_endpoint"):
                fetched_low, fetched_high = await _fetch_day_range(client, source_config, headers)
                day_low = day_low if day_low is not None else fetched_low
                day_high = day_high if day_high is not None else fetched_high

        return PriceTick(
            symbol=source_config.get("symbol", "XAUUSD"),
            price=float(price),
            timestamp=timestamp,
            source=source_config.get("name", source_config.get("type", "http")),
            day_low=day_low,
            day_high=day_high,
        )


def _httpx_verify_option(source_config: dict[str, Any]) -> bool | ssl.SSLContext:
    if not source_config.get("legacy_tls"):
        return True
    context = ssl.create_default_context()
    context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return context


async def _fetch_day_range(
    client: httpx.AsyncClient,
    source_config: dict[str, Any],
    headers: dict[str, str],
) -> tuple[Optional[float], Optional[float]]:
    endpoint = source_config["day_range_endpoint"]
    method = str(source_config.get("day_range_method", "get")).upper()
    params = dict(source_config.get("day_range_params", {}))
    request_kwargs: dict[str, Any] = {"headers": headers}
    if method == "POST":
        request_kwargs["data"] = params
    else:
        request_kwargs["params"] = params

    try:
        response = await client.request(method, endpoint, **request_kwargs)
        response.raise_for_status()
        payload = _parse_response_payload(
            response.text,
            source_config.get("day_range_response_format", "json"),
        )
    except Exception as exc:  # noqa: BLE001
        log_event(
            30,
            "market_day_range_fetch_failed",
            source=source_config.get("name", source_config.get("type", "http")),
            error=str(exc),
        )
        return None, None

    return (
        _optional_float(get_by_path(payload, "latest.low_price")),
        _optional_float(get_by_path(payload, "latest.high_price")),
    )


def _parse_response_payload(text: str, response_format: str) -> dict[str, Any]:
    if response_format == "jsonp":
        match = re.match(r"^[\w$]+\((.*)\)\s*;?\s*$", text.strip(), re.DOTALL)
        if not match:
            raise MarketDataError("invalid JSONP market data response")
        return json.loads(match.group(1))
    if response_format == "icbc_chart":
        return _parse_icbc_chart_payload(text)
    if response_format == "icbc_accrual":
        return _parse_icbc_accrual_payload(text)
    if response_format == "jdjygold_latest":
        return _parse_jdjygold_latest_payload(text)
    if response_format == "jdjygold_today_prices":
        return _parse_jdjygold_today_prices_payload(text)
    if response_format == "jsvar":
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise MarketDataError("invalid jsvar market data response")
        return json.loads(match.group(0))
    return json.loads(text)


def _parse_icbc_chart_payload(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    chart_data = json.loads(payload.get("chartArrayStr") or "[]")
    if not chart_data:
        raise MarketDataError("invalid ICBC chart response: no price points")

    latest = chart_data[-1]
    if len(latest) < 2:
        raise MarketDataError("invalid ICBC chart response: malformed latest point")

    payload["latest"] = {
        "price": float(latest[1]),
        "timestamp": _icbc_point_timestamp(payload.get("datetime"), str(latest[0])),
    }
    return payload


def _parse_icbc_accrual_payload(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    quotes = payload.get("rf") or []
    if not quotes:
        raise MarketDataError("invalid ICBC accrual response: no quotes")

    latest = quotes[0]
    active_price = latest.get("ActivePrice")
    if active_price in (None, ""):
        raise MarketDataError("invalid ICBC accrual response: missing active price")

    payload["latest"] = {
        "price": float(active_price),
        "timestamp": _icbc_timestamp(payload.get("sysdate")),
        "product_name": latest.get("ProductName"),
        "high_price": _optional_float(latest.get("HighPrice")),
        "low_price": _optional_float(latest.get("LowPrice")),
        "regular_price": _optional_float(latest.get("RegPrice")),
        "sell_price": _optional_float(latest.get("SellPrice")),
    }
    return payload


def _parse_jdjygold_latest_payload(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    result_data = payload.get("resultData") or {}
    if not payload.get("success") or result_data.get("status") != "SUCCESS":
        raise MarketDataError("invalid JDJYGold response: request was not successful")

    latest = result_data.get("datas") or {}
    price = latest.get("price")
    timestamp = latest.get("time")
    if price in (None, ""):
        raise MarketDataError("invalid JDJYGold response: missing price")
    if timestamp in (None, ""):
        raise MarketDataError("invalid JDJYGold response: missing timestamp")

    payload["latest"] = {
        "price": float(price),
        "timestamp": int(timestamp),
        "product_sku": str(latest.get("productSku") or ""),
        "change": _optional_float(latest.get("upAndDownAmt")),
        "change_percent": latest.get("upAndDownRate"),
        "yesterday_price": _optional_float(latest.get("yesterdayPrice")),
    }
    return payload


def _parse_jdjygold_today_prices_payload(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    result_data = payload.get("resultData") or {}
    if not payload.get("success") or result_data.get("status") != "SUCCESS":
        raise MarketDataError("invalid JDJYGold today prices response: request was not successful")

    prices: list[float] = []
    candles: list[dict[str, float | str]] = []
    for item in result_data.get("datas") or []:
        value = item.get("value")
        raw_price = value[1] if isinstance(value, list) and len(value) > 1 else item.get("price")
        raw_time = value[0] if isinstance(value, list) and value else item.get("name") or item.get("time")
        parsed = _optional_float(raw_price)
        if parsed is not None:
            prices.append(parsed)
            candles.append(
                {
                    "time": str(raw_time).replace(" ", "T"),
                    "open": parsed,
                    "high": parsed,
                    "low": parsed,
                    "close": parsed,
                }
            )

    if not prices:
        raise MarketDataError("invalid JDJYGold today prices response: no price points")

    candles.sort(key=lambda item: str(item["time"]))
    payload["latest"] = {
        "low_price": min(prices),
        "high_price": max(prices),
        "candles": candles,
    }
    return payload


def _icbc_point_timestamp(datetime_value: Any, point_time: str) -> str:
    date_part = str(datetime_value or datetime.now(timezone.utc).date()).split(" ")[0]
    if re.match(r"^\d{6}$", point_time):
        time_part = f"{point_time[0:2]}:{point_time[2:4]}:{point_time[4:6]}"
    else:
        time_part = "00:00:00"
    return f"{date_part}T{time_part}+08:00"


def _icbc_timestamp(value: Any) -> str:
    return f"{str(value or datetime.now(timezone.utc).date()).split('.')[0]}+08:00".replace(" ", "T")


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1e12:  # 毫秒级 epoch -> 秒
            seconds /= 1000.0
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    raise MarketDataError(f"unsupported timestamp value: {value}")
