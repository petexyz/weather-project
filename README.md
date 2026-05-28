# Lowell Weather

A self-hosted weather data pipeline that collects real-time observations for
Lowell, MA from the [Tomorrow.io](https://www.tomorrow.io/) API, stores them
both as JSON files and in a TimescaleDB hypertable, and serves a live dashboard.

## Architecture

```
                 ┌──────────────┐   every COLLECTION_INTERVAL seconds
                 │  Tomorrow.io │◀──────────────┐
                 │  realtime API│               │
                 └──────────────┘               │
                                                │
   ┌───────────────────────────────────────────┴───────┐
   │ collector (weather_collector.py)                   │
   │  1. fetch reading                                  │
   │  2. save JSON  → weather_data/YYYYMM/YYYYMMDD/...   │  ← source of truth
   │  3. insert row → TimescaleDB                        │
   └───────────────────────────┬────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ TimescaleDB (PG14)  │  weather_readings hypertable
                    │ derived store       │  (compressed after 7 days)
                    └──────────┬──────────┘
                               │ read-only
                    ┌──────────▼──────────┐
                    │ web (FastAPI)       │  JSON API + dashboard
                    │ localhost:8080      │
                    └─────────────────────┘
```

**Key property:** the JSON files in `weather_data/` are the **source of truth**.
The database is a derived store that can be fully rebuilt from those files at any
time via `import_historical.py` (see [Backup & recovery](#backup--recovery)).

## Project structure

```
weather-project/
├── collector/                # Data collection service
│   ├── weather_collector.py  # Main collection loop (entrypoint)
│   ├── import_historical.py  # Rebuilds the DB from JSON files
│   ├── database.py           # Connection pool + insert
│   ├── config.py             # Env-driven configuration
│   ├── logger.py             # Colored console + file logging
│   ├── requirements.txt
│   └── Dockerfile
├── web/                      # Dashboard service
│   ├── app.py                # FastAPI app + routes (entrypoint)
│   ├── database.py           # Connection pool + read queries
│   ├── config.py             # Env-driven configuration
│   ├── static/index.html     # Single-page dashboard
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   └── init.sql              # Schema, hypertable, compression policy
├── scripts/
│   └── restart.sh            # Rebuild/restart helper (per service)
├── weather_data/             # Collected JSON (gitignored, source of truth)
├── backups/                  # DB dumps (gitignored)
├── docker-compose.yml
├── .env                      # Secrets + config (gitignored)
└── .env.example              # Template for .env
```

## Prerequisites

- Podman (or Docker) with Compose support
- A [Tomorrow.io API key](https://app.tomorrow.io/development/keys)

## Configuration

Copy the template and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Example |
|---|---|---|
| `DB_HOST` | Database hostname (compose service name) | `database` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Postgres credentials | `weather_db` / `weather_user` / … |
| `DB_PORT` | Postgres port | `5432` |
| `WEATHER_API_KEY` | Tomorrow.io API key (**required**) | — |
| `WEATHER_API_URL` | Realtime endpoint | `https://api.tomorrow.io/v4/weather/realtime` |
| `LOCATION_LAT` / `LOCATION_LON` | Coordinates to collect for | `42.621864` / `-71.28336` |
| `COLLECTION_INTERVAL` | Seconds between readings (min 60) | `180` |
| `RETRY_DELAY` / `MAX_RETRIES` / `TIMEOUT_SECONDS` | API request tuning | `30` / `3` / `10` |
| `DATA_DIR` | JSON path inside containers | `/data` |
| `WEB_SERVER_PORT` | Host/container port for the dashboard | `8080` |
| `WEB_CONTEXT` | Build context for the web image | `./web` |

## Running

```bash
# Start everything (build images, create DB from init.sql on first run)
podman compose up -d

# Or use the helper script
./scripts/restart.sh            # rebuild + restart all services
./scripts/restart.sh web        # just the web service
./scripts/restart.sh collector  # just the collector
./scripts/restart.sh database   # restart DB (no rebuild)
```

The dashboard is then available at <http://localhost:8080/>.

> **Note:** `init.sql` only runs when the database volume is **empty** (first
> start). Editing it does not affect an existing database — see
> [Backup & recovery](#backup--recovery) for how to apply schema changes to a
> populated DB.

## API reference

All endpoints are served by the `web` service on port `8080`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | The dashboard (HTML) |
| `GET` | `/api/latest` | Most recent reading |
| `GET` | `/api/history/24h` | All readings from the last 24 hours |
| `GET` | `/api/history/7d` | Hourly min/avg/max aggregates for the last 7 days |
| `GET` | `/api/stats` | Record counts, date span, 24h summary, collection count |
| `GET` | `/api/health` | Health check (DB connectivity) |

Temperatures are stored and returned in Celsius; the dashboard converts to
Fahrenheit client-side.

## Database

The schema lives in `database/init.sql`. `weather_readings` is a TimescaleDB
hypertable partitioned on `time`, with a compression policy that compresses
chunks older than 7 days. The primary key is `(time, location_lat,
location_lon)`, so re-inserting an existing reading is a no-op
(`ON CONFLICT DO NOTHING`) — making imports idempotent.

Running versions: **TimescaleDB 2.19.3** on **PostgreSQL 14**, pinned in
`docker-compose.yml` (`timescale/timescaledb:2.19.3-pg14`).

## Backup & recovery

Because every reading is written to `weather_data/` before it is inserted into
the database, the JSON files are a complete, authoritative copy of the data.

**Rebuild the database from JSON** (e.g. after a schema change or data loss):

```bash
# Recreate the schema (drops existing data!)
podman exec weather-db psql -U weather_user -d weather_db \
  -c "DROP TABLE IF EXISTS weather_readings CASCADE;"
podman exec -i weather-db psql -U weather_user -d weather_db < database/init.sql

# Reimport all JSON files (idempotent, ~2000 files/sec)
podman compose run --rm --no-deps collector python import_historical.py
```

**Point-in-time DB snapshots** (optional, faster restore than reimport):

```bash
# Full-table CSV export
podman exec weather-db psql -U weather_user -d weather_db \
  -c "\copy (SELECT * FROM weather_readings ORDER BY time) TO STDOUT WITH CSV HEADER" \
  | gzip > backups/weather_readings-$(date +%Y%m%d-%H%M%S).csv.gz
```

## Development notes

- Pinned dependencies live in each service's `requirements.txt`; rebuild the
  relevant image after changing them.
- `web/database.py` uses a `ThreadedConnectionPool` (FastAPI serves sync routes
  across a thread pool) and `RealDictCursor` so query results map to columns by
  name rather than position.
- `init.sql` is PostgreSQL/TimescaleDB syntax. Editors using a SQL Server (T-SQL)
  parser will report false errors; `.vscode/settings.json` disables that.
