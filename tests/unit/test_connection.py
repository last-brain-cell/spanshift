"""Tests for connection validation."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from spanshift.core.connection import validate_connection
from spanshift.exceptions import ConnectionError


def test_validate_connection_success():
    """validate_connection passes when ddl_statements is reachable."""
    db = MagicMock()
    db.ddl_statements = []
    validate_connection(db, timeout=5)


def test_validate_connection_timeout():
    """validate_connection raises ConnectionError on timeout."""
    import time

    db = MagicMock()
    type(db).ddl_statements = PropertyMock(side_effect=lambda: time.sleep(30))

    with pytest.raises(ConnectionError, match="timed out"):
        validate_connection(db, timeout=1)


def test_validate_connection_auth_error():
    """validate_connection raises ConnectionError with auth help on failure."""
    db = MagicMock()
    type(db).ddl_statements = PropertyMock(
        side_effect=PermissionError("no credentials")
    )

    with pytest.raises(ConnectionError, match="gcloud auth application-default login"):
        validate_connection(db, timeout=5)


def test_validate_connection_wraps_original_exception():
    """validate_connection preserves the original exception as __cause__."""
    original = RuntimeError("something broke")
    db = MagicMock()
    type(db).ddl_statements = PropertyMock(side_effect=original)

    with pytest.raises(ConnectionError) as exc_info:
        validate_connection(db, timeout=5)

    assert exc_info.value.__cause__ is original
