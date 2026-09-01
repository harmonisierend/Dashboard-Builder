"""Logging setup.

Anthropic API keys and HA tokens must never reach logs — call sites are
responsible for not passing secrets as log arguments; nothing here echoes
config values wholesale.
"""

from __future__ import annotations

import logging
import sys

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_logging(level: str = "info") -> None:
    logging.basicConfig(
        level=_LEVELS.get(level.lower(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )
