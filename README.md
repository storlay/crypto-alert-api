# CryptoAlert API

Async FastAPI service that streams 1-minute candles for BTC/ETH/SOL/BNB/XRP from
Binance, lets authenticated users create price alerts, broadcasts live prices
over WebSocket, and notifies users in Telegram when alerts fire.

## Stack

- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg, Alembic
- PostgreSQL 16, Redis 7
- aiogram 3 (Telegram bot)
- slowapi (rate limiting), PyJWT, bcrypt
- pytest + pytest-asyncio + testcontainers
- `uv` for dependency management

## Project layout

```
src/
  main.py            FastAPI app factory + lifespan
  config.py          Pydantic Settings (.env)
  container.py       Shared engine/redis/ws state
  db.py / deps.py    DB session and DI helpers
  models.py          User, Alert, Candle1m
  schemas.py         Pydantic request/response models
  security.py        bcrypt + JWT
  limits.py          slowapi limiter
  routers/           auth, me, alerts, prices, ws, health
  services/          binance consumer, alert checker, ws broadcaster
  telegram_bot.py    aiogram polling bot
  migrations/        Alembic migrations
tests/               pytest suite (testcontainers-backed)
```

## Environment

Copy `.env.example` to `.env` and fill in the values.

```
POSTGRES_USER=crypto
POSTGRES_PASSWORD=crypto
POSTGRES_DB=crypto

DATABASE_URL=postgresql+asyncpg://crypto:crypto@postgres:5432/crypto
REDIS_URL=redis://redis:6379/0

JWT_SECRET=change-me
JWT_TTL_MIN=1440
TELEGRAM_BOT_TOKEN=your-tg-bot-token
MAX_ALERTS_PER_USER=20
```

For local (non-Docker) runs, change hosts to `localhost`:
`postgresql+asyncpg://crypto:crypto@localhost:5432/crypto` and
`redis://localhost:6379/0`.

## Run with Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build         # postgres + redis + migrate + api
docker compose --profile bot up   # add the Telegram bot
```

API will be available at `http://localhost:8000`, OpenAPI docs at
`http://localhost:8000/docs`. The `migrate` service runs `alembic upgrade head`
before the API starts.

Stop and clean up:

```bash
docker compose down          # keep data
docker compose down -v       # drop the postgres volume
```

## Run locally

Requires `uv` (https://docs.astral.sh/uv/) and running Postgres + Redis
(easiest: `docker compose up postgres redis`).

```bash
uv sync                              # install deps into .venv
uv run alembic upgrade head          # apply migrations
uv run uvicorn src.main:app --reload # start API
uv run python -m src.telegram_bot    # start Telegram bot (separate process)
```

## Migrations

```bash
uv run alembic upgrade head
uv run alembic revision -m "message" --autogenerate
uv run alembic downgrade -1
```

## Tests

The suite spins up Postgres and Redis via `testcontainers`, so Docker must be
running.

```bash
uv run pytest
uv run pytest --cov=src
uv run pytest tests/test_alerts.py -k create
```

## Lint / typecheck

```bash
uv run ruff check
uv run ruff format
uv run pyright
```

## API overview

Base URL: `http://localhost:8000`. Auth: `Authorization: Bearer <jwt>` from
`/auth/login`.

| Method | Path                       | Description                       |
| ------ | -------------------------- | --------------------------------- |
| POST   | `/auth/register`           | Register by email + password      |
| POST   | `/auth/login`              | Get JWT                           |
| PATCH  | `/me`                      | Bind Telegram chat via link code  |
| POST   | `/alerts`                  | Create price alert                |
| GET    | `/alerts?status=active`    | List user alerts                  |
| DELETE | `/alerts/{id}`             | Cancel an active alert            |
| GET    | `/prices/{coin}/history`   | 1m candles for last `hours` (1–168) |
| WS     | `/ws/prices?token=<jwt>`   | Live prices; client sends `{"subscribe":["BTC","ETH"]}` |
| GET    | `/healthz` / `/readyz`     | Liveness / readiness              |

Supported coins: `BTC`, `ETH`, `SOL`, `BNB`, `XRP`.

### Quick example

```bash
curl -X POST localhost:8000/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"u@example.com","password":"password123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"u@example.com","password":"password123"}' | jq -r .access_token)

curl -X POST localhost:8000/alerts \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"coin":"BTC","direction":"above","threshold":"70000"}'
```

### Telegram linking

1. Start the bot (`docker compose --profile bot up` or `python -m src.telegram_bot`).
2. Send `/start` to the bot — it replies with a one-time `link_code` (TTL 10 min).
3. Call `PATCH /me` with `{"link_code": "<code>"}`. Triggered alerts will be
   delivered to that chat.

## Background workers

Started inside the API process by the FastAPI lifespan:

- `binance_consumer` — Binance WS → 1m candles in Postgres + Redis pub/sub.
- `alert_checker` — evaluates active alerts on each new price.
- `ws_broadcaster` — fans out price updates to connected WebSocket clients.
