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


async def test_energy_saving_variant_keeps_regime(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    await optimizer._async_sample()
    since = optimizer.data["regime_since"]
    attrs = dict(hass.states.get("climate.vicare_heating").attributes)
    # la chaudière chauffe : « comfortEnergySaving » devient « comfort », même consigne
    hass.states.async_set("climate.vicare_heating", "auto", {**attrs, "active_vicare_program": "comfort"})
    await optimizer._async_sample()
    # rechargement de ViCare : programme momentanément absent
    hass.states.async_set("climate.vicare_heating", "auto", {**attrs, "active_vicare_program": None})
    await optimizer._async_sample()
    assert optimizer.data["regime_since"] == since
    # vrai changement : passage en réduit
    hass.states.async_set("climate.vicare_heating", "auto", {**attrs, "active_vicare_program": "reduced", "temperature": 17})
    await optimizer._async_sample()
    assert optimizer.data["regime_since"] > since
    await hass.config_entries.async_unload(entry.entry_id)


async def test_electric_held_while_gas_heats(hass: HomeAssistant, vicare):
    """Fil pilote en confort : arrêté pendant que le chauffage gaz tourne, rétabli ensuite, sauf séchage."""
    from homeassistant.helpers import area_registry as ar, device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _register(hass, PUMP, "circulation_pump", "off")
    _register(hass, TANK, "dhw_storage_temperature", "45")
    z2m = MockConfigEntry(domain="mqtt")
    z2m.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Salle de bains")
    module = dr.async_get(hass).async_get_or_create(config_entry_id=z2m.entry_id, identifiers={("mqtt", "legrand")})
    dr.async_get(hass).async_update_device(module.id, area_id=area.id)
    ents = er.async_get(hass)
    select = ents.async_get_or_create("select", "mqtt", "pilot", suggested_object_id="sdb_pilot_wire_mode",
                                      device_id=module.id).entity_id
    hum = ents.async_get_or_create("sensor", "mqtt", "hum", suggested_object_id="sdb_humidity",
                                   device_id=module.id, original_device_class="humidity").entity_id
    modes = ["comfort", "eco", "frost_protection", "off", "comfort_-1", "comfort_-2"]
    hass.states.async_set(select, "off", {"options": modes})
    hass.states.async_set(hum, "60")

    async def select_option(call):
        hass.states.async_set(call.data["entity_id"][0] if isinstance(call.data["entity_id"], list)
                              else call.data["entity_id"], call.data["option"], {"options": modes})

    entry = await _pilot_entry(hass, rooms_demand=True)
    hass.services.async_register("select", "select_option", select_option)  # après le composant select de HA
    optimizer = entry.runtime_data
    optimizer.cfg["electric_gas_priority"] = True

    # le planning demande le confort, la chaudière est à l'arrêt : confort
    await hass.services.async_call("select", "select_option", {"entity_id": select, "option": "comfort"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(select).state == "comfort"

    # le chauffage gaz tourne (pompe en marche, ballon stable) : arrêt, la demande reste le confort
    hass.states.async_set(PUMP, "on")
    await hass.async_block_till_done()
    optimizer.data["pump_on_at"] = time.time() - 700
    await optimizer._async_electric_priority()
    assert hass.states.get(select).state == "off"
    heater, = optimizer.snapshot()["electric"]
    assert heater["demand"] == "comfort" and heater["held"]

    # douche : l'humidité dépasse 80 %, le séchage électrique reprend malgré le gaz
    hass.states.async_set(hum, "90")
    await optimizer._async_electric_priority()
    assert hass.states.get(select).state == "comfort"
    hass.states.async_set(hum, "70")
    await optimizer._async_electric_priority()
    assert hass.states.get(select).state == "off"

    # un arrêt demandé pendant la retenue est mémorisé, même sans changement d'état
    await hass.services.async_call("select", "select_option", {"entity_id": select, "option": "off"}, blocking=True)
    await hass.async_block_till_done()
    hass.states.async_set(PUMP, "off")
    await hass.async_block_till_done()
    await optimizer._async_electric_priority()
    assert hass.states.get(select).state == "off"

    # nouvelle demande de confort, gaz arrêté : confort
    await hass.services.async_call("select", "select_option", {"entity_id": select, "option": "comfort"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(select).state == "comfort"
    await hass.config_entries.async_unload(entry.entry_id)
