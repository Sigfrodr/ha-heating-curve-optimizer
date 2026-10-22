"""Bouton d'évaluation immédiate."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OptimizerConfigEntry
from .const import CONF_BOILER_SWITCH
from .entity import OptimizerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: OptimizerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entities = [EvaluateButton(entry.runtime_data), MaintenanceDoneButton(entry.runtime_data)]
    if entry.runtime_data.cfg.get(CONF_BOILER_SWITCH):
        entities.append(RestartBoilerButton(entry.runtime_data))
    async_add_entities(entities)


class EvaluateButton(OptimizerEntity, ButtonEntity):
    _attr_icon = "mdi:calculator-variant"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "evaluate")

    async def async_press(self) -> None:
        await self.optimizer.async_evaluate()


class MaintenanceDoneButton(OptimizerEntity, ButtonEntity):
    _attr_icon = "mdi:wrench-check"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "maintenance_done")

    async def async_press(self) -> None:
        await self.optimizer.async_set_maintenance()


class RestartBoilerButton(OptimizerEntity, ButtonEntity):
    """Coupe 30 s l'alimentation de la chaudière (prise connectée) : relance aussi le Vitotrol."""

    _attr_icon = "mdi:restart-alert"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "restart_boiler")

    async def async_press(self) -> None:
        await self.optimizer.async_restart_boiler("bouton Redémarrer la chaudière")
