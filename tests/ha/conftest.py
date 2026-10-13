"""Tests d'intégration Home Assistant (venv avec pytest-homeassistant-custom-component)."""

from unittest.mock import patch

import pytest

# Le harnais HA n'existe que sous Linux (tools/ha-tests.sh) : ailleurs, on saute ces tests.
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.helpers import device_registry as dr  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

import custom_components.heating_curve_optimizer  # noqa: E402,F401  (cible des patch)

DOMAIN = "heating_curve_optimizer"
CLIMATE = "climate.vicare_heating"
OUTSIDE = "sensor.vicare_outside_temperature"
SLOPE = "number.vicare_heating_curve_slope"
SHIFT = "number.vicare_heating_curve_shift"
ENTRY_DATA = {"climate": CLIMATE, "outside_temperature": OUTSIDE, "slope": SLOPE, "shift": SHIFT}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def fake_frontend(hass):
    """Le paquet du frontend n'est pas installé avec le harnais : on le déclare chargé."""
    hass.config.components.update({"frontend", "panel_custom", "websocket_api"})
    hass.config.language = "fr"  # identifiants et textes attendus en français


@pytest.fixture
def vicare(hass):
    """Entités ViCare simulées, rattachées à un même appareil comme dans la vraie intégration."""
    vicare_entry = MockConfigEntry(domain="vicare")
    vicare_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=vicare_entry.entry_id, identifiers={("vicare", "boiler")}
    )
    registry = er.async_get(hass)
    entities = {
        CLIMATE: "heating",
        OUTSIDE: "outside_temperature",
        SLOPE: "heating_curve_slope",
        SHIFT: "heating_curve_shift",
        "number.vicare_comfort_temperature": "comfort_temperature",
        "number.vicare_dhw_temperature": "dhw_temperature",
        "sensor.vicare_supply_pressure": "supply_pressure",
        "sensor.vicare_burner_starts": "burner_starts",
        "sensor.vicare_burner_hours": "burner_hours",
    }
    for entity_id, key in entities.items():
        domain, object_id = entity_id.split(".")
        registry.async_get_or_create(
            domain, "vicare", object_id, suggested_object_id=object_id,
            device_id=device.id, translation_key=key, config_entry=vicare_entry,
        )
    hass.states.async_set(CLIMATE, "auto", {
        "active_vicare_program": "comfortEnergySaving", "room_temperature": 20.4,
        "temperature": None, "vicare_programs": ["comfort", "comfortEnergySaving", "normal", "reduced"],
    })
    hass.states.async_set(OUTSIDE, "5.0")
    hass.states.async_set(SLOPE, "0.2")
    hass.states.async_set(SHIFT, "25")
    hass.states.async_set("number.vicare_comfort_temperature", "19")
    hass.states.async_set("number.vicare_dhw_temperature", "55")
    hass.states.async_set("sensor.vicare_supply_pressure", "1.4")
    hass.states.async_set("sensor.vicare_burner_starts", "15464")
    hass.states.async_set("sensor.vicare_burner_hours", "9358")
    return entities


@pytest.fixture
async def loaded_entry(hass, vicare):
    """Entrée de l'optimiseur chargée (frontend simulé : le panneau n'est pas testé ici)."""
    hass.config.components.update({"frontend", "http", "panel_custom", "websocket_api"})
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={"settle_minutes": 0})
    entry.add_to_hass(hass)
    with patch(f"custom_components.{DOMAIN}.async_register_panel"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    yield entry
    await hass.config_entries.async_unload(entry.entry_id)
