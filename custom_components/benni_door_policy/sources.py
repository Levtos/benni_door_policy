"""HA-free source resolution helpers for Door Policy."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_PRESENCE_EFFECTIVE,
    CONF_PROFILE,
    DEFAULT_PROFILE_ROUTE,
    PROFILE_PREFILL,
)


def effective_presence_entity(options: Mapping[str, Any], default: str | None = None) -> str | None:
    """Resolve the effective-presence source for old and migrated config entries."""
    configured = options.get(CONF_PRESENCE_EFFECTIVE)
    if configured:
        return str(configured)
    profile = str(options.get(CONF_PROFILE) or DEFAULT_PROFILE_ROUTE)
    return PROFILE_PREFILL.get(profile, {}).get(CONF_PRESENCE_EFFECTIVE, default)
