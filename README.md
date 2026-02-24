# Spanshift

Schema migration tool for Google Cloud Spanner.

- **Chain validation** -- migrations form a linked list; broken chains are caught before execution
- **Distributed locking** -- prevents concurrent migration runs across multiple machines
- **Dry-run mode** -- preview DDL changes without touching your database
- **Checksum verification** -- detects modified migration files after they've been applied
- **Multi-environment config** -- manage dev, staging, and production from one `spanshift.toml`

## Installation

```bash
pip install spanshift
```

Requires Python 3.11+ and [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) configured for GCP access.

## Quick Start

### 1. Initialize your project

```bash
spanshift init \
  --project-id my-gcp-project \
  --instance-id my-instance \
  --database-id my-database
```

This creates a `spanshift.toml` config file, a `migrations/` directory, and tracking tables in Spanner.

### 2. Create a migration

```bash
spanshift new "create users table"
```

This generates a timestamped migration file in `migrations/`:

```python
"""create users table.

Revision: 20260225_143012
Down-revision: None
Created: 2026-02-25T14:30:12+00:00
"""

revision = "20260225_143012"
down_revision = None
description = "create users table"


def upgrade(ctx):
    ctx.execute_ddl([
        """CREATE TABLE Users (
            UserId STRING(36) NOT NULL,
            Email STRING(320) NOT NULL,
            CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
        ) PRIMARY KEY (UserId)""",
    ])


def downgrade(ctx):
    ctx.execute_ddl([
        "DROP TABLE Users",
    ])
```

### 3. Apply the migration

```bash
spanshift upgrade
```

### 4. Check status

```bash
spanshift status
```

## Configuration

Spanshift reads from `spanshift.toml` in the project root:

```toml
[spanshift]
migrations_dir = "migrations"
naming = "timestamp"           # "timestamp" or "sequential"
tracking_table = "spanshift_migrations"
lock_table = "spanshift_lock"
lock_timeout_seconds = 300
ddl_timeout_seconds = 600

[environments.default]
project_id = "my-gcp-project"
instance_id = "my-instance"
database_id = "my-database"

[environments.staging]
project_id = "my-gcp-project"
instance_id = "my-instance"
database_id = "my-database-staging"
```

### Environment variable overrides

Environment variables take precedence over `spanshift.toml` values:

| Variable | Overrides |
|---|---|
| `SPANSHIFT_PROJECT_ID` | `project_id` |
| `SPANSHIFT_INSTANCE_ID` | `instance_id` |
| `SPANSHIFT_DATABASE_ID` | `database_id` |
| `SPANSHIFT_CREDENTIALS_PATH` | `credentials_path` |

Resolution order: CLI flags > environment variables > `spanshift.toml` > defaults.

## CLI Reference

| Command | Description | Key flags |
|---|---|---|
| `spanshift init` | Initialize config, migrations dir, and tracking tables | `--project-id`, `--instance-id`, `--database-id`, `--skip-db` |
| `spanshift new <description>` | Generate a new migration file | `--env` |
| `spanshift upgrade [target]` | Apply pending migrations (optionally up to a target revision) | `--env`, `--dry-run`, `--yes` |
| `spanshift downgrade [steps]` | Revert the last N migrations (default: 1, 0 = all) | `--env`, `--dry-run`, `--yes` |
| `spanshift status` | Show applied/pending status for all migrations | `--env` |
| `spanshift current` | Show the latest applied revision | `--env` |
| `spanshift history` | Show applied migration history with timestamps and durations | `--env` |
| `spanshift schema` | Dump current database DDL from Spanner | `--env` |

Use `--env` to target a specific environment (defaults to `default`).

## Migration Context API

Migration functions receive a `MigrationContext` object:

```python
def upgrade(ctx):
    # DDL -- schema changes (CREATE TABLE, ALTER TABLE, CREATE INDEX, etc.)
    ctx.execute_ddl([
        "CREATE INDEX UsersByEmail ON Users(Email)",
    ])

    # DML -- single-transaction data changes
    ctx.execute_dml(
        "UPDATE Users SET Active = @active WHERE CreatedAt < @cutoff",
        params={"active": False, "cutoff": "2025-01-01T00:00:00Z"},
        param_types={"active": spanner.param_types.BOOL, "cutoff": spanner.param_types.TIMESTAMP},
    )

    # Partitioned DML -- large-scale data changes across splits
    ctx.execute_partitioned_dml(
        "DELETE FROM Logs WHERE Timestamp < @cutoff",
        params={"cutoff": "2024-01-01T00:00:00Z"},
        param_types={"cutoff": spanner.param_types.TIMESTAMP},
    )

    # Check if running in dry-run mode
    if ctx.dry_run:
        return

    # Direct database access for advanced use cases
    ctx.database.run_in_transaction(...)
```

| Method | Purpose |
|---|---|
| `execute_ddl(statements)` | Batch DDL via `update_ddl()`. Blocks until complete. |
| `execute_dml(dml, params, param_types)` | Run DML in a read-write transaction. Returns row count. |
| `execute_partitioned_dml(dml, params, param_types)` | Partitioned DML for large-scale changes. Returns row count. |
| `dry_run` | `bool` property -- `True` when running with `--dry-run`. |
| `database` | Direct access to the Spanner `Database` object. |

All methods are no-ops during dry-run (DDL is collected, DML returns 0).

## Safety Features

**Distributed locking** -- A lock table in Spanner ensures only one migration process runs at a time, even across multiple machines. Lock automatically expires after the configured timeout (default: 300s).

**Checksum verification** -- Each migration file's content is checksummed at apply time. `spanshift status` flags any files that have been modified after being applied.

**Chain validation** -- Migrations form a singly-linked list via `down_revision`. Broken links, duplicates, or forks are detected before execution.

**Confirmation prompts** -- `upgrade` and `downgrade` require interactive confirmation unless `--yes` or `--dry-run` is passed.

## License

MIT
