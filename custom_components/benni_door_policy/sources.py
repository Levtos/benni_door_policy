"""HA-free source resolution helpers for Door Policy."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_PRESENCE_EFFECTIVE,
    CONF_PROFILE,
    DEFAULT_PROFILE_ROUTE,
    LEGACY_PRESENCE_EFFECTIVE_IDS,
    PROFILE_PREFILL,
)


def effective_presence_entity(options: Mapping[str, Any], default: str | None = None) -> str | None:
    """Resolve the effective-presence source for old and migrated config entries."""
    configured = options.get(CONF_PRESENCE_EFFECTIVE)
    if configured:
        return str(configured)
    profile = str(options.get(CONF_PROFILE) or DEFAULT_PROFILE_ROUTE)
    return PROFILE_PREFILL.get(profile, {}).get(CONF_PRESENCE_EFFECTIVE, default)


def migrate_effective_presence(
    data: Mapping[str, Any], options: Mapping[str, Any], profile: str
) -> str | None:
    """Pure decision: which value should be written into ``data[CONF_PRESENCE_EFFECTIVE]``?

    Returns the new value, or ``None`` when nothing should change. HA-free and
    unit-testable. Rules (renamed-device ``system_`` Entity-ID-Fix):

    * An explicit **options** override always wins → never migrate (``None``).
    * No stored data value → fill with the current profile default.
    * Stored data value is a known **legacy** default (a slug that never existed
      live, auto-written by an older build) → **repoint** to the current default.
    * Any other stored data value is treated as an explicit choice → keep
      (``None``).

    The migration only ever *rebinds* a stale auto-default; it never fabricates a
    presence source out of nothing beyond the existing prefill behaviour, and it
    never silences a genuinely missing entity (the coordinator/policy still
    surface ``presence_effective_missing`` if the target is absent).
    """
    if options.get(CONF_PRESENCE_EFFECTIVE):
        return None
    default = PROFILE_PREFILL.get(profile, {}).get(CONF_PRESENCE_EFFECTIVE)
    if not default:
        return None
    stored = data.get(CONF_PRESENCE_EFFECTIVE)
    if not stored:
        return default
    if stored != default and str(stored) in LEGACY_PRESENCE_EFFECTIVE_IDS:
        return default
    return None
