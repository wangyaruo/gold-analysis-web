from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from backend.app.core.logging import log_event
from backend.app.services.alerts import AlertEvent, AlertRule, AlertStore, evaluate_alert_rule
from backend.app.services.data_provider import PriceProvider, SHANGHAI_TZ
from backend.app.services.display_price import convert_usd_oz_to_cny_g
from backend.app.services.email_sender import (
    EmailConfigError,
    build_alert_email_message,
    build_email_config,
    send_email,
)
from backend.app.services.kline_store import KlineStore
from backend.app.services.predicted_range import build_predicted_daily_range
from backend.app.services.validation import validate_price_tick


SendEmailFunc = Callable[[Any, Any], None]


def start_alert_worker(
    config: dict[str, Any],
    provider: PriceProvider,
    store: AlertStore,
    kline_store: KlineStore,
) -> Optional[asyncio.Task]:
    alerts_config = config.get("alerts", {})
    if not alerts_config.get("enabled", False):
        return None
    interval = max(1, int(alerts_config.get("check_interval_seconds", 15)))
    return asyncio.create_task(_alert_loop(config, provider, store, kline_store, interval))


async def _alert_loop(
    config: dict[str, Any],
    provider: PriceProvider,
    store: AlertStore,
    kline_store: KlineStore,
    interval: int,
) -> None:
    while True:
        await run_alert_check(config, provider, store, kline_store)
        await asyncio.sleep(interval)


async def run_alert_check(
    config: dict[str, Any],
    provider: PriceProvider,
    store: AlertStore,
    kline_store: KlineStore,
    send_email_func: SendEmailFunc = send_email,
) -> list[AlertEvent]:
    rules = [rule for rule in store.list_delivery_rules() if rule.enabled]
    if not rules:
        return []

    alerts_config = config.get("alerts", {})
    try:
        email_config = build_email_config(alerts_config.get("email", {}))
    except EmailConfigError as exc:
        log_event(30, "alert_email_config_missing", error=str(exc))
        return []

    emitted: list[AlertEvent] = []
    for rule in rules:
        try:
            events = await _evaluate_rule(config, provider, store, kline_store, email_config, send_email_func, rule)
            emitted.extend(events)
        except Exception as exc:  # noqa: BLE001
            log_event(30, "alert_rule_check_failed", rule_id=rule.id, error=str(exc))
    return emitted


async def _evaluate_rule(
    config: dict[str, Any],
    provider: PriceProvider,
    store: AlertStore,
    kline_store: KlineStore,
    email_config: Any,
    send_email_func: SendEmailFunc,
    rule: AlertRule,
) -> list[AlertEvent]:
    source_config = provider.source_config(rule.source)
    source_key = source_config.get("_key", rule.source)
    tick = await provider.latest_tick(rule.source)
    realtime_config = config.get("realtime", {})
    max_delay = int(source_config.get("max_data_delay_seconds", realtime_config.get("max_data_delay_seconds", 5)))
    validated_tick = validate_price_tick(
        tick,
        min_price=float(source_config.get("min_price", 500)),
        max_price=float(source_config.get("max_price", 8000)),
        max_delay_seconds=max_delay,
    )
    display_config = config.get("display", {})
    display_unit = f"{display_config.get('currency', 'CNY')}/{display_config.get('unit', 'g')}"
    display_price = _convert_price_for_display(validated_tick.price, display_config, source_config)
    kline_store.record_price(source_key, display_price, validated_tick.timestamp)
    display_today_range = _display_today_range(provider.today_range(source_key), display_config, source_config)
    predicted_range = build_predicted_daily_range(
        display_price,
        range_percent=float(config.get("realtime", {}).get("predicted_range_percent", 0.02)),
        candles=kline_store.get_candles(source_key, "1min"),
        now=validated_tick.timestamp,
        source_range=display_today_range,
    )
    alert_date = validated_tick.timestamp.astimezone(SHANGHAI_TZ).date().isoformat()
    state = store.get_state(int(rule.id or 0), source_key, alert_date)
    result = evaluate_alert_rule(
        rule,
        state,
        current_price=display_price,
        predicted_range=predicted_range,
        step=float(config.get("alerts", {}).get("predicted_breakout_step_cny_g", 2)),
    )
    if not result.events:
        store.save_state(result.state)
        return []

    for event in result.events:
        message = build_alert_email_message(
            recipient_email=event.recipient_email,
            from_email=email_config.from_email,
            alert_kind=event.kind,
            source_label=source_config.get("label", source_config.get("name", source_key)),
            current_price=event.current_price,
            display_unit=display_unit,
            predicted_range=predicted_range,
            target_price=event.target_price,
            event_time=_format_event_time(validated_tick.timestamp),
            rule_id=event.rule_id,
        )
        send_email_func(email_config, message)
    store.save_state(result.state)
    return result.events


def _convert_price_for_display(
    price: float,
    display_config: dict[str, Any],
    source_config: dict[str, Any],
) -> float:
    source_currency = source_config.get("currency", display_config.get("source_currency", "USD"))
    source_unit = source_config.get("unit", display_config.get("source_unit", "oz"))
    display_currency = display_config.get("currency", "CNY")
    display_unit = display_config.get("unit", "g")

    if source_currency == display_currency and source_unit == display_unit:
        return round(float(price), 2)
    if source_currency != "USD" or source_unit != "oz" or display_currency != "CNY" or display_unit != "g":
        raise ValueError(f"unsupported display conversion: {source_currency}/{source_unit} to {display_currency}/{display_unit}")
    return convert_usd_oz_to_cny_g(
        float(price),
        usd_cny_rate=float(display_config.get("usd_cny_rate", 6.808596)),
        troy_ounce_grams=float(display_config.get("troy_ounce_grams", 31.1034768)),
    )


def _display_today_range(
    today_range: Optional[dict[str, Any]],
    display_config: dict[str, Any],
    source_config: dict[str, Any],
) -> Optional[dict[str, float]]:
    if not today_range:
        return None
    return {
        "low": _convert_price_for_display(float(today_range["low"]), display_config, source_config),
        "high": _convert_price_for_display(float(today_range["high"]), display_config, source_config),
    }


def _format_event_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
