"""Tests for distributed locking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from spanshift.core.lock import LOCK_KEY, MigrationLock
from spanshift.exceptions import LockError


def _make_lock(db=None, timeout=300):
    return MigrationLock(db or MagicMock(), timeout_seconds=timeout)


def test_acquire_inserts_when_no_existing_lock():
    db = MagicMock()

    def run_txn(fn):
        txn = MagicMock()
        txn.execute_sql.return_value = []  # No existing lock
        fn(txn)
        txn.execute_update.assert_called_once()
        sql = txn.execute_update.call_args[0][0]
        assert "INSERT" in sql

    db.run_in_transaction.side_effect = run_txn

    lock = _make_lock(db)
    lock.acquire()


def test_acquire_raises_when_lock_held():
    db = MagicMock()
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    def run_txn(fn):
        txn = MagicMock()
        txn.execute_sql.return_value = [
            ("other-id", "other-host", datetime.now(timezone.utc), future)
        ]
        fn(txn)

    db.run_in_transaction.side_effect = run_txn

    lock = _make_lock(db)
    with pytest.raises(LockError, match="lock held by"):
        lock.acquire()


def test_acquire_replaces_expired_lock():
    db = MagicMock()
    past = datetime.now(timezone.utc) - timedelta(hours=1)

    def run_txn(fn):
        txn = MagicMock()
        txn.execute_sql.return_value = [
            ("old-id", "old-host", past - timedelta(hours=1), past)
        ]
        fn(txn)
        sql = txn.execute_update.call_args[0][0]
        assert "UPDATE" in sql

    db.run_in_transaction.side_effect = run_txn

    lock = _make_lock(db)
    lock.acquire()


def test_release_deletes_own_lock():
    db = MagicMock()
    lock = _make_lock(db)

    def run_txn(fn):
        txn = MagicMock()
        txn.execute_sql.return_value = [(lock._lock_id,)]
        fn(txn)
        sql = txn.execute_update.call_args[0][0]
        assert "DELETE" in sql

    db.run_in_transaction.side_effect = run_txn
    lock.release()


def test_release_does_not_delete_other_lock():
    db = MagicMock()
    lock = _make_lock(db)

    def run_txn(fn):
        txn = MagicMock()
        txn.execute_sql.return_value = [("different-id",)]
        fn(txn)
        # execute_update should NOT be called
        txn.execute_update.assert_not_called()

    db.run_in_transaction.side_effect = run_txn
    lock.release()


def test_context_manager():
    db = MagicMock()
    lock = _make_lock(db)

    # Patch acquire/release for simple test
    with patch.object(lock, "acquire") as mock_acq, patch.object(lock, "release") as mock_rel:
        with lock:
            mock_acq.assert_called_once()
        mock_rel.assert_called_once()


def test_ensure_table_ignores_existing():
    db = MagicMock()
    op = MagicMock()
    op.result.side_effect = Exception("Duplicate name in schema: spanshift_lock")
    db.update_ddl.return_value = op

    lock = _make_lock(db)
    lock.ensure_table()  # Should not raise
