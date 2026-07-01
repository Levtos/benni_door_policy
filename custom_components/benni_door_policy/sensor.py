"""Sensor-Plattform: Combined Lock State (+ Attribute) und Debug."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    NAME_DEBUG,
    NAME_LOCK_STATE,
    UID_DEBUG,
    UID_LOCK_STATE,
    unique_id,
)
from .entity import DoorPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        LockStateSensor(coord, entry),
        DebugSensor(coord, entry),
    ])


class LockStateSensor(DoorPolicyEntity, SensorEntity):
    """Zentraler Combined-Sensor (Lastenheft §3). State = fachlicher Zustand."""

    _attr_icon = "mdi:lock"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_LOCK_STATE)
        self._attr_name = NAME_LOCK_STATE

    @property
    def native_value(self):
        d = self.coord.last_decision
        return d.combined_state if d else None

    @property
    def extra_state_attributes(self):
        d = self.coord.last_decision
        ctx = self.coord.build_context()
        return {
            "raw_lock_state": ctx.raw_lock_state,
            "auto_lock_aktiv": d.auto_lock_active if d else None,
            "auto_unlock_aktiv": d.auto_unlock_active if d else None,
            "batterie_prozent": ctx.battery_percent,
            "batterie_kritisch": d.battery_critical if d else None,
            "effective_presence": ctx.effective_presence,
            "presence_confidence": ctx.presence_confidence,
        }


class DebugSensor(DoorPolicyEntity, SensorEntity):
    """State = aktive Aktion; Attribute = volle Begründung + Gating-Internals."""

    _attr_icon = "mdi:bug-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_DEBUG)
        self._attr_name = NAME_DEBUG

    @property
    def native_value(self):
        d = self.coord.last_decision
        return d.action if d else None

    @property
    def extra_state_attributes(self):
        d = self.coord.last_decision
        ctx = self.coord.build_context()
        return {
            "combined_state": d.combined_state if d else None,
            "action": d.action if d else None,
            "reason": d.reason if d else None,
            "auto_lock_active": d.auto_lock_active if d else None,
            "auto_unlock_active": d.auto_unlock_active if d else None,
            "raw_lock_state": ctx.raw_lock_state,
            "effective_presence": ctx.effective_presence,
            "presence_confidence": ctx.presence_confidence,
            "battery_percent": ctx.battery_percent,
            "battery_critical": d.battery_critical if d else None,
            "profile": self.coord.profile_route,
            "apply_enabled": self.coord.apply_enabled,
            "startup_ready": self.coord.startup_ready,
            "blockers": list(d.blockers) if d else [],
        }
