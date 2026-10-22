"""Sonde d'ambiance figée : mesures ignorées et retirées, alerte, retour à la normale."""

import time

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service

from .test_heating_active import _register
from .test_integration import _pilot_entry

CLIMATE = "climate.vicare_heating"
STARTS = "sensor.vicare_burner_starts"
REF = "sensor.detecteur_couloir_temperature"


def _room(hass: HomeAssistant, value: float) -> None:
    st = hass.states.get(CLIMATE)
    hass.states.async_set(CLIMATE, st.state, {**st.attributes, "room_temperature": value})


async def test_frozen_room_sensor(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    now = time.time()
    _room(hass, 20.8)
    await optimizer._async_sample()
    # même valeur depuis 4 h, 4 démarrages du brûleur : figée
    optimizer.data["room_watch"]["since"] = since = now - 4 * 3600
    optimizer.data["samples"] = [
        {"t": since - 600, "outside": 5, "room": 20.7, "target": 21},
        {"t": since + 600, "outside": 5, "room": 20.8, "target": 21},
    ]
    hass.states.async_set(STARTS, "15468")
    await optimizer._async_sample()
    assert optimizer.data["room_frozen"][0] == 20.8
    assert [s["room"] for s in optimizer.data["samples"]] == [20.7]
    assert optimizer.status == "sonde d'ambiance figée (mesure ignorée)"
    assert "room_frozen" in optimizer.data["alerts"]

    # la sonde repart (thermostat redémarré)
    _room(hass, 23.4)
    await optimizer._async_sample()
    assert not optimizer.data["room_frozen"]
    assert "room_frozen" not in optimizer.data["alerts"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reference_sensor_divergence_fallback_and_failsafe(hass: HomeAssistant, vicare):
    _register(hass, "number.vicare_normal_temperature", "normal_temperature", "20")
    _register(hass, "number.vicare_reduced_temperature", "reduced_temperature", "17")
    hass.states.async_set("number.vicare_comfort_temperature", "21")
    calls = async_mock_service(hass, "number", "set_value")
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    optimizer.cfg.update({"room_reference": REF, "room_reference_offset": 0.1})
    optimizer.data["heating_active_at"] = time.time()
    st = hass.states.get(CLIMATE)
    hass.states.async_set(CLIMATE, st.state, {
        **st.attributes, "room_temperature": 20.8, "temperature": 21, "active_vicare_program": "comfort",
    })

    # couloir cohérent (+0,1 K) : rien
    hass.states.async_set(REF, "20.9")
    await optimizer._async_sample()
    assert not optimizer.room_faulty

    # le couloir monte, la sonde reste à 20,8 : écart > 1 K, mais pas encore depuis 1 h
    hass.states.async_set(REF, "22.2")
    optimizer.data["samples"] = [{"t": time.time() - 60, "outside": 5, "room": 20.8, "target": 21}]
    await optimizer._async_sample()
    assert not optimizer.room_faulty
    optimizer.data["room_diverge_since"] = time.time() - 3700
    await optimizer._async_sample()
    assert optimizer.data["room_diverging"][:2] == [20.8, 22.2]
    assert "room_diverging" in optimizer.data["alerts"]
    # la mesure fausse est retirée, la référence prend le relais
    assert [s.get("src") for s in optimizer.data["samples"]] == ["ref"]
    assert optimizer.data["samples"][0]["room"] == 22.1
    assert optimizer.status == "collecte (sonde de référence)"
    assert not calls  # 22,1 < 21 + 1,5 : pas encore de surchauffe

    # surchauffe : consignes confort et normal abaissées au réduit
    hass.states.async_set(REF, "22.8")
    await optimizer._async_sample()
    assert {(c.data["entity_id"], c.data["value"]) for c in calls} == {
        ("number.vicare_comfort_temperature", 17.0), ("number.vicare_normal_temperature", 17.0),
    }
    assert optimizer.data["failsafe"]["originals"] == {
        "number.vicare_comfort_temperature": 21.0, "number.vicare_normal_temperature": 20.0,
    }
    assert "failsafe" in optimizer.data["alerts"]
    hass.states.async_set("number.vicare_comfort_temperature", "17")
    hass.states.async_set("number.vicare_normal_temperature", "17")
    st = hass.states.get(CLIMATE)
    hass.states.async_set(CLIMATE, st.state, {**st.attributes, "temperature": 17})
    await optimizer._async_sample()
    assert optimizer.data["samples"][-1]["target"] == 21  # consigne réelle, pas la consigne abaissée

    # la sonde repart : consignes rendues
    calls.clear()
    _room(hass, 22.7)
    await optimizer._async_sample()
    assert not optimizer.room_faulty and not optimizer.data["failsafe"]
    assert {(c.data["entity_id"], c.data["value"]) for c in calls} == {
        ("number.vicare_comfort_temperature", 21.0), ("number.vicare_normal_temperature", 20.0),
    }
    await hass.config_entries.async_unload(entry.entry_id)
