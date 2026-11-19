# PaperFeed

Release 1.0.0 — initial development release.

Research discovery and discussion platform with personalized feed ranking. A modular FastAPI application, PostgreSQL/pgvector, Redis feed snapshots, private S3 media and transactional engagement processing. Designed for a small community, with a separate Kafka configuration for distributed-system experiments.

## Architecture

Browser → Caddy → FastAPI → PostgreSQL / Redis. Browser uploads media directly to S3 using restricted presigned forms. A database outbox drives a background worker; the optional Kafka configuration uses a relay and consumer instead. Ranking combines semantic relevance, interests, freshness, author affinity, engagement and reading history. Feed snapshots expire after 180 seconds.

## Local setup

Requires Docker Compose, an S3 bucket and AWS credentials authorized for that bucket. Copy `.env.example` to `.env`, replace both database password placeholders with the same URL-safe secret, set bucket and region. For local development only, provide AWS credentials through the environment file (never commit it). Configure bucket CORS for the exact application origin. Run `docker compose up --build -d`, then `docker compose run --rm api python -m scripts.create_user alex Alex`. Open http://localhost:8080. Optional sample records: `docker compose run --rm api python -m scripts.seed` (adds fictional posts; run once on a development database). Sample original image and video are in `samples/` and can be uploaded through the UI.

For Kafka use `docker compose -f compose.yaml -f compose.kafka.yaml up --build -d` instead of the default configuration. Do not run both worker modes concurrently.

## Repository

- `paperfeed/`: application, persistence, ranking, authentication, media and event processing.
- `db/migrations/`: versioned database schema.
- `frontend/`: React interface and reverse proxy.
- `scripts/`: migration, account provisioning and synthetic content.
- `tests/`: automated checks.
- `deploy/`: deployment guidance.

## Verification

`python -m pytest -q` after installing dependencies and pytest. See `docs/verification.md` for scope and outstanding checks. No production availability or performance claims are made.
