"""TOML config loading with environment variable resolution."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from spanshift.config.models import SpannerTarget, SpanshiftConfig
from spanshift.exceptions import ConfigError

CONFIG_FILENAME = "spanshift.toml"

ENV_PREFIX = "SPANSHIFT_"
ENV_MAP = {
    "PROJECT_ID": "project_id",
    "INSTANCE_ID": "instance_id",
    "DATABASE_ID": "database_id",
    "CREDENTIALS_PATH": "credentials_path",
}


def find_config_file(start: Path | None = None) -> Path | None:
    """Walk up from start directory looking for spanshift.toml."""
    current = (start or Path.cwd()).resolve()
    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _resolve_env_vars(target_dict: dict) -> dict:
    """Override target fields with SPANSHIFT_* env vars."""
    for env_suffix, field in ENV_MAP.items():
        env_val = os.environ.get(f"{ENV_PREFIX}{env_suffix}")
        if env_val is not None:
            target_dict[field] = env_val
    return target_dict


def load_config(
    config_path: Path | None = None,
    environment: str | None = None,
    cli_overrides: dict | None = None,
) -> tuple[SpanshiftConfig, SpannerTarget]:
    """Load and resolve configuration.

    Resolution order: CLI flags > env vars > spanshift.toml > defaults.
    Returns (config, target) tuple.
    """
    raw: dict = {}

    # Load TOML if available
    path = config_path or find_config_file()
    if path is not None:
        try:
            with open(path, "rb") as f:
                raw = tomllib.load(f)
        except Exception as exc:
            raise ConfigError(f"Failed to parse {path}: {exc}") from exc

    spanshift_section = raw.get("spanshift", {})
    environments_section = raw.get("environments", {})

    # Build config
    config = SpanshiftConfig(
        migrations_dir=spanshift_section.get("migrations_dir", "migrations"),
        naming=spanshift_section.get("naming", "timestamp"),
        tracking_table=spanshift_section.get(
            "tracking_table", "spanshift_migrations"
        ),
        lock_table=spanshift_section.get("lock_table", "spanshift_lock"),
        lock_timeout_seconds=spanshift_section.get("lock_timeout_seconds", 300),
        ddl_timeout_seconds=spanshift_section.get("ddl_timeout_seconds", 600),
        default_environment=spanshift_section.get("default_environment", "default"),
    )

    # Resolve target
    env_name = environment or config.default_environment
    target_dict = dict(environments_section.get(env_name, {}))

    # Apply env var overrides
    target_dict = _resolve_env_vars(target_dict)

    # Apply CLI overrides
    if cli_overrides:
        for k, v in cli_overrides.items():
            if v is not None:
                target_dict[k] = v

    if not target_dict.get("project_id"):
        raise ConfigError(
            f"No project_id configured for environment '{env_name}'. "
            "Set it in spanshift.toml, via SPANSHIFT_PROJECT_ID env var, or --project-id flag."
        )

    try:
        target = SpannerTarget(**target_dict)
    except Exception as exc:
        raise ConfigError(f"Invalid target configuration: {exc}") from exc

    return config, target
