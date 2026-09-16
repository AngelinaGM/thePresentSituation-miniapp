# Party Wishlist — Telegram Mini App

FastAPI backend for anonymous gift reservations. The existing frontend remains in `public/`; PostgreSQL access uses SQLAlchemy 2 and Alembic.

## Local run

1. Install Python 3.11+ and PostgreSQL.
2. Create a virtual environment, then run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `DATABASE_URL`, `BOT_TOKEN`, `BOT_USERNAME`, `APP_URL`, and `SESSION_SECRET`.
4. Run `alembic upgrade head`.
5. Start with `uvicorn app.main:app --reload --port 8000`.

Telegram Mini Apps require HTTPS; use an HTTPS tunnel for local testing.

## Railway

Create and link a Railway PostgreSQL service (it supplies `DATABASE_URL`). Add `BOT_TOKEN`, `BOT_USERNAME`, `APP_URL`, and `SESSION_SECRET` as Railway variables. `railway.toml` runs `alembic upgrade head` before Uvicorn and checks `/health`. No deployment is performed automatically.

## Rules

- The initial migration creates `users`, `wishlists`, `gifts`, and `reservations`.
- A database-level unique `reservations.gift_id` prevents double booking.
- Owners cannot reserve their own gifts; guests can cancel only their own reservation.
- Owner responses never expose reservation state, availability, or guest identity.
- `status` and `party_at` are included; future X/Y time limits are deliberately not implemented yet.
