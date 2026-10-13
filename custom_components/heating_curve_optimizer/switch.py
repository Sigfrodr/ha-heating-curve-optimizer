"""Interrupteur ajustement automatique (éteint = simulation)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OptimizerConfigEntry
from .entity import OptimizerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: OptimizerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([AutoAdjustSwitch(entry.runtime_data)])


class AutoAdjustSwitch(OptimizerEntity, SwitchEntity):
    _attr_icon = "mdi:auto-fix"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "auto", "Ajustement automatique")

    @property
    def is_on(self) -> bool:
        return self.optimizer.auto

    async def async_turn_on(self, **kwargs) -> None:
        await self.optimizer.async_set_auto(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.optimizer.async_set_auto(False)
