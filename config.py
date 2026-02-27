from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "t", "yes", "y", "on")


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else v


@dataclass(frozen=True)
class AppConfig:
    # UI / feature flags
    ff_show_scorecard: bool = _env_bool("FF_SHOW_SCORECARD", True)
    ff_show_gaps: bool = _env_bool("FF_SHOW_GAPS", True)
    ff_show_tailoring: bool = _env_bool("FF_SHOW_TAILORING", True)
    ff_show_export: bool = _env_bool("FF_SHOW_EXPORT", True)
    ff_show_sponsorship: bool = _env_bool("FF_SHOW_SPONSORSHIP", True)

    # Persistence
    ff_allow_save_run: bool = _env_bool("FF_ALLOW_SAVE_RUN", True)

    # Export behavior
    export_auto_build: bool = _env_bool("EXPORT_AUTO_BUILD", True)

    export_cache_enabled: bool = _env_bool("EXPORT_CACHE_ENABLED", True)

    # Debug
    debug_ui: bool = _env_bool("DEBUG_UI", False)

    # Optional: where to write saved runs
    data_dir: str = _env_str("DATA_DIR", "data")


CONFIG = AppConfig()
