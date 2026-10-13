"""Mode de pilotage de la consigne (désactivé / simulation / actif)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OptimizerConfigEntry
from .entity import OptimizerEntity

LABELS = {"off": "Désactivé", "simulation": "Simulation", "active": "Actif"}
MODES = {label: mode for mode, label in LABELS.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: OptimizerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ControlModeSelect(entry.runtime_data)])


class ControlModeSelect(OptimizerEntity, SelectEntity):
    _attr_icon = "mdi:home-thermometer"
    _attr_options = list(LABELS.values())

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "control_mode", "Pilotage de la consigne")

    @property
    def current_option(self) -> str:
        return LABELS[self.optimizer.pilot.mode]

    async def async_select_option(self, option: str) -> None:
        await self.optimizer.pilot.async_set_mode(MODES[option])
