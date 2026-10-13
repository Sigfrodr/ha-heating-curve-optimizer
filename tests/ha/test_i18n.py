"""Installation en anglais : noms d'entités, états et messages traduits."""

from homeassistant.core import HomeAssistant

from .test_integration import _pilot_entry


async def test_english_install(hass: HomeAssistant, vicare):
    hass.config.language = "en"
    entry = await _pilot_entry(hass, rooms_demand=True)
    status = hass.states.get("sensor.heating_curve_optimizer_status")
    assert status is not None, sorted(s.entity_id for s in hass.states.async_all("sensor"))
    assert status.state == "starting"
    assert hass.states.get("select.heating_curve_optimizer_setpoint_pilot").state == "off"
    hass.states.async_set("sensor.vicare_supply_pressure", "0.7")
    await entry.runtime_data._async_sample()
    await hass.async_block_till_done()
    alert = hass.states.get("binary_sensor.heating_curve_optimizer_boiler_alert")
    assert alert.attributes["alertes"][0].startswith("Low water pressure: 0.7 bar")
    snap = entry.runtime_data.snapshot()
    assert snap["language"] == "en" and snap["status"] == "collecting"
    await hass.config_entries.async_unload(entry.entry_id)
