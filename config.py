import os
from dataclasses import dataclass

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}

@dataclass(frozen=True)
class AppConfig:
    # Debug
    debug_ui: bool = _env_bool("DEBUG_UI", False)

    # Feature flags (toggle sections without code edits)
    ff_show_sponsorship: bool = _env_bool("FF_SHOW_SPONSORSHIP", True)
    ff_show_scorecard: bool = _env_bool("FF_SHOW_SCORECARD", True)
    ff_show_gaps: bool = _env_bool("FF_SHOW_GAPS", True)
    ff_show_tailoring: bool = _env_bool("FF_SHOW_TAILORING", True)
    ff_show_export: bool = _env_bool("FF_SHOW_EXPORT", True)
    ff_allow_save_run: bool = _env_bool("FF_ALLOW_SAVE_RUN", True)

    # Export behavior
    export_auto_build: bool = _env_bool("EXPORT_AUTO_BUILD", True)  # auto build on Export tab
    export_cache_enabled: bool = _env_bool("EXPORT_CACHE_ENABLED", True)

CONFIG = AppConfig()
