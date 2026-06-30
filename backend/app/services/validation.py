from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class PriceTick:
    symbol: str
    price: float
    timestamp: datetime
    source: str
    day_low: Optional[float] = None
    day_high: Optional[float] = None


def validate_price_tick(
    tick: PriceTick,
    min_price: float,
    max_price: float,
    max_delay_seconds: int,
) -> PriceTick:
    if tick.price < min_price or tick.price > max_price:
        raise ValueError(f"price {tick.price} outside allowed range {min_price}-{max_price}")
    if tick.timestamp.tzinfo is None:
        raise ValueError("timestamp must include timezone")

    now = datetime.now(timezone.utc)
    age_seconds = (now - tick.timestamp.astimezone(timezone.utc)).total_seconds()
    if age_seconds < -2:
        raise ValueError("timestamp is in the future")
    if age_seconds > max_delay_seconds:
        raise ValueError(f"price tick is stale by {round(age_seconds, 3)} seconds")
    return tick
