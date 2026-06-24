from __future__ import annotations

from statistics import pstdev
from typing import Sequence

from backend.app.services.indicators import compute_sma


def compute_volatility(prices: Sequence[float], window: int) -> float:
    if window <= 1:
        raise ValueError("volatility window must be greater than one")
    if len(prices) < window:
        raise ValueError("not enough prices for volatility window")
    return round(pstdev([float(price) for price in prices[-window:]]), 6)


def detect_ma_cross(prices: Sequence[float], short_period: int, long_period: int) -> tuple[str, float]:
    if len(prices) < long_period + 1:
        return ("none", 0.0)

    previous_prices = prices[:-1]
    previous_short = compute_sma(previous_prices, short_period)
    previous_long = compute_sma(previous_prices, long_period)
    current_short = compute_sma(prices, short_period)
    current_long = compute_sma(prices, long_period)

    if previous_short <= previous_long and current_short > current_long:
        return ("golden_cross", round((current_short - current_long) / current_long, 6))
    if previous_short >= previous_long and current_short < current_long:
        return ("death_cross", round((current_long - current_short) / current_long, 6))
    return ("none", round(abs(current_short - current_long) / current_long, 6))


def detect_bollinger_breakout(
    prices: Sequence[float],
    period: int,
    stddev_multiplier: float,
) -> tuple[str, float, float]:
    if len(prices) < period:
        return ("none", 0.0, 0.0)
    window = [float(price) for price in prices[-period:]]
    middle = sum(window) / period
    deviation = pstdev(window)
    upper = middle + (stddev_multiplier * deviation)
    lower = middle - (stddev_multiplier * deviation)
    current = window[-1]
    if current > upper:
        return ("upper", round(upper, 6), round(lower, 6))
    if current < lower:
        return ("lower", round(upper, 6), round(lower, 6))
    return ("none", round(upper, 6), round(lower, 6))
