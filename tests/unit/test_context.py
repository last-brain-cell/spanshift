"""Tests for MigrationContext (dry-run mode)."""

from unittest.mock import MagicMock

from spanshift.core.context import MigrationContext


def test_dry_run_collects_ddl():
    db = MagicMock()
    ctx = MigrationContext(db, dry_run=True)
    ctx.execute_ddl(["CREATE TABLE foo (id STRING(36)) PRIMARY KEY (id)"])
    ctx.execute_ddl(["CREATE INDEX ix ON foo(id)"])
    assert len(ctx.collected_ddl) == 2
    assert "CREATE TABLE" in ctx.collected_ddl[0]


def test_dry_run_dml_returns_zero():
    db = MagicMock()
    ctx = MigrationContext(db, dry_run=True)
    assert ctx.execute_dml("UPDATE foo SET bar = 1") == 0
    db.run_in_transaction.assert_not_called()


def test_dry_run_partitioned_dml_returns_zero():
    db = MagicMock()
    ctx = MigrationContext(db, dry_run=True)
    assert ctx.execute_partitioned_dml("UPDATE foo SET bar = 1") == 0
    db.execute_partitioned_dml.assert_not_called()


def test_execute_ddl_calls_update_ddl():
    db = MagicMock()
    op = MagicMock()
    db.update_ddl.return_value = op

    ctx = MigrationContext(db, dry_run=False, ddl_timeout=120)
    ctx.execute_ddl(["CREATE TABLE t (id STRING(36)) PRIMARY KEY (id)"])

    db.update_ddl.assert_called_once()
    op.result.assert_called_once_with(120)
