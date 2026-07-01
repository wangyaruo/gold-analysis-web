# Price Email Alerts Design

## Scope

Add a single-user email notification feature for the existing gold analysis dashboard. The feature lets the user receive email when the live display price reaches custom thresholds or crosses the system-predicted daily high/low range. It builds on the current FastAPI backend, Vue dashboard, `config.yaml` business configuration, and existing realtime market polling flow.

This design does not introduce multi-user login, account ownership, SMS, push notifications, or brokerage/trading actions.

## Goals

- Let the user configure one or more email alert rules from the dashboard.
- Send email when the current display price reaches a user-defined high or low target.
- Send email when the current display price first touches the system-predicted high or low.
- Continue sending email when price keeps moving beyond the touched predicted boundary by each additional `2 CNY/g` step.
- Keep alert decisions on the backend so notifications work even when the browser is closed.
- Use one shared predicted range calculation for both dashboard display and email alert evaluation.

## Architecture

The backend owns alert evaluation. A new alert service periodically fetches the active price source, computes the same display price and predicted daily range used by the UI, evaluates enabled alert rules, and sends email through SMTP when a rule fires.

The current frontend predicted range calculation in `frontend/src/utils/dayRange.js` should be ported to a backend service, then returned from `/api/market/snapshot` as `predicted_range`. The frontend should render that backend value instead of computing its own independent range. This prevents the screen and email engine from disagreeing.

Recommended backend units:

- `backend/app/services/predicted_range.py`: builds today range and predicted daily range from candles, current price, and source-provided day range.
- `backend/app/services/alerts.py`: stores alert rules and alert state, evaluates trigger conditions, and produces notification events.
- `backend/app/services/email_sender.py`: sends email using SMTP configuration and logs delivery failures.
- `backend/app/alert_worker.py` or a FastAPI lifespan task: runs alert checks at the configured interval.

## Configuration

Add an `alerts` section to `config.yaml`:

```yaml
alerts:
  enabled: false
  check_interval_seconds: 15
  predicted_breakout_step_cny_g: 2
  storage_path: "data/price_alerts.sqlite"
  default_source: "icbc"
  email:
    smtp_host_env: "ALERT_SMTP_HOST"
    smtp_port_env: "ALERT_SMTP_PORT"
    smtp_username_env: "ALERT_SMTP_USERNAME"
    smtp_password_env: "ALERT_SMTP_PASSWORD"
    from_email_env: "ALERT_FROM_EMAIL"
    use_tls_env: "ALERT_SMTP_USE_TLS"
```

SMTP secrets stay in environment variables and Docker environment wiring, not in `config.yaml`.

## Alert Rule Model

Store rules and state in SQLite under the configured `storage_path`, matching the existing lightweight local storage style used for K-lines.

Rule fields:

- `id`
- `enabled`
- `source`
- `recipient_email`
- `target_high_price`
- `target_low_price`
- `notify_on_custom_high`
- `notify_on_custom_low`
- `notify_on_predicted_high`
- `notify_on_predicted_low`
- `created_at`
- `updated_at`

State fields:

- `rule_id`
- `source`
- `alert_date`
- `last_custom_high_alert_price`
- `last_custom_low_alert_price`
- `last_predicted_high_alert_price`
- `last_predicted_low_alert_price`
- `last_predicted_high_value`
- `last_predicted_low_value`
- `last_alerted_at`

The `last_predicted_high_value` and `last_predicted_low_value` fields record the predicted boundary involved in the most recent evaluation, while `last_predicted_*_alert_price` records the price level that last generated an email. Predicted-boundary state is scoped by `source` and `alert_date` in Asia/Shanghai. A new date or source starts a fresh first-touch cycle.

## Trigger Rules

All comparisons use display prices in `CNY/g`, because the dashboard shows and the user thinks in that unit.

### Custom Target Alerts

If `notify_on_custom_high` is enabled and `current_price >= target_high_price`, send a custom high email once for that target crossing. If the user edits the target price, reset the corresponding custom alert state.

If `notify_on_custom_low` is enabled and `current_price <= target_low_price`, send a custom low email once for that target crossing. If the user edits the target price, reset the corresponding custom alert state.

### Predicted High Alerts

If `notify_on_predicted_high` is enabled and `current_price >= predicted_range.high`:

1. If `last_predicted_high_alert_price` is empty, send the first predicted high touch email immediately.
2. Otherwise, send another email only when `current_price >= last_predicted_high_alert_price + predicted_breakout_step_cny_g`.
3. After sending, set `last_predicted_high_alert_price` to the current price and store the current `predicted_range.high`.

Example with predicted high `890 CNY/g` and step `2 CNY/g`:

- `890`: send first touch email.
- `891`: no email.
- `892`: send breakout email.
- `893`: no email.
- `894`: send breakout email.

### Predicted Low Alerts

If `notify_on_predicted_low` is enabled and `current_price <= predicted_range.low`:

1. If `last_predicted_low_alert_price` is empty, send the first predicted low touch email immediately.
2. Otherwise, send another email only when `current_price <= last_predicted_low_alert_price - predicted_breakout_step_cny_g`.
3. After sending, set `last_predicted_low_alert_price` to the current price and store the current `predicted_range.low`.

Example with predicted low `880 CNY/g` and step `2 CNY/g`:

- `880`: send first touch email.
- `879`: no email.
- `878`: send breakout email.
- `877`: no email.
- `876`: send breakout email.

There is no time-based cooldown for predicted boundary alerts. Duplicate protection is based only on the `2 CNY/g` price step.

There is no separate "predicted range updated" email. A changed predicted high or low only matters when the current price reaches that latest boundary or extends another `2 CNY/g` beyond the last notified price.

## API Design

Add authenticated endpoints under the existing bearer-token API:

- `GET /api/alerts/rules`: list alert rules and current state summary.
- `POST /api/alerts/rules`: create a rule.
- `PUT /api/alerts/rules/{id}`: update a rule and reset affected state when thresholds change.
- `DELETE /api/alerts/rules/{id}`: delete a rule.
- `POST /api/alerts/test-email`: send a test email using the configured SMTP settings.

Extend `GET /api/market/snapshot` with:

```json
{
  "predicted_range": {
    "low": 878.12,
    "high": 895.68,
    "range_percent": 0.02,
    "unit": "CNY/g"
  }
}
```

## Frontend Design

Add a compact alert settings panel to the dashboard rather than a separate marketing-like page. It should support:

- Recipient email input.
- Source selector using the existing public source options.
- Custom high and low target inputs.
- Toggles for custom high, custom low, predicted high, and predicted low alerts.
- Save, disable, delete, and test email actions.
- A small status line showing whether SMTP is configured and when the last alert was sent.

The existing price card should continue to show predicted high and low, but it should read from `snapshot.predicted_range` once the backend owns the calculation.

## Email Content

Each alert email should include:

- Alert type, such as custom high, custom low, predicted high touch, predicted high breakout, predicted low touch, or predicted low breakout.
- Current display price and unit.
- Price source label.
- Predicted high and low when available.
- Custom target price when relevant.
- Event time in Asia/Shanghai.
- A short risk disclaimer that data is for reference only and not investment advice.

## Error Handling

- If SMTP is not configured, alert rules may still be saved, but sending test email and runtime delivery should return or log a clear configuration error.
- If price fetching fails during an alert worker tick, log the failure and retry on the next interval.
- If one rule fails to send email, continue evaluating other enabled rules.
- If predicted range cannot be computed, skip predicted-boundary rules for that tick but still evaluate custom target rules.

## Testing

Backend tests should cover:

- Predicted range calculation parity with existing frontend examples.
- Custom high and custom low trigger behavior.
- First predicted high/low touch sends immediately.
- Predicted high sends again only after each additional `2 CNY/g` rise from the last high alert price.
- Predicted low sends again only after each additional `2 CNY/g` fall from the last low alert price.
- No time cooldown is applied to predicted boundary alerts.
- SMTP send is mocked and delivery failures do not crash the worker.

Frontend tests should cover:

- Rendering the alert settings panel.
- Saving an alert rule through the API.
- Showing backend-provided `predicted_range`.
- Sending a test email action and surfacing success or failure.

## Rollout

Implement in this order:

1. Move predicted range calculation to backend and expose it in snapshot.
2. Add alert rule/state storage and pure trigger evaluation tests.
3. Add SMTP email sender and test-email endpoint.
4. Add background worker.
5. Add frontend alert settings panel.
6. Update docs, Docker environment examples, and tests.
