"""Panneau latéral « Courbe de chauffe » et son API websocket."""

from __future__ import annotations

import json
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

PANEL_URL_PATH = "courbe-de-chauffe"
PANEL_COMPONENT = "heating-curve-panel"
STATIC_URL = f"/{DOMAIN}_static"
_REGISTERED = f"{DOMAIN}_panel_registered"
_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True
    root = Path(__file__).parent
    manifest = await hass.async_add_executor_job((root / "manifest.json").read_text, "utf-8")
    version = json.loads(manifest)["version"]
    if not hass.data.get(_STATIC_REGISTERED):
        # Chemin statique et commandes websocket : une seule fois par démarrage de HA.
        hass.data[_STATIC_REGISTERED] = True
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(root / "frontend"), cache_headers=False)]
        )
        websocket_api.async_register_command(hass, ws_get)
        websocket_api.async_register_command(hass, ws_set_curve)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{STATIC_URL}/{PANEL_COMPONENT}.js?v={version}",
        sidebar_title="Courbe de chauffe",
        sidebar_icon="mdi:chart-bell-curve-cumulative",
        require_admin=True,
    )


@callback
def async_unregister_panel(hass: HomeAssistant) -> None:
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    hass.data[_REGISTERED] = False


def _optimizer(hass: HomeAssistant, entry_id: str | None):
    entries = [
        e for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if entry_id in (None, e.entry_id)
    ]
    return entries[0].runtime_data if entries else None


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/get", vol.Optional("entry_id"): str}
)
@websocket_api.require_admin
@callback
def ws_get(hass: HomeAssistant, connection, msg: dict) -> None:
    optimizer = _optimizer(hass, msg.get("entry_id"))
    if optimizer is None:
        connection.send_error(msg["id"], "not_found", "Optimiseur non configuré")
        return
    connection.send_result(msg["id"], optimizer.snapshot())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/set_curve",
        vol.Optional("entry_id"): str,
        vol.Required("slope"): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=3.5)),
        vol.Required("shift"): vol.All(vol.Coerce(float), vol.Range(min=-13, max=40)),
        vol.Optional("reason", default="réglage manuel"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_curve(hass: HomeAssistant, connection, msg: dict) -> None:
    optimizer = _optimizer(hass, msg.get("entry_id"))
    if optimizer is None:
        connection.send_error(msg["id"], "not_found", "Optimiseur non configuré")
        return
    try:
        await optimizer.async_set_curve(
            round(msg["slope"], 1), round(msg["shift"]), msg["reason"]
        )
    except ValueError as err:
        connection.send_error(msg["id"], "unavailable", str(err))
        return
    connection.send_result(msg["id"], optimizer.snapshot())
