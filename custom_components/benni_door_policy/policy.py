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
    BAND_HOME,
    DEFAULT_BATTERY_CRITICAL,
    PRESENCE_AWAY,
    PRESENCE_HOME,
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
)

# Unsichere Combined-Zustände — hier niemals automatisch handeln (R-04).
_UNSAFE_STATES: frozenset[str] = frozenset({STATE_UNBEKANNT, STATE_NICHT_ERREICHBAR})


@dataclass(frozen=True)
class Context:
    """Snapshot aller Quell-Inputs für eine Entscheidung. None = unknown."""

    raw_lock_state: str | None = None       # locked / unlocked / unlocking / ...
    presence_personal: str | None = None    # zuhause / abwesend / bei_eltern
    home_band: str | None = None            # home / near / preheat / far
    battery_percent: float | None = None    # % (Attribut, optional)


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
) -> Decision:
    """Vollständige Entscheidung inkl. Gating-Overlay (Lastenheft §4.2/§4.3, R-01..R-08).

    Auto-Lock   (R-01): Anwesenheit = abwesend UND Zustand = entriegelt → ``lock``.
    Auto-Unlock (R-02): Heimband = home UND Anwesenheit ≠ zuhause UND Zustand =
                        verriegelt → ``unlock``.
    R-03 (Zielzustand erreicht) ergibt sich implizit: Auto-Lock verlangt entriegelt,
    Auto-Unlock verlangt verriegelt — ist das Schloss schon im Ziel, matcht keine Regel.
    R-04 (unsicher) + R-05 (keine Verriegelung bei Anwesenheit) sind explizit gegated.
    """
    state = combined_state(ctx.raw_lock_state)
    bat_crit = battery_critical(ctx.battery_percent, battery_threshold)

    # Szenarien (rein kontextuell, ohne Gating).
    auto_lock_active = (
        ctx.presence_personal == PRESENCE_AWAY and state == STATE_ENTRIEGELT
    )
    auto_unlock_active = (
        ctx.home_band == BAND_HOME
        and ctx.presence_personal != PRESENCE_HOME
        and state == STATE_VERRIEGELT
    )

    blockers: list[str] = []
    apply_allowed = True

    # R-04: unsicherer Zustand → niemals automatisch handeln.
    if state in _UNSAFE_STATES:
        blockers.append(f"source_unsafe:{state}")
        apply_allowed = False

    # R-05: keine automatische Verriegelung bei Anwesenheit (Fluchtweg).
    #       (Greift nur defensiv; auto_lock_active ist bei zuhause ohnehin False.)
    if ctx.presence_personal == PRESENCE_HOME:
        blockers.append("present_no_autolock")

    if ctx.presence_personal is None:
        # Lastenheft §2: Anwesenheit unknown → konservativ als zuhause behandeln
        # (keine automatische Verriegelung).
        blockers.append("presence_unknown")

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
        reason = "auto_lock: abwesend + entriegelt → verriegeln (R-01)"
    elif auto_unlock_active:
        action = ACTION_UNLOCK
        reason = "auto_unlock: Heimband home + nicht zuhause + verriegelt → entriegeln (R-02)"
    else:
        action = ACTION_NONE
        reason = "kein Szenario aktiv — Schloss bleibt (R-03)"

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
