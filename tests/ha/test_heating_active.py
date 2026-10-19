"""Une mesure ne compte que si le chauffage a réellement fonctionné (pas l'eau chaude seule)."""

import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_integration import _pilot_entry

PUMP = "binary_sensor.vicare_circulation_pump_active"
TANK = "sensor.vicare_dhw_storage_temperature"
GAS = "sensor.vicare_heating_gas_consumption_current_day"


def _register(hass: HomeAssistant, entity_id: str, key: str, state: str) -> None:
    registry = er.async_get(hass)
    device_id = registry.async_get("climate.vicare_heating").device_id
    domain, object_id = entity_id.split(".")
    registry.async_get_or_create(
        domain, "vicare", key, suggested_object_id=object_id, device_id=device_id, translation_key=key,
    )
    hass.states.async_set(entity_id, state)


async def test_pump_without_gas_counter(hass: HomeAssistant, vicare):
    _register(hass, PUMP, "circulation_pump", "off")
    _register(hass, TANK, "dhw_storage_temperature", "45")
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    optimizer.data["samples"] = []

    # temps doux, chaudière à l'arrêt depuis longtemps : pas de mesure
    optimizer.data["heating_active_at"] = time.time() - 4 * 3600
    await optimizer._async_sample()
    assert optimizer.status == "chauffage inactif (mesure ignorée)"

    # la pompe démarre pour le ballon : il monte, ce n'est pas le chauffage
    hass.states.async_set(PUMP, "on")
    await hass.async_block_till_done()
    optimizer.data["pump_on_at"] = time.time() - 700
    hass.states.async_set(TANK, "52")
    await optimizer._async_sample()
    assert optimizer.data["samples"] == []
    hass.states.async_set(PUMP, "off")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert optimizer.data["samples"] == []

    # la pompe tourne 10 min sans que le ballon monte : chauffage
    hass.states.async_set(PUMP, "on")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert optimizer.data["samples"] == []  # trop tôt pour trancher
    optimizer.data["pump_on_at"] = time.time() - 700
    await optimizer._async_sample()
    assert optimizer.status == "collecte" and len(optimizer.data["samples"]) == 1

    # arrêt de la pompe depuis moins d'une heure (cycle normal) : la mesure compte encore
    hass.states.async_set(PUMP, "off")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert len(optimizer.data["samples"]) == 2
    await hass.config_entries.async_unload(entry.entry_id)


async def test_heating_gas_counter_confirms_pump_runs(hass: HomeAssistant, vicare):
    _register(hass, PUMP, "circulation_pump", "off")
    _register(hass, TANK, "dhw_storage_temperature", "45")
    _register(hass, GAS, "gas_summary_consumption_heating_currentday", "0.3")
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    optimizer.data["samples"] = []
    optimizer.data["heating_active_at"] = 0

    # pompe allumée, ballon qui monte, gaz chauffage immobile : eau chaude seule
    hass.states.async_set(PUMP, "on")
    await hass.async_block_till_done()
    optimizer.data["pump_on_at"] -= 700
    hass.states.async_set(TANK, "52")
    await optimizer._async_sample()
    assert optimizer.data["samples"] == []

    # remise à zéro de minuit du compteur : pas une activité
    hass.states.async_set(GAS, "0")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert optimizer.data["samples"] == []

    # le compteur de gaz chauffage avance (mis à jour toutes les ~2 h) : la marche était du chauffage
    hass.states.async_set(GAS, "0.1")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert optimizer.status == "collecte" and len(optimizer.data["samples"]) == 1

    # pompe arrêtée depuis moins d'une heure, gaz confirmé : la mesure compte encore
    hass.states.async_set(PUMP, "off")
    await hass.async_block_till_done()
    await optimizer._async_sample()
    assert len(optimizer.data["samples"]) == 2
    await hass.config_entries.async_unload(entry.entry_id)


async def test_settle_survives_reload(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    await entry.runtime_data._async_sample()
    since = entry.runtime_data.data["regime_since"]
    from unittest.mock import patch

    with patch("custom_components.heating_curve_optimizer.async_register_panel"):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    await entry.runtime_data._async_sample()
    assert entry.runtime_data.data["regime_since"] == since  # pas de nouvelle stabilisation de 2 h
    await hass.config_entries.async_unload(entry.entry_id)


async def test_old_samples_purged_once_on_upgrade(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    assert optimizer.data["heating_filter"] == 2
    await hass.config_entries.async_unload(entry.entry_id)
