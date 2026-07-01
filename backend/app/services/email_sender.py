from __future__ import annotations

import os
import ssl
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Mapping, Optional


class EmailConfigError(RuntimeError):
    pass


class EmailSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    envelope_from_email: str = ""
    use_tls: bool = True
    use_ssl: bool = False


ALERT_KIND_LABELS = {
    "custom_high": "预设清仓价格提醒",
    "custom_low": "预设抄底价格提醒",
    "predicted_high_touch": "预估高点首次触达",
    "predicted_high_breakout": "预估高点继续突破",
    "predicted_low_touch": "预估低点首次触达",
    "predicted_low_breakout": "预估低点继续突破",
    "test": "测试邮件",
}

DEFAULT_FROM_NAME = "黄金价格-波动通知"


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

    use_ssl = _bool(
        _env_value(env, email_config.get("use_ssl_env", "ALERT_SMTP_USE_SSL")),
        default=port == 465,
    )

    return EmailConfig(
        host=host,
        port=port,
        username=_env_value(env, email_config.get("smtp_username_env", "ALERT_SMTP_USERNAME")) or "",
        password=_env_value(env, email_config.get("smtp_password_env", "ALERT_SMTP_PASSWORD")) or "",
        from_email=from_email,
        envelope_from_email=_env_value(
            env,
            email_config.get("envelope_from_email_env", "ALERT_ENVELOPE_FROM_EMAIL"),
        ),
        use_tls=_bool(_env_value(env, email_config.get("use_tls_env", "ALERT_SMTP_USE_TLS")), default=True),
        use_ssl=use_ssl,
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
    message["From"] = formataddr((DEFAULT_FROM_NAME, from_email))
    message["To"] = recipient_email
    message.set_content("\n".join(lines))
    return message


def build_verification_email_message(
    *,
    recipient_email: str,
    from_email: str,
    code: str,
    expires_minutes: int,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "黄金价格-波动通知：邮箱验证码"
    message["From"] = formataddr((DEFAULT_FROM_NAME, from_email))
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "你正在为黄金价格提醒绑定邮箱。",
                "",
                f"验证码：{code}",
                f"有效期：{expires_minutes} 分钟",
                "",
                "如果不是你本人操作，可以忽略这封邮件。",
            ]
        )
    )
    return message


def send_email(config: EmailConfig, message: EmailMessage) -> None:
    stage = "connect"
    try:
        connector = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
        kwargs: dict[str, Any] = {"timeout": 10}
        if config.use_ssl:
            kwargs["context"] = ssl.create_default_context()
        with connector(config.host, config.port, **kwargs) as smtp:
            if config.use_tls and not config.use_ssl:
                stage = "starttls"
                smtp.starttls()
            if config.username and config.password:
                stage = "login"
                smtp.login(config.username, config.password)
            stage = "send"
            smtp.send_message(
                message,
                from_addr=config.envelope_from_email or config.from_email,
            )
    except smtplib.SMTPServerDisconnected as exc:
        if stage == "send":
            raise EmailSendError(
                "SMTP服务器已登录，但发信阶段被服务商断开。"
                "常见原因是发件人不被允许、邮箱服务商风控或短时间发送过于频繁；"
                "请检查 ALERT_FROM_EMAIL / ALERT_ENVELOPE_FROM_EMAIL，稍后重试或更换 SMTP 服务。"
            ) from exc
        raise EmailSendError(f"SMTP连接在{stage}阶段被服务商断开：{exc}") from exc
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailSendError("SMTP认证失败，请检查邮箱账号、密码或客户端授权码。") from exc
    except smtplib.SMTPSenderRefused as exc:
        raise EmailSendError(f"SMTP服务商拒绝当前发件人：{exc.smtp_error!r}") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EmailSendError(f"SMTP服务商拒绝当前收件人：{exc.recipients!r}") from exc
    except smtplib.SMTPException as exc:
        raise EmailSendError(f"SMTP发送失败：{exc}") from exc


def _env_value(environ: Mapping[str, str], name: Any) -> str:
    return str(environ.get(str(name), "")).strip()


def _bool(value: Optional[str], *, default: bool) -> bool:
    if value in (None, ""):
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}
