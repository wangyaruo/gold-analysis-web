from __future__ import annotations

from datetime import timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.auth import require_bearer_token
from backend.app.core.config import load_config
from backend.app.services.data_provider import MarketDataError, PriceProvider
from backend.app.services.decision import TechnicalSignal, build_recommendation
from backend.app.services.display_price import convert_usd_oz_to_cny_g
from backend.app.services.indicators import compute_stop_loss
from backend.app.services.market_math import (
    compute_volatility,
    detect_bollinger_breakout,
    detect_ma_cross,
)
from backend.app.services.news_provider import fetch_news_articles
from backend.app.services.pnl import calculate_pnl
from backend.app.services.sentiment import analyze_news_sentiment
from backend.app.services.validation import validate_price_tick
from backend.app.services.klines import get_klines, supported_periods


router = APIRouter()
_config = load_config()
_provider = PriceProvider(_config)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/market/snapshot", dependencies=[Depends(require_bearer_token)])
async def market_snapshot(source: Optional[str] = None) -> dict[str, Any]:
    config = load_config()
    selected_source = source or None
    try:
        source_config = _provider.source_config(selected_source)
        tick = await _provider.latest_tick(selected_source)
    except MarketDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    realtime_config = config.get("realtime", {})
    max_data_delay_seconds = _max_data_delay_seconds(realtime_config, source_config)
    validated_tick = validate_price_tick(
        tick,
        min_price=float(source_config.get("min_price", 500)),
        max_price=float(source_config.get("max_price", 8000)),
        max_delay_seconds=max_data_delay_seconds,
    )

    prices = _ensure_history(_provider.price_history(source_config.get("_key")), validated_tick.price, minimum=25)
    indicator_config = config.get("indicators", {})
    stop_loss_config = indicator_config.get("stop_loss", {})
    volatility = compute_volatility(prices, int(stop_loss_config.get("volatility_window", 20)))
    stop_loss = compute_stop_loss(
        prices,
        indicator_type=stop_loss_config.get("type", "SMA"),
        period=int(stop_loss_config.get("period", 20)),
        multiplier=float(stop_loss_config.get("multiplier", 2)),
        volatility=volatility,
    )

    ma_config = indicator_config.get("moving_average", {})
    ma_cross, cross_strength = detect_ma_cross(
        prices,
        short_period=int(ma_config.get("short_period", 5)),
        long_period=int(ma_config.get("long_period", 20)),
    )
    bollinger_config = indicator_config.get("bollinger_bands", {})
    breakout, upper_band, lower_band = detect_bollinger_breakout(
        prices,
        period=int(bollinger_config.get("period", 20)),
        stddev_multiplier=float(bollinger_config.get("stddev_multiplier", 2)),
    )

    articles = await fetch_news_articles(config)
    sentiment = analyze_news_sentiment(articles, config.get("news", {}).get("sentiment", {}))
    recommendation = build_recommendation(
        TechnicalSignal(
            ma_cross=ma_cross,
            cross_strength=cross_strength,
            bollinger_breakout=breakout,
            current_price=validated_tick.price,
        ),
        sentiment.label,
        config.get("decision_rules", {}),
    )
    display_config = config.get("display", {})
    display_unit = f"{display_config.get('currency', 'CNY')}/{display_config.get('unit', 'g')}"
    source_unit = _source_display_unit(source_config, display_config)
    display_prices = _convert_prices_for_display(prices, display_config, source_config)
    display_stop_loss = _convert_price_for_display(stop_loss.stop_loss, display_config, source_config)
    today_range = _provider.today_range(source_config.get("_key"))

    return {
        "price": {
            "symbol": validated_tick.symbol,
            "value": validated_tick.price,
            "unit": source_unit,
            "display_value": display_prices[-1],
            "display_unit": display_unit,
            "timestamp": validated_tick.timestamp.astimezone(timezone.utc).isoformat(),
            "source": validated_tick.source,
            "requested_source": source_config.get("_key"),
        },
        "today_range": _display_today_range(today_range, display_config, source_config),
        "history": _build_history(prices, display_prices),
        "indicators": {
            "stop_loss": {
                **stop_loss.__dict__,
                "display_stop_loss": display_stop_loss,
                "display_unit": display_unit,
            },
            "ma_cross": ma_cross,
            "cross_strength": cross_strength,
            "bollinger": {
                "breakout": breakout,
                "upper_band": upper_band,
                "lower_band": lower_band,
                "display_upper_band": _convert_price_for_display(upper_band, display_config, source_config) if upper_band else 0.0,
                "display_lower_band": _convert_price_for_display(lower_band, display_config, source_config) if lower_band else 0.0,
                "display_unit": display_unit,
            },
        },
        "sentiment": sentiment.__dict__,
        "recommendation": recommendation.__dict__,
        "refresh_seconds": realtime_config.get("frontend_refresh_seconds", 10),
        "max_data_delay_seconds": max_data_delay_seconds,
    }


@router.get("/market/klines", dependencies=[Depends(require_bearer_token)])
async def market_klines(period: str = "1day", source: Optional[str] = None) -> dict[str, Any]:
    try:
        return await get_klines(period, source=source, provider=_provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"klines fetch failed: {exc}") from exc


@router.get("/market/periods", dependencies=[Depends(require_bearer_token)])
async def market_periods() -> dict[str, Any]:
    return {"periods": supported_periods()}


@router.post("/portfolio/pnl", dependencies=[Depends(require_bearer_token)])
async def portfolio_pnl(payload: dict[str, float]) -> dict[str, float]:
    try:
        result = calculate_pnl(
            buy_price=float(payload["buy_price"]),
            quantity=float(payload["quantity"]),
            current_price=float(payload["current_price"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.__dict__


@router.get("/config/public", dependencies=[Depends(require_bearer_token)])
async def public_config() -> dict[str, Any]:
    config = load_config()
    return {
        "realtime": config.get("realtime", {}),
        "portfolio_defaults": config.get("portfolio_defaults", {}),
        "display": config.get("display", {}),
        "data_sources": _public_data_sources(config),
        "indicator_defaults": config.get("indicators", {}),
        "decision_rule_defaults": config.get("decision_rules", {}),
    }


def _ensure_history(prices: list[float], latest_price: float, minimum: int) -> list[float]:
    if len(prices) >= minimum:
        return prices
    seed = prices[0] if prices else latest_price
    generated = [round(seed - ((minimum - index) * 0.75), 2) for index in range(minimum - len(prices))]
    return generated + prices


def _max_data_delay_seconds(realtime_config: dict[str, Any], source_config: dict[str, Any]) -> int:
    return int(source_config.get("max_data_delay_seconds", realtime_config.get("max_data_delay_seconds", 5)))


def _convert_price_for_display(
    price: float,
    display_config: dict[str, Any],
    source_config: Optional[dict[str, Any]] = None,
) -> float:
    source_config = source_config or {}
    source_currency = source_config.get("currency", display_config.get("source_currency", "USD"))
    source_unit = source_config.get("unit", display_config.get("source_unit", "oz"))
    display_currency = display_config.get("currency", "CNY")
    display_unit = display_config.get("unit", "g")

    if source_currency == display_currency and source_unit == display_unit:
        return round(price, 2)
    if source_currency != "USD" or source_unit != "oz" or display_currency != "CNY" or display_unit != "g":
        raise ValueError(f"unsupported display conversion: {source_currency}/{source_unit} to {display_currency}/{display_unit}")
    return convert_usd_oz_to_cny_g(
        price,
        usd_cny_rate=float(display_config.get("usd_cny_rate", 6.808596)),
        troy_ounce_grams=float(display_config.get("troy_ounce_grams", 31.1034768)),
    )


def _convert_prices_for_display(
    prices: list[float],
    display_config: dict[str, Any],
    source_config: Optional[dict[str, Any]] = None,
) -> list[float]:
    return [_convert_price_for_display(price, display_config, source_config) for price in prices]


def _display_today_range(
    today_range: Optional[dict[str, Any]],
    display_config: dict[str, Any],
    source_config: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if not today_range:
        return None
    low = float(today_range["low"])
    high = float(today_range["high"])
    return {
        "date": today_range.get("date"),
        "low": _convert_price_for_display(low, display_config, source_config),
        "high": _convert_price_for_display(high, display_config, source_config),
    }


def _source_display_unit(source_config: dict[str, Any], display_config: dict[str, Any]) -> str:
    return (
        f"{source_config.get('currency', display_config.get('source_currency', 'USD'))}/"
        f"{source_config.get('unit', display_config.get('source_unit', 'oz'))}"
    )


def _build_history(prices: list[float], display_prices: list[float]) -> list[dict[str, float]]:
    pairs = list(zip(prices, display_prices))[-80:]
    return [
        {"index": index + 1, "price": price, "display_price": display_price}
        for index, (price, display_price) in enumerate(pairs)
    ]


def _public_data_sources(config: dict[str, Any]) -> dict[str, Any]:
    sources = config.get("data_sources", {})
    price_sources = sources.get("price", {})
    options = []
    for key, source_config in price_sources.items():
        api_key_env = source_config.get("api_key_env") or ""
        options.append(
            {
                "key": key,
                "label": source_config.get("label", source_config.get("name", key)),
                "type": source_config.get("type", "http"),
                "symbol": source_config.get("symbol", "XAUUSD"),
                "description": source_config.get("description", ""),
                "requires_api_key": bool(api_key_env),
            }
        )
    return {
        "active": sources.get("active", "demo"),
        "fallback": sources.get("fallback"),
        "options": options,
    }
