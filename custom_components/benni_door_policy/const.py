"""Konstanten der Benni Door Policy (Türschloss Aqara U200, L2-Policy).

Eigenständige HACS-Custom-Integration. Konsumiert den stabilisierten
Effective-Presence-Vertrag aus benni_core_state AUSSCHLIESSLICH als HA-Entity-ID
aus dem Config-Flow — kein Python-Cross-Modul-Import.

Profil-Modell (FLEET-16): Slug-Schema ``<profile>_door_policy_<feature>`` via
``has_entity_name`` + profil-benanntem Device. Blaupause: benni_blind_policy.

Lastenheft: einhornzentrale/docs/lastenhefte/reviewed/tuerschloss/
"""
from __future__ import annotations

from typing import Final

DOMAIN: Final[str] = "benni_door_policy"
MODULE_ID: Final[str] = "door_policy"
NAME: Final[str] = "Door Policy"

STORAGE_VERSION: Final[int] = 1
CONFIG_ENTRY_VERSION: Final[int] = 2

# Datenwurzel in hass.data[DOMAIN].
DATA_COORDINATOR: Final[str] = "coordinator"
DATA_SKIP_RELOAD_COUNT: Final[str] = "skip_reload_count"
DATA_WS_REGISTERED: Final[str] = "_ws_registered"
DATA_VIEW_STATIC: Final[str] = "_view_static_registered"
DATA_VIEW_PANEL: Final[str] = "_view_panel_registered"


def unique_id(entry_id: str, suffix: str) -> str:
    """Stabile, kollisionsfreie unique_id (Domain + Entry + Suffix)."""
    return f"{DOMAIN}_{entry_id}_{suffix}"


def storage_suffix(entry_id: str) -> str:
    return f"state_{entry_id}"


# --------------------------------------------------------------------------- #
# Profile (Route benni / eltern) — FLEET-16, Blaupause benni_core_state
# --------------------------------------------------------------------------- #
CONF_PROFILE: Final = "profile"
PROFILE_BENNI: Final = "benni"
PROFILE_ELTERN: Final = "eltern"
PROFILES: Final = [PROFILE_BENNI, PROFILE_ELTERN]
DEFAULT_PROFILE_ROUTE: Final = PROFILE_BENNI
PROFILE_LABELS: Final = {PROFILE_BENNI: "Benni", PROFILE_ELTERN: "Eltern"}

# --------------------------------------------------------------------------- #
# Combined-Zustände (Lastenheft §4.1)
# --------------------------------------------------------------------------- #
STATE_VERRIEGELT: Final = "verriegelt"
STATE_ENTRIEGELT: Final = "entriegelt"
STATE_UNBEKANNT: Final = "unbekannt"
STATE_NICHT_ERREICHBAR: Final = "nicht_erreichbar"

# Roh-Zustände des physischen Schlosses (HA lock-Domain).
RAW_LOCKED: Final = "locked"
RAW_UNLOCKED: Final = "unlocked"
RAW_UNLOCKING: Final = "unlocking"
RAW_LOCKING: Final = "locking"
RAW_OPEN: Final = "open"
RAW_UNKNOWN: Final = "unknown"
RAW_UNAVAILABLE: Final = "unavailable"

# Aktionen, die der Coordinator ausführen darf. R-06: NIEMALS lock.open.
ACTION_LOCK: Final = "lock"
ACTION_UNLOCK: Final = "unlock"
ACTION_NONE: Final = "none"

# --------------------------------------------------------------------------- #
# Eingangs-Wertebereiche (konsumiert aus benni_core_state)
# --------------------------------------------------------------------------- #
EFFECTIVE_HOME: Final = "home"
EFFECTIVE_AWAY: Final = "away"
EFFECTIVE_ARRIVING: Final = "arriving"
EFFECTIVE_LEAVING: Final = "leaving"
EFFECTIVE_UNCERTAIN: Final = "uncertain"
EFFECTIVE_STALE: Final = "stale"

# --------------------------------------------------------------------------- #
# Schwellen & Konstanten (Lastenheft §6) — nicht konfigurierbar außer Batterie.
# --------------------------------------------------------------------------- #
AUTO_LOCK_STABILIZE_SECONDS: Final = 60   # R-01: Schutz gegen kurze PSC-Flaps
AUTO_UNLOCK_STABILIZE_SECONDS: Final = 5  # R-02: kurzer Bestätigungspuffer
HA_START_DELAY_SECONDS: Final = 30        # R-07: System muss stabil sein
UPDATE_INTERVAL_SECONDS: Final = 60       # periodische Re-Evaluation
UNLOCK_COOLDOWN_SECONDS: Final = 180
LOCK_UNLOCK_ANTI_FLAP_SECONDS: Final = 120
AUTO_UNLOCK_MIN_CONFIDENCE: Final = 0.9
LOCK_FEATURE_OPEN: Final = 1

DEFAULT_BATTERY_CRITICAL: Final = 20      # < 20 % (Lastenheft §6, konfigurierbar)

# --------------------------------------------------------------------------- #
# Config-Keys — Quell-Entities (alle als Entity-IDs aus dem Flow)
# --------------------------------------------------------------------------- #
CONF_LOCK_ENTITY: Final = "lock_entity"
CONF_PRESENCE_EFFECTIVE: Final = "presence_effective_entity"
CONF_BATTERY: Final = "battery_entity"          # optional

# Options.
CONF_APPLY_ENABLED: Final = "apply_enabled"
CONF_STARTUP_BLOCK_SECONDS: Final = "startup_block_seconds"
CONF_BATTERY_CRITICAL: Final = "battery_critical_percent"

# Defaults.
DEFAULT_APPLY_ENABLED: Final = False            # Shadow-safe out of the box
DEFAULT_STARTUP_BLOCK_SECONDS: Final = HA_START_DELAY_SECONDS

# --------------------------------------------------------------------------- #
# Per-Profil-Prefill: bekannte Live-IDs (greift nur, WENN Entity existiert).
# Benni-Anlage (einhornzentrale) via HA-MCP ermittelt. "eltern" bewusst leer.
# --------------------------------------------------------------------------- #
PROFILE_PREFILL: Final[dict[str, dict[str, str]]] = {
    PROFILE_BENNI: {
        CONF_LOCK_ENTITY: "lock.aqara_smart_lock_u200",
        # Live existiert (renamed-device, system_-Präfix) NUR der system_-Slug.
        # Der frühere clean slug existierte nie → presence_effective_missing.
        CONF_PRESENCE_EFFECTIVE: "sensor.system_benni_core_state_presence_effective",
        CONF_BATTERY: "sensor.aqara_smart_lock_u200_battery",
    },
    PROFILE_ELTERN: {},
}

# Renamed-device (system_) Entity-ID-Fix: alte Builds prefillten/auto-migrierten
# den clean slug in entry.data, der live nie existierte → presence_effective_missing.
# Diese Legacy-IDs werden beim Setup auf den aktuellen PROFILE_PREFILL-Default
# repointet — NUR wenn keine explizite Options-Override vorliegt (User gewinnt).
LEGACY_PRESENCE_EFFECTIVE_IDS: Final[frozenset[str]] = frozenset({
    "sensor.benni_core_state_presence_effective",
})

# Reihenfolge der Quell-Felder im Config-Flow (ein Schritt) + Optionen.
SOURCE_KEYS: Final = (
    CONF_LOCK_ENTITY, CONF_PRESENCE_EFFECTIVE, CONF_BATTERY,
)
OPTION_KEYS: Final = (
    CONF_APPLY_ENABLED, CONF_STARTUP_BLOCK_SECONDS, CONF_BATTERY_CRITICAL,
)

# --------------------------------------------------------------------------- #
# unique_id-Suffixe + Feature-Namen (→ <profile>_door_policy_<feature>)
# --------------------------------------------------------------------------- #
UID_LOCK_STATE: Final = "lock_state"
UID_DEBUG: Final = "debug"
UID_AUTO_LOCK: Final = "auto_lock_active"
UID_AUTO_UNLOCK: Final = "auto_unlock_active"
UID_BATTERY_CRITICAL: Final = "battery_critical"
UID_APPLY_BLOCKED: Final = "apply_blocked"

NAME_LOCK_STATE: Final = "Lock State"
NAME_DEBUG: Final = "Debug"
NAME_AUTO_LOCK: Final = "Auto Lock Active"
NAME_AUTO_UNLOCK: Final = "Auto Unlock Active"
NAME_BATTERY_CRITICAL: Final = "Battery Critical"
NAME_APPLY_BLOCKED: Final = "Apply Blocked"

# --------------------------------------------------------------------------- #
# Services
# --------------------------------------------------------------------------- #
SERVICE_APPLY_NOW: Final = "apply_now"
SERVICE_RESYNC: Final = "resync"
SERVICE_SET_APPLY_ENABLED: Final = "set_apply_enabled"

# --------------------------------------------------------------------------- #
# Panel / WebSocket-API (Observability + Shadow-Steuerung, Muster blind_policy)
# --------------------------------------------------------------------------- #
PANEL_URL_PATH: Final = "benni_door_policy"
PANEL_TITLE: Final = "Door Policy"
PANEL_ICON: Final = "mdi:lock-smart"
FRONTEND_DIR_URL: Final = "/benni_door_policy_app"
FRONTEND_ENTRY: Final = f"{FRONTEND_DIR_URL}/main.js"
PANEL_ELEMENT: Final = "bdp-app"

WS_GET_STATUS: Final = f"{DOMAIN}/get_status"
WS_APPLY_NOW: Final = f"{DOMAIN}/apply_now"
WS_RESYNC: Final = f"{DOMAIN}/resync"
WS_SET_APPLY_ENABLED: Final = f"{DOMAIN}/set_apply_enabled"
