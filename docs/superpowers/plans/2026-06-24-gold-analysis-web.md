# Gold Analysis Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a maintainable full-stack gold analysis application with realtime display, configurable indicators, recommendations, PnL, tests, and docs.

**Architecture:** Vue 3 + Vite frontend polls a FastAPI backend. The backend reads all business parameters from root `config.yaml`, injects secrets through environment variables, validates market data, and exposes authenticated APIs.

**Tech Stack:** Vue 3, Vite, JavaScript, Playwright, Python 3, FastAPI, httpx, PyYAML, Docker.

---

### Task 1: Backend Business Logic

**Files:**
- Create: `backend/tests/test_market_logic.py`
- Create: `backend/app/services/indicators.py`
- Create: `backend/app/services/sentiment.py`
- Create: `backend/app/services/decision.py`
- Create: `backend/app/services/pnl.py`
- Create: `backend/app/services/validation.py`

- [x] Write failing unit tests for indicators, sentiment, recommendations, PnL, and validation.
- [x] Run `python3 -m unittest backend.tests.test_market_logic -v` and confirm module import failure.
- [x] Implement minimal services.
- [x] Re-run unit tests and confirm 10 tests pass.

### Task 2: Backend API

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/api.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/auth.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/services/data_provider.py`
- Create: `backend/app/services/news_provider.py`
- Create: `backend/app/services/market_math.py`
- Create: `backend/requirements.txt`

- [x] Add YAML config loader.
- [x] Add bearer token authentication.
- [x] Add price provider with demo and HTTP modes.
- [x] Add retry and structured logging.
- [x] Add market snapshot, public config, health, and PnL endpoints.

### Task 3: Frontend Dashboard

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/src/main.js`
- Create: `frontend/src/api.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/components/PriceChart.vue`
- Create: `frontend/src/styles.css`

- [x] Build realtime dashboard layout.
- [x] Add loading and connection interrupted indicators.
- [x] Render price, chart, stop-loss, signals, sentiment, recommendation, and PnL form.
- [x] Poll every configured refresh interval.

### Task 4: Frontend E2E Tests

**Files:**
- Create: `frontend/playwright.config.js`
- Create: `frontend/tests/e2e/dashboard.spec.js`

- [x] Mock API responses.
- [x] Verify snapshot rendering.
- [x] Verify PnL calculation workflow.

### Task 5: Documentation and Deployment

**Files:**
- Create: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/CONFIGURATION.md`
- Create: `docs/API.md`
- Create: `docs/DEPLOYMENT.md`
- Create: `docs/TESTING.md`
- Create: `Dockerfile.backend`
- Create: `Dockerfile.frontend`
- Create: `docker-compose.yml`

- [x] Document architecture and data flow.
- [x] Document formulas and strategy effects.
- [x] Document API, config, tests, and deployment.
- [x] Run available verification commands.
