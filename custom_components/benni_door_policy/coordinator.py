"""Door-Policy-Coordinator (Single-Instance pro Config-Entry).

HA-Brücke um die pure Engine (policy.py):

  * liest Quell-Entities (Schloss, Anwesenheit, Heimband, Batterie),
  * rechnet ``policy.decide`` und führt die Aktion **gated** aus (apply_enabled =
    Shadow-Master, Default False),
  * Stabilisierung wie im Lastenheft (R-01: 60 s, R-02: 5 s) via verzögertem
    Re-Check vor dem Schaltbefehl — eine instabile Quelle löst keinen Befehl aus,
  * Resync nach HA-Start (R-07, 30 s) und periodisch.

SICHERHEIT (R-06, absolut): Der Coordinator ruft ausschließlich ``lock.lock`` und
``lock.unlock``. ``lock.open`` wird nirgends aufgerufen.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)

try:  # pragma: no cover
    from homeassistant.helpers.start import async_at_started
except Exception:  # pragma: no cover
    async_at_started = None  # type: ignore[assignment]

from . import policy
from .const import (
    ACTION_LOCK,
    ACTION_NONE,
    ACTION_UNLOCK,
    AUTO_LOCK_STABILIZE_SECONDS,
    AUTO_UNLOCK_STABILIZE_SECONDS,
    CONF_APPLY_ENABLED,
    CONF_BATTERY,
    CONF_BATTERY_CRITICAL,
    CONF_HOME_BAND,
    CONF_LOCK_ENTITY,
    CONF_PRESENCE_PERSONAL,
    CONF_PROFILE,
    CONF_STARTUP_BLOCK_SECONDS,
    DATA_SKIP_RELOAD_COUNT,
    DEFAULT_APPLY_ENABLED,
    DEFAULT_BATTERY_CRITICAL,
    DEFAULT_PROFILE_ROUTE,
    DEFAULT_STARTUP_BLOCK_SECONDS,
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)
from .storage import make_store

_LOGGER = logging.getLogger(__name__)


def _float_or_none(s: str | None) -> float | None:
    if s in (None, "", "unknown", "unavailable"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


class DoorPolicyCoordinator:
    """Eine Instanz pro Config-Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = make_store(hass, entry.entry_id)
        self._unsub: list[CALLBACK_TYPE] = []
        self._listeners: list[CALLBACK_TYPE] = []

        self._started_at = time.monotonic()
        self._ha_started = False
        self._startup_unsub: CALLBACK_TYPE | None = None

        # Verzögerter (stabilisierter) Schaltauftrag — höchstens einer offen.
        self._pending_action: str | None = None
        self._pending_unsub: CALLBACK_TYPE | None = None
        self._pending_started_at: float | None = None   # monotonic
        self._pending_delay: int = 0

        self._last_decision: policy.Decision | None = None

    # ----- options / profile -----
    @property
    def _opts(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    def _opt(self, key: str, default: Any = None) -> Any:
        return self._opts.get(key, default)

    @property
    def profile_route(self) -> str:
        return self._opt(CONF_PROFILE, DEFAULT_PROFILE_ROUTE)

    @property
    def lock_entity(self) -> str | None:
        return self._opt(CONF_LOCK_ENTITY)

    @property
    def apply_enabled(self) -> bool:
        return bool(self._opt(CONF_APPLY_ENABLED, DEFAULT_APPLY_ENABLED))

    @property
    def startup_block_seconds(self) -> int:
        return int(self._opt(CONF_STARTUP_BLOCK_SECONDS, DEFAULT_STARTUP_BLOCK_SECONDS))

    @property
    def battery_threshold(self) -> int:
        return int(self._opt(CONF_BATTERY_CRITICAL, DEFAULT_BATTERY_CRITICAL))

    # ----- öffentliche Status-Accessoren -----
    @property
    def last_decision(self) -> policy.Decision | None:
        return self._last_decision

    def _startup_ready(self) -> bool:
        if not self._ha_started:
            return False
        return (time.monotonic() - self._started_at) >= self.startup_block_seconds

    @property
    def startup_ready(self) -> bool:
        return self._startup_ready()

    # ----- lifecycle -----
    @callback
    def async_start(self) -> None:
        if async_at_started is not None:
            self._unsub.append(async_at_started(self.hass, self._on_started))
        elif self.hass.is_running:
            self._on_started(None)
        else:
            self._unsub.append(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._on_started)
            )

        watch: set[str] = set()
        for key in (CONF_LOCK_ENTITY, CONF_PRESENCE_PERSONAL, CONF_HOME_BAND, CONF_BATTERY):
            v = self._opt(key)
            if isinstance(v, str) and v:
                watch.add(v)
        if watch:
            self._unsub.append(
                async_track_state_change_event(self.hass, list(watch), self._on_state_change)
            )
        self._unsub.append(
            async_track_time_interval(
                self.hass, self._on_interval, timedelta(seconds=UPDATE_INTERVAL_SECONDS)
            )
        )

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        for unsub in (self._startup_unsub, self._pending_unsub):
            if unsub is not None:
                unsub()
        self._startup_unsub = None
        self._pending_unsub = None

    @callback
    def _on_started(self, _event) -> None:
        self._ha_started = True
        self._started_at = time.monotonic()
        self._schedule_startup_expiry()
        self.hass.async_create_task(self.async_evaluate())

    def _schedule_startup_expiry(self) -> None:
        if self._startup_unsub is not None:
            self._startup_unsub()
        seconds = max(0, int(self.startup_block_seconds))

        @callback
        def _fire(_now) -> None:
            self._startup_unsub = None
            self.hass.async_create_task(self.async_evaluate())

        # R-07: nach HA-Start-Delay erneut prüfen (Resync).
        self._startup_unsub = async_call_later(self.hass, seconds + 1, _fire)

    @callback
    def _on_interval(self, _now) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _on_state_change(self, _event: Event) -> None:
        self.hass.async_create_task(self.async_evaluate())

    # ----- persistence -----
    async def async_load(self) -> None:
        raw = await self._store.async_load() or {}
        # Door-Policy ist weitgehend zustandslos; persistierte Decision dient nur
        # der Sofort-Anzeige nach Neustart bis zur ersten Re-Evaluation.
        _ = raw

    async def _async_save(self) -> None:
        await self._store.async_save({
            "last_decision": self._last_decision.as_dict() if self._last_decision else None,
        })

    # ----- context -----
    def _read(self, key: str) -> str | None:
        eid = self._opt(key)
        if not eid:
            return None
        st = self.hass.states.get(eid)
        if st is None:
            return None
        return st.state

    def _battery_percent(self) -> float | None:
        """Batterie aus eigener Entity ODER als Attribut am Schloss (Lastenheft N-2)."""
        eid = self._opt(CONF_BATTERY)
        if eid:
            val = _float_or_none(self._read(CONF_BATTERY))
            if val is not None:
                return val
        # Fallback: Attribut battery_level am Lock-Entity.
        if self.lock_entity:
            st = self.hass.states.get(self.lock_entity)
            if st is not None:
                return _float_or_none(st.attributes.get("battery_level"))
        return None

    def build_context(self) -> policy.Context:
        # Roh-Schlosszustand inkl. unavailable (nicht über _read filtern!).
        lock_st = self.hass.states.get(self.lock_entity) if self.lock_entity else None
        raw_lock = lock_st.state if lock_st is not None else None
        return policy.Context(
            raw_lock_state=raw_lock,
            presence_personal=self._read(CONF_PRESENCE_PERSONAL),
            home_band=self._read(CONF_HOME_BAND),
            battery_percent=self._battery_percent(),
        )

    # ----- evaluation -----
    async def async_evaluate(self) -> policy.Decision:
        ctx = self.build_context()
        decision = policy.decide(
            ctx,
            apply_enabled=self.apply_enabled,
            startup_ready=self._startup_ready(),
            battery_threshold=self.battery_threshold,
        )
        self._last_decision = decision

        # Stabilisierten Schaltauftrag planen (oder einen widersprechenden abbrechen).
        if decision.apply_allowed and decision.action in (ACTION_LOCK, ACTION_UNLOCK):
            self._schedule_action(decision.action)
        else:
            self._cancel_pending()

        await self._async_save()
        for cb in self._listeners:
            cb()
        return decision

    # ----- stabilisierter Apply (R-01/R-02) -----
    def _schedule_action(self, action: str) -> None:
        # Schon der gleiche Auftrag in der Pipeline → nicht neu starten (kein Reset
        # der Stabilisierungsuhr durch jeden Quell-Tick).
        if self._pending_action == action and self._pending_unsub is not None:
            return
        self._cancel_pending()
        self._pending_action = action
        delay = (
            AUTO_LOCK_STABILIZE_SECONDS if action == ACTION_LOCK
            else AUTO_UNLOCK_STABILIZE_SECONDS
        )
        self._pending_started_at = time.monotonic()
        self._pending_delay = delay

        @callback
        def _fire(_now) -> None:
            self._pending_unsub = None
            self.hass.async_create_task(self._confirm_and_apply(action))

        self._pending_unsub = async_call_later(self.hass, delay, _fire)

    def _cancel_pending(self) -> None:
        if self._pending_unsub is not None:
            self._pending_unsub()
        self._pending_unsub = None
        self._pending_action = None
        self._pending_started_at = None
        self._pending_delay = 0

    async def _confirm_and_apply(self, action: str) -> None:
        """Nach Stabilisierung: Context neu lesen, nur ausführen, wenn die Aktion
        immer noch gewünscht und erlaubt ist (Schutz gegen kurze Flaps)."""
        self._pending_action = None
        ctx = self.build_context()
        decision = policy.decide(
            ctx,
            apply_enabled=self.apply_enabled,
            startup_ready=self._startup_ready(),
            battery_threshold=self.battery_threshold,
        )
        self._last_decision = decision
        if not (decision.apply_allowed and decision.action == action):
            for cb in self._listeners:
                cb()
            return
        await self._apply(action)
        for cb in self._listeners:
            cb()

    async def _apply(self, action: str) -> None:
        if not self.lock_entity:
            return
        # R-06: NUR lock/unlock. Niemals 'open'.
        service = "lock" if action == ACTION_LOCK else "unlock"
        try:
            await self.hass.services.async_call(
                "lock", service, {"entity_id": self.lock_entity}, blocking=False
            )
            _LOGGER.info("door_policy: lock.%s → %s", service, self.lock_entity)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("door_policy: lock.%s failed: %s", service, err)

    # ----- service surface -----
    async def async_apply_now(self) -> policy.Decision:
        """Sofort prüfen und (ohne Stabilisierung) anwenden, falls erlaubt."""
        decision = await self.async_evaluate()
        if decision.apply_allowed and decision.action in (ACTION_LOCK, ACTION_UNLOCK):
            self._cancel_pending()
            await self._apply(decision.action)
        return decision

    async def async_resync(self) -> policy.Decision:
        return await self.async_evaluate()

    async def async_set_apply_enabled(self, value: bool) -> None:
        self._skip_next_entry_reload()
        new_options = {**self.entry.options, CONF_APPLY_ENABLED: bool(value)}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        await self.async_evaluate()

    def _skip_next_entry_reload(self) -> None:
        data = self.hass.data.setdefault(DOMAIN, {})
        data[DATA_SKIP_RELOAD_COUNT] = int(data.get(DATA_SKIP_RELOAD_COUNT) or 0) + 1

    # ----- status snapshot (WS-API / Panel) -----
    def _pending_remaining(self) -> int | None:
        if self._pending_action is None or self._pending_started_at is None:
            return None
        rem = self._pending_delay - (time.monotonic() - self._pending_started_at)
        return max(0, int(round(rem)))

    def _startup_remaining(self) -> int:
        if not self._ha_started:
            return self.startup_block_seconds
        rem = self.startup_block_seconds - (time.monotonic() - self._started_at)
        return max(0, int(round(rem)))

    def status_snapshot(self) -> dict[str, Any]:
        d = self.last_decision
        ctx = self.build_context()
        return {
            "profile": self.profile_route,
            "apply_enabled": self.apply_enabled,
            "startup_ready": self.startup_ready,
            "startup_remaining_s": self._startup_remaining(),
            "ha_start_delay_s": self.startup_block_seconds,
            "combined_state": d.combined_state if d else None,
            "action": d.action if d else None,
            "auto_lock_active": d.auto_lock_active if d else None,
            "auto_unlock_active": d.auto_unlock_active if d else None,
            "reason": d.reason if d else None,
            "apply_allowed": d.apply_allowed if d else None,
            "blockers": list(d.blockers) if d else [],
            "battery_critical": d.battery_critical if d else None,
            "battery_threshold": self.battery_threshold,
            # Pending wird vom Coordinator NUR gesetzt, wenn apply_allowed — d.h.
            # während des Startup-Blocks gibt es bewusst keinen Countdown.
            "pending_action": self._pending_action,
            "pending_remaining_s": self._pending_remaining(),
            "stabilize_lock_s": AUTO_LOCK_STABILIZE_SECONDS,
            "stabilize_unlock_s": AUTO_UNLOCK_STABILIZE_SECONDS,
            "lock_entity": self.lock_entity,
            "context": {
                "raw_lock_state": ctx.raw_lock_state,
                "presence_personal": ctx.presence_personal,
                "home_band": ctx.home_band,
                "battery_percent": ctx.battery_percent,
            },
        }

    # ----- listeners -----
    def add_listener(self, cb: CALLBACK_TYPE) -> None:
        self._listeners.append(cb)

    def remove_listener(self, cb: CALLBACK_TYPE) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)


# ------------------------------------------------------------------- lookups
def all_coordinators(hass: HomeAssistant) -> list[DoorPolicyCoordinator]:
    from .const import DATA_COORDINATOR
    return [
        b[DATA_COORDINATOR]
        for b in hass.data.get(DOMAIN, {}).values()
        if isinstance(b, dict) and DATA_COORDINATOR in b
    ]
