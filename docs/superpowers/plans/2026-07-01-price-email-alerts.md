# 价格邮件提醒实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现单用户价格邮件提醒：自定义高低价、预估高低点首次触达、以及每继续突破 `2 CNY/g` 的阶梯通知。

**Architecture:** 后端负责预估区间计算、提醒规则存储、触发判断、SMTP 发送和后台定时检查；前端只展示后端返回的预估区间，并提供提醒设置面板。规则和状态使用 SQLite，遵循现有 K 线存储的轻量本地模式。

**Tech Stack:** FastAPI, Python stdlib sqlite3/smtplib/email, PyYAML, Vue 3, Vite, Playwright, Python unittest.

---

### Task 1: 后端预估区间计算

**Files:**
- Create: `backend/app/services/predicted_range.py`
- Modify: `backend/app/api.py`
- Test: `backend/tests/test_market_logic.py`

- [ ] **Step 1: Write failing backend tests**

Add tests that assert backend predicted range matches the existing frontend examples:

```python
from backend.app.services.predicted_range import build_predicted_daily_range, build_today_range

def test_predicted_daily_range_centers_on_current_price_without_candles(self):
    result = build_predicted_daily_range(885.53, range_percent=0.02)
    self.assertEqual(result["low"], 876.76)
    self.assertEqual(result["high"], 894.3)

def test_predicted_daily_range_includes_observed_high_or_low(self):
    now = datetime(2026, 6, 29, 12, 0)
    candles = [
        {"time": "2026-06-29T09:30:00", "open": 550, "high": 552, "low": 549, "close": 551},
        {"time": "2026-06-29T09:31:00", "open": 551, "high": 553, "low": 550, "close": 552},
    ]
    self.assertEqual(build_predicted_daily_range(580, 0.02, candles, now), {"low": 545.02, "high": 580, "range_percent": 0.02})
    self.assertEqual(build_predicted_daily_range(520, 0.02, candles, now), {"low": 520, "high": 555.92, "range_percent": 0.02})
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

Expected: import error for `backend.app.services.predicted_range`.

- [ ] **Step 3: Implement predicted range service and snapshot response**

Port the logic from `frontend/src/utils/dayRange.js` into `backend/app/services/predicted_range.py`. In `backend/app/api.py`, compute `predicted_range` after `today_range` is available and include it in `/api/market/snapshot`.

- [ ] **Step 4: Verify backend tests pass**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

Expected: all backend tests pass.

### Task 2: 提醒触发逻辑和 SQLite 存储

**Files:**
- Create: `backend/app/services/alerts.py`
- Test: `backend/tests/test_market_logic.py`

- [ ] **Step 1: Write failing alert tests**

Add tests for custom thresholds, first predicted high/low touch, and `2 CNY/g` step behavior:

```python
from backend.app.services.alerts import AlertRule, AlertState, evaluate_alert_rule

def test_predicted_high_first_touch_then_two_yuan_steps(self):
    rule = AlertRule(id=1, source="icbc", recipient_email="me@example.com", notify_on_predicted_high=True)
    state = AlertState(rule_id=1, source="icbc", alert_date="2026-07-01")
    first = evaluate_alert_rule(rule, state, current_price=890, predicted_range={"high": 890, "low": 880}, step=2)
    self.assertEqual([event.kind for event in first.events], ["predicted_high_touch"])
    second = evaluate_alert_rule(rule, first.state, current_price=891, predicted_range={"high": 890, "low": 880}, step=2)
    self.assertEqual(second.events, [])
    third = evaluate_alert_rule(rule, second.state, current_price=892, predicted_range={"high": 890, "low": 880}, step=2)
    self.assertEqual([event.kind for event in third.events], ["predicted_high_breakout"])
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

Expected: import error for `backend.app.services.alerts`.

- [ ] **Step 3: Implement alerts service**

Create dataclasses for `AlertRule`, `AlertState`, `AlertEvent`, `EvaluationResult`, plus an `AlertStore` that creates `alert_rules` and `alert_states` tables and supports list/create/update/delete/state save operations.

- [ ] **Step 4: Verify backend tests pass**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

Expected: alert trigger tests and existing tests pass.

### Task 3: 邮件发送、API 和后台 worker

**Files:**
- Create: `backend/app/services/email_sender.py`
- Create: `backend/app/alert_worker.py`
- Modify: `backend/app/api.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_market_logic.py`

- [ ] **Step 1: Write failing tests**

Add tests for missing SMTP config, mocked send, and API helper behavior:

```python
from backend.app.services.email_sender import EmailConfigError, build_email_config

def test_email_config_requires_smtp_host(self):
    with self.assertRaises(EmailConfigError):
        build_email_config({"smtp_host_env": "MISSING_SMTP_HOST"}, environ={})
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

Expected: import error for `backend.app.services.email_sender`.

- [ ] **Step 3: Implement email sender and alert APIs**

Use stdlib `smtplib` and `email.message.EmailMessage`. Add authenticated endpoints:

- `GET /api/alerts/rules`
- `POST /api/alerts/rules`
- `PUT /api/alerts/rules/{id}`
- `DELETE /api/alerts/rules/{id}`
- `POST /api/alerts/test-email`

Add a FastAPI lifespan task in `backend/app/main.py` that starts the worker only when `alerts.enabled` is true.

- [ ] **Step 4: Verify backend tests pass**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

Expected: backend tests pass.

### Task 4: 前端 API 和面板

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/tests/e2e/dashboard.spec.js`

- [ ] **Step 1: Write failing Playwright test**

Add routes for `/api/alerts/rules` and `/api/alerts/test-email`. Assert the panel renders, saves a rule, and shows test email result.

- [ ] **Step 2: Verify test fails**

Run: `cd frontend && npx playwright test tests/e2e/dashboard.spec.js --project=chromium`

Expected: alert panel locators not found.

- [ ] **Step 3: Implement frontend API helpers and panel**

Add `getAlertRules`, `createAlertRule`, `updateAlertRule`, `deleteAlertRule`, and `sendTestEmail` helpers. Add a compact alert panel in `App.vue` with email, high/low inputs, toggles, save, delete, and test email actions. Use backend `snapshot.predicted_range` for the price-card predicted high/low display, with the existing front-end calculation as fallback during migration.

- [ ] **Step 4: Verify frontend tests pass**

Run: `cd frontend && npm test && npx playwright test tests/e2e/dashboard.spec.js --project=chromium`

Expected: unit and e2e tests pass.

### Task 5: 配置、Docker 和文档

**Files:**
- Modify: `config.yaml`
- Modify: `docker-compose.yml`
- Modify: `docs/CONFIGURATION.md`
- Modify: `docs/API.md`

- [ ] **Step 1: Add config defaults**

Add `alerts` defaults to `config.yaml` with `enabled: false`, `check_interval_seconds: 15`, `predicted_breakout_step_cny_g: 2`, and SMTP env names.

- [ ] **Step 2: Document API and environment variables**

Update docs with alert endpoints, SMTP environment variables, and the `predicted_range` snapshot field.

- [ ] **Step 3: Verify docs/config are parseable**

Run: `python - <<'PY'\nfrom backend.app.core.config import load_config\nload_config.cache_clear()\nconfig = load_config()\nassert config['alerts']['predicted_breakout_step_cny_g'] == 2\nprint('ok')\nPY`

Expected: prints `ok`.

### Task 6: Final verification and commit

**Files:**
- All changed files

- [ ] **Step 1: Run full backend tests**

Run: `python -m pytest backend/tests/test_market_logic.py -q`

- [ ] **Step 2: Run frontend unit tests**

Run: `cd frontend && npm test`

- [ ] **Step 3: Run targeted Playwright tests**

Run: `cd frontend && npx playwright test tests/e2e/dashboard.spec.js --project=chromium`

- [ ] **Step 4: Review diff and commit only related files**

Run: `git diff --stat` and ensure unrelated existing frontend work is not accidentally reverted. Commit the implementation with `git commit -m "feat: add price email alerts"`.
