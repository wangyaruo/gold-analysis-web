from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class StopLossResult:
    indicator_type: str
    period: int
    multiplier: float
    indicator_value: float
    volatility: float
    stop_loss: float


def _require_period(prices: Sequence[float], period: int) -> None:
    if period <= 0:
        raise ValueError("period must be greater than zero")
    if len(prices) < period:
        raise ValueError("not enough prices for requested period")


def compute_sma(prices: Sequence[float], period: int) -> float:
    _require_period(prices, period)
    window = prices[-period:]
    return round(sum(window) / period, 6)


def compute_ema(prices: Sequence[float], period: int) -> float:
    _require_period(prices, period)
    alpha = 2 / (period + 1)
    ema = float(prices[0])
    for price in prices[1:]:
        ema = (float(price) * alpha) + (ema * (1 - alpha))
    return round(ema, 6)


def compute_stop_loss(
    prices: Sequence[float],
    indicator_type: str,
    period: int,
    multiplier: float,
    volatility: float,
) -> StopLossResult:
    if multiplier <= 0:
        raise ValueError("multiplier must be greater than zero")
    if volatility < 0:
        raise ValueError("volatility cannot be negative")

    normalized = indicator_type.upper()
    if normalized == "SMA":
        indicator_value = compute_sma(prices, period)
    elif normalized == "EMA":
        indicator_value = compute_ema(prices, period)
    else:
        raise ValueError(f"unsupported indicator type: {indicator_type}")

    stop_loss = indicator_value - (multiplier * volatility)
    return StopLossResult(
        indicator_type=normalized,
        period=period,
        multiplier=multiplier,
        indicator_value=round(indicator_value, 6),
        volatility=round(volatility, 6),
        stop_loss=round(stop_loss, 6),
    )
