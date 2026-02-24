"""Distributed lock via Spanner table to prevent concurrent migrations."""

from __future__ import annotations

import socket
import uuid
from datetime import datetime, timedelta, timezone

from google.cloud.spanner_v1 import param_types
from google.cloud.spanner_v1.database import Database

from spanshift.exceptions import LockError

LOCK_TABLE_DDL = """\
CREATE TABLE {table} (
    lock_key STRING(1) NOT NULL,
    lock_id STRING(36) NOT NULL,
    locked_by STRING(255),
    locked_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
) PRIMARY KEY (lock_key)"""

LOCK_KEY = "L"


class MigrationLock:
    """Distributed lock backed by a Spanner table.

    Prevents multiple processes from running migrations concurrently.
    Uses a single-row table with TTL-based expiration.
    """

    def __init__(
        self,
        database: Database,
        table_name: str = "spanshift_lock",
        timeout_seconds: int = 300,
    ):
        self._database = database
        self._table = table_name
        self._timeout = timeout_seconds
        self._lock_id = str(uuid.uuid4())
        self._locked_by = f"{socket.gethostname()}:{self._lock_id[:8]}"

    def ensure_table(self) -> None:
        """Create the lock table if it doesn't exist."""
        ddl = LOCK_TABLE_DDL.format(table=self._table)
        try:
            operation = self._database.update_ddl([ddl])
            operation.result(120)
        except Exception as exc:
            if "Duplicate name in schema" in str(exc) or "already exists" in str(exc):
                return
            raise

    def acquire(self) -> None:
        """Acquire the migration lock. Raises LockError if already held."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self._timeout)

        def _try_acquire(transaction):
            # Check for existing lock
            row = list(
                transaction.execute_sql(
                    f"SELECT lock_id, locked_by, locked_at, expires_at "
                    f"FROM {self._table} WHERE lock_key = @key",
                    params={"key": LOCK_KEY},
                    param_types={"key": param_types.STRING},
                )
            )

            if row:
                existing_expires = row[0][3]
                if existing_expires.tzinfo is None:
                    existing_expires = existing_expires.replace(tzinfo=timezone.utc)
                if existing_expires > now:
                    locked_by = row[0][1]
                    locked_at = row[0][2]
                    raise LockError(
                        f"Migration lock held by '{locked_by}' since {locked_at}. "
                        f"Expires at {existing_expires}. "
                        f"If this is stale, wait for expiry or manually delete the lock row."
                    )
                # Expired lock -- replace it
                transaction.execute_update(
                    f"UPDATE {self._table} SET "
                    f"lock_id = @lock_id, locked_by = @locked_by, "
                    f"locked_at = @locked_at, expires_at = @expires_at "
                    f"WHERE lock_key = @key",
                    params={
                        "key": LOCK_KEY,
                        "lock_id": self._lock_id,
                        "locked_by": self._locked_by,
                        "locked_at": now,
                        "expires_at": expires_at,
                    },
                    param_types={
                        "key": param_types.STRING,
                        "lock_id": param_types.STRING,
                        "locked_by": param_types.STRING,
                        "locked_at": param_types.TIMESTAMP,
                        "expires_at": param_types.TIMESTAMP,
                    },
                )
            else:
                # No lock exists -- insert
                transaction.execute_update(
                    f"INSERT INTO {self._table} "
                    f"(lock_key, lock_id, locked_by, locked_at, expires_at) "
                    f"VALUES (@key, @lock_id, @locked_by, @locked_at, @expires_at)",
                    params={
                        "key": LOCK_KEY,
                        "lock_id": self._lock_id,
                        "locked_by": self._locked_by,
                        "locked_at": now,
                        "expires_at": expires_at,
                    },
                    param_types={
                        "key": param_types.STRING,
                        "lock_id": param_types.STRING,
                        "locked_by": param_types.STRING,
                        "locked_at": param_types.TIMESTAMP,
                        "expires_at": param_types.TIMESTAMP,
                    },
                )

        try:
            self._database.run_in_transaction(_try_acquire)
        except LockError:
            raise
        except Exception as exc:
            raise LockError(f"Failed to acquire migration lock: {exc}") from exc

    def release(self) -> None:
        """Release the migration lock. Only releases if we own it."""

        def _release(transaction):
            rows = list(
                transaction.execute_sql(
                    f"SELECT lock_id FROM {self._table} WHERE lock_key = @key",
                    params={"key": LOCK_KEY},
                    param_types={"key": param_types.STRING},
                )
            )
            if rows and rows[0][0] == self._lock_id:
                transaction.execute_update(
                    f"DELETE FROM {self._table} WHERE lock_key = @key",
                    params={"key": LOCK_KEY},
                    param_types={"key": param_types.STRING},
                )

        try:
            self._database.run_in_transaction(_release)
        except Exception:
            pass  # Best-effort release; TTL will clean up

    def __enter__(self) -> MigrationLock:
        self.acquire()
        return self

    def __exit__(self, *args) -> None:
        self.release()
