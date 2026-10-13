"""Budget d'écritures ViCare, compteur de gaz, onglet Réglages (websocket)."""

import time

import pytest
from homeassistant.core import HomeAssistant

from .test_integration import _pilot_entry


@pytest.fixture(autouse=True)
def fake_frontend(hass):
    """Comme dans le conftest, mais avec le vrai module websocket (test de l'API du panneau)."""
    hass.config.components.update({"frontend", "panel_custom"})
    hass.config.language = "fr"
    from unittest.mock import patch

    with patch("custom_components.heating_curve_optimizer.async_register_panel"):
        yield


async def test_write_budget_blocks_lowering_but_not_returning(hass: HomeAssistant, vicare, freezer):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to("2026-10-12 10:00:00+02:00")
    writes = []

    async def set_temp(call):
        writes.append(call.data["temperature"])

    hass.services.async_register("climate", "set_temperature", set_temp)
    entry = await _pilot_entry(hass, rooms_demand=False)
    optimizer = entry.runtime_data
    pilot = optimizer.pilot
    await pilot.async_set_mode("active")
    budget = optimizer.write_budget
    optimizer.data["writes"] = [time.time()] * (budget - 1)  # une seule écriture restante
    pilot._no_demand_since = time.time() - 3600
    pilot._last_write = 0
    await pilot.async_tick()
    assert writes == []  # passer en veille laisserait sans moyen de revenir au confort
    assert "write_budget" not in optimizer.data["alerts"]
    # la remontée au confort reste possible avec la dernière écriture
    hass.states.async_set("climate.vicare_heating", "auto", {
        "active_vicare_program": "comfortEnergySaving", "room_temperature": 18.0, "temperature": 15})
    hass.states.async_set("climate.chambre", "heat", {"current_temperature": 18, "temperature": 19, "hvac_action": "heating"})
    await pilot.async_tick()
    assert writes == [19.0]
    assert optimizer.writes_24h == budget
    await optimizer._async_monitor(hass.states.get("climate.vicare_heating"))
    assert "write_budget" in optimizer.data["alerts"]
    await pilot.async_set_mode("off")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_gas_meter_in_kwh_is_converted(hass: HomeAssistant, vicare):
    hass.states.async_set("sensor.gazpar", "1234", {"unit_of_measurement": "kWh", "device_class": "energy",
                                                    "state_class": "total_increasing"})
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    assert optimizer.gas_source[1] == 1.0  # pas de compteur : relevés ViCare en m³
    hass.config_entries.async_update_entry(entry, options={**entry.options, "gas_meter": "sensor.gazpar"})
    await hass.async_block_till_done()
    optimizer = entry.runtime_data
    entity, factor = optimizer.gas_source
    assert entity == "sensor.gazpar" and abs(factor - 1 / 11.0) < 1e-9
    await hass.config_entries.async_unload(entry.entry_id)


async def test_settings_websocket_roundtrip(hass: HomeAssistant, vicare, hass_ws_client):
    hass.states.async_set("weather.maison", "cloudy", {"friendly_name": "Maison"})
    from homeassistant.components import websocket_api

    from custom_components.heating_curve_optimizer import panel

    entry = await _pilot_entry(hass, rooms_demand=True)
    for command in (panel.ws_get_settings, panel.ws_set_settings):
        websocket_api.async_register_command(hass, command)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "heating_curve_optimizer/get_settings"})
    res = await client.receive_json()
    assert res["success"], res
    data = res["result"]
    keys = {f["key"] for f in data["fields"]}
    assert {"gas_price", "write_budget", "billing_start", "rooms", "notify"} <= keys
    labels = {f["key"]: f["label"] for f in data["fields"]}
    assert labels["gas_price"] == "Prix du gaz"  # libellé traduit, pas la clé
    assert {"value": "weather.maison", "label": "Maison"} in data["choices"]["weather"]
    assert data["values"]["gas_price"] == 0.11
    await client.send_json_auto_id({"type": "heating_curve_optimizer/set_settings",
                                    "values": {"gas_price": 0.098, "billing_start": "2026-04-11", "write_budget": 6}})
    res = await client.receive_json()
    assert res["success"], res
    await hass.async_block_till_done()
    assert entry.options["gas_price"] == 0.098 and entry.options["write_budget"] == 6.0
    assert entry.options["billing_start"] == "2026-04-11"
    # valeur hors limites refusée
    await client.send_json_auto_id({"type": "heating_curve_optimizer/set_settings", "values": {"gas_price": 5}})
    res = await client.receive_json()
    assert not res["success"] and "hors limites" in res["error"]["message"]
    await hass.config_entries.async_unload(entry.entry_id)
