"""Optimiseur de courbe de chauffe pour chaudière Viessmann (ViCare)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .optimizer import HeatingCurveOptimizer
from .panel import async_register_panel, async_unregister_panel

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON, Platform.BINARY_SENSOR]

type OptimizerConfigEntry = ConfigEntry[HeatingCurveOptimizer]


async def async_setup_entry(hass: HomeAssistant, entry: OptimizerConfigEntry) -> bool:
    optimizer = HeatingCurveOptimizer(hass, entry)
    await optimizer.async_start()
    entry.runtime_data = optimizer
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_panel(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OptimizerConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
        others = [e for e in hass.config_entries.async_loaded_entries(DOMAIN) if e is not entry]
        if not others:
            async_unregister_panel(hass)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: OptimizerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
