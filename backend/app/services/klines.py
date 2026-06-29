from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from backend.app.core.config import load_config
from backend.app.services.display_price import convert_usd_oz_to_cny_g

# Twelve Data time_series endpoint (USD/oz OHLC for XAU/USD).
_TD_ENDPOINT = "https://api.twelvedata.com/time_series"
_TD_SYMBOL = "XAU/USD"

# period -> (twelve_data interval, outputsize, cache_ttl_seconds, aggregate_every)
# aggregate_every>1 means: fetch `interval` bars then merge every N into one bar (for 5h).
_PERIODS: dict[str, dict[str, Any]] = {
    "1min": {"interval": "1min", "outputsize": 120, "ttl": 30, "agg": 1},
    "1h": {"interval": "1h", "outputsize": 120, "ttl": 300, "agg": 1},
    "5h": {"interval": "1h", "outputsize": 150, "ttl": 600, "agg": 5},
    "1day": {"interval": "1day", "outputsize": 30, "ttl": 3600, "agg": 1},
    "1month": {"interval": "1month", "outputsize": 12, "ttl": 21600, "agg": 1},
}

# Simple in-memory cache: period -> (expires_at_epoch, payload)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def supported_periods() -> list[dict[str, str]]:
    labels = {
        "1min": "分线",
        "1h": "时线",
        "5h": "5小时线",
        "1day": "日线",
        "1month": "月线",
    }
    return [{"key": k, "label": labels[k]} for k in _PERIODS]


def _twelve_data_key(config: dict[str, Any]) -> Optional[str]:
    # Reuse the same env var the twelve_data price source uses.
    import os

    sources = config.get("data_sources", {}).get("price", {})
    td = sources.get("twelve_data", {})
    env_name = td.get("api_key_env") or "TWELVE_DATA_KEY"
    raw = os.getenv(env_name) or ""
    # .env stores it as "apikey XXdef ...". Strip the scheme prefix to get bare key.
    return raw.replace("apikey", "").strip() or None


async def _fetch_time_series(interval: str, outputsize: int, apikey: str) -> list[dict[str, Any]]:
    params = {
        "symbol": _TD_SYMBOL,
        "interval": interval,
        "outputsize": str(outputsize),
        "apikey": apikey,
        "order": "ASC",
        "timezone": "Asia/Shanghai",
    }
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(_TD_ENDPOINT, params=params, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        payload = resp.json()
    if payload.get("status") == "error":
        raise RuntimeError(payload.get("message", "twelve_data error"))
    return list(payload.get("values", []))


def _parse_dt(s: str) -> datetime:
    # Twelve Data 已按 Asia/Shanghai 返回, 这里保持 naive 本地时间, 不贴时区,
    # 前端按字面显示, 避免二次换算导致时间错乱。
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


def _aggregate(bars: list[dict[str, Any]], every: int) -> list[dict[str, Any]]:
    """Merge every N consecutive bars into one (open=first.open, close=last.close,
    high=max, low=min). Used to synthesize 5h bars from 1h data."""
    if every <= 1:
        return bars
    out: list[dict[str, Any]] = []
    for i in range(0, len(bars), every):
        chunk = bars[i : i + every]
        if not chunk:
            continue
        out.append(
            {
                "datetime": chunk[0]["datetime"],
                "open": chunk[0]["open"],
                "high": max(float(b["high"]) for b in chunk),
                "low": min(float(b["low"]) for b in chunk),
                "close": chunk[-1]["close"],
            }
        )
    return out


def _convert_ohlc(bars: list[dict[str, Any]], display_config: dict[str, Any]) -> list[dict[str, Any]]:
    rate = float(display_config.get("usd_cny_rate", 6.808596))
    grams = float(display_config.get("troy_ounce_grams", 31.1034768))

    def to_cny(usd: float) -> float:
        return convert_usd_oz_to_cny_g(usd, usd_cny_rate=rate, troy_ounce_grams=grams)

    out = []
    for b in bars:
        try:
            o, h, l, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
        except (KeyError, ValueError, TypeError):
            continue
        dt = _parse_dt(str(b.get("datetime", "")))
        out.append(
            {
                "time": dt.isoformat(),
                "open_usd": round(o, 2),
                "high_usd": round(h, 2),
                "low_usd": round(l, 2),
                "close_usd": round(c, 2),
                "open": round(to_cny(o), 3),
                "high": round(to_cny(h), 3),
                "low": round(to_cny(l), 3),
                "close": round(to_cny(c), 3),
            }
        )
    return out


async def get_klines(period: str) -> dict[str, Any]:
    if period not in _PERIODS:
        raise ValueError(f"unsupported period: {period}")

    now = time.time()
    cached = _cache.get(period)
    if cached and cached[0] > now:
        return cached[1]

    config = load_config()
    apikey = _twelve_data_key(config)
    if not apikey:
        raise RuntimeError("TWELVE_DATA_KEY not configured")

    spec = _PERIODS[period]
    raw = await _fetch_time_series(spec["interval"], int(spec["outputsize"]), apikey)
    aggregated = _aggregate(raw, int(spec["agg"]))
    display_config = config.get("display", {})
    display_unit = f"{display_config.get('currency', 'CNY')}/{display_config.get('unit', 'g')}"
    candles = _convert_ohlc(aggregated, display_config)

    payload = {
        "period": period,
        "display_unit": display_unit,
        "count": len(candles),
        "candles": candles,
    }
    _cache[period] = (now + float(spec["ttl"]), payload)
    return payload
