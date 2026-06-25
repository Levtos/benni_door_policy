"""WebSocket-API für das Door-Policy-Panel.

Konsolidierter Status-Snapshot (Combined-State + Szenarien + Inputs + Gating +
Pending) plus Mutations-Commands (Apply now, Resync, Shadow/Live umschalten).
Read-Command ohne Admin; Schreib-Commands nur Admin.
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    WS_APPLY_NOW,
    WS_GET_STATUS,
    WS_RESYNC,
    WS_SET_APPLY_ENABLED,
)


def _coordinator(hass: HomeAssistant):
    for bucket in (hass.data.get(DOMAIN) or {}).values():
        if isinstance(bucket, dict) and DATA_COORDINATOR in bucket:
            return bucket[DATA_COORDINATOR]
    return None


def async_setup_websocket_api(hass: HomeAssistant) -> None:
    @websocket_api.websocket_command({vol.Required("type"): WS_GET_STATUS})
    @websocket_api.async_response
    async def ws_get_status(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Door Policy not loaded")
            return
        connection.send_result(msg["id"], coord.status_snapshot())

    @websocket_api.websocket_command({vol.Required("type"): WS_APPLY_NOW})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_apply_now(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Door Policy not loaded")
            return
        await coord.async_apply_now()
        connection.send_result(msg["id"], coord.status_snapshot())

    @websocket_api.websocket_command({vol.Required("type"): WS_RESYNC})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_resync(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Door Policy not loaded")
            return
        await coord.async_resync()
        connection.send_result(msg["id"], coord.status_snapshot())

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SET_APPLY_ENABLED,
        vol.Required("enabled"): bool,
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def ws_set_apply_enabled(hass, connection, msg) -> None:
        coord = _coordinator(hass)
        if coord is None:
            connection.send_error(msg["id"], "not_ready", "Door Policy not loaded")
            return
        await coord.async_set_apply_enabled(msg["enabled"])
        connection.send_result(msg["id"], coord.status_snapshot())

    for cmd in (ws_get_status, ws_apply_now, ws_resync, ws_set_apply_enabled):
        websocket_api.async_register_command(hass, cmd)
