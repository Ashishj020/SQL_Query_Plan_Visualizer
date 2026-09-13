# Planlight

SQL execution-plan analyzer and optimizer advisor. Paste a `SELECT`, run **Analyze plan**, and Planlight executes `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` against Postgres, turns the plan into a cost-colored D3 tree, and writes copy-paste index / query fixes from a rule engine.

The UI follows a **dark glass** system (Space Grotesk / Manrope / JetBrains Mono, teal → amber → rose by cost).

## Stack

- **Backend:** FastAPI + psycopg — sanitize SQL, `EXPLAIN ANALYZE`, parse the JSON tree, rule-based advisor
- **Frontend:** Vite + React + Monaco + D3
- **Database:** Postgres 16 with a seeded shop schema (no secondary indexes on purpose)

## Quick start

Postgres must be empty on first boot so the init scripts can load (~40k customers, 10k products, 180k orders, 540k items, 250k reviews). First `docker compose up` takes a minute.

```bash
docker compose up -d postgres
```

Wait until `docker compose logs postgres` shows `database system is ready` and the seed has finished (`ANALYZE reviews`).

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Use the sample chips or paste your own read-only `SELECT` / `WITH`.

Postgres is published on **5433** so it does not collide with another local instance on 5432. Override `DATABASE_URL` if you already have a shop database elsewhere.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Postgres connectivity |
| `GET` | `/api/samples` | Five demo queries |
| `POST` | `/api/analyze` | `{ "sql": "...", "analyze": true }` |

Only a single `SELECT` or `WITH` is accepted. The service sets `default_transaction_read_only` and a statement timeout.

## Advisor rules

- Sequential scans on large / high-cost relations → `CREATE INDEX`
- `LIKE` / `ILIKE '%…%'` → `pg_trgm` GIN
- Nested loops that re-scan the inner side → index the join key
- Expensive `Sort` → index `ORDER BY` keys
- Estimate vs actual mismatch → `ANALYZE`
- High rows-removed-by-filter, hash spills, CTE materialization, heap fetches on index-only scans
- Any node ≥ 30% exclusive cost is flagged as a hotspot

## Five slow queries

See [BENCHMARKS.md](BENCHMARKS.md) for measured before/after times. The benchmark script applies the recommended indexes, times the same (or rewritten) SQL, then **drops the indexes again** so the live UI still shows the slow plans.

```bash
cd backend
python scripts/benchmark.py
```

## Safety

`EXPLAIN ANALYZE` **executes** the query. Planlight rejects DML/DDL and forces a read-only session, but a heavy `SELECT` can still run until the timeout. Point `DATABASE_URL` at a replica or a disposable local database.
