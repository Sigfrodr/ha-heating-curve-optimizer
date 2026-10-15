"""Rafraîchissement ViCare par l'optimiseur pour libérer le quota d'appels."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .test_integration import _pilot_entry


@pytest.fixture(autouse=True)
def no_panel():
    """Les changements d'options rechargent l'intégration : le panneau reste simulé."""
    with patch("custom_components.heating_curve_optimizer.async_register_panel"):
        yield


async def test_optimizer_takes_over_vicare_polling(hass: HomeAssistant, vicare):
    calls = []
    hass.services.async_register("homeassistant", "update_entity", lambda call: calls.append(call.data["entity_id"]))
    vicare_entry = hass.config_entries.async_entries("vicare")[0]
    vicare_entry.mock_state(hass, ConfigEntryState.LOADED)
    entry = await _pilot_entry(hass, rooms_demand=True)
    assert not vicare_entry.pref_disable_polling  # option à 0 : on ne touche pas à ViCare

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        hass.config_entries.async_update_entry(entry, options={**entry.options, "vicare_refresh_minutes": 5})
        await hass.async_block_till_done()
        assert vicare_entry.pref_disable_polling and reload.called
        optimizer = entry.runtime_data
        assert optimizer.data["vicare_polling_disabled"] is True

        await optimizer._async_refresh_vicare()
        assert calls[0] == ["climate.vicare_heating"]  # une entité d'abord : un seul appel API
        assert "sensor.vicare_supply_pressure" not in calls[0] and len(calls) == 2

        # retour à 0 : ViCare reprend son interrogation automatique
        hass.config_entries.async_update_entry(entry, options={**entry.options, "vicare_refresh_minutes": 0})
        await hass.async_block_till_done()
        assert not vicare_entry.pref_disable_polling
        assert "vicare_polling_disabled" not in entry.runtime_data.data
    await hass.config_entries.async_unload(entry.entry_id)
    vicare_entry.mock_state(hass, ConfigEntryState.NOT_LOADED)


async def test_polling_disabled_by_user_is_left_alone(hass: HomeAssistant, vicare):
    vicare_entry = hass.config_entries.async_entries("vicare")[0]
    hass.config_entries.async_update_entry(vicare_entry, pref_disable_polling=True)
    entry = await _pilot_entry(hass, rooms_demand=True)
    with patch.object(hass.config_entries, "async_schedule_reload"):
        hass.config_entries.async_update_entry(entry, options={**entry.options, "vicare_refresh_minutes": 5})
        await hass.async_block_till_done()
        assert "vicare_polling_disabled" not in entry.runtime_data.data
        hass.config_entries.async_update_entry(entry, options={**entry.options, "vicare_refresh_minutes": 0})
        await hass.async_block_till_done()
    assert vicare_entry.pref_disable_polling  # coupé par l'utilisateur : laissé tel quel
    await hass.config_entries.async_unload(entry.entry_id)
