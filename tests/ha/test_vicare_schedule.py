"""Écriture du planning de la chaudière via l'API PyViCare de l'intégration ViCare."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from .test_integration import _pilot_entry

PROP = "heating.circuits.0.heating.schedule"


class FakeService:
    def __init__(self):
        self.entries = {"mon": [{"start": "06:30", "end": "23:00", "mode": "comfort", "position": 0}]}
        self.written = []

    def getProperty(self, prop):  # noqa: N802 — API PyViCare
        assert prop == PROP
        return {
            "properties": {"entries": {"value": self.entries}},
            "commands": {"setSchedule": {"isExecutable": True, "params": {"newSchedule": {"constraints": {
                "maxEntries": 2, "resolution": 10, "modes": ["normal", "comfort"], "defaultMode": "reduced"}}}}},
        }

    def setProperty(self, prop, action, data):  # noqa: N802
        self.written.append((prop, action, data))


@pytest.fixture(autouse=True)
def no_panel():
    with patch("custom_components.heating_curve_optimizer.async_register_panel"):
        yield


async def test_push_schedule_to_boiler(hass: HomeAssistant, vicare):
    service = FakeService()
    vicare_entry = hass.config_entries.async_entries("vicare")[0]
    vicare_entry.runtime_data = SimpleNamespace(devices=[SimpleNamespace(api=SimpleNamespace(service=service))])
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    await optimizer.pilot.async_set_schedule({str(d): [["07:00", "22:30"]] for d in range(7)}, 21, 17)

    view = await optimizer.async_vicare_schedule()
    assert view["constraints"]["max_entries"] == 2 and view["current"]["mon"][0]["start"] == "06:30"
    assert view["proposals"]["90"]["mon"][0] == {"start": "05:30", "end": "07:00", "mode": "normal", "position": 0}

    before = optimizer.writes_24h
    result = await optimizer.async_push_vicare_schedule(90)
    prop, action, data = service.written[0]
    assert (prop, action) == (PROP, "setSchedule")
    assert data["newSchedule"]["sun"][1] == {"start": "07:00", "end": "22:30", "mode": "comfort", "position": 1}
    assert result["current"] == data["newSchedule"] and optimizer.writes_24h == before + 1
    assert optimizer.data["vicare_preheat_minutes"] == 90

    # budget épuisé : pas d'écriture
    optimizer.data["writes"] = [__import__("time").time()] * optimizer.write_budget
    with pytest.raises(RuntimeError):
        await optimizer.async_push_vicare_schedule(90)
    assert len(service.written) == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_dhw_schedule_roundtrip(hass: HomeAssistant, vicare):
    service = FakeService()
    service.getProperty = lambda prop: {
        "properties": {"entries": {"value": {"mon": [{"start": "18:00", "end": "23:30", "mode": "on", "position": 0}]}}},
        "commands": {"setSchedule": {"isExecutable": True, "params": {"newSchedule": {"constraints": {
            "maxEntries": 2, "resolution": 10, "modes": ["on"], "defaultMode": "off"}}}}},
    }
    vicare_entry = hass.config_entries.async_entries("vicare")[0]
    vicare_entry.runtime_data = SimpleNamespace(devices=[SimpleNamespace(api=SimpleNamespace(service=service))])
    entry = await _pilot_entry(hass, rooms_demand=True)
    optimizer = entry.runtime_data
    assert (await optimizer.async_dhw_schedule())["current"]["mon"][0]["end"] == "23:30"
    week = {d: [["00:00", "00:30"], ["18:00", "24:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    await optimizer.async_set_dhw_schedule(week)
    prop, action, data = service.written[0]
    assert (prop, action) == ("heating.dhw.schedule", "setSchedule")
    assert data["newSchedule"]["sun"][1] == {"start": "18:00", "end": "24:00", "mode": "on", "position": 1}
    # relu juste après l'envoi : le planning écrit, pas l'ancien encore en cache
    assert (await optimizer.async_dhw_schedule())["current"]["mon"][1]["end"] == "24:00"
    with pytest.raises(ValueError):
        await optimizer.async_set_dhw_schedule({"mon": [["18:00", "19:00"], ["18:30", "20:00"]]})
    await hass.config_entries.async_unload(entry.entry_id)
