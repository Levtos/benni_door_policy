"""Pure Decision-Engine der Door-Policy (Türschloss U200) — HA-frei, voll testbar.

Implementiert das reviewte Lastenheft
``einhornzentrale/docs/lastenhefte/reviewed/tuerschloss/`` 1:1:

  * ``combined_state()``  — Roh-Schlosszustand → fachlicher Combined-Zustand (§4.1).
  * ``decide()``          — Auto-Lock-/Auto-Unlock-Szenarien (R-01..R-08) + Gating.

Strikte Trennung: ``decide`` ermittelt nur die *gewünschte* Aktion rein aus dem
Context; das Gating-Overlay setzt ``apply_allowed``/``blockers``, ohne die Aktion
zu verändern (Shadow-Vergleich bleibt aussagekräftig).

SICHERHEIT (R-06, absolut): Diese Engine gibt ausschließlich ``lock`` / ``unlock`` /
``none`` zurück. ``open`` (Falle ziehen) ist kein gültiger Rückgabewert und darf vom
Coordinator niemals abgeleitet werden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import (
    ACTION_LOCK,
    ACTION_NONE,
    ACTION_UNLOCK,
    AUTO_UNLOCK_MIN_CONFIDENCE,
    DEFAULT_BATTERY_CRITICAL,
    EFFECTIVE_ARRIVING,
    EFFECTIVE_AWAY,
    EFFECTIVE_HOME,
    EFFECTIVE_LEAVING,
    EFFECTIVE_STALE,
    EFFECTIVE_UNCERTAIN,
    LOCK_UNLOCK_ANTI_FLAP_SECONDS,
    RAW_LOCKED,
    RAW_LOCKING,
    RAW_OPEN,
    RAW_UNAVAILABLE,
    RAW_UNLOCKED,
    RAW_UNLOCKING,
    RAW_UNKNOWN,
    STATE_ENTRIEGELT,
    STATE_NICHT_ERREICHBAR,
    STATE_UNBEKANNT,
    STATE_VERRIEGELT,
    UNLOCK_COOLDOWN_SECONDS,
)

# Unsichere Combined-Zustände — hier niemals automatisch handeln (R-04).
_UNSAFE_STATES: frozenset[str] = frozenset({STATE_UNBEKANNT, STATE_NICHT_ERREICHBAR})
_PERSONAL_AWAY = "abwesend"
_PERSONAL_HOME = "zuhause"
_PERSONAL_HOME_EQUIVALENT: frozenset[str] = frozenset({"zuhause", "bei_eltern"})
# Persönliche Anwesenheit ist "unbekannt" → konservativ als zuhause behandeln
# (Lastenheft §2: keine automatische Aktion, weder Lock noch Unlock).
_PERSONAL_UNKNOWN: frozenset[str] = frozenset({"", "unknown", "unavailable"})


@dataclass(frozen=True)
class Context:
    """Snapshot aller Quell-Inputs für eine Entscheidung. None = unknown."""

    raw_lock_state: str | None = None       # locked / unlocked / unlocking / ...
    effective_presence: str | None = None   # home / away / arriving / leaving / uncertain / stale
    presence_confidence: float | None = None
    raw_presence: str | None = None         # zuhause / bei_eltern / abwesend
    battery_percent: float | None = None    # % (Attribut, optional)
    lock_supported_features: int | None = None


@dataclass
class Decision:
    combined_state: str
    action: str                              # lock / unlock / none (NIE open)
    auto_lock_active: bool
    auto_unlock_active: bool
    reason: str
    battery_critical: bool = False
    blockers: list[str] = field(default_factory=list)
    apply_allowed: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "combined_state": self.combined_state,
            "action": self.action,
            "auto_lock_active": self.auto_lock_active,
            "auto_unlock_active": self.auto_unlock_active,
            "reason": self.reason,
            "battery_critical": self.battery_critical,
            "blockers": list(self.blockers),
            "apply_allowed": self.apply_allowed,
        }


def combined_state(raw_lock_state: str | None) -> str:
    """Roh-Schlosszustand → fachlicher Combined-Zustand (Lastenheft §4.1)."""
    raw = (raw_lock_state or "").lower()
    if raw == RAW_LOCKED:
        return STATE_VERRIEGELT
    if raw in (RAW_UNLOCKED, RAW_UNLOCKING, RAW_LOCKING, RAW_OPEN):
        # locking/open werden konservativ als "nicht verriegelt" behandelt;
        # eine laufende Verriegelung soll keinen zweiten Lock-Befehl provozieren,
        # aber auch keinen Unlock — das deckt R-03 (Zielzustand) im Coordinator ab.
        return STATE_ENTRIEGELT
    if raw == RAW_UNAVAILABLE:
        return STATE_NICHT_ERREICHBAR
    # RAW_UNKNOWN, leer, alles Unerwartete → unbekannt (konservativ, R-04).
    return STATE_UNBEKANNT


def battery_critical(battery_percent: float | None, threshold: int) -> bool:
    return battery_percent is not None and battery_percent < threshold


def decide(
    ctx: Context,
    *,
    apply_enabled: bool,
    startup_ready: bool,
    battery_threshold: int = DEFAULT_BATTERY_CRITICAL,
    recent_lock_action: str | None = None,
    recent_lock_action_age_s: float | None = None,
    raw_lock_changed_age_s: float | None = None,
) -> Decision:
    """Vollständige Entscheidung inkl. Gating-Overlay (Lastenheft §4.2/§4.3, R-01..R-08).

    Auto-Lock   (R-01): effective_presence away/leaving UND persoenliche Anwesenheit
                        abwesend UND Zustand entriegelt → ``lock``.
    Auto-Unlock (R-02): effective_presence home/arriving mit hoher Confidence UND
                        Zustand verriegelt → ``unlock``.
    R-03 (Zielzustand erreicht) ergibt sich implizit: Auto-Lock verlangt entriegelt,
    Auto-Unlock verlangt verriegelt — ist das Schloss schon im Ziel, matcht keine Regel.
    R-04 (unsicher) + R-05 (keine Verriegelung bei Anwesenheit) sind explizit gegated.
    """
    state = combined_state(ctx.raw_lock_state)
    bat_crit = battery_critical(ctx.battery_percent, battery_threshold)

    # Szenarien (rein kontextuell, ohne Gating).
    confidence = ctx.presence_confidence
    high_confidence = (
        confidence is not None and confidence >= AUTO_UNLOCK_MIN_CONFIDENCE
    )
    personal_away = ctx.raw_presence == _PERSONAL_AWAY
    # Lastenheft §4.3 / R-02: Auto-Unlock verlangt "Persönliche Anwesenheit ≠ zuhause".
    # Unbekannt/leer wird konservativ als zuhause behandelt (§2) → kein Auto-Unlock.
    personal_not_home = (
        ctx.raw_presence is not None
        and ctx.raw_presence != _PERSONAL_HOME
        and ctx.raw_presence not in _PERSONAL_UNKNOWN
    )
    auto_lock_active = (
        ctx.effective_presence in (EFFECTIVE_AWAY, EFFECTIVE_LEAVING)
        and personal_away
        and state == STATE_ENTRIEGELT
    )
    auto_unlock_active = (
        ctx.effective_presence in (EFFECTIVE_HOME, EFFECTIVE_ARRIVING)
        and high_confidence
        and personal_not_home
        and state == STATE_VERRIEGELT
    )

    blockers: list[str] = []
    apply_allowed = True

    # R-04: unsicherer Zustand → niemals automatisch handeln.
    if state in _UNSAFE_STATES:
        blockers.append(f"source_unsafe:{state}")
        apply_allowed = False

    if ctx.effective_presence == EFFECTIVE_HOME:
        blockers.append("present_no_autolock")
    # R-02: zuhause bereits anwesend → Auto-Unlock ist ein Heimkehr-Event, kein
    # Dauerzustand. Informativer Blocker macht den Morgen-Fall sichtbar.
    if state == STATE_VERRIEGELT and ctx.raw_presence == _PERSONAL_HOME:
        blockers.append("present_no_autounlock")
    if ctx.raw_presence in _PERSONAL_HOME_EQUIVALENT:
        blockers.append("personal_present_no_autolock")
    elif ctx.raw_presence is None or ctx.raw_presence in ("", "unknown", "unavailable"):
        blockers.append("presence_personal_missing")

    if ctx.effective_presence is None:
        blockers.append("presence_effective_missing")
    elif ctx.effective_presence in (EFFECTIVE_UNCERTAIN, EFFECTIVE_STALE):
        blockers.append(f"presence_{ctx.effective_presence}")

    if ctx.effective_presence == EFFECTIVE_ARRIVING and not high_confidence:
        blockers.append("arriving_confidence_low")
    if ctx.effective_presence == EFFECTIVE_HOME and not high_confidence:
        blockers.append("home_confidence_low")

    if not apply_enabled:
        blockers.append("apply_disabled")
        apply_allowed = False
    if not startup_ready:
        blockers.append("startup_block")
        apply_allowed = False

    # Aktion bestimmen (R-04 hat Vorrang).
    if state in _UNSAFE_STATES:
        action = ACTION_NONE
        reason = f"unsicherer Zustand ({state}) — keine Aktion (R-04)"
    elif auto_lock_active:
        action = ACTION_LOCK
        reason = "auto_lock: effective_presence away/leaving + personal abwesend + entriegelt → verriegeln (R-01)"
    elif auto_unlock_active:
        action = ACTION_UNLOCK
        reason = "auto_unlock: home/arriving + high confidence + persönlich ≠ zuhause + verriegelt → entriegeln (R-02)"
    else:
        action = ACTION_NONE
        reason = "kein Szenario aktiv — Schloss bleibt (R-03)"

    if action == ACTION_UNLOCK and _recent(
        recent_lock_action, recent_lock_action_age_s, ACTION_UNLOCK, UNLOCK_COOLDOWN_SECONDS
    ):
        blockers.append("unlock_cooldown")
        apply_allowed = False

    if action in (ACTION_LOCK, ACTION_UNLOCK):
        opposite = ACTION_UNLOCK if action == ACTION_LOCK else ACTION_LOCK
        if _recent(
            recent_lock_action,
            recent_lock_action_age_s,
            opposite,
            LOCK_UNLOCK_ANTI_FLAP_SECONDS,
        ):
            blockers.append("lock_unlock_anti_flap")
            apply_allowed = False
        if (
            raw_lock_changed_age_s is not None
            and raw_lock_changed_age_s < LOCK_UNLOCK_ANTI_FLAP_SECONDS
        ):
            blockers.append("raw_lock_recently_changed")
            apply_allowed = False

    return Decision(
        combined_state=state,
        action=action,
        auto_lock_active=auto_lock_active,
        auto_unlock_active=auto_unlock_active,
        reason=reason,
        battery_critical=bat_crit,
        blockers=blockers,
        apply_allowed=apply_allowed,
    )


def _recent(
    recent_action: str | None,
    age_s: float | None,
    expected_action: str,
    window_s: int,
) -> bool:
    return (
        recent_action == expected_action
        and age_s is not None
        and age_s < window_s
    )
