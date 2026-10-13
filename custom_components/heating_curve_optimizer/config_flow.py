"""Configuration via l'interface."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_CLIMATE,
    CONF_EVALUATE_AT,
    CONF_HEATING_LIMIT,
    CONF_LEGIONELLA_MINUTES,
    CONF_LEGIONELLA_TEMP,
    CONF_LEGIONELLA_TIME,
    CONF_LEGIONELLA_WEEKDAY,
    CONF_MIN_PRESSURE,
    CONF_MAX_AGE_DAYS,
    CONF_MIN_SAMPLES,
    CONF_NOTIFY,
    CONF_OUTSIDE,
    CONF_PROGRAMS,
    CONF_ROOM,
    CONF_ROOMS,
    CONF_SAMPLE_MINUTES,
    CONF_SETTLE_MINUTES,
    CONF_SHIFT,
    CONF_SHORT_CYCLE_MINUTES,
    CONF_SLOPE,
    CONF_SOLAR_CLOUD_MAX,
    CONF_SOLAR_FILTER,
    CONF_SOLAR_MIN_ELEVATION,
    CONF_WEATHER,
    CONF_DEMAND_DELAY,
    CONF_GAS_PRICE,
    CONF_KWH_PER_M3,
    CONF_REPORT_TIME,
    CONF_REPORT_WEEKDAY,
    CONF_STANDBY_TEMP,
    CONF_SUN_ANTICIPATION,
    CONF_WEEKLY_REPORT,
    DEFAULT_OPTIONS,
    DOMAIN,
)


def _number(lo: float, hi: float, step: float, unit: str | None = None) -> selector.NumberSelector:
    # Le schéma des sélecteurs refuse une clé à None : ne la passer que si elle est définie.
    config = selector.NumberSelectorConfig(
        min=lo, max=hi, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _entity(domain: str, device_class: str | None = None) -> selector.EntitySelector:
    config = selector.EntitySelectorConfig(domain=domain)
    if device_class:
        config["device_class"] = device_class
    return selector.EntitySelector(config)


ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIMATE): _entity("climate"),
        vol.Required(CONF_OUTSIDE): _entity("sensor", "temperature"),
        vol.Required(CONF_SLOPE): _entity("number"),
        vol.Required(CONF_SHIFT): _entity("number"),
        vol.Optional(CONF_ROOM): _entity("sensor", "temperature"),
    }
)


class HeatingCurveOptimizerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_CLIMATE])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Courbe de chauffe", data=user_input, options=dict(DEFAULT_OPTIONS)
            )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(ENTITIES_SCHEMA, self._vicare_suggestions()),
        )

    def _vicare_suggestions(self) -> dict[str, str]:
        """Pré-remplit avec les entités de l'intégration ViCare."""
        suggestions: dict[str, str] = {}
        for entry in er.async_get(self.hass).entities.values():
            if entry.platform != "vicare" or entry.disabled:
                continue
            key = (entry.translation_key or "") + " " + entry.entity_id
            if entry.domain == "climate":
                suggestions.setdefault(CONF_CLIMATE, entry.entity_id)
            elif entry.domain == "sensor" and "outside_temperature" in key:
                suggestions.setdefault(CONF_OUTSIDE, entry.entity_id)
            elif entry.domain == "number" and "heating_curve_slope" in key:
                suggestions.setdefault(CONF_SLOPE, entry.entity_id)
            elif entry.domain == "number" and "heating_curve_shift" in key:
                suggestions.setdefault(CONF_SHIFT, entry.entity_id)
        return suggestions

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return HeatingCurveOptimizerOptionsFlow()


class HeatingCurveOptimizerOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            flat: dict[str, Any] = {}
            for key, value in user_input.items():
                if key in SECTIONS:
                    flat.update(value)
                else:
                    flat[key] = value
            flat.setdefault(CONF_NOTIFY, "")
            flat.setdefault(CONF_WEATHER, "")
            flat.setdefault(CONF_ROOMS, [])
            return self.async_create_entry(data=flat)

        climate = self.hass.states.get(self.config_entry.data[CONF_CLIMATE])
        programs = list(climate.attributes.get("vicare_programs", [])) if climate else []
        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        programs = sorted(set(programs) | set(current[CONF_PROGRAMS]))
        weekdays = [
            selector.SelectOptionDict(value=str(i), label=label)
            for i, label in enumerate(
                ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
            )
        ]

        fields = {
            None: {
                vol.Required(CONF_PROGRAMS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=programs, multiple=True, custom_value=True)
                ),
                vol.Required(CONF_HEATING_LIMIT): _number(5, 25, 0.5, "°C"),
                vol.Required(CONF_EVALUATE_AT): selector.TimeSelector(),
                vol.Optional(CONF_NOTIFY): selector.TextSelector(),
            },
            "rooms_weather": {
                vol.Optional(CONF_ROOMS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_WEATHER): _entity("weather"),
                vol.Required(CONF_SOLAR_FILTER): selector.BooleanSelector(),
                vol.Required(CONF_SOLAR_CLOUD_MAX): _number(0, 100, 5, "%"),
                vol.Required(CONF_SOLAR_MIN_ELEVATION): _number(0, 60, 1, "°"),
            },
            "alerts": {
                vol.Required(CONF_MIN_PRESSURE): _number(0.3, 2.5, 0.1, "bar"),
                vol.Required(CONF_SHORT_CYCLE_MINUTES): _number(2, 30, 1, "min"),
            },
            "dhw": {
                vol.Required(CONF_LEGIONELLA_WEEKDAY): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=weekdays)
                ),
                vol.Required(CONF_LEGIONELLA_TIME): selector.TimeSelector(),
                vol.Required(CONF_LEGIONELLA_TEMP): _number(55, 70, 1, "°C"),
                vol.Required(CONF_LEGIONELLA_MINUTES): _number(30, 240, 10, "min"),
            },
            "pilot": {
                vol.Required(CONF_STANDBY_TEMP): _number(5, 20, 1, "°C"),
                vol.Required(CONF_DEMAND_DELAY): _number(5, 120, 5, "min"),
                vol.Required(CONF_SUN_ANTICIPATION): selector.BooleanSelector(),
            },
            "costs_report": {
                vol.Required(CONF_GAS_PRICE): _number(0.01, 1, 0.001, "€/kWh"),
                vol.Required(CONF_KWH_PER_M3): _number(8, 13, 0.01, "kWh/m³"),
                vol.Required(CONF_WEEKLY_REPORT): selector.BooleanSelector(),
                vol.Required(CONF_REPORT_WEEKDAY): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=weekdays)
                ),
                vol.Required(CONF_REPORT_TIME): selector.TimeSelector(),
            },
            "algorithm": {
                vol.Required(CONF_SETTLE_MINUTES): _number(0, 720, 10, "min"),
                vol.Required(CONF_SAMPLE_MINUTES): _number(5, 60, 1, "min"),
                vol.Required(CONF_MIN_SAMPLES): _number(6, 2000, 1),
                vol.Required(CONF_MAX_AGE_DAYS): _number(1, 60, 1, "j"),
                vol.Required("damping"): _number(0.1, 1, 0.05),
                vol.Required("max_shift_step"): _number(1, 10, 1, "K"),
                vol.Required("max_slope_step"): _number(0.1, 1, 0.1),
                vol.Required("shift_min"): _number(-13, 40, 1, "K"),
                vol.Required("shift_max"): _number(-13, 40, 1, "K"),
                vol.Required("slope_min"): _number(0.2, 3.5, 0.1),
                vol.Required("slope_max"): _number(0.2, 3.5, 0.1),
                vol.Required("deadband"): _number(0, 2, 0.1, "K"),
                vol.Required("min_outside_spread"): _number(0, 20, 1, "K"),
            },
        }
        schema: dict = dict(fields[None])
        suggested: dict[str, Any] = {str(k): current.get(str(k)) for k in fields[None]}
        for name in SECTIONS:
            schema[vol.Required(name)] = section(
                vol.Schema(fields[name]), {"collapsed": name != "rooms_weather"}
            )
            suggested[name] = {
                str(k): current.get(str(k)) for k in fields[name] if current.get(str(k)) not in (None, "")
            }
        suggested = {k: v for k, v in suggested.items() if v not in (None, "")}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(schema), suggested),
        )


SECTIONS = ("rooms_weather", "pilot", "costs_report", "alerts", "dhw", "algorithm")
