"""Notifications actionnables, consignes par pièce, tableau Énergie, entretien, fuite lente."""

import time

from homeassistant.core import HomeAssistant

from .conftest import SLOPE
from .test_integration import _pilot_entry


async def test_room_targets_follow_planning_and_restore(hass: HomeAssistant, vicare, freezer):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to("2026-10-12 23:30:00+02:00")  # période réduite
    calls = []

    async def set_temp(call):
        calls.append((call.data["entity_id"], call.data["temperature"]))

    hass.services.async_register("climate", "set_temperature", set_temp)
    entry = await _pilot_entry(hass, rooms_demand=False)
    pilot = entry.runtime_data.pilot
    await pilot.async_set_room_targets({"climate.chambre": {"enabled": True, "comfort": 20, "reduced": 16.5}})
    await pilot.async_set_mode("active")
    pilot._room_writes.clear()
    await pilot.async_tick()
    assert ("climate.chambre", 16.5) in calls
    assert entry.runtime_data.data["room_originals"]["climate.chambre"] == 19.0
    await pilot.async_set_mode("simulation")
    assert ("climate.chambre", 19.0) in calls  # consigne d'origine remise
    assert entry.runtime_data.data["room_originals"] == {}
    await hass.config_entries.async_unload(entry.entry_id)


async def test_notification_action_applies_proposal(hass: HomeAssistant, vicare):
    calls = []

    async def set_number(call):
        calls.append((call.data["entity_id"], call.data["value"]))

    hass.services.async_register("number", "set_value", set_number)
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    optimizer.data["last_proposal"] = {"t": time.time(), "slope": 0.2, "shift": 25,
                                       "new_slope": 0.3, "new_shift": 23}
    hass.bus.async_fire("mobile_app_notification_action", {"action": "HCO_APPLY"})
    await hass.async_block_till_done()
    assert calls[0] == (SLOPE, 0.3)
    assert optimizer.data["history"][-1]["reason"] == "proposition validée depuis le téléphone"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_energy_sensors(hass: HomeAssistant, vicare):
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    device_id = registry.async_get("climate.vicare_heating").device_id
    registry.async_get_or_create(
        "sensor", "vicare", "gas_day", suggested_object_id="vicare_gas_day", device_id=device_id,
        translation_key="gas_summary_consumption_heating_currentday",
    )
    hass.states.async_set("sensor.vicare_gas_day", "2.0")
    entry = await _pilot_entry(hass, rooms_demand=True)
    price = hass.states.get("sensor.optimiseur_courbe_de_chauffe_prix_du_gaz")
    assert price.state == "1.21" and price.attributes["unit_of_measurement"] == "EUR/m³"
    cost = hass.states.get("sensor.optimiseur_courbe_de_chauffe_cout_du_gaz_chauffage_aujourd_hui")
    assert cost.state == "2.42"  # 2 m³ × 11 kWh × 0,11 €
    hass.states.async_set("sensor.vicare_gas_day", "3.0")
    await hass.async_block_till_done()
    assert hass.states.get(cost.entity_id).state == "3.63"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_maintenance_button_and_due_alert(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    await optimizer.async_set_maintenance("2025-10-30")
    assert optimizer.data["maintenance"]["hours"] == 9358.0
    await optimizer._async_daily_checks()
    assert "maintenance" in optimizer.data["daily_alerts"]
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.optimiseur_courbe_de_chauffe_entretien_effectue"}, blocking=True
    )
    assert "maintenance" not in optimizer.data["daily_alerts"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_slow_pressure_leak_alert(hass: HomeAssistant, vicare):
    from datetime import date, timedelta

    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    start = date(2026, 9, 1)
    optimizer.data["pressure_days"] = {
        (start + timedelta(days=i)).isoformat(): 1.6 - 0.012 * i for i in range(28)
    }
    await optimizer._async_daily_checks()
    assert "slow_leak" in optimizer.data["daily_alerts"]
    await optimizer._async_sample()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.optimiseur_courbe_de_chauffe_alerte_chaudiere").state == "on"
    await hass.config_entries.async_unload(entry.entry_id)
