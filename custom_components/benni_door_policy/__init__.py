"""Benni Door Policy — Türschloss U200 (L2-Policy, eigene HACS-Integration).

Decision/Apply-Pattern wie blind_policy/light_policy: der Coordinator hört auf die
Quell-Entities, rechnet ``policy.decide`` und schaltet das Schloss — gated an
``apply_enabled`` (Default False = Shadow-safe). R-06: niemals lock.open.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DATA_COORDINATOR,
    DATA_SKIP_RELOAD_COUNT,
    DATA_WS_REGISTERED,
    DOMAIN,
    SERVICE_APPLY_NOW,
    SERVICE_RESYNC,
    SERVICE_SET_APPLY_ENABLED,
)
from .coordinator import DoorPolicyCoordinator, all_coordinators
from .view import async_remove_view, async_setup_view
from .websocket_api import async_setup_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = DoorPolicyCoordinator(hass, entry)
    await coord.async_load()
    coord.async_start()
    await coord.async_evaluate()

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {DATA_COORDINATOR: coord}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)

    await async_setup_view(hass)
    if not data.get(DATA_WS_REGISTERED):
        async_setup_websocket_api(hass)
        data[DATA_WS_REGISTERED] = True

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    skip_count = int(data.get(DATA_SKIP_RELOAD_COUNT) or 0)
    if skip_count > 0:
        data[DATA_SKIP_RELOAD_COUNT] = skip_count - 1
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        bucket = hass.data[DOMAIN].pop(entry.entry_id, None)
        if bucket:
            bucket[DATA_COORDINATOR].async_stop()
        if not all_coordinators(hass):
            async_remove_view(hass)
            for svc in (SERVICE_APPLY_NOW, SERVICE_RESYNC, SERVICE_SET_APPLY_ENABLED):
                if hass.services.has_service(DOMAIN, svc):
                    hass.services.async_remove(DOMAIN, svc)
    return unloaded


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_NOW):
        return

    async def _apply_now(_call: ServiceCall) -> None:
        for coord in all_coordinators(hass):
            await coord.async_apply_now()

    async def _resync(_call: ServiceCall) -> None:
        for coord in all_coordinators(hass):
            await coord.async_resync()

    async def _set_apply_enabled(call: ServiceCall) -> None:
        value = bool(call.data.get("enabled", True))
        for coord in all_coordinators(hass):
            await coord.async_set_apply_enabled(value)

    hass.services.async_register(DOMAIN, SERVICE_APPLY_NOW, _apply_now)
    hass.services.async_register(DOMAIN, SERVICE_RESYNC, _resync)
    hass.services.async_register(DOMAIN, SERVICE_SET_APPLY_ENABLED, _set_apply_enabled)
