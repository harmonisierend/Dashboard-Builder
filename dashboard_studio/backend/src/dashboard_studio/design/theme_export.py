"""Render a DesignTokenSet as an HA `themes.yaml`-compatible theme.

Variable names verified against home-assistant/frontend's
src/resources/theme/color/color.globals.ts: primary-color, accent-color,
primary-background-color, card-background-color, primary-text-color,
warning-color, error-color, and the generic state-active-color/
state-inactive-color pair all exist as documented, global (non-domain-
specific) theme variables.

Per spec: exporting is optional for the user and requires a manual theme
reload in HA to take effect -- the UI is responsible for showing that
hint, this module only renders the YAML text.
"""

from __future__ import annotations

import re

import yaml

from dashboard_studio.design.tokens import DesignTokenSet

_VALID_THEME_NAME = re.compile(r"^[A-Za-z0-9 _-]{1,64}$")


class ThemeNameError(ValueError):
    """Raised when a theme name isn't safe to use as a YAML key / filename."""


def render_theme_yaml(theme_name: str, tokens: DesignTokenSet) -> str:
    if not _VALID_THEME_NAME.match(theme_name):
        raise ThemeNameError(
            "Theme-Name darf nur Buchstaben, Zahlen, Leerzeichen, '_' und '-' "
            "enthalten (max. 64 Zeichen)."
        )

    def mode_vars(is_dark: bool) -> dict[str, str]:
        pick = (lambda pair: pair.dark) if is_dark else (lambda pair: pair.light)
        palette = tokens.colors
        return {
            "primary-color": pick(palette.primary),
            "accent-color": pick(palette.accent),
            "primary-background-color": pick(palette.background),
            "card-background-color": pick(palette.surface),
            "primary-text-color": pick(palette.on_surface),
            "state-active-color": pick(palette.state_on),
            "state-inactive-color": pick(palette.state_off),
            "warning-color": pick(palette.warn),
            "error-color": pick(palette.critical),
        }

    theme_body: dict[str, object] = {
        "ha-card-border-radius": f"{tokens.form.border_radius_px}px",
        "ha-card-box-shadow": tokens.form.shadow,
        "modes": {
            "light": mode_vars(is_dark=False),
            "dark": mode_vars(is_dark=True),
        },
    }

    return yaml.safe_dump({theme_name: theme_body}, sort_keys=False, allow_unicode=True)
