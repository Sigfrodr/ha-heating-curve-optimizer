"""Chauffage électrique d'appoint (Versatile Thermostat) : compteur d'énergie et humidité de la pièce."""

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
    assert snap["electric"] == [{"climate": "climate.radiateur_sdb", "energy": "sensor.radiateur_sdb_energy",
                                 "humidity": "sensor.capteur_sdb_humidity"}]
    assert snap["costs"]["elec_price"] == 0.25
    await hass.config_entries.async_unload(entry.entry_id)
