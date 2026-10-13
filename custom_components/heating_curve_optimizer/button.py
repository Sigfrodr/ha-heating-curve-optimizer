"""Bouton d'évaluation immédiate."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OptimizerConfigEntry
from .entity import OptimizerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: OptimizerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EvaluateButton(entry.runtime_data), MaintenanceDoneButton(entry.runtime_data)])


class EvaluateButton(OptimizerEntity, ButtonEntity):
    _attr_icon = "mdi:calculator-variant"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "evaluate", "Évaluer maintenant")

    async def async_press(self) -> None:
        await self.optimizer.async_evaluate()


class MaintenanceDoneButton(OptimizerEntity, ButtonEntity):
    _attr_icon = "mdi:wrench-check"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "maintenance_done", "Entretien effectué")

    async def async_press(self) -> None:
        await self.optimizer.async_set_maintenance()
