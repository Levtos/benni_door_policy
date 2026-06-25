"""Binary-Sensor-Plattform: Auto-Lock-/Auto-Unlock-Szenario, Batterie-kritisch, Apply-Blocked."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    NAME_APPLY_BLOCKED,
    NAME_AUTO_LOCK,
    NAME_AUTO_UNLOCK,
    NAME_BATTERY_CRITICAL,
    UID_APPLY_BLOCKED,
    UID_AUTO_LOCK,
    UID_AUTO_UNLOCK,
    UID_BATTERY_CRITICAL,
    unique_id,
)
from .entity import DoorPolicyEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([
        AutoLockBinarySensor(coord, entry),
        AutoUnlockBinarySensor(coord, entry),
        BatteryCriticalBinarySensor(coord, entry),
        ApplyBlockedBinarySensor(coord, entry),
    ])


class AutoLockBinarySensor(DoorPolicyEntity, BinarySensorEntity):
    _attr_icon = "mdi:lock-clock"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_AUTO_LOCK)
        self._attr_name = NAME_AUTO_LOCK

    @property
    def is_on(self) -> bool:
        d = self.coord.last_decision
        return bool(d and d.auto_lock_active)


class AutoUnlockBinarySensor(DoorPolicyEntity, BinarySensorEntity):
    _attr_icon = "mdi:lock-open-variant"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_AUTO_UNLOCK)
        self._attr_name = NAME_AUTO_UNLOCK

    @property
    def is_on(self) -> bool:
        d = self.coord.last_decision
        return bool(d and d.auto_unlock_active)


class BatteryCriticalBinarySensor(DoorPolicyEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_BATTERY_CRITICAL)
        self._attr_name = NAME_BATTERY_CRITICAL

    @property
    def is_on(self) -> bool:
        d = self.coord.last_decision
        return bool(d and d.battery_critical)


class ApplyBlockedBinarySensor(DoorPolicyEntity, BinarySensorEntity):
    """on = Decision darf gerade NICHT angewendet werden (Gating aktiv)."""

    _attr_icon = "mdi:lock-alert"

    def __init__(self, coord, entry):
        super().__init__(coord, entry)
        self._attr_unique_id = unique_id(entry.entry_id, UID_APPLY_BLOCKED)
        self._attr_name = NAME_APPLY_BLOCKED

    @property
    def is_on(self) -> bool:
        d = self.coord.last_decision
        return bool(d and not d.apply_allowed)

    @property
    def extra_state_attributes(self):
        d = self.coord.last_decision
        return {"blockers": list(d.blockers) if d else []}
