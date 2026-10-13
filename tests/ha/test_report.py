"""Rapport hebdomadaire : nécessite le recorder, qui doit démarrer avant hass."""

import pytest
from homeassistant.core import HomeAssistant

from .test_integration import _pilot_entry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Remplace celui du conftest : le recorder doit être demandé avant hass."""
    yield


@pytest.fixture(autouse=True)
def fake_frontend(recorder_mock, hass):
    """Remplace celui du conftest : le recorder doit être demandé avant hass."""
    hass.config.components.update({"frontend", "panel_custom", "websocket_api"})


async def test_weekly_report_text(hass: HomeAssistant, vicare):
    entry = await _pilot_entry(hass, rooms_demand=True)
    text = await entry.runtime_data.async_weekly_report_text()
    assert "Ajustements de courbe : 0." in text and "Alertes : aucune." in text
    await hass.config_entries.async_unload(entry.entry_id)
