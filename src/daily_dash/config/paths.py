from __future__ import annotations

import os
from pathlib import Path


def default_config_dir() -> Path:
    """Resolve the DailyDash configuration directory."""

    explicit = os.getenv("DAILY_DASH_CONFIG_DIR")
    if explicit:
        return Path(explicit)

    home = os.getenv("DAILY_DASH_HOME")
    if home:
        return Path(home) / "config"

    return Path("config")
