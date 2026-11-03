# PostgreSQL/pgvector quickstart

Start Docker Desktop/Engine first. From the repository root:

```sh
docker compose up -d --wait postgres
```

The checked-in Compose file uses `pgvector/pgvector:pg16`, initializes the vector
extension in `public` on a new volume, and waits for PostgreSQL readiness. Its
default settings match the library's development connection:

```text
postgresql://vectorprism:vectorprism@127.0.0.1:5433/vectorprism
```

PowerShell:

```powershell
$env:VECTORPRISM_PG_DSN = "postgresql://vectorprism:vectorprism@127.0.0.1:5433/vectorprism"
cpu-llm-demo healthcare --out healthcare-new-run
```

POSIX shell:

```sh
export VECTORPRISM_PG_DSN='postgresql://vectorprism:vectorprism@127.0.0.1:5433/vectorprism'
cpu-llm-demo healthcare --out healthcare-new-run
```

Prepare the [encoder cache](offline-setup.md) first if the demo must run without
Hub access. Database readiness does not download model assets or ingest knowledge.
The demonstration creates an isolated namespace and ingests its fictional data.

## Alternate port or single-command setup

When port 5433 is occupied, set `CPULLM_POSTGRES_PORT=5434` before Compose and set
the application DSN to port 5434. Changing the environment password applies only
when initializing a new volume; it does not rotate an existing database password.
The default credentials are for development and the port binds only to loopback.

Without Compose, this one-line alternative supplies the same database/user:

```sh
docker run -d --name cpullm-pgvector-test -p 127.0.0.1:5434:5432 -e POSTGRES_USER=vectorprism -e POSTGRES_PASSWORD=vectorprism -e POSTGRES_DB=vectorprism pgvector/pgvector:pg16
```

For that container, wait for readiness and initialize the extension explicitly:

```sh
docker exec cpullm-pgvector-test pg_isready -U vectorprism -d vectorprism
docker exec cpullm-pgvector-test psql -U vectorprism -d vectorprism -c "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;"
```

Use `postgresql://vectorprism:vectorprism@127.0.0.1:5434/vectorprism`. If you use
the audit's alternative `POSTGRES_PASSWORD=postgres` command without a custom
user/database, its DSN is instead
`postgresql://postgres:postgres@127.0.0.1:5434/postgres`; setting the port alone
does not change cpu-llm's default credentials or database name.

## Existing databases and troubleshooting

Existing PostgreSQL installations are supported with a matching DSN, the vector
extension, and permissions to create the appliance's schemas/tables. Initialization
scripts run only on a new Compose volume. Existing volumes must have the extension
enabled separately; do not delete stored data to make a quickstart work.

Use `docker compose ps` and `docker compose logs postgres` for readiness failures.
Stop this development service with `docker compose stop postgres`. Do not run both
examples on the same host port. The release's latest recorded smoke used native
PostgreSQL 18 on port 55433; older runs also used pg16 containers on 5433/5434.
Those historical environments are distinct from a new Compose validation.

Upstream: [pgvector Docker instructions](https://github.com/pgvector/pgvector#docker).
