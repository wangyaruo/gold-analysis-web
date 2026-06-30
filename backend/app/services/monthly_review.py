from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from backend.app.core.config import PROJECT_ROOT
from backend.app.services.data_provider import SHANGHAI_TZ
from backend.app.services.kline_store import KlineStore


def parse_seed_file(path: str | Path) -> list[dict[str, Any]]:
    seed_path = _resolve_seed_path(path)
    if not seed_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in seed_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("| 20"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 7:
            continue
        current_date = parts[0]
        if parts[1] == "--":
            rows.append(_empty_item(current_date))
            continue
        try:
            rows.append(
                {
                    "date": current_date,
                    "open": float(parts[1]),
                    "high": float(parts[2]),
                    "low": float(parts[3]),
                    "close": float(parts[4]),
                    "change_percent": _parse_percent(parts[5]),
                    "intraday_range_percent": _parse_percent(parts[6]),
                    "source": "seed",
                    "has_data": True,
                }
            )
        except ValueError:
            rows.append(_empty_item(current_date))
    return rows


def build_monthly_review(
    source: str,
    config: dict[str, Any],
    store: KlineStore,
    days: int = 30,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    day_count = max(1, int(days))
    commodities = _commodity_configs(config)
    key = _resolve_review_key(source, commodities)
    source_config = commodities.get(key, {})
    unit = f"{source_config.get('currency', 'CNY')}/{source_config.get('unit', 'g')}"
    label = source_config.get("label") or source_config.get("name") or key
    theme = source_config.get("theme", "")

    seed_path = source_config.get("seed_file") or source_config.get("seed_path")
    seed_rows = parse_seed_file(seed_path) if seed_path else []
    seed_by_date = {row["date"]: row for row in seed_rows}
    real_by_date = _real_daily_rows(key, store)
    end = _review_end_date(seed_rows, real_by_date, now)
    start = end - timedelta(days=day_count - 1)

    items = []
    for offset in range(day_count):
        current = (start + timedelta(days=offset)).isoformat()
        if current in real_by_date:
            items.append(real_by_date[current])
        elif current in seed_by_date:
            items.append(dict(seed_by_date[current]))
        else:
            items.append(_empty_item(current))

    return {
        "key": key,
        "source": key,
        "label": label,
        "unit": unit,
        "theme": theme,
        "days": day_count,
        "generated_at": _local_now(now).isoformat(),
        "has_seed": bool(seed_rows),
        "items": items,
        "summary": _summary(items),
        "weekly": _weekly(items),
    }


def build_monthly_reviews(
    config: dict[str, Any],
    store: KlineStore,
    days: int = 30,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    day_count = max(1, int(days))
    commodities = _commodity_configs(config)
    generated_at = _local_now(now).isoformat()
    return {
        "days": day_count,
        "generated_at": generated_at,
        "items": [
            build_monthly_review(key, config, store, days=day_count, now=now)
            for key in commodities
        ],
    }


def _commodity_configs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    market_review = config.get("market_review", {})
    commodities = market_review.get("commodities")
    if commodities:
        return dict(commodities)

    legacy_seed_files = market_review.get("seed_files", {})
    price_sources = config.get("data_sources", {}).get("price", {})
    result: dict[str, dict[str, Any]] = {}
    for key, seed_file in legacy_seed_files.items():
        source_config = price_sources.get(key, {})
        result[key] = {
            "label": source_config.get("label", source_config.get("name", key)),
            "currency": source_config.get("currency", "CNY"),
            "unit": source_config.get("unit", "g"),
            "seed_file": seed_file,
            "theme": source_config.get("theme", ""),
        }
    return result


def _resolve_review_key(source: str, commodities: dict[str, dict[str, Any]]) -> str:
    if source in commodities:
        return source
    legacy_aliases = {
        "icbc": "gold",
        "jdjygold_zheshang": "gold",
        "hongyun_gold_reference": "gold",
    }
    mapped = legacy_aliases.get(source, source)
    if mapped in commodities:
        return mapped
    raise ValueError(f"unknown monthly review source: {source}")


def _resolve_seed_path(path: str | Path) -> Path:
    seed_path = Path(path).expanduser()
    if seed_path.is_absolute():
        return seed_path
    return PROJECT_ROOT / seed_path


def _parse_percent(raw: str) -> float:
    text = raw.strip().replace("%", "").replace("+", "")
    return float(text) / 100


def _empty_item(day: str) -> dict[str, Any]:
    return {
        "date": day,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "change_percent": None,
        "intraday_range_percent": None,
        "source": "none",
        "has_data": False,
    }


def _real_daily_rows(source: str, store: KlineStore) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for candle in store.get_candles(source, "1day"):
        try:
            open_value = float(candle["open"])
            high_value = float(candle["high"])
            low_value = float(candle["low"])
            close_value = float(candle["close"])
        except (KeyError, TypeError, ValueError):
            continue
        day = str(candle.get("time", "")).split("T")[0]
        if not day:
            continue
        rows[day] = {
            "date": day,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "change_percent": _change_percent(open_value, close_value),
            "intraday_range_percent": _intraday_range_percent(low_value, high_value),
            "source": "realtime",
            "has_data": True,
        }
    return rows


def _review_end_date(
    seed_rows: list[dict[str, Any]],
    real_by_date: dict[str, dict[str, Any]],
    now: Optional[datetime],
) -> date:
    if seed_rows:
        seed_dates = [_parse_day(row.get("date")) for row in seed_rows]
        valid_seed_dates = [item for item in seed_dates if item]
        if valid_seed_dates:
            return max(valid_seed_dates)

    candidates: list[date] = [_local_now(now).date()]
    for row in seed_rows:
        parsed = _parse_day(row.get("date"))
        if parsed:
            candidates.append(parsed)
    for key in real_by_date:
        parsed = _parse_day(key)
        if parsed:
            candidates.append(parsed)
    if candidates:
        return max(candidates)
    return _local_now(now).date()


def _local_now(value: Optional[datetime]) -> datetime:
    current = value or datetime.now(SHANGHAI_TZ)
    if current.tzinfo is not None:
        return current.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
    return current


def _parse_day(raw: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _change_percent(open_value: float, close_value: float) -> Optional[float]:
    if not open_value:
        return None
    return (close_value - open_value) / open_value


def _intraday_range_percent(low_value: float, high_value: float) -> Optional[float]:
    if not low_value:
        return None
    return (high_value - low_value) / low_value


def _data_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("has_data")]


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    data = _data_items(items)
    up_days = [item for item in data if (item.get("change_percent") or 0) > 0]
    down_days = [item for item in data if (item.get("change_percent") or 0) < 0]
    flat_days = [item for item in data if item.get("change_percent") == 0]
    first = data[0] if data else None
    last = data[-1] if data else None
    cumulative = None
    if first and last and first.get("open"):
        cumulative = (float(last["close"]) - float(first["open"])) / float(first["open"])

    return {
        "trading_days": len(data),
        "missing_days": len(items) - len(data),
        "up_days": len(up_days),
        "down_days": len(down_days),
        "flat_days": len(flat_days),
        "best_day": max(data, key=lambda item: item["change_percent"]) if data else None,
        "worst_day": min(data, key=lambda item: item["change_percent"]) if data else None,
        "cumulative_change_percent": cumulative,
    }


def _weekly(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_monday: Optional[date] = None
    for item in items:
        current_date = _parse_day(item.get("date"))
        if not current_date:
            continue
        monday = current_date - timedelta(days=current_date.weekday())
        if current_monday is None or monday != current_monday:
            if current_group:
                groups.append(current_group)
            current_group = []
            current_monday = monday
        current_group.append(item)
    if current_group:
        groups.append(current_group)

    result = []
    for index, group in enumerate(groups, start=1):
        valid = _data_items(group)
        change = None
        if valid and valid[0].get("open"):
            change = (float(valid[-1]["close"]) - float(valid[0]["open"])) / float(valid[0]["open"])
        result.append(
            {
                "label": f"第{index}周",
                "start_date": group[0]["date"],
                "end_date": group[-1]["date"],
                "change_percent": change,
                "trading_days": len(valid),
            }
        )
    return result
