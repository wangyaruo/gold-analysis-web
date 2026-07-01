from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.app.core.auth import require_bearer_token
from backend.app.core.config import load_config
from backend.app.core.logging import log_event
from backend.app.services.alerts import AlertStore, AlertSubscriber, mask_email, rule_to_dict, state_to_dict
from backend.app.services.data_provider import MarketDataError, PriceProvider
from backend.app.services.decision import TechnicalSignal, build_recommendation
from backend.app.services.display_price import convert_usd_oz_to_cny_g
from backend.app.services.email_sender import (
    EmailConfigError,
    EmailSendError,
    build_alert_email_message,
    build_email_config,
    build_verification_email_message,
    send_email,
)
from backend.app.services.indicators import compute_stop_loss
from backend.app.services.kline_store import KlineStore
from backend.app.services.factors import build_market_factors
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
from backend.app.services.monthly_review import build_monthly_review, build_monthly_reviews
from backend.app.services.predicted_range import build_predicted_daily_range


router = APIRouter()
_config = load_config()
_provider = PriceProvider(_config)
_kline_store = KlineStore.from_config(_config)
_alert_store = AlertStore.from_config(_config)


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
    source_key = source_config.get("_key")
    _kline_store.record_price(source_key, display_prices[-1], validated_tick.timestamp)
    _schedule_passive_history_capture(config, source_key)
    today_range = _provider.today_range(source_key)
    display_today_range = _display_today_range(today_range, display_config, source_config)
    predicted_range = build_predicted_daily_range(
        display_prices[-1],
        range_percent=float(config.get("realtime", {}).get("predicted_range_percent", 0.02)),
        candles=_kline_store.get_candles(source_key, "1min"),
        now=validated_tick.timestamp,
        source_range=display_today_range,
    )

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
        "today_range": display_today_range,
        "predicted_range": {
            **predicted_range,
            "unit": display_unit,
        } if predicted_range else None,
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
        "refresh_seconds": realtime_config.get("frontend_refresh_seconds", 2),
        "max_data_delay_seconds": max_data_delay_seconds,
    }


@router.get("/market/factors", dependencies=[Depends(require_bearer_token)])
async def market_factors(source: Optional[str] = None) -> dict[str, Any]:
    config = load_config()
    try:
        _provider.source_config(source or None)
        articles = await fetch_news_articles(config)
        return await build_market_factors(
            source=source,
            config=config,
            provider=_provider,
            articles=articles,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"market factors fetch failed: {exc}") from exc


@router.get("/market/klines", dependencies=[Depends(require_bearer_token)])
async def market_klines(period: str = "1day", source: Optional[str] = None) -> dict[str, Any]:
    try:
        return await get_klines(period, source=source, provider=_provider, store=_kline_store)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"klines fetch failed: {exc}") from exc


@router.get("/market/periods", dependencies=[Depends(require_bearer_token)])
async def market_periods() -> dict[str, Any]:
    return {"periods": supported_periods()}


@router.get("/market/monthly-review", dependencies=[Depends(require_bearer_token)])
async def market_monthly_review(source: Optional[str] = None, days: int = 30) -> dict[str, Any]:
    config = load_config()
    selected_source = source or "gold"
    try:
        return build_monthly_review(selected_source, config, _kline_store, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/market/monthly-reviews", dependencies=[Depends(require_bearer_token)])
async def market_monthly_reviews(days: int = 30) -> dict[str, Any]:
    config = load_config()
    return build_monthly_reviews(config, _kline_store, days=days)


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


async def _require_alert_subscriber(x_alert_session: str = Header("", alias="X-Alert-Session")) -> AlertSubscriber:
    subscriber = _alert_store.get_subscriber_by_token(x_alert_session)
    if not subscriber:
        raise HTTPException(status_code=401, detail="alert session is required")
    return subscriber


@router.post("/alerts/session/request-code", dependencies=[Depends(require_bearer_token)])
async def request_alert_session_code(payload: dict[str, Any]) -> dict[str, Any]:
    email = _validate_alert_email(payload.get("email"))
    config = load_config()
    expires_minutes = max(1, int(config.get("alerts", {}).get("verification_code_minutes", 10)))
    code = _generate_verification_code()
    expires_at = _utc_text(datetime.now(timezone.utc) + timedelta(minutes=expires_minutes))
    _alert_store.upsert_subscriber_verification(
        email,
        code_hash=_hash_verification_code(email, code),
        expires_at=expires_at,
    )
    try:
        email_config = build_email_config(config.get("alerts", {}).get("email", {}))
        message = build_verification_email_message(
            recipient_email=email,
            from_email=email_config.from_email,
            code=code,
            expires_minutes=expires_minutes,
        )
        send_email(email_config, message)
    except EmailConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmailSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"verification email send failed: {exc}") from exc
    return {"sent": True, "subscriber": {"email": mask_email(email)}}


@router.post("/alerts/session/verify", dependencies=[Depends(require_bearer_token)])
async def verify_alert_session(payload: dict[str, Any]) -> dict[str, Any]:
    email = _validate_alert_email(payload.get("email"))
    code = str(payload.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=422, detail="verification code is required")
    config = load_config()
    try:
        subscriber = _alert_store.verify_subscriber(
            email,
            code_hash=_hash_verification_code(email, code),
            session_token=_generate_alert_session_token(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _alert_store.ensure_default_rules_for_subscriber(
        subscriber,
        default_source=_default_alert_source(config),
    )
    return {
        "session_token": subscriber.session_token,
        "subscriber": {"email": mask_email(subscriber.email)},
    }


@router.get("/alerts/session/me", dependencies=[Depends(require_bearer_token)])
async def get_alert_session(subscriber: AlertSubscriber = Depends(_require_alert_subscriber)) -> dict[str, Any]:
    return {"subscriber": {"email": mask_email(subscriber.email)}}


@router.get("/alerts/rules", dependencies=[Depends(require_bearer_token)])
async def list_alert_rules(subscriber: AlertSubscriber = Depends(_require_alert_subscriber)) -> dict[str, Any]:
    rules = []
    for rule in _alert_store.list_rules(subscriber_id=subscriber.id):
        state = _alert_store.latest_state_for_rule(int(rule.id or 0))
        rules.append({
            **_public_rule_dict(rule),
            "state": state_to_dict(state) if state else None,
        })
    return {
        "rules": rules,
        "smtp_configured": _smtp_configured(load_config()),
    }


@router.post("/alerts/rules", dependencies=[Depends(require_bearer_token)])
async def create_alert_rule(
    payload: dict[str, Any],
    subscriber: AlertSubscriber = Depends(_require_alert_subscriber),
) -> dict[str, Any]:
    _validate_alert_rule_payload(payload)
    rule = _alert_store.create_rule(payload, subscriber=subscriber)
    return {"rule": _public_rule_dict(rule)}


@router.put("/alerts/rules/{rule_id}", dependencies=[Depends(require_bearer_token)])
async def update_alert_rule(
    rule_id: int,
    payload: dict[str, Any],
    subscriber: AlertSubscriber = Depends(_require_alert_subscriber),
) -> dict[str, Any]:
    _validate_alert_rule_payload(payload, partial=True)
    rule = _alert_store.update_rule(rule_id, payload, subscriber_id=subscriber.id)
    if not rule:
        raise HTTPException(status_code=404, detail="alert rule not found")
    return {"rule": _public_rule_dict(rule)}


@router.delete("/alerts/rules/{rule_id}", dependencies=[Depends(require_bearer_token)])
async def delete_alert_rule(
    rule_id: int,
    subscriber: AlertSubscriber = Depends(_require_alert_subscriber),
) -> dict[str, bool]:
    deleted = _alert_store.delete_rule(rule_id, subscriber_id=subscriber.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="alert rule not found")
    return {"deleted": True}


@router.post("/alerts/test-email", dependencies=[Depends(require_bearer_token)])
async def send_test_alert_email(
    payload: dict[str, Any],
    subscriber: AlertSubscriber = Depends(_require_alert_subscriber),
) -> dict[str, bool]:
    config = load_config()
    try:
        email_config = build_email_config(config.get("alerts", {}).get("email", {}))
        message = build_alert_email_message(
            recipient_email=subscriber.email,
            from_email=email_config.from_email,
            alert_kind="test",
            source_label=str(payload.get("source_label") or "测试行情源"),
            current_price=float(payload.get("current_price") or 0),
            display_unit=str(payload.get("display_unit") or "CNY/g"),
            predicted_range=payload.get("predicted_range"),
            target_price=None,
            event_time=str(payload.get("event_time") or "--"),
            rule_id=None,
        )
        send_email(email_config, message)
        if subscriber.id is not None:
            _alert_store.mark_test_email_sent(subscriber.id)
    except EmailConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmailSendError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"test email send failed: {exc}") from exc
    return {"sent": True}


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
        "alerts": _public_alert_config(config),
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


def _history_kline_source_keys(config: dict[str, Any], selected_key: Optional[str] = None) -> list[str]:
    price_sources = config.get("data_sources", {}).get("price", {})
    return [
        key
        for key, source_config in price_sources.items()
        if key != selected_key and source_config.get("kline_mode") == "history"
    ]


async def _capture_kline_tick_for_source(
    provider: PriceProvider,
    store: KlineStore,
    config: dict[str, Any],
    source_key: str,
) -> None:
    source_config = provider.source_config(source_key)
    tick = await provider.latest_tick(source_key)
    realtime_config = config.get("realtime", {})
    max_data_delay_seconds = _max_data_delay_seconds(realtime_config, source_config)
    validated_tick = validate_price_tick(
        tick,
        min_price=float(source_config.get("min_price", 500)),
        max_price=float(source_config.get("max_price", 8000)),
        max_delay_seconds=max_data_delay_seconds,
    )
    display_price = _convert_price_for_display(validated_tick.price, config.get("display", {}), source_config)
    store.record_price(source_key, display_price, validated_tick.timestamp)


async def _capture_passive_history_sources(config: dict[str, Any], selected_key: Optional[str]) -> None:
    for source_key in _history_kline_source_keys(config, selected_key=selected_key):
        try:
            await _capture_kline_tick_for_source(_provider, _kline_store, config, source_key)
        except Exception as exc:  # noqa: BLE001
            log_event(30, "passive_kline_capture_failed", source=source_key, error=str(exc))


def _schedule_passive_history_capture(config: dict[str, Any], selected_key: Optional[str]) -> None:
    if not _history_kline_source_keys(config, selected_key=selected_key):
        return
    try:
        asyncio.get_running_loop().create_task(_capture_passive_history_sources(config, selected_key))
    except RuntimeError:
        return


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


def _public_alert_config(config: dict[str, Any]) -> dict[str, Any]:
    alerts = config.get("alerts", {})
    return {
        "enabled": bool(alerts.get("enabled", False)),
        "check_interval_seconds": int(alerts.get("check_interval_seconds", 15)),
        "predicted_breakout_step_cny_g": float(alerts.get("predicted_breakout_step_cny_g", 2)),
        "default_source": alerts.get("default_source", config.get("data_sources", {}).get("active", "demo")),
        "smtp_configured": _smtp_configured(config),
    }


def _smtp_configured(config: dict[str, Any]) -> bool:
    try:
        build_email_config(config.get("alerts", {}).get("email", {}))
        return True
    except EmailConfigError:
        return False


def _public_rule_dict(rule: Any) -> dict[str, Any]:
    data = rule_to_dict(rule)
    data["recipient_email"] = mask_email(str(data.get("recipient_email") or ""))
    data.pop("subscriber_id", None)
    return data


def _default_alert_source(config: dict[str, Any]) -> str:
    return str(config.get("alerts", {}).get("default_source") or config.get("data_sources", {}).get("active") or "demo")


def _validate_alert_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    local, separator, domain = email.partition("@")
    if not local or separator != "@" or "." not in domain:
        raise HTTPException(status_code=422, detail="valid email is required")
    return email


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _generate_alert_session_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_verification_code(email: str, code: str) -> str:
    normalized_email = str(email or "").strip().lower()
    normalized_code = str(code or "").strip()
    return hashlib.sha256(f"{normalized_email}:{normalized_code}".encode("utf-8")).hexdigest()


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_alert_rule_payload(payload: dict[str, Any], *, partial: bool = False) -> None:
    if not partial or "recipient_email" in payload:
        recipient = str(payload.get("recipient_email") or "").strip()
        if recipient and "@" not in recipient:
            raise HTTPException(status_code=422, detail="recipient_email must be a valid email")
        if not partial and "recipient_email" in payload and not recipient:
            raise HTTPException(status_code=422, detail="recipient_email is required")
    for field in ("target_high_price", "target_low_price"):
        if field not in payload or payload.get(field) in (None, ""):
            continue
        try:
            value = float(payload[field])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{field} must be a number") from exc
        if value <= 0:
            raise HTTPException(status_code=422, detail=f"{field} must be positive")
