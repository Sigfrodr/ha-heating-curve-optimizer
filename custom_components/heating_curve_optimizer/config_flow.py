"""Configuration via l'interface."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_CLIMATE,
    CONF_EVALUATE_AT,
    CONF_HEATING_LIMIT,
    CONF_MAX_AGE_DAYS,
    CONF_MIN_SAMPLES,
    CONF_NOTIFY,
    CONF_OUTSIDE,
    CONF_PROGRAMS,
    CONF_ROOM,
    CONF_SAMPLE_MINUTES,
    CONF_SETTLE_MINUTES,
    CONF_SHIFT,
    CONF_SLOPE,
    DEFAULT_OPTIONS,
    DOMAIN,
)


def _number(lo: float, hi: float, step: float, unit: str | None = None) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=lo, max=hi, step=step, unit_of_measurement=unit, mode=selector.NumberSelectorMode.BOX
        )
    )


def _entity(domain: str, device_class: str | None = None) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain, device_class=device_class))


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
            user_input.setdefault(CONF_NOTIFY, "")
            return self.async_create_entry(data=user_input)

        climate = self.hass.states.get(self.config_entry.data[CONF_CLIMATE])
        programs = list(climate.attributes.get("vicare_programs", [])) if climate else []
        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        programs = sorted(set(programs) | set(current[CONF_PROGRAMS]))

        schema = vol.Schema(
            {
                vol.Required(CONF_PROGRAMS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=programs, multiple=True, custom_value=True)
                ),
                vol.Required(CONF_HEATING_LIMIT): _number(5, 25, 0.5, "°C"),
                vol.Required(CONF_SETTLE_MINUTES): _number(0, 720, 10, "min"),
                vol.Required(CONF_SAMPLE_MINUTES): _number(5, 60, 1, "min"),
                vol.Required(CONF_MIN_SAMPLES): _number(6, 2000, 1),
                vol.Required(CONF_MAX_AGE_DAYS): _number(1, 60, 1, "j"),
                vol.Required(CONF_EVALUATE_AT): selector.TimeSelector(),
                vol.Optional(CONF_NOTIFY): selector.TextSelector(),
                vol.Required("damping"): _number(0.1, 1, 0.05),
                vol.Required("max_shift_step"): _number(1, 10, 1, "K"),
                vol.Required("max_slope_step"): _number(0.1, 1, 0.1),
                vol.Required("shift_min"): _number(-13, 40, 1, "K"),
                vol.Required("shift_max"): _number(-13, 40, 1, "K"),
                vol.Required("slope_min"): _number(0.2, 3.5, 0.1),
                vol.Required("slope_max"): _number(0.2, 3.5, 0.1),
                vol.Required("deadband"): _number(0, 2, 0.1, "K"),
                vol.Required("min_outside_spread"): _number(0, 20, 1, "K"),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=self.add_suggested_values_to_schema(schema, current)
        )
