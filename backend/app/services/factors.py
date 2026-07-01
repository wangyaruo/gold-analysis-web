from __future__ import annotations

import asyncio
import csv
import os
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Iterable, Optional

import httpx

from backend.app.services.data_provider import MarketDataError, SHANGHAI_TZ
from backend.app.services.display_price import convert_usd_oz_to_cny_g
from backend.app.services.klines import _fetch_time_series, _twelve_data_key


FRED_CSV_ENDPOINT = "https://fred.stlouisfed.org/graph/fredgraph.csv"
SGE_DELAYED_QUOTES_URL = "https://www.sge.com.cn/sjzx/yshqbg"

FRED_FACTORS = [
    {
        "key": "usd_cny",
        "label": "美元兑人民币",
        "series_id": "DEXCHUS",
        "unit": "",
        "positive_when": "up",
        "source_name": "FRED DEXCHUS",
        "strength_multiplier": 100,
        "explanation": "美元兑人民币上行会抬高人民币计价黄金。",
    },
    {
        "key": "usd_index",
        "label": "美元指数",
        "series_id": "DTWEXBGS",
        "unit": "",
        "positive_when": "down",
        "source_name": "FRED DTWEXBGS",
        "strength_multiplier": 10,
        "explanation": "美元走强通常压制国际金价，走弱则减轻压力。",
    },
    {
        "key": "real_yield",
        "label": "美国实际利率",
        "series_id": "DFII10",
        "unit": "%",
        "positive_when": "down",
        "source_name": "FRED DFII10",
        "strength_multiplier": 100,
        "explanation": "实际利率上行会增加持有黄金的机会成本。",
    },
    {
        "key": "inflation_expectation",
        "label": "通胀预期",
        "series_id": "T10YIE",
        "unit": "%",
        "positive_when": "up",
        "source_name": "FRED T10YIE",
        "strength_multiplier": 100,
        "explanation": "通胀预期上行会增强黄金保值需求。",
    },
    {
        "key": "risk_volatility",
        "label": "避险波动率",
        "series_id": "VIXCLS",
        "unit": "",
        "positive_when": "up",
        "source_name": "FRED VIXCLS",
        "strength_multiplier": 1,
        "explanation": "市场波动率上升通常代表避险需求升温。",
    },
]

NEWS_FACTORS = [
    {
        "key": "rate_expectation_news",
        "label": "降息/加息预期",
        "positive": ["rate cut", "dovish", "降息", "鸽派"],
        "negative": ["rate hike", "hawkish", "加息", "鹰派"],
        "explanation": "降息预期利好黄金，加息或鹰派预期利空。",
    },
    {
        "key": "safe_haven_news",
        "label": "避险/地缘风险",
        "positive": ["safe haven", "geopolitical", "避险", "地缘"],
        "negative": ["risk appetite", "风险偏好"],
        "explanation": "避险需求升温通常支撑黄金。",
    },
    {
        "key": "central_bank_news",
        "label": "央行购金",
        "positive": ["central bank buying", "central banks buy", "央行购金", "央行买金"],
        "negative": ["central bank selling", "央行减持", "央行售金"],
        "explanation": "央行购金支撑中长期黄金需求，减持则偏利空。",
    },
]


def parse_fred_csv(text: str, series_id: str) -> dict[str, Any]:
    reader = csv.DictReader(StringIO(text.strip()))
    values: list[tuple[str, float]] = []
    for row in reader:
        raw_date = str(row.get("DATE") or row.get("date") or "").strip()
        raw_value = str(row.get(series_id) or "").strip()
        if not raw_date or raw_value in {"", "."}:
            continue
        try:
            values.append((raw_date, float(raw_value)))
        except ValueError:
            continue
    if not values:
        raise ValueError(f"FRED series {series_id} has no valid observations")

    latest_date, latest_value = values[-1]
    previous_value = values[-2][1] if len(values) > 1 else latest_value
    return {
        "date": latest_date,
        "value": latest_value,
        "previous_value": previous_value,
        "change": round(latest_value - previous_value, 6),
    }


def parse_sge_au9999(text: str) -> dict[str, Any]:
    row_match = re.search(
        r"<tr[^>]*>[\s\S]*?<td[^>]*>\s*Au99\.99\s*</td>[\s\S]*?</tr>",
        text,
        re.IGNORECASE,
    )
    if not row_match:
        raise ValueError("SGE delayed quotes did not include Au99.99")

    cells = [
        re.sub(r"<[^>]+>", "", cell).strip()
        for cell in re.findall(r"<td[^>]*>([\s\S]*?)</td>", row_match.group(0), re.IGNORECASE)
    ]
    if len(cells) < 5:
        raise ValueError("SGE Au99.99 row is missing quote cells")

    date = ""
    date_match = re.search(r"(\d{4})年(\d{2})月(\d{2})日延时行情", text)
    if date_match:
        date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    latest = float(cells[1])
    high = float(cells[2])
    low = float(cells[3])
    open_value = float(cells[4])
    return {
        "contract": "Au99.99",
        "date": date,
        "value": latest,
        "open": open_value,
        "high": high,
        "low": low,
        "change": round(latest - open_value, 6),
    }


def build_directional_factor(
    *,
    key: str,
    label: str,
    value: Optional[float],
    change: Optional[float],
    unit: str,
    positive_when: str,
    source_name: str,
    updated_at: str,
    explanation: str,
    status: str = "ok",
    strength: Optional[float] = None,
) -> dict[str, Any]:
    numeric_change = _optional_float(change)
    if status != "ok":
        signal = "neutral"
    elif numeric_change is None or abs(numeric_change) < 1e-9:
        signal = "neutral"
    elif positive_when == "down":
        signal = "positive" if numeric_change < 0 else "negative"
    else:
        signal = "positive" if numeric_change > 0 else "negative"

    numeric_strength = abs(float(strength)) if strength is not None else abs(numeric_change or 0)
    return {
        "key": key,
        "label": label,
        "value": _round_optional(value),
        "change": _round_optional(change),
        "unit": unit,
        "signal": signal,
        "strength": round(numeric_strength, 4),
        "source_name": source_name,
        "updated_at": updated_at,
        "explanation": explanation,
        "status": status,
    }


def rank_factor_items(items: Iterable[dict[str, Any]], limit: Optional[int] = None) -> list[dict[str, Any]]:
    ranked = sorted(list(items), key=_rank_score, reverse=True)
    return ranked[:limit] if limit else ranked


async def build_market_factors(
    *,
    source: Optional[str],
    config: dict[str, Any],
    provider: Any,
    articles: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    source_config = provider.source_config(source)
    source_key = source_config.get("_key", source)
    generated_at = datetime.now(SHANGHAI_TZ).replace(microsecond=0).isoformat()

    bank_task = _bank_price_factor(provider, source_key, source_config, config)
    external_tasks = [_sge_factor(), _international_gold_factor(config)]
    external_tasks.extend(_fred_factor(spec) for spec in FRED_FACTORS)
    results = await asyncio.gather(bank_task, *external_tasks)

    items = [item for item in results if item]
    items.extend(_news_factors(articles or [], generated_at))
    items.append(_domestic_premium_factor(items, generated_at))

    ranked = rank_factor_items(items)
    return {
        "generated_at": generated_at,
        "basis": "银行积存金 CNY/g",
        "overall_bias": _overall_bias(ranked),
        "items": ranked,
    }


async def _bank_price_factor(provider: Any, source_key: str, source_config: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    history_before = provider.price_history(source_key)
    try:
        tick = await provider.latest_tick(source_key)
    except Exception as exc:  # noqa: BLE001
        return _unavailable_factor(
            key="bank_price",
            label="银行积存金",
            source_name=source_config.get("label", source_key),
            explanation=f"当前银行积存金报价暂不可用：{exc}",
        )

    display_value = _convert_price_for_display(float(tick.price), config.get("display", {}), source_config)
    previous_value = history_before[-1] if history_before else display_value
    change = round(display_value - previous_value, 6)
    strength = _percent_strength(change, previous_value, multiplier=10)
    return build_directional_factor(
        key="bank_price",
        label="银行积存金",
        value=display_value,
        change=change,
        unit="CNY/g",
        positive_when="up",
        source_name=source_config.get("label", tick.source),
        updated_at=tick.timestamp.astimezone(SHANGHAI_TZ).replace(microsecond=0).isoformat(),
        explanation="当前银行对客积存金报价上行偏利好，下行偏利空。",
        strength=strength,
    )


async def _sge_factor() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(SGE_DELAYED_QUOTES_URL)
            response.raise_for_status()
        parsed = parse_sge_au9999(response.text)
        strength = _percent_strength(parsed["change"], parsed["open"], multiplier=10)
        return build_directional_factor(
            key="sge_au9999",
            label="上金所Au99.99",
            value=parsed["value"],
            change=parsed["change"],
            unit="CNY/g",
            positive_when="up",
            source_name="上海黄金交易所",
            updated_at=parsed["date"],
            explanation="境内黄金现货上行对银行积存金报价形成支撑。",
            strength=strength,
        )
    except Exception as exc:  # noqa: BLE001
        return _unavailable_factor(
            key="sge_au9999",
            label="上金所Au99.99",
            source_name="上海黄金交易所",
            explanation=f"上金所延时行情暂不可用：{exc}",
        )


async def _fred_factor(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(FRED_CSV_ENDPOINT, params={"id": spec["series_id"]})
            response.raise_for_status()
        parsed = parse_fred_csv(response.text, spec["series_id"])
        strength = abs(parsed["change"]) * float(spec.get("strength_multiplier", 1))
        return build_directional_factor(
            key=spec["key"],
            label=spec["label"],
            value=parsed["value"],
            change=parsed["change"],
            unit=spec["unit"],
            positive_when=spec["positive_when"],
            source_name=spec["source_name"],
            updated_at=parsed["date"],
            explanation=spec["explanation"],
            strength=strength,
        )
    except Exception as exc:  # noqa: BLE001
        return _unavailable_factor(
            key=spec["key"],
            label=spec["label"],
            source_name=spec["source_name"],
            explanation=f"{spec['source_name']} 暂不可用：{exc}",
        )


async def _international_gold_factor(config: dict[str, Any]) -> dict[str, Any]:
    if not _twelve_data_key(config) and not os.getenv("TWELVE_DATA_KEY"):
        return _unavailable_factor(
            key="xau_usd",
            label="国际金价",
            source_name="Twelve Data XAU/USD",
            explanation="未配置 TWELVE_DATA_KEY，国际金价因子暂不参与排序。",
        )
    try:
        apikey = _twelve_data_key(config) or os.getenv("TWELVE_DATA_KEY") or ""
        rows = await _fetch_time_series("1day", 3, apikey)
        parsed_rows = [
            row for row in rows
            if _optional_float(row.get("close")) is not None and row.get("datetime")
        ]
        if not parsed_rows:
            raise ValueError("Twelve Data response had no close prices")
        latest = parsed_rows[-1]
        previous = parsed_rows[-2] if len(parsed_rows) > 1 else latest
        value = float(latest["close"])
        previous_value = float(previous["close"])
        change = value - previous_value
        return build_directional_factor(
            key="xau_usd",
            label="国际金价",
            value=value,
            change=change,
            unit="USD/oz",
            positive_when="up",
            source_name="Twelve Data XAU/USD",
            updated_at=str(latest.get("datetime") or ""),
            explanation="国际现货黄金上行通常会传导至银行积存金。",
            strength=_percent_strength(change, previous_value, multiplier=10),
        )
    except Exception as exc:  # noqa: BLE001
        return _unavailable_factor(
            key="xau_usd",
            label="国际金价",
            source_name="Twelve Data XAU/USD",
            explanation=f"国际金价因子暂不可用：{exc}",
        )


def _news_factors(articles: list[dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    return [_news_factor(spec, articles, generated_at) for spec in NEWS_FACTORS]


def _news_factor(spec: dict[str, Any], articles: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    if not articles:
        return _unavailable_factor(
            key=spec["key"],
            label=spec["label"],
            source_name="NewsAPI",
            explanation="暂无新闻样本，新闻型因子暂不参与排序。",
        )

    positive_hits = 0
    negative_hits = 0
    latest_time = ""
    for article in articles:
        text = _article_text(article)
        if not latest_time:
            latest_time = str(article.get("publishedAt") or article.get("published_at") or article.get("time") or "")
        positive_hits += sum(1 for keyword in spec["positive"] if keyword.lower() in text)
        negative_hits += sum(1 for keyword in spec["negative"] if keyword.lower() in text)

    score = positive_hits - negative_hits
    return build_directional_factor(
        key=spec["key"],
        label=spec["label"],
        value=score,
        change=score,
        unit="",
        positive_when="up",
        source_name="NewsAPI",
        updated_at=latest_time or generated_at,
        explanation=spec["explanation"],
        status="ok",
        strength=abs(score),
    )


def _domestic_premium_factor(items: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    bank = _find_item(items, "bank_price")
    sge = _find_item(items, "sge_au9999")
    if not bank or not sge or bank.get("value") is None or sge.get("value") is None:
        return _unavailable_factor(
            key="domestic_premium",
            label="国内溢价",
            source_name="银行报价 - 上金所Au99.99",
            explanation="需要同时取得银行积存金与上金所 Au99.99 才能计算国内溢价。",
        )
    premium = float(bank["value"]) - float(sge["value"])
    return build_directional_factor(
        key="domestic_premium",
        label="国内溢价",
        value=premium,
        change=premium,
        unit="CNY/g",
        positive_when="up",
        source_name="银行报价 - 上金所Au99.99",
        updated_at=generated_at,
        explanation="银行积存金相对境内现货溢价扩大，说明人民币计价报价更坚挺。",
        strength=abs(premium),
    )


def _overall_bias(items: list[dict[str, Any]]) -> dict[str, Any]:
    score = 0.0
    for item in items:
        if item.get("status") != "ok":
            continue
        strength = float(item.get("strength") or 0)
        if item.get("signal") == "positive":
            score += strength
        elif item.get("signal") == "negative":
            score -= strength
    if score > 0.25:
        signal = "positive"
    elif score < -0.25:
        signal = "negative"
    else:
        signal = "neutral"
    return {"signal": signal, "score": round(score, 4)}


def _unavailable_factor(*, key: str, label: str, source_name: str, explanation: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": None,
        "change": None,
        "unit": "",
        "signal": "neutral",
        "strength": 0.0,
        "source_name": source_name,
        "updated_at": "",
        "explanation": explanation,
        "status": "unavailable",
    }


def _rank_score(item: dict[str, Any]) -> float:
    status = str(item.get("status") or "ok")
    status_weight = {
        "ok": 1.0,
        "stale": 0.55,
        "unavailable": 0.02,
    }.get(status, 0.1)
    status_floor = {
        "ok": 0.001,
        "stale": 0.0005,
        "unavailable": 0.0,
    }.get(status, 0.0)
    return (float(item.get("strength") or 0) * status_weight) + status_floor


def _article_text(article: dict[str, Any]) -> str:
    return " ".join(
        str(article.get(field) or "")
        for field in ("title", "description", "content")
    ).lower()


def _find_item(items: Iterable[dict[str, Any]], key: str) -> Optional[dict[str, Any]]:
    return next((item for item in items if item.get("key") == key), None)


def _percent_strength(change: float, base: float, *, multiplier: float = 1) -> float:
    if not base:
        return abs(change)
    return abs(change / base) * 100 * multiplier


def _optional_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_optional(value: Any) -> Optional[float]:
    parsed = _optional_float(value)
    if parsed is None:
        return None
    return round(parsed, 4)


def _convert_price_for_display(price: float, display_config: dict[str, Any], source_config: dict[str, Any]) -> float:
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
