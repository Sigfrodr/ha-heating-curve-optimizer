"""Capteurs d'état de l'optimiseur."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util
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
            PilotSetpointSensor(optimizer),
            GasPriceSensor(optimizer),
            GasCostTodaySensor(optimizer, "heating"),
            GasCostTodaySensor(optimizer, "dhw"),
        ]
    )


class StatusSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:chart-bell-curve-cumulative"

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "status")

    @property
    def native_value(self) -> str:
        return self.optimizer.tr(self.optimizer.status)

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
        super().__init__(optimizer, "mean_error")

    @property
    def native_value(self) -> float | None:
        return self.optimizer.mean_error


class SampleCountSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "samples")

    @property
    def native_value(self) -> int:
        return len(self.optimizer.data["samples"])


class BurnerStartsSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:fire-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "burner_starts_24h")

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
        super().__init__(optimizer, "cycle_minutes_24h")

    @property
    def native_value(self) -> float | None:
        b = self.optimizer.burner
        return b.cycle_minutes if b else None


class PilotSetpointSensor(OptimizerEntity, SensorEntity):
    _attr_icon = "mdi:thermostat-auto"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "pilot_setpoint")

    @property
    def native_value(self) -> float | None:
        state = self.optimizer.data.get("control_state")
        return state.get("setpoint") if state else None

    @property
    def extra_state_attributes(self) -> dict:
        state = self.optimizer.data.get("control_state") or {}
        return {
            "pilotage": self.optimizer.pilot.mode,
            "mode": state.get("mode"),
            "raison": self.optimizer.tr(state["reason"]) if state.get("reason") else None,
        }



class GasPriceSensor(OptimizerEntity, SensorEntity):
    """Prix du m³ de gaz : à choisir comme « entité de prix » dans le tableau Énergie."""

    _attr_icon = "mdi:currency-eur"
    _attr_native_unit_of_measurement = "EUR/m³"
    _attr_suggested_display_precision = 3

    def __init__(self, optimizer) -> None:
        super().__init__(optimizer, "gas_price")

    @property
    def native_value(self) -> float:
        cfg = self.optimizer.cfg
        return round(float(cfg["gas_price"]) * float(cfg["kwh_per_m3"]), 4)


class GasCostTodaySensor(OptimizerEntity, SensorEntity):
    """Coût du gaz consommé aujourd'hui (chauffage ou eau chaude), remis à zéro chaque jour."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2

    KEYS = {
        "heating": "gas_summary_consumption_heating_currentday",
        "dhw": "hotwater_gas_summary_consumption_heating_currentday",
    }

    def __init__(self, optimizer, kind: str) -> None:
        self._source_key = self.KEYS[kind]
        super().__init__(optimizer, f"gas_cost_today_{kind}")

    @property
    def _source(self) -> str | None:
        return self.optimizer._device_entity("sensor", self._source_key)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._source:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._source], self._on_source_change)
            )

    @callback
    def _on_source_change(self, _event) -> None:
        self.async_write_ha_state()

    @property
    def last_reset(self) -> datetime:
        return dt_util.start_of_local_day()

    @property
    def native_value(self) -> float | None:
        m3 = self.optimizer._entity_float(self._source)
        if m3 is None:
            return None
        cfg = self.optimizer.cfg
        return round(m3 * float(cfg["kwh_per_m3"]) * float(cfg["gas_price"]), 2)
