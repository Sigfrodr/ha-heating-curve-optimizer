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
CARD_COMPONENT = "heating-curve-card"
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
        websocket_api.async_register_command(hass, ws_recoveries)
        websocket_api.async_register_command(hass, ws_set_control_mode)
        websocket_api.async_register_command(hass, ws_set_schedule)
        websocket_api.async_register_command(hass, ws_diagnostics)
        websocket_api.async_register_command(hass, ws_weekly_report)
        websocket_api.async_register_command(hass, ws_set_room_targets)
        websocket_api.async_register_command(hass, ws_set_maintenance)
        websocket_api.async_register_command(hass, ws_set_internal_gains)
        websocket_api.async_register_command(hass, ws_vicare_schedule)
        websocket_api.async_register_command(hass, ws_push_vicare_schedule)
        websocket_api.async_register_command(hass, ws_dhw_schedule)
        websocket_api.async_register_command(hass, ws_set_dhw_schedule)
        websocket_api.async_register_command(hass, ws_set_heating_limit)
        websocket_api.async_register_command(hass, ws_get_settings)
        websocket_api.async_register_command(hass, ws_set_settings)
        websocket_api.async_register_command(hass, ws_bill_forecast)
        # Carte de tableau de bord, chargée sur toutes les pages
        frontend.add_extra_js_url(hass, f"{STATIC_URL}/{CARD_COMPONENT}.js?v={version}")
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recoveries",
        vol.Optional("entry_id"): str,
        vol.Optional("days", default=7): vol.All(int, vol.Range(min=1, max=30)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_recoveries(hass: HomeAssistant, connection, msg: dict) -> None:
    optimizer = _optimizer(hass, msg.get("entry_id"))
    if optimizer is None:
        connection.send_error(msg["id"], "not_found", "Optimiseur non configuré")
        return
    try:
        result = await optimizer.async_recoveries(msg["days"])
    except (KeyError, RuntimeError) as err:  # recorder absent ou indisponible
        connection.send_error(msg["id"], "unavailable", f"Historique indisponible : {err}")
        return
    connection.send_result(msg["id"], result)


def _command(name: str, extra: dict | None = None):
    return websocket_api.websocket_command(
        {vol.Required("type"): f"{DOMAIN}/{name}", vol.Optional("entry_id"): str, **(extra or {})}
    )


async def _run(hass, connection, msg, func) -> None:
    optimizer = _optimizer(hass, msg.get("entry_id"))
    if optimizer is None:
        connection.send_error(msg["id"], "not_found", "Optimiseur non configuré")
        return
    try:
        result = await func(optimizer)
    except (ValueError, KeyError, RuntimeError) as err:
        connection.send_error(msg["id"], "failed", str(err))
        return
    connection.send_result(msg["id"], result)


@_command("set_control_mode", {vol.Required("mode"): vol.In(["off", "simulation", "active"])})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_control_mode(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        await o.pilot.async_set_mode(msg["mode"])
        return o.snapshot()

    await _run(hass, connection, msg, run)


PERIOD = vol.All([vol.Match(r"^([01]\d|2[0-4]):[0-5]\d$")], vol.Length(min=2, max=2))


@_command(
    "set_schedule",
    {
        vol.Required("schedule"): {vol.Coerce(str): [PERIOD]},
        vol.Required("comfort"): vol.All(vol.Coerce(float), vol.Range(min=10, max=26)),
        vol.Required("reduced"): vol.All(vol.Coerce(float), vol.Range(min=5, max=24)),
    },
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_schedule(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        await o.pilot.async_set_schedule(msg["schedule"], msg["comfort"], msg["reduced"])
        return o.snapshot()

    await _run(hass, connection, msg, run)


@_command("diagnostics")
@websocket_api.require_admin
@websocket_api.async_response
async def ws_diagnostics(hass: HomeAssistant, connection, msg: dict) -> None:
    await _run(hass, connection, msg, lambda o: o.async_diagnostics())


@_command("weekly_report", {vol.Optional("send", default=False): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_weekly_report(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        text = await (o.async_send_weekly_report() if msg["send"] else o.async_weekly_report_text())
        return {"text": text}

    await _run(hass, connection, msg, run)


ROOM_TARGET = vol.Schema({
    vol.Required("enabled"): bool,
    vol.Required("comfort"): vol.All(vol.Coerce(float), vol.Range(min=5, max=28)),
    vol.Required("reduced"): vol.All(vol.Coerce(float), vol.Range(min=5, max=28)),
})


@_command("set_room_targets", {vol.Required("targets"): {str: ROOM_TARGET}})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_room_targets(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        await o.pilot.async_set_room_targets(msg["targets"])
        return o.snapshot()

    await _run(hass, connection, msg, run)


@_command("set_maintenance", {vol.Optional("date"): vol.Match(r"^\d{4}-\d{2}-\d{2}$")})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_maintenance(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        await o.async_set_maintenance(msg.get("date"))
        return o.snapshot()

    await _run(hass, connection, msg, run)


@_command("set_internal_gains", {vol.Required("entity_id"): str, vol.Required("enabled"): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_internal_gains(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        o.set_internal_gains(msg["entity_id"], msg["enabled"])
        return await o.async_diagnostics()

    await _run(hass, connection, msg, run)


@_command("vicare_schedule")
@websocket_api.require_admin
@websocket_api.async_response
async def ws_vicare_schedule(hass: HomeAssistant, connection, msg: dict) -> None:
    await _run(hass, connection, msg, lambda o: o.async_vicare_schedule())


@_command("push_vicare_schedule", {vol.Required("preheat_minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=180))})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_push_vicare_schedule(hass: HomeAssistant, connection, msg: dict) -> None:
    await _run(hass, connection, msg, lambda o: o.async_push_vicare_schedule(msg["preheat_minutes"]))


@_command("dhw_schedule")
@websocket_api.require_admin
@websocket_api.async_response
async def ws_dhw_schedule(hass: HomeAssistant, connection, msg: dict) -> None:
    await _run(hass, connection, msg, lambda o: o.async_dhw_schedule())


@_command("set_dhw_schedule", {vol.Required("schedule"): {vol.In(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]): [PERIOD]}})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_dhw_schedule(hass: HomeAssistant, connection, msg: dict) -> None:
    await _run(hass, connection, msg, lambda o: o.async_set_dhw_schedule(msg["schedule"]))


@_command("set_heating_limit", {vol.Required("value"): vol.All(vol.Coerce(float), vol.Range(min=8, max=22))})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_heating_limit(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        await o.async_set_heating_limit(msg["value"])
        return {"heating_limit": msg["value"]}

    await _run(hass, connection, msg, run)


@_command("get_settings")
@websocket_api.require_admin
@websocket_api.async_response
async def ws_get_settings(hass: HomeAssistant, connection, msg: dict) -> None:
    await _run(hass, connection, msg, lambda o: o.async_settings())


@_command("set_settings", {vol.Required("values"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_set_settings(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        await o.async_save_settings(msg["values"])
        return {"saved": True}

    await _run(hass, connection, msg, run)


@_command("bill_forecast")
@websocket_api.require_admin
@websocket_api.async_response
async def ws_bill_forecast(hass: HomeAssistant, connection, msg: dict) -> None:
    async def run(o):
        return {"forecast": await o.async_bill_forecast()}

    await _run(hass, connection, msg, run)
