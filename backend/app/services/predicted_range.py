from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _date_key(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    return parsed.date().isoformat()


def _positive_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _average(values: list[Optional[float]]) -> Optional[float]:
    valid_values = [value for value in values if value is not None]
    if not valid_values:
        return None
    return sum(valid_values) / len(valid_values)


def _today_candles(candles: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    today = _date_key(now)
    return [candle for candle in candles or [] if _date_key(candle.get("time")) == today]


def _first_opening_price(candles: list[dict[str, Any]]) -> Optional[float]:
    for candle in candles:
        open_value = _positive_number(candle.get("open"))
        if open_value is not None:
            return open_value
        close_value = _positive_number(candle.get("close"))
        if close_value is not None:
            return close_value
    return None


def _typical_price(candle: dict[str, Any]) -> Optional[float]:
    return _average([
        _positive_number(candle.get("high")),
        _positive_number(candle.get("low")),
        _positive_number(candle.get("close")),
    ])


def _source_range_midpoint(source_range: Optional[dict[str, Any]]) -> Optional[float]:
    if not source_range:
        return None
    low = _positive_number(source_range.get("low"))
    high = _positive_number(source_range.get("high"))
    if low is None or high is None:
        return None
    return (low + high) / 2


def _prediction_basis(
    current_price: Any,
    candles: list[dict[str, Any]],
    now: datetime,
    source_range: Optional[dict[str, Any]],
) -> Optional[float]:
    candles_for_today = _today_candles(candles, now)
    opening_price = _first_opening_price(candles_for_today)
    intraday_average = _average([_typical_price(candle) for candle in candles_for_today])
    stable_average = intraday_average if intraday_average is not None else _source_range_midpoint(source_range)

    if opening_price is not None and stable_average is not None:
        return (opening_price * 0.6) + (stable_average * 0.4)

    return stable_average if stable_average is not None else opening_price or _positive_number(current_price)


def build_today_range(
    candles: list[dict[str, Any]],
    current_price: Any,
    now: Optional[datetime] = None,
    source_range: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, float]]:
    if source_range:
        values = [
            number
            for number in (
                _positive_number(source_range.get("low")),
                _positive_number(source_range.get("high")),
                _positive_number(current_price),
            )
            if number is not None
        ]
        if values:
            return {"low": min(values), "high": max(values)}

    current_time = now or datetime.now()
    today = _date_key(current_time)
    values: list[float] = []

    for candle in candles or []:
        if _date_key(candle.get("time")) != today:
            continue
        for key in ("low", "high", "open", "close"):
            number = _positive_number(candle.get(key))
            if number is not None:
                values.append(number)

    current = _positive_number(current_price)
    if current is not None:
        values.append(current)

    if not values:
        return None
    return {"low": min(values), "high": max(values)}


def _round_price(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def build_predicted_daily_range(
    current_price: Any,
    range_percent: float = 0.02,
    candles: Optional[list[dict[str, Any]]] = None,
    now: Optional[datetime] = None,
    source_range: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, float]]:
    candle_values = candles or []
    current_time = now or datetime.now()
    price = _prediction_basis(current_price, candle_values, current_time, source_range)
    try:
        range_value = float(range_percent)
    except (TypeError, ValueError):
        return None
    if price is None or price <= 0 or range_value <= 0:
        return None

    low = (2 * price) / (2 + range_value)
    high = low * (1 + range_value)
    observed_range = build_today_range(candle_values, current_price, current_time, source_range)
    return {
        "low": _round_price(min(low, observed_range["low"]) if observed_range else low),
        "high": _round_price(max(high, observed_range["high"]) if observed_range else high),
        "range_percent": range_value,
    }
