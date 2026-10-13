"""Entité de base liée à l'optimiseur."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .optimizer import HeatingCurveOptimizer


class OptimizerEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, optimizer: HeatingCurveOptimizer, key: str) -> None:
        self.optimizer = optimizer
        entry_id = optimizer.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_translation_key = key  # nom traduit (translations/<langue>.json, section entity)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            translation_key="optimizer",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.optimizer.add_listener(self.async_write_ha_state))
