from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from dashboard_studio.db.migrate import MIGRATIONS_DIR


def make_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def table_columns(db_path: Path, table: str) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    finally:
        con.close()


def table_names(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in cur.fetchall()}
    finally:
        con.close()


def test_upgrade_head_creates_all_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHBOARD_STUDIO_DATA_DIR", str(tmp_path))
    config = make_config()

    command.upgrade(config, "head")

    db_path = tmp_path / "dashboard_studio.db"
    assert db_path.is_file()
    tables = table_names(db_path)
    assert {"projects", "token_presets", "generations", "backups"} <= tables
    assert "token_schema_version" in table_columns(db_path, "token_presets")


def test_downgrade_to_0001_drops_the_new_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHBOARD_STUDIO_DATA_DIR", str(tmp_path))
    config = make_config()
    command.upgrade(config, "head")

    command.downgrade(config, "0001")

    db_path = tmp_path / "dashboard_studio.db"
    assert "token_schema_version" not in table_columns(db_path, "token_presets")
    # the table itself, and the other 0001 tables, must survive the downgrade
    assert "token_presets" in table_names(db_path)


def test_downgrade_to_base_drops_all_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHBOARD_STUDIO_DATA_DIR", str(tmp_path))
    config = make_config()
    command.upgrade(config, "head")

    command.downgrade(config, "base")

    db_path = tmp_path / "dashboard_studio.db"
    tables = table_names(db_path)
    assert "token_presets" not in tables
    assert "projects" not in tables
