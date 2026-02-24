"""Tests for config loading."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from spanshift.config.loader import load_config
from spanshift.config.models import SpanshiftConfig
from spanshift.exceptions import ConfigError


def test_load_config_from_toml(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "spanshift.toml"
    config_file.write_text("""\
[spanshift]
migrations_dir = "db/migrations"
naming = "sequential"

[environments.default]
project_id = "test-project"
instance_id = "test-instance"
database_id = "test-db"
""")

    config, target = load_config(config_path=config_file)
    assert config.migrations_dir == Path("db/migrations")
    assert config.naming == "sequential"
    assert target.project_id == "test-project"
    assert target.instance_id == "test-instance"
    assert target.database_id == "test-db"


def test_load_config_env_var_override(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "spanshift.toml"
    config_file.write_text("""\
[environments.default]
project_id = "from-toml"
instance_id = "from-toml"
database_id = "from-toml"
""")
    monkeypatch.setenv("SPANSHIFT_PROJECT_ID", "from-env")

    config, target = load_config(config_path=config_file)
    assert target.project_id == "from-env"
    assert target.instance_id == "from-toml"


def test_load_config_cli_override(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "spanshift.toml"
    config_file.write_text("""\
[environments.default]
project_id = "from-toml"
instance_id = "from-toml"
database_id = "from-toml"
""")

    config, target = load_config(
        config_path=config_file,
        cli_overrides={"project_id": "from-cli"},
    )
    assert target.project_id == "from-cli"


def test_load_config_missing_project_raises(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "spanshift.toml"
    config_file.write_text("[spanshift]\n")

    with pytest.raises(ConfigError, match="No project_id"):
        load_config(config_path=config_file)


def test_defaults():
    config = SpanshiftConfig()
    assert config.migrations_dir == Path("migrations")
    assert config.naming == "timestamp"
    assert config.tracking_table == "spanshift_migrations"
    assert config.ddl_timeout_seconds == 600
