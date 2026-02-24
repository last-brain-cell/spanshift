"""Spanner client/instance/database factory."""

from __future__ import annotations

import concurrent.futures

from google.cloud import spanner
from google.cloud.spanner_v1.database import Database

from spanshift.config.models import SpannerTarget
from spanshift.exceptions import ConnectionError


def get_database(target: SpannerTarget) -> Database:
    """Create a Spanner database handle from target config."""
    kwargs = {}
    if target.credentials_path:
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            target.credentials_path
        )
        kwargs["credentials"] = credentials

    client = spanner.Client(project=target.project_id, **kwargs)
    instance = client.instance(target.instance_id)
    database = instance.database(target.database_id)
    return database


AUTH_HELP = (
    "To authenticate with Google Cloud Spanner, try one of:\n"
    "  1. gcloud auth application-default login\n"
    "  2. Set GOOGLE_APPLICATION_CREDENTIALS to a service account key file\n"
    "  3. Pass --credentials-path to the spanshift command"
)


def validate_connection(database: Database, timeout: int = 10) -> None:
    """Verify that the Spanner database is reachable and credentials work.

    Performs a lightweight read (``database.ddl_statements``) inside a
    thread-pool so we can enforce a hard *timeout* (seconds) and fail fast
    instead of hanging on gRPC channel establishment.
    """

    def _probe():
        # ddl_statements is a lightweight metadata call
        database.ddl_statements  # noqa: B018

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_probe)
        try:
            future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise ConnectionError(
                f"Connection to Spanner timed out after {timeout}s.\n{AUTH_HELP}"
            )
        except Exception as exc:
            raise ConnectionError(
                f"Failed to connect to Spanner: {exc}\n{AUTH_HELP}"
            ) from exc
