from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.app.core.config import PROJECT_ROOT


@dataclass(frozen=True)
class AlertRule:
    id: Optional[int] = None
    enabled: bool = True
    source: str = "icbc"
    recipient_email: str = ""
    target_high_price: Optional[float] = None
    target_low_price: Optional[float] = None
    notify_on_custom_high: bool = False
    notify_on_custom_low: bool = False
    notify_on_predicted_high: bool = True
    notify_on_predicted_low: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class AlertState:
    rule_id: int
    source: str
    alert_date: str
    last_custom_high_alert_price: Optional[float] = None
    last_custom_low_alert_price: Optional[float] = None
    last_predicted_high_alert_price: Optional[float] = None
    last_predicted_low_alert_price: Optional[float] = None
    last_predicted_high_value: Optional[float] = None
    last_predicted_low_value: Optional[float] = None
    last_alerted_at: Optional[str] = None


@dataclass(frozen=True)
class AlertEvent:
    kind: str
    rule_id: int
    recipient_email: str
    source: str
    current_price: float
    target_price: Optional[float] = None
    predicted_high: Optional[float] = None
    predicted_low: Optional[float] = None


@dataclass(frozen=True)
class EvaluationResult:
    events: list[AlertEvent]
    state: AlertState


def evaluate_alert_rule(
    rule: AlertRule,
    state: AlertState,
    *,
    current_price: float,
    predicted_range: Optional[dict[str, Any]],
    step: float,
) -> EvaluationResult:
    if not rule.enabled:
        return EvaluationResult([], state)

    events: list[AlertEvent] = []
    next_state = state
    price = float(current_price)
    step_value = float(step)
    now_text = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    predicted_high = _optional_float((predicted_range or {}).get("high"))
    predicted_low = _optional_float((predicted_range or {}).get("low"))

    if (
        rule.notify_on_custom_high
        and rule.target_high_price is not None
        and next_state.last_custom_high_alert_price is None
        and price >= float(rule.target_high_price)
    ):
        events.append(_event("custom_high", rule, price, target_price=float(rule.target_high_price)))
        next_state = replace(next_state, last_custom_high_alert_price=price, last_alerted_at=now_text)

    if (
        rule.notify_on_custom_low
        and rule.target_low_price is not None
        and next_state.last_custom_low_alert_price is None
        and price <= float(rule.target_low_price)
    ):
        events.append(_event("custom_low", rule, price, target_price=float(rule.target_low_price)))
        next_state = replace(next_state, last_custom_low_alert_price=price, last_alerted_at=now_text)

    if rule.notify_on_predicted_high and predicted_high is not None and price >= predicted_high:
        last_price = next_state.last_predicted_high_alert_price
        if last_price is None:
            events.append(_event("predicted_high_touch", rule, price, predicted_high=predicted_high, predicted_low=predicted_low))
            next_state = replace(
                next_state,
                last_predicted_high_alert_price=price,
                last_predicted_high_value=predicted_high,
                last_predicted_low_value=predicted_low,
                last_alerted_at=now_text,
            )
        elif price >= float(last_price) + step_value:
            events.append(_event("predicted_high_breakout", rule, price, predicted_high=predicted_high, predicted_low=predicted_low))
            next_state = replace(
                next_state,
                last_predicted_high_alert_price=price,
                last_predicted_high_value=predicted_high,
                last_predicted_low_value=predicted_low,
                last_alerted_at=now_text,
            )

    if rule.notify_on_predicted_low and predicted_low is not None and price <= predicted_low:
        last_price = next_state.last_predicted_low_alert_price
        if last_price is None:
            events.append(_event("predicted_low_touch", rule, price, predicted_high=predicted_high, predicted_low=predicted_low))
            next_state = replace(
                next_state,
                last_predicted_low_alert_price=price,
                last_predicted_high_value=predicted_high,
                last_predicted_low_value=predicted_low,
                last_alerted_at=now_text,
            )
        elif price <= float(last_price) - step_value:
            events.append(_event("predicted_low_breakout", rule, price, predicted_high=predicted_high, predicted_low=predicted_low))
            next_state = replace(
                next_state,
                last_predicted_low_alert_price=price,
                last_predicted_high_value=predicted_high,
                last_predicted_low_value=predicted_low,
                last_alerted_at=now_text,
            )

    return EvaluationResult(events, next_state)


def _event(
    kind: str,
    rule: AlertRule,
    current_price: float,
    *,
    target_price: Optional[float] = None,
    predicted_high: Optional[float] = None,
    predicted_low: Optional[float] = None,
) -> AlertEvent:
    return AlertEvent(
        kind=kind,
        rule_id=int(rule.id or 0),
        recipient_email=rule.recipient_email,
        source=rule.source,
        current_price=current_price,
        target_price=target_price,
        predicted_high=predicted_high,
        predicted_low=predicted_low,
    )


class AlertStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "AlertStore":
        alerts_config = config.get("alerts", {})
        raw_path = str(alerts_config.get("storage_path") or "data/price_alerts.sqlite")
        db_path = raw_path if raw_path == ":memory:" else _resolve_db_path(raw_path)
        return cls(db_path)

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enabled INTEGER NOT NULL,
                source TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                target_high_price REAL,
                target_low_price REAL,
                notify_on_custom_high INTEGER NOT NULL,
                notify_on_custom_low INTEGER NOT NULL,
                notify_on_predicted_high INTEGER NOT NULL,
                notify_on_predicted_low INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_states (
                rule_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                alert_date TEXT NOT NULL,
                last_custom_high_alert_price REAL,
                last_custom_low_alert_price REAL,
                last_predicted_high_alert_price REAL,
                last_predicted_low_alert_price REAL,
                last_predicted_high_value REAL,
                last_predicted_low_value REAL,
                last_alerted_at TEXT,
                PRIMARY KEY (rule_id, source, alert_date)
            )
            """
        )
        self._conn.commit()

    def create_rule(self, payload: dict[str, Any]) -> AlertRule:
        now_text = _now_text()
        rule = _rule_from_payload(payload, created_at=now_text, updated_at=now_text)
        cursor = self._conn.execute(
            """
            INSERT INTO alert_rules (
                enabled, source, recipient_email, target_high_price, target_low_price,
                notify_on_custom_high, notify_on_custom_low, notify_on_predicted_high,
                notify_on_predicted_low, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _rule_values(rule),
        )
        self._conn.commit()
        return replace(rule, id=int(cursor.lastrowid))

    def list_rules(self) -> list[AlertRule]:
        rows = self._conn.execute("SELECT * FROM alert_rules ORDER BY id ASC").fetchall()
        return [_rule_from_row(row) for row in rows]

    def get_rule(self, rule_id: int) -> Optional[AlertRule]:
        row = self._conn.execute("SELECT * FROM alert_rules WHERE id = ?", (rule_id,)).fetchone()
        return _rule_from_row(row) if row else None

    def update_rule(self, rule_id: int, payload: dict[str, Any]) -> Optional[AlertRule]:
        current = self.get_rule(rule_id)
        if current is None:
            return None
        data = {**asdict(current), **payload, "id": rule_id, "created_at": current.created_at, "updated_at": _now_text()}
        next_rule = _rule_from_payload(data, rule_id=rule_id, created_at=current.created_at, updated_at=data["updated_at"])
        self._conn.execute(
            """
            UPDATE alert_rules
            SET enabled = ?, source = ?, recipient_email = ?, target_high_price = ?, target_low_price = ?,
                notify_on_custom_high = ?, notify_on_custom_low = ?, notify_on_predicted_high = ?,
                notify_on_predicted_low = ?, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (*_rule_values(next_rule), rule_id),
        )
        if current.target_high_price != next_rule.target_high_price:
            self._conn.execute("UPDATE alert_states SET last_custom_high_alert_price = NULL WHERE rule_id = ?", (rule_id,))
        if current.target_low_price != next_rule.target_low_price:
            self._conn.execute("UPDATE alert_states SET last_custom_low_alert_price = NULL WHERE rule_id = ?", (rule_id,))
        self._conn.commit()
        return next_rule

    def delete_rule(self, rule_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        self._conn.execute("DELETE FROM alert_states WHERE rule_id = ?", (rule_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_state(self, rule_id: int, source: str, alert_date: str) -> AlertState:
        row = self._conn.execute(
            "SELECT * FROM alert_states WHERE rule_id = ? AND source = ? AND alert_date = ?",
            (rule_id, source, alert_date),
        ).fetchone()
        if not row:
            return AlertState(rule_id=rule_id, source=source, alert_date=alert_date)
        return AlertState(
            rule_id=int(row["rule_id"]),
            source=row["source"],
            alert_date=row["alert_date"],
            last_custom_high_alert_price=row["last_custom_high_alert_price"],
            last_custom_low_alert_price=row["last_custom_low_alert_price"],
            last_predicted_high_alert_price=row["last_predicted_high_alert_price"],
            last_predicted_low_alert_price=row["last_predicted_low_alert_price"],
            last_predicted_high_value=row["last_predicted_high_value"],
            last_predicted_low_value=row["last_predicted_low_value"],
            last_alerted_at=row["last_alerted_at"],
        )

    def latest_state_for_rule(self, rule_id: int) -> Optional[AlertState]:
        row = self._conn.execute(
            """
            SELECT * FROM alert_states
            WHERE rule_id = ?
            ORDER BY COALESCE(last_alerted_at, '') DESC, alert_date DESC
            LIMIT 1
            """,
            (rule_id,),
        ).fetchone()
        if not row:
            return None
        return AlertState(
            rule_id=int(row["rule_id"]),
            source=row["source"],
            alert_date=row["alert_date"],
            last_custom_high_alert_price=row["last_custom_high_alert_price"],
            last_custom_low_alert_price=row["last_custom_low_alert_price"],
            last_predicted_high_alert_price=row["last_predicted_high_alert_price"],
            last_predicted_low_alert_price=row["last_predicted_low_alert_price"],
            last_predicted_high_value=row["last_predicted_high_value"],
            last_predicted_low_value=row["last_predicted_low_value"],
            last_alerted_at=row["last_alerted_at"],
        )

    def save_state(self, state: AlertState) -> None:
        self._conn.execute(
            """
            INSERT INTO alert_states (
                rule_id, source, alert_date, last_custom_high_alert_price, last_custom_low_alert_price,
                last_predicted_high_alert_price, last_predicted_low_alert_price, last_predicted_high_value,
                last_predicted_low_value, last_alerted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rule_id, source, alert_date) DO UPDATE SET
                last_custom_high_alert_price = excluded.last_custom_high_alert_price,
                last_custom_low_alert_price = excluded.last_custom_low_alert_price,
                last_predicted_high_alert_price = excluded.last_predicted_high_alert_price,
                last_predicted_low_alert_price = excluded.last_predicted_low_alert_price,
                last_predicted_high_value = excluded.last_predicted_high_value,
                last_predicted_low_value = excluded.last_predicted_low_value,
                last_alerted_at = excluded.last_alerted_at
            """,
            (
                state.rule_id,
                state.source,
                state.alert_date,
                state.last_custom_high_alert_price,
                state.last_custom_low_alert_price,
                state.last_predicted_high_alert_price,
                state.last_predicted_low_alert_price,
                state.last_predicted_high_value,
                state.last_predicted_low_value,
                state.last_alerted_at,
            ),
        )
        self._conn.commit()


def _rule_from_payload(
    payload: dict[str, Any],
    *,
    rule_id: Optional[int] = None,
    created_at: Optional[str],
    updated_at: Optional[str],
) -> AlertRule:
    return AlertRule(
        id=rule_id,
        enabled=_bool(payload.get("enabled", True)),
        source=str(payload.get("source") or "icbc"),
        recipient_email=str(payload.get("recipient_email") or ""),
        target_high_price=_optional_float(payload.get("target_high_price")),
        target_low_price=_optional_float(payload.get("target_low_price")),
        notify_on_custom_high=_bool(payload.get("notify_on_custom_high", False)),
        notify_on_custom_low=_bool(payload.get("notify_on_custom_low", False)),
        notify_on_predicted_high=_bool(payload.get("notify_on_predicted_high", True)),
        notify_on_predicted_low=_bool(payload.get("notify_on_predicted_low", True)),
        created_at=created_at,
        updated_at=updated_at,
    )


def _rule_from_row(row: sqlite3.Row) -> AlertRule:
    return AlertRule(
        id=int(row["id"]),
        enabled=bool(row["enabled"]),
        source=row["source"],
        recipient_email=row["recipient_email"],
        target_high_price=row["target_high_price"],
        target_low_price=row["target_low_price"],
        notify_on_custom_high=bool(row["notify_on_custom_high"]),
        notify_on_custom_low=bool(row["notify_on_custom_low"]),
        notify_on_predicted_high=bool(row["notify_on_predicted_high"]),
        notify_on_predicted_low=bool(row["notify_on_predicted_low"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _rule_values(rule: AlertRule) -> tuple[Any, ...]:
    return (
        int(rule.enabled),
        rule.source,
        rule.recipient_email,
        rule.target_high_price,
        rule.target_low_price,
        int(rule.notify_on_custom_high),
        int(rule.notify_on_custom_low),
        int(rule.notify_on_predicted_high),
        int(rule.notify_on_predicted_low),
        rule.created_at or _now_text(),
        rule.updated_at or _now_text(),
    )


def _event_to_dict(event: AlertEvent) -> dict[str, Any]:
    return asdict(event)


def rule_to_dict(rule: AlertRule) -> dict[str, Any]:
    return asdict(rule)


def state_to_dict(state: AlertState) -> dict[str, Any]:
    return asdict(state)


def event_to_dict(event: AlertEvent) -> dict[str, Any]:
    return _event_to_dict(event)


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _now_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _resolve_db_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
