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
    CONF_OUTSIDE,
    CONF_PROGRAMS,
    CONF_ROOM,
    CONF_SHIFT,
    CONF_SLOPE,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from .settings_spec import EMPTY, FIELDS, SECTIONS


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


def _selector(field: dict, programs: list[str]):
    """Sélecteur HA correspondant à un champ de settings_spec."""
    kind = field["kind"]
    if kind == "number":
        return _number(field["min"], field["max"], field["step"], field.get("unit"))
    if kind == "bool":
        return selector.BooleanSelector()
    if kind == "time":
        return selector.TimeSelector()
    if kind == "date":
        return selector.DateSelector()
    if kind == "weekday":
        return selector.SelectSelector(
            selector.SelectSelectorConfig(options=[str(i) for i in range(7)], translation_key="weekday")
        )
    if kind == "programs":
        return selector.SelectSelector(
            selector.SelectSelectorConfig(options=programs, multiple=True, custom_value=True)
        )
    if kind == "entities":
        return selector.EntitySelector(selector.EntitySelectorConfig(domain=field["domain"], multiple=True))
    if kind == "entity":
        return _entity(field["domain"], field.get("device_class"))
    if kind == "secret":
        return selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
    return selector.TextSelector()


class HeatingCurveOptimizerOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            flat: dict[str, Any] = {}
            for key, value in user_input.items():
                if key in SECTIONS:
                    flat.update(value)
                else:
                    flat[key] = value
            for key, empty in EMPTY.items():
                flat.setdefault(key, empty)
            return self.async_create_entry(data=flat)

        climate = self.hass.states.get(self.config_entry.data[CONF_CLIMATE])
        programs = list(climate.attributes.get("vicare_programs", [])) if climate else []
        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        programs = sorted(set(programs) | set(current[CONF_PROGRAMS]))

        groups: dict[str | None, dict] = {None: {}, **{name: {} for name in SECTIONS}}
        for field in FIELDS:
            marker = vol.Optional if field.get("optional") else vol.Required
            groups[field["section"]][marker(field["key"])] = _selector(field, programs)

        def suggest(group: dict) -> dict:
            return {str(k): current.get(str(k)) for k in group if current.get(str(k)) not in (None, "")}

        schema: dict = dict(groups[None])
        suggested: dict[str, Any] = suggest(groups[None])
        for name in SECTIONS:
            schema[vol.Required(name)] = section(vol.Schema(groups[name]), {"collapsed": name != "rooms_weather"})
            suggested[name] = suggest(groups[name])
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(schema), suggested),
        )
