"""MigrationContext passed to upgrade/downgrade functions."""

from __future__ import annotations

from typing import Any

from google.cloud.spanner_v1.database import Database


class MigrationContext:
    """Context object passed to migration upgrade/downgrade functions."""

    def __init__(self, database: Database, *, dry_run: bool = False, ddl_timeout: int = 600):
        self._database = database
        self._dry_run = dry_run
        self._ddl_timeout = ddl_timeout
        self._collected_ddl: list[str] = []

    @property
    def database(self) -> Database:
        """Direct Spanner database access for advanced use cases."""
        return self._database

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    @property
    def collected_ddl(self) -> list[str]:
        """DDL statements collected during dry-run."""
        return list(self._collected_ddl)

    def execute_ddl(self, statements: list[str]) -> None:
        """Batch DDL via database.update_ddl(). Blocks until complete."""
        if self._dry_run:
            self._collected_ddl.extend(statements)
            return
        operation = self._database.update_ddl(statements)
        operation.result(self._ddl_timeout)

    def execute_dml(
        self,
        dml: str,
        params: dict[str, Any] | None = None,
        param_types: dict | None = None,
    ) -> int:
        """Run DML in a read-write transaction. Returns rows modified."""
        if self._dry_run:
            return 0

        row_count = 0

        def _run(transaction):
            nonlocal row_count
            row_count = transaction.execute_update(
                dml, params=params, param_types=param_types
            )

        self._database.run_in_transaction(_run)
        return row_count

    def execute_partitioned_dml(
        self,
        dml: str,
        params: dict[str, Any] | None = None,
        param_types: dict | None = None,
    ) -> int:
        """Partitioned DML for large-scale data changes. Returns rows modified."""
        if self._dry_run:
            return 0
        return self._database.execute_partitioned_dml(
            dml, params=params, param_types=param_types
        )
