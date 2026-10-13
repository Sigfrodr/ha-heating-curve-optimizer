"""Capteurs d'état de l'optimiseur."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OptimizerConfigEntry
from .entity import OptimizerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: OptimizerConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    optimizer = entry.runtime_data
    async_add_entities(
        [
            StatusSensor(optimizer),
            MeanErrorSensor(optimizer),
            SampleCountSensor(optimizer),
            BurnerStartsSensor(optimizer),
            CycleLengthSensor(optimizer),
        ]
    )


class StatusSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "status", "État")

    @property
    def native_value(self) -> str:
        return self.optimizer.status

    @property
    def extra_state_attributes(self) -> dict:
        data = self.optimizer.data
        return {
            "ajustement_auto": self.optimizer.auto,
            "derniere_proposition": data["last_proposal"],
            "dernier_ajustement": data["history"][-1] if data["history"] else None,
        }


class MeanErrorSensor(OptimizerEntity, SensorEntity):
    # Pas de device_class température : HA convertirait ces K en °C absolus.
    _attr_icon = "mdi:thermometer-lines"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.KELVIN
    _attr_suggested_display_precision = 2

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "mean_error", "Écart moyen ambiance - consigne")

    @property
    def native_value(self) -> float | None:
        return self.optimizer.mean_error


class SampleCountSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "samples", "Échantillons")

    @property
    def native_value(self) -> int:
        return len(self.optimizer.data["samples"])


class BurnerStartsSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:fire-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "burner_starts_24h", "Démarrages brûleur (24 h)")

    @property
    def native_value(self) -> int | None:
        b = self.optimizer.burner
        return b.starts if b else None


class CycleLengthSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "cycle_minutes_24h", "Durée moyenne de cycle brûleur (24 h)")

    @property
    def native_value(self) -> float | None:
        b = self.optimizer.burner
        return b.cycle_minutes if b else None
