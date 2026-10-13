from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import CLIMATE, DOMAIN, ENTRY_DATA, OUTSIDE, SHIFT, SLOPE


async def test_config_flow_suggests_vicare_entities(hass: HomeAssistant, vicare):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    suggested = {
        str(k): k.description["suggested_value"]
        for k in result["data_schema"].schema
        if k.description and "suggested_value" in k.description
    }
    assert suggested == {"climate": CLIMATE, "outside_temperature": OUTSIDE, "slope": SLOPE, "shift": SHIFT}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["shift_max"] == 40.0


async def test_options_form_loads_over_http(hass: HomeAssistant, hass_client, vicare):
    """Le formulaire d'options doit se sérialiser (régression : erreur 400 en 0.3.0)."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    resp = await client.post(
        "/api/config/config_entries/options/flow", json={"handler": entry.entry_id}
    )
    assert resp.status == 200, await resp.text()
    body = await resp.json()
    names = [field["name"] for field in body["data_schema"]]
    assert {"programs", "rooms_weather", "alerts", "dhw", "algorithm"} <= set(names)


async def test_options_flow_flattens_sections(hass: HomeAssistant, vicare):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "programs": ["comfortEnergySaving"],
            "heating_limit": 16,
            "evaluate_at": "04:00:00",
            "rooms_weather": {"rooms": ["climate.cuisine"], "solar_filter": True,
                              "solar_cloud_max": 60, "solar_min_elevation": 10},
            "alerts": {"min_pressure": 1.0, "short_cycle_minutes": 10},
            "pilot": {"standby_temp": 15, "demand_delay_minutes": 20, "sun_anticipation": True},
            "costs_report": {"gas_price": 0.11, "kwh_per_m3": 11.0, "weekly_report": True,
                             "report_weekday": "0", "report_time": "08:00:00"},
            "dhw": {"legionella_weekday": "6", "legionella_time": "14:00:00",
                    "legionella_temp": 60, "legionella_minutes": 90},
            "algorithm": {"settle_minutes": 120, "sample_minutes": 10, "min_samples": 72,
                          "max_age_days": 10, "damping": 0.5, "max_shift_step": 3,
                          "max_slope_step": 0.1, "shift_min": -13, "shift_max": 40,
                          "slope_min": 0.2, "slope_max": 3.5, "deadband": 0.3,
                          "min_outside_spread": 5},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["rooms"] == ["climate.cuisine"]
    assert entry.options["min_pressure"] == 1.0
    assert entry.options["weather"] == ""
    assert entry.options["gas_price"] == 0.11


async def test_entities_created(hass: HomeAssistant, loaded_entry):
    ids = {s.entity_id for s in hass.states.async_all() if s.entity_id.startswith(
        ("sensor.optimiseur", "switch.optimiseur", "button.optimiseur", "binary_sensor.optimiseur",
         "select.optimiseur"))}
    assert len(ids) == 11
    assert hass.states.get("switch.optimiseur_courbe_de_chauffe_ajustement_automatique").state == "off"


async def test_sample_uses_program_target_fallback(hass: HomeAssistant, loaded_entry):
    optimizer = loaded_entry.runtime_data
    await optimizer._async_sample()
    assert optimizer.status == "collecte"
    sample = optimizer.data["samples"][-1]
    assert sample["target"] == 19.0  # consigne lue sur number.comfort_temperature
    assert sample["room"] == 20.4


async def test_multi_room_effective_error(hass: HomeAssistant, vicare):
    hass.config.components.update({"frontend", "http", "panel_custom", "websocket_api"})
    hass.states.async_set("climate.chambre", "heat", {
        "current_temperature": 18.2, "temperature": 19, "hvac_action": "heating"})
    hass.states.async_set("climate.cuisine", "heat", {
        "current_temperature": 21.0, "temperature": 19, "hvac_action": "idle"})
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={
        "settle_minutes": 0, "rooms": ["climate.chambre", "climate.cuisine"]})
    entry.add_to_hass(hass)
    from unittest.mock import patch
    with patch(f"custom_components.{DOMAIN}.async_register_panel"):
        assert await hass.config_entries.async_setup(entry.entry_id)
    optimizer = entry.runtime_data
    await optimizer._async_sample()
    sample = optimizer.data["samples"][-1]
    assert sample["lim"] == "climate.chambre"
    assert abs(sample["eff"] - (-0.8)) < 1e-6
    await hass.config_entries.async_unload(entry.entry_id)


async def test_low_pressure_raises_alert(hass: HomeAssistant, loaded_entry):
    hass.states.async_set("sensor.vicare_supply_pressure", "0.7")
    optimizer = loaded_entry.runtime_data
    await optimizer._async_sample()
    await hass.async_block_till_done()
    alert = hass.states.get("binary_sensor.optimiseur_courbe_de_chauffe_alerte_chaudiere")
    assert alert.state == "on"
    assert "Pression" in alert.attributes["alertes"][0]
    hass.states.async_set("sensor.vicare_supply_pressure", "1.3")
    await optimizer._async_sample()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.optimiseur_courbe_de_chauffe_alerte_chaudiere").state == "off"


async def test_set_curve_writes_slope_then_waits_for_shift(hass: HomeAssistant, loaded_entry):
    calls = []

    async def record(call):
        calls.append((call.data["entity_id"], call.data["value"]))

    hass.services.async_register("number", "set_value", record)
    optimizer = loaded_entry.runtime_data
    await optimizer.async_set_curve(0.3, 23, "test")
    # La pente part tout de suite ; le décalage attend que ViCare ait relu la pente.
    assert calls == [(SLOPE, 0.3)]
    assert optimizer.data["samples"] == []
    assert optimizer.data["history"][-1]["new_shift"] == 23


# ---------------------------------------------------------------- pilotage

async def _pilot_entry(hass, rooms_demand: bool):
    hass.states.async_set("number.vicare_reduced_temperature", "17")
    hass.states.async_set("climate.chambre", "heat", {
        "current_temperature": 19.5, "temperature": 19,
        "hvac_action": "heating" if rooms_demand else "idle"})
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={
        "settle_minutes": 0, "rooms": ["climate.chambre"], "demand_delay_minutes": 20})
    entry.add_to_hass(hass)
    from unittest.mock import patch
    with patch(f"custom_components.{DOMAIN}.async_register_panel"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_pilot_simulation_goes_standby_without_writing(hass: HomeAssistant, vicare, freezer):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to("2026-10-12 10:00:00+02:00")  # lundi, période confort du planning par défaut
    writes = []
    hass.services.async_register("climate", "set_temperature", lambda call: writes.append(call.data))
    entry = await _pilot_entry(hass, rooms_demand=False)
    pilot = entry.runtime_data.pilot
    await pilot.async_set_mode("simulation")
    pilot._no_demand_since = __import__("time").time() - 3600
    await pilot.async_tick()
    state = entry.runtime_data.data["control_state"]
    assert state["mode"] == "veille" and state["setpoint"] == 15.0
    assert writes == []
    assert hass.states.get("sensor.optimiseur_courbe_de_chauffe_consigne_pilotee").state == "15.0"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_pilot_active_writes_and_restores(hass: HomeAssistant, vicare, freezer):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to("2026-10-12 10:00:00+02:00")
    writes, numbers = [], []

    async def set_temp(call):
        writes.append(call.data["temperature"])

    async def set_number(call):
        numbers.append((call.data["entity_id"], call.data["value"]))

    hass.services.async_register("climate", "set_temperature", set_temp)
    hass.services.async_register("number", "set_value", set_number)
    entry = await _pilot_entry(hass, rooms_demand=False)
    pilot = entry.runtime_data.pilot
    await pilot.async_set_mode("active")
    assert entry.runtime_data.data["control_originals"]["number.vicare_comfort_temperature"] == 19.0
    pilot._no_demand_since = __import__("time").time() - 3600
    pilot._last_write = 0
    await pilot.async_tick()
    assert writes and writes[-1] == 15.0
    # la consigne du confort a été modifiée par la chaudière : le retour à « désactivé » la remet
    hass.states.async_set("number.vicare_comfort_temperature", "15")
    await pilot.async_set_mode("off")
    assert ("number.vicare_comfort_temperature", 19.0) in numbers
    assert entry.runtime_data.data["control_originals"] is None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_form_has_pilot_and_cost_sections(hass: HomeAssistant, hass_client, vicare):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    resp = await client.post("/api/config/config_entries/options/flow", json={"handler": entry.entry_id})
    assert resp.status == 200, await resp.text()
    names = [f["name"] for f in (await resp.json())["data_schema"]]
    assert {"pilot", "costs_report"} <= set(names)

