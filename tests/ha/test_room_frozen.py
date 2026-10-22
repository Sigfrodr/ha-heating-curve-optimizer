"""Sonde d'ambiance figée : mesures ignorées et retirées, alerte, retour à la normale."""

import time

from homeassistant.core import HomeAssistant

from .test_integration import _pilot_entry

CLIMATE = "climate.vicare_heating"
STARTS = "sensor.vicare_burner_starts"


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
