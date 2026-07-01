from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Mapping, Optional


class EmailConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_tls: bool = True


ALERT_KIND_LABELS = {
    "custom_high": "自定义高价提醒",
    "custom_low": "自定义低价提醒",
    "predicted_high_touch": "预估高点首次触达",
    "predicted_high_breakout": "预估高点继续突破",
    "predicted_low_touch": "预估低点首次触达",
    "predicted_low_breakout": "预估低点继续突破",
    "test": "测试邮件",
}


def build_email_config(email_config: dict[str, Any], environ: Optional[Mapping[str, str]] = None) -> EmailConfig:
    env = environ or os.environ
    host = _env_value(env, email_config.get("smtp_host_env", "ALERT_SMTP_HOST"))
    if not host:
        raise EmailConfigError("SMTP host is not configured")

    from_email = _env_value(env, email_config.get("from_email_env", "ALERT_FROM_EMAIL"))
    if not from_email:
        raise EmailConfigError("alert from email is not configured")

    port_text = _env_value(env, email_config.get("smtp_port_env", "ALERT_SMTP_PORT")) or "587"
    try:
        port = int(port_text)
    except ValueError as exc:
        raise EmailConfigError(f"invalid SMTP port: {port_text}") from exc

    return EmailConfig(
        host=host,
        port=port,
        username=_env_value(env, email_config.get("smtp_username_env", "ALERT_SMTP_USERNAME")) or "",
        password=_env_value(env, email_config.get("smtp_password_env", "ALERT_SMTP_PASSWORD")) or "",
        from_email=from_email,
        use_tls=_bool(_env_value(env, email_config.get("use_tls_env", "ALERT_SMTP_USE_TLS")), default=True),
    )


def build_alert_email_message(
    *,
    recipient_email: str,
    from_email: str,
    alert_kind: str,
    source_label: str,
    current_price: float,
    display_unit: str,
    predicted_range: Optional[dict[str, Any]],
    target_price: Optional[float],
    event_time: str,
    rule_id: Optional[int],
) -> EmailMessage:
    label = ALERT_KIND_LABELS.get(alert_kind, alert_kind)
    subject = f"黄金价格提醒：{label}"
    lines = [
        f"提醒类型：{label}",
        f"当前价格：{current_price:.2f} {display_unit}",
        f"行情源：{source_label}",
        f"触发时间：{event_time}",
    ]
    if target_price is not None:
        lines.append(f"目标价格：{float(target_price):.2f} {display_unit}")
    if predicted_range:
        high = predicted_range.get("high")
        low = predicted_range.get("low")
        if high is not None:
            lines.append(f"系统预估高点：{float(high):.2f} {display_unit}")
        if low is not None:
            lines.append(f"系统预估低点：{float(low):.2f} {display_unit}")
    if rule_id is not None:
        lines.append(f"提醒规则：#{rule_id}")
    lines.append("")
    lines.append("风险提示：数据仅供参考，不构成投资建议。")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = recipient_email
    message.set_content("\n".join(lines))
    return message


def send_email(config: EmailConfig, message: EmailMessage) -> None:
    with smtplib.SMTP(config.host, config.port, timeout=10) as smtp:
        if config.use_tls:
            smtp.starttls()
        if config.username and config.password:
            smtp.login(config.username, config.password)
        smtp.send_message(message)


def _env_value(environ: Mapping[str, str], name: Any) -> str:
    return str(environ.get(str(name), "")).strip()


def _bool(value: Optional[str], *, default: bool) -> bool:
    if value in (None, ""):
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}
