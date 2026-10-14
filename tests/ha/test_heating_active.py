"""Une mesure ne compte que si le chauffage a réellement fonctionné (pompe du circuit)."""

import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_integration import _pilot_entry

PUMP = "binary_sensor.vicare_circulation_pump_active"


def _register_pump(hass: HomeAssistant, state: str) -> None:
    registry = er.async_get(hass)
    device_id = registry.async_get("climate.vicare_heating").device_id
    registry.async_get_or_create(
        "binary_sensor", "vicare", "circulation_pump", suggested_object_id="vicare_circulation_pump_active",
        device_id=device_id, translation_key="circulation_pump",
    )
    hass.states.async_set(PUMP, state)


async def test_samples_only_while_heating(hass: HomeAssistant, vicare):
    _register_pump(hass, "off")
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    optimizer.data["samples"] = []

    # temps doux, chaudière à l'arrêt depuis longtemps : pas de mesure
    optimizer.data["heating_active_at"] = time.time() - 4 * 3600
    await optimizer._async_sample()
    assert optimizer.status == "chauffage inactif (mesure ignorée)"
    assert optimizer.data["samples"] == []

    # la pompe du circuit démarre : la mesure compte
    hass.states.async_set(PUMP, "on")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert optimizer.status == "collecte" and len(optimizer.data["samples"]) == 1

    # arrêt de la pompe depuis moins d'une heure (cycle normal) : la mesure compte encore
    hass.states.async_set(PUMP, "off")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert len(optimizer.data["samples"]) == 2
    await hass.config_entries.async_unload(entry.entry_id)


async def test_old_samples_purged_once_on_upgrade(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    assert optimizer.data["heating_filter"] is True
    await hass.config_entries.async_unload(entry.entry_id)
