"""App configuration.

Options come from the App's `/data/options.json` (written by the Supervisor
from the user's config.yaml options) in production, with environment
variables as the local-dev path when that file doesn't exist.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path(os.environ.get("DASHBOARD_STUDIO_DATA_DIR", "/data"))
OPTIONS_FILE = DEFAULT_DATA_DIR / "options.json"


def _load_options_file() -> dict[str, object]:
    if OPTIONS_FILE.is_file():
        return json.loads(OPTIONS_FILE.read_text())
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DASHBOARD_STUDIO_", extra="ignore")

    log_level: str = "info"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    long_lived_token: str = ""
    ha_url: str = "http://homeassistant.local:8123"
    data_dir: Path = DEFAULT_DATA_DIR

    @classmethod
    def load(cls) -> Settings:
        options = _load_options_file()
        # Supervisor options.json keys match config.yaml's `options:` block
        # verbatim; env vars (DASHBOARD_STUDIO_*) are the local-dev override.
        return cls(**options)  # type: ignore[arg-type]


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
