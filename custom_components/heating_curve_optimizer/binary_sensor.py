"""Alerte chaudière (pression, injoignable, antigel, cycles courts)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OptimizerConfigEntry
from .entity import OptimizerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: OptimizerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([BoilerAlertSensor(entry.runtime_data)])


class BoilerAlertSensor(OptimizerEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "alert")

    @property
    def is_on(self) -> bool:
        return bool(self.optimizer.data["alerts"])

    @property
    def extra_state_attributes(self) -> dict:
        return {"alertes": [self.optimizer.tr(a) for a in self.optimizer.data["alerts"].values()]}
