from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from backend.app.core.config import load_config
from backend.app.services.display_price import convert_usd_oz_to_cny_g

# Twelve Data time_series endpoint (USD/oz OHLC for XAU/USD).
_TD_ENDPOINT = "https://api.twelvedata.com/time_series"
_TD_SYMBOL = "XAU/USD"

# period -> (twelve_data interval, outputsize, cache_ttl_seconds, aggregate_every)
# aggregate_every>1 means: fetch `interval` bars then merge every N into one bar.
_PERIODS: dict[str, dict[str, Any]] = {
    # 加载更多历史供 dataZoom 滑块拖动浏览; 前端默认窗口=约10刻度宽, 拖动滚历史
    "1min": {"interval": "1min", "outputsize": 480, "ttl": 30, "agg": 1},     # 约8小时分钟线
    "1h": {"interval": "1h", "outputsize": 120, "ttl": 300, "agg": 1},        # 约5天小时线
    "1day": {"interval": "1day", "outputsize": 90, "ttl": 3600, "agg": 1},    # 约3个月日线
    "1month": {"interval": "1month", "outputsize": 36, "ttl": 21600, "agg": 1},  # 3年月线
}

# Simple in-memory cache: (source, period) -> (expires_at_epoch, payload)
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def supported_periods() -> list[dict[str, str]]:
    labels = {
        "1min": "分线",
        "1h": "时线",
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


def _period_delta(period: str) -> timedelta:
    if period == "1min":
        return timedelta(minutes=1)
    if period == "1h":
        return timedelta(hours=1)
    if period == "1month":
        return timedelta(days=30)
    return timedelta(days=1)


def _ensure_source_history(prices: list[float], latest_price: float, minimum: int = 25) -> list[float]:
    if len(prices) >= minimum:
        return prices
    seed = prices[0] if prices else latest_price
    generated = [round(seed - ((minimum - index) * 0.15), 2) for index in range(minimum - len(prices))]
    return generated + prices


def _build_source_history_candles(prices: list[float], period: str) -> list[dict[str, Any]]:
    spec = _PERIODS[period]
    selected = prices[-int(spec["outputsize"]) :]
    step = _period_delta(period)
    start = datetime.now() - (step * max(len(selected) - 1, 0))
    candles = []
    for index, price in enumerate(selected):
        current_time = start + (step * index)
        value = round(float(price), 3)
        candles.append(
            {
                "time": current_time.replace(microsecond=0).isoformat(),
                "open": value,
                "high": value,
                "low": value,
                "close": value,
            }
        )
    return candles


async def _get_source_history_klines(period: str, source: str, provider: Any, source_config: dict[str, Any]) -> dict[str, Any]:
    tick = await provider.latest_tick(source)
    prices = _ensure_source_history(provider.price_history(source), tick.price)
    display_unit = f"{source_config.get('currency', 'CNY')}/{source_config.get('unit', 'g')}"
    candles = _build_source_history_candles(prices, period)
    return {
        "period": period,
        "source": source,
        "display_unit": display_unit,
        "count": len(candles),
        "candles": candles,
    }


async def get_klines(period: str, source: Optional[str] = None, provider: Any = None) -> dict[str, Any]:
    if period not in _PERIODS:
        raise ValueError(f"unsupported period: {period}")

    if source and provider is not None:
        source_config = provider.source_config(source)
        if source_config.get("kline_mode") == "history":
            return await _get_source_history_klines(period, source, provider, source_config)

    now = time.time()
    cache_key = (source or "twelve_data", period)
    cached = _cache.get(cache_key)
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
        "source": "twelve_data",
        "display_unit": display_unit,
        "count": len(candles),
        "candles": candles,
    }
    _cache[cache_key] = (now + float(spec["ttl"]), payload)
    return payload
