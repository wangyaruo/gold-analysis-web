# Gold Analysis Web Design

## Scope

Build a greenfield full-stack web application in the current directory without using git. The system provides realtime gold prices, chart visualization, configurable stop-loss calculation, structured buy recommendations, keyword-based news sentiment, portfolio PnL, authentication, tests, and deployment documentation.

## Architecture

Frontend lives in `frontend/` as a Vue 3 + Vite app. Backend lives in `backend/` as a FastAPI app. Business configuration is centralized in root `config.yaml`, while API keys and bearer tokens are injected through environment variables.

## Data Flow

The browser polls `/api/market/snapshot` every 10 seconds. The backend fetches a price tick from the active configured provider, validates freshness within 5 seconds, computes indicators and recommendation state, fetches or falls back to demo news, analyzes sentiment, and returns one consolidated snapshot.

## Resilience

The price provider supports exponential backoff with configurable attempts. Validation rejects unreasonable prices and stale timestamps. Data parsing failures are logged with structured JSON context. Demo fallbacks keep local development usable without external API keys.

## Testing

Backend unit tests cover business formulas and rules using Python `unittest`. Frontend Playwright tests mock API responses and verify dashboard rendering and PnL behavior.
