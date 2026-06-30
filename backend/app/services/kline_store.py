from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from backend.app.core.config import PROJECT_ROOT
from backend.app.services.data_provider import SHANGHAI_TZ


DEFAULT_RETENTION = {
    "1min_days": 30,
    "1day_days": 31,
    "1month_months": 36,
}


class KlineStore:
    def __init__(self, db_path: str | Path, retention: Optional[dict[str, Any]] = None) -> None:
        self.db_path = str(db_path)
        self.retention = {**DEFAULT_RETENTION, **(retention or {})}
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "KlineStore":
        storage = config.get("storage", {})
        raw_path = str(storage.get("kline_db_path") or "data/kline_bars.sqlite")
        db_path = raw_path if raw_path == ":memory:" else _resolve_db_path(raw_path)
        return cls(db_path, storage.get("kline_retention"))

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kline_bars (
                source TEXT NOT NULL,
                period TEXT NOT NULL,
                time TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                change REAL NOT NULL,
                change_percent REAL NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source, period, time)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kline_bars_source_period_time ON kline_bars(source, period, time)"
        )
        self._conn.commit()

    def record_price(self, source: str, price: float, timestamp: datetime) -> None:
        local = _local_naive(timestamp)
        value = float(price)
        self.upsert_bar(source, "1min", _format_dt(_floor_minute(local)), value, value, value, value)
        self.upsert_bar(source, "1day", _format_dt(_floor_day(local)), value, value, value, value)
        self.upsert_bar(source, "1month", _format_dt(_floor_month(local)), value, value, value, value)
        self.prune(local)

    def upsert_candles(self, source: str, period: str, candles: Iterable[dict[str, Any]]) -> None:
        for candle in candles:
            try:
                self.upsert_bar(
                    source,
                    period,
                    str(candle["time"]),
                    float(candle["open"]),
                    float(candle["high"]),
                    float(candle["low"]),
                    float(candle["close"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
        self.prune(datetime.now())

    def upsert_bar(
        self,
        source: str,
        period: str,
        time_value: str,
        open_value: float,
        high_value: float,
        low_value: float,
        close_value: float,
    ) -> None:
        bar_time = _format_dt(_parse_dt(time_value))
        open_number = float(open_value)
        close_number = float(close_value)
        change = close_number - open_number
        change_percent = change / open_number if open_number else 0.0
        now_text = _format_dt(datetime.now())
        self._conn.execute(
            """
            INSERT INTO kline_bars (
                source, period, time, open, high, low, close, change, change_percent, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, period, time) DO UPDATE SET
                high = MAX(kline_bars.high, excluded.high),
                low = MIN(kline_bars.low, excluded.low),
                close = excluded.close,
                change = excluded.close - kline_bars.open,
                change_percent = CASE
                    WHEN kline_bars.open = 0 THEN 0
                    ELSE (excluded.close - kline_bars.open) / kline_bars.open
                END,
                updated_at = excluded.updated_at
            """,
            (
                source,
                period,
                bar_time,
                open_number,
                float(high_value),
                float(low_value),
                close_number,
                change,
                change_percent,
                now_text,
            ),
        )
        self._conn.commit()

    def get_candles(self, source: str, period: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT time, open, high, low, close, change, change_percent
            FROM kline_bars
            WHERE source = ? AND period = ?
            ORDER BY time ASC
            """,
            (source, period),
        ).fetchall()
        return [
            {
                "time": row["time"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "change": row["change"],
                "change_percent": row["change_percent"],
            }
            for row in rows
        ]

    def prune(self, now: Optional[datetime] = None) -> None:
        current = _local_naive(now or datetime.now())
        cutoffs = {
            "1min": _format_dt(current - timedelta(days=int(self.retention["1min_days"]))),
            "1day": _format_dt(_floor_day(current - timedelta(days=int(self.retention["1day_days"])))),
            "1month": _format_dt(_add_months(_floor_month(current), -int(self.retention["1month_months"]))),
        }
        for period, cutoff in cutoffs.items():
            self._conn.execute(
                "DELETE FROM kline_bars WHERE period = ? AND time < ?",
                (period, cutoff),
            )
        self._conn.commit()


def _resolve_db_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _parse_dt(raw: str) -> datetime:
    text = str(raw).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return _local_naive(parsed)


def _local_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
    return value.replace(tzinfo=None)


def _format_dt(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _floor_day(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _floor_month(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(value: datetime, months: int) -> datetime:
    total = value.year * 12 + value.month - 1 + months
    year = total // 12
    month = total % 12 + 1
    return value.replace(year=year, month=month, day=1)
