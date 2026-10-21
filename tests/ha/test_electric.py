"""Chauffage électrique d'appoint (Versatile Thermostat ou module fil pilote) : compteur d'énergie et humidité."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .test_integration import _pilot_entry


async def test_electric_heater_discovery(hass: HomeAssistant, vicare):
    vt = MockConfigEntry(domain="versatile_thermostat")
    vt.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Salle de bains")
    device = dr.async_get(hass).async_get_or_create(config_entry_id=vt.entry_id, identifiers={("vt", "sdb")})
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    ents = er.async_get(hass)
    ents.async_get_or_create("climate", "versatile_thermostat", "sdb", suggested_object_id="radiateur_sdb", device_id=device.id)
    ents.async_get_or_create("sensor", "versatile_thermostat", "sdb_energy", suggested_object_id="radiateur_sdb_energy",
                             device_id=device.id, original_device_class="energy")
    other = dr.async_get(hass).async_get_or_create(config_entry_id=vt.entry_id, identifiers={("mqtt", "capteur")})
    dr.async_get(hass).async_update_device(other.id, area_id=area.id)
    ents.async_get_or_create("sensor", "mqtt", "hum", suggested_object_id="capteur_sdb_humidity",
                             device_id=other.id, original_device_class="humidity")
    entry = await _pilot_entry(hass, rooms_demand=True)
    snap = entry.runtime_data.snapshot()
    assert snap["electric"] == [{"entity": "climate.radiateur_sdb", "name": device.name or "climate.radiateur_sdb",
                                 "energy": "sensor.radiateur_sdb_energy",
                                 "measured": False, "humidity": "sensor.capteur_sdb_humidity"}]
    assert snap["costs"]["elec_price"] == 0.25
    # un compteur mesuré dans la même pièce (intégrale de la puissance de la prise) est préféré
    meter = ents.async_get_or_create("sensor", "integration", "sdb_kwh", suggested_object_id="energie_sdb_mesuree",
                                     original_device_class="energy")
    ents.async_update_entity(meter.entity_id, area_id=area.id)
    heater = entry.runtime_data.snapshot()["electric"][0]
    assert heater["energy"] == "sensor.energie_sdb_mesuree" and heater["measured"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_pilot_wire_heater_discovery(hass: HomeAssistant, vicare):
    """Sans thermostat : le module fil pilote est le radiateur, son compteur est une mesure."""
    z2m = MockConfigEntry(domain="mqtt")
    z2m.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Salle de bains")
    devs, ents = dr.async_get(hass), er.async_get(hass)
    module = devs.async_get_or_create(config_entry_id=z2m.entry_id, identifiers={("mqtt", "legrand")},
                                      name="Radiateur salle de bains")
    devs.async_update_device(module.id, area_id=area.id)
    select = ents.async_get_or_create("select", "mqtt", "pilot", suggested_object_id="radiateur_sdb_pilot_wire_mode",
                                      device_id=module.id)
    ents.async_get_or_create("select", "mqtt", "behavior", suggested_object_id="radiateur_sdb_power_on_behavior",
                             device_id=module.id)
    hass.states.async_set(select.entity_id, "off",
                          {"options": ["comfort", "eco", "frost_protection", "off", "comfort_-1", "comfort_-2"]})
    hass.states.async_set("select.radiateur_sdb_power_on_behavior", "off", {"options": ["off", "on", "previous"]})
    ents.async_get_or_create("sensor", "mqtt", "kwh", suggested_object_id="radiateur_sdb_energy",
                             device_id=module.id, original_device_class="energy")
    entry = await _pilot_entry(hass, rooms_demand=True)
    heater, = entry.runtime_data.snapshot()["electric"]
    assert heater["entity"] == "select.radiateur_sdb_pilot_wire_mode"
    assert heater["name"] == "Radiateur salle de bains"
    assert heater["energy"] == "sensor.radiateur_sdb_energy" and heater["measured"]
    assert "comfort" in heater["pilot_modes"]
    await hass.config_entries.async_unload(entry.entry_id)
