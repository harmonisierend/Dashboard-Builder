"""Run Alembic migrations programmatically at app startup.

The App container has no interactive shell to run `alembic upgrade head`
from, so the app must migrate its own database on boot. Config is built in
code rather than by reading `alembic.ini` off disk: `alembic.ini`'s
`script_location = src/dashboard_studio/db/migrations` is relative to the
backend/ checkout directory, which doesn't exist inside the installed
package -- only `alembic.ini` itself stays for local CLI use
(`alembic upgrade head` during development).

`migrations/env.py` recomputes `sqlalchemy.url` itself from
DASHBOARD_STUDIO_DATA_DIR, so nothing needs to be set here beyond
`script_location`.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations() -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    command.upgrade(config, "head")
