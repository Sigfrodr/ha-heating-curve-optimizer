"""Filtre solaire : couverture nuageuse lue dans l'état de la météo, sinon dans la prévision horaire."""

from homeassistant.core import HomeAssistant, SupportsResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .test_integration import DOMAIN, ENTRY_DATA

WEATHER = "weather.maison"
NOW = "2026-10-27 13:20:00+00:00"


async def _solar_entry(hass, forecast: list | None):
    """Optimiseur avec filtre solaire ; `forecast` = réponse horaire de weather.get_forecasts."""
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 25})
    if forecast is not None:
        async def get_forecasts(call):
            return {WEATHER: {"forecast": forecast}}

        hass.services.async_register("weather", "get_forecasts", get_forecasts,
                                     supports_response=SupportsResponse.ONLY)
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={
        "weather": WEATHER, "solar_filter": True, "solar_cloud_max": 60, "solar_min_elevation": 10})
    entry.add_to_hass(hass)
    from unittest.mock import patch
    with patch(f"custom_components.{DOMAIN}.async_register_panel"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_cloud_coverage_from_state_attribute(hass: HomeAssistant, vicare, freezer):
    freezer.move_to(NOW)
    hass.states.async_set(WEATHER, "sunny", {"cloud_coverage": 20})
    # prévision contradictoire : l'attribut de l'état (met.no) prime
    entry = await _solar_entry(hass, [{"datetime": "2026-10-27T13:00:00+00:00", "cloud_coverage": 90}])
    optimizer = entry.runtime_data
    await optimizer.pilot._async_refresh_forecast()
    assert optimizer._solar_gain()
    hass.states.async_set(WEATHER, "cloudy", {"cloud_coverage": 80})
    assert not optimizer._solar_gain()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_cloud_coverage_from_hourly_forecast(hass: HomeAssistant, vicare, freezer):
    freezer.move_to(NOW)
    hass.states.async_set(WEATHER, "partlycloudy", {"temperature": 9})  # Open-Meteo : pas de cloud_coverage
    forecast = [  # commence avant l'heure en cours : le rang 0 n'est pas « maintenant »
        {"datetime": "2026-10-27T11:00:00+00:00", "cloud_coverage": 90},
        {"datetime": "2026-10-27T12:00:00+00:00", "cloud_coverage": 90},
        {"datetime": "2026-10-27T13:00:00+00:00", "cloud_coverage": 15},
        {"datetime": "2026-10-27T14:00:00+00:00", "cloud_coverage": 95},
    ]
    entry = await _solar_entry(hass, forecast)
    optimizer = entry.runtime_data
    await optimizer.pilot._async_refresh_forecast()
    assert optimizer._solar_gain()  # 15 % à 13 h
    freezer.move_to("2026-10-27 14:05:00+00:00")
    assert not optimizer._solar_gain()  # 95 % à 14 h
    await hass.config_entries.async_unload(entry.entry_id)


async def test_no_cloud_value_keeps_measurement(hass: HomeAssistant, vicare, freezer):
    freezer.move_to(NOW)
    hass.states.async_set(WEATHER, "partlycloudy", {"temperature": 9})
    entry = await _solar_entry(hass, None)  # pas de service de prévisions
    optimizer = entry.runtime_data
    await optimizer.pilot._async_refresh_forecast()
    assert not optimizer._solar_gain()
    await hass.config_entries.async_unload(entry.entry_id)
