"""Pilotage HA de la consigne : planning, veille sur demande, relance optimale, météo.

ViCare ne permet ni de modifier le planning de la chaudière ni de forcer un
programme : le seul levier est la consigne du programme actif (comme dans
l'appli ViCare). Le pilote calcule la consigne voulue et, en mode actif,
l'écrit via climate.set_temperature. Les consignes d'origine des programmes
sont mémorisées et remises quand le pilotage est désactivé.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Event, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLIMATE,
    CONF_DEMAND_DELAY,
    CONF_ROOMS,
    CONF_STANDBY_TEMP,
    CONF_SUN_ANTICIPATION,
    CONF_WEATHER,
    CONTROL_MODES,
)
from .control import (
    DEFAULT_SCHEDULE,
    ControlInputs,
    decide_setpoint,
    forecast_factor,
    normalize_schedule,
    preheat_rate,
    schedule_from_trvs,
    sun_expected,
)

if TYPE_CHECKING:
    from .optimizer import HeatingCurveOptimizer

_LOGGER = logging.getLogger(__name__)

PROGRAM_KEYS = ("comfort", "normal", "reduced")
MIN_WRITE_INTERVAL = 300  # s entre deux écritures de consigne
MAX_WRITES_PER_DAY = 48
WEEKDAYS_EN = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class HeatingPilot:
    def __init__(self, optimizer: HeatingCurveOptimizer) -> None:
        self.o = optimizer
        self.hass = optimizer.hass
        d = optimizer.data
        d.setdefault("control_mode", "off")
        d.setdefault("schedule", None)
        d.setdefault("temps", None)
        d.setdefault("control_originals", None)
        d.setdefault("control_state", None)
        d.setdefault("decision_log", [])
        d.setdefault("standby_log", [])
        d.setdefault("preheat_rate", None)
        d.setdefault("writes", [])
        d.setdefault("room_targets", {})
        d.setdefault("room_originals", {})
        self._room_writes: dict[str, float] = {}
        self._no_demand_since: float | None = None
        self._forecast: dict = {}
        self._last_write = 0.0

    # ------------------------------------------------------------ cycle de vie

    async def async_start(self) -> None:
        o = self.o
        if o.data["temps"] is None:
            comfort = o._entity_float(o._device_entity("number", "comfort_temperature")) or 19.0
            reduced = o._entity_float(o._device_entity("number", "reduced_temperature")) or 17.0
            o.data["temps"] = {"comfort": comfort, "reduced": reduced}
        if o.data["schedule"] is None:
            o.data["schedule"] = self.trv_schedule_suggestion() or DEFAULT_SCHEDULE
            o._save()
        rooms = o.cfg.get(CONF_ROOMS) or []
        if rooms:
            o._unsubs.append(async_track_state_change_event(self.hass, rooms, self._on_room_change))
        o._unsubs.append(async_track_time_interval(self.hass, self.async_tick, timedelta(minutes=5)))
        o._unsubs.append(async_track_time_interval(self.hass, self._async_refresh_forecast, timedelta(minutes=30)))
        self.hass.async_create_task(self._async_refresh_forecast())
        self.hass.async_create_task(self.async_learn_preheat())

    @property
    def mode(self) -> str:
        return self.o.data["control_mode"]

    @property
    def temps(self) -> dict:
        return self.o.data["temps"]

    @property
    def schedule(self) -> dict:
        return normalize_schedule(self.o.data["schedule"] or DEFAULT_SCHEDULE)

    # ----------------------------------------------------------- réglages

    async def async_set_mode(self, mode: str) -> None:
        if mode not in CONTROL_MODES:
            raise ValueError(mode)
        previous = self.mode
        if mode == previous:
            return
        if mode == "active":
            self._save_originals()
        self.o.data["control_mode"] = mode
        self.o._save()
        if previous == "active":
            await self._async_restore_originals()
            for entity_id in list(self.o.data["room_originals"]):
                await self._async_restore_room(entity_id)
        await self.async_tick()

    async def async_set_schedule(self, schedule: dict, comfort: float, reduced: float) -> None:
        self.o.data["schedule"] = normalize_schedule(schedule)
        self.o.data["temps"] = {"comfort": float(comfort), "reduced": float(reduced)}
        self.o._save()
        await self.async_tick()

    # ----------------------------------------------------------- consignes par pièce

    def room_targets(self) -> dict[str, dict]:
        """Réglage de chaque pièce suivie (désactivée par défaut, consignes de la maison)."""
        targets = self.o.data["room_targets"]
        out = {}
        for entity_id in self.o.cfg.get(CONF_ROOMS) or []:
            out[entity_id] = targets.get(entity_id) or {
                "enabled": False, "comfort": self.temps["comfort"], "reduced": self.temps["reduced"],
            }
        return out

    async def async_set_room_targets(self, targets: dict[str, dict]) -> None:
        rooms = set(self.o.cfg.get(CONF_ROOMS) or [])
        for entity_id, t in targets.items():
            if entity_id not in rooms:
                raise ValueError(f"pièce non suivie : {entity_id}")
            self.o.data["room_targets"][entity_id] = {
                "enabled": bool(t["enabled"]), "comfort": float(t["comfort"]), "reduced": float(t["reduced"]),
            }
            if not t["enabled"]:
                await self._async_restore_room(entity_id)
        self.o._save()
        await self.async_tick()

    def _room_plan(self, mode: str) -> dict[str, float]:
        level = "reduced" if mode == "réduit" else "comfort"
        return {e: t[level] for e, t in self.room_targets().items() if t["enabled"]}

    async def _async_apply_rooms(self, plan: dict[str, float], now: float) -> None:
        for entity_id, target in plan.items():
            st = self.hass.states.get(entity_id)
            if st is None or st.state in ("off", "unavailable", "unknown"):
                continue
            if st.attributes.get("window_open") or st.attributes.get("window_state") == "on":
                continue  # Better Thermostat gère la fenêtre ouverte
            current = st.attributes.get("temperature")
            if current is not None and abs(float(current) - target) < 0.25:
                continue
            if now - self._room_writes.get(entity_id, 0) < MIN_WRITE_INTERVAL:
                continue
            originals = self.o.data["room_originals"]
            if entity_id not in originals and current is not None:
                originals[entity_id] = float(current)
            await self.hass.services.async_call(
                "climate", "set_temperature", {"entity_id": entity_id, "temperature": target}, blocking=True
            )
            self._room_writes[entity_id] = now
            _LOGGER.info("Pilotage : %s %s → %s °C", entity_id, current, target)

    async def _async_restore_room(self, entity_id: str) -> None:
        original = self.o.data["room_originals"].pop(entity_id, None)
        if original is None:
            return
        await self.hass.services.async_call(
            "climate", "set_temperature", {"entity_id": entity_id, "temperature": original}, blocking=True
        )
        self.o._save()

    def _program_entities(self) -> dict[str, str]:
        o = self.o
        return {k: e for k in PROGRAM_KEYS if (e := o._device_entity("number", f"{k}_temperature"))}

    def _save_originals(self) -> None:
        if self.o.data["control_originals"]:
            return  # déjà mémorisées (pilotage interrompu par un redémarrage)
        self.o.data["control_originals"] = {
            entity: value
            for entity in self._program_entities().values()
            if (value := self.o._entity_float(entity)) is not None
        }

    async def _async_restore_originals(self) -> None:
        originals = self.o.data["control_originals"] or {}
        for entity, value in originals.items():
            if self.o._entity_float(entity) != value:
                await self.o._async_set_number(entity, value)
        self.o.data["control_originals"] = None
        self.o._save()
        _LOGGER.info("Pilotage désactivé : consignes d'origine remises %s", originals)

    # ----------------------------------------------------------- planning des têtes

    def trv_schedule_suggestion(self) -> dict | None:
        """Planning déduit des plannings des têtes thermostatiques (capteurs *_schedule_<jour>)."""
        prefixes = self._trv_prefixes()
        trvs = []
        for prefix in prefixes:
            days = {}
            for i, name in enumerate(WEEKDAYS_EN):
                st = self.hass.states.get(f"sensor.{prefix}_schedule_{name}")
                if st and st.state not in ("unknown", "unavailable"):
                    days[i] = st.state
            if days:
                trvs.append(days)
        if not trvs:
            return None
        return schedule_from_trvs(trvs)

    def _trv_prefixes(self) -> list[str]:
        """Têtes des pièces suivies (attribut batteries de Better Thermostat), sinon toutes."""
        prefixes: set[str] = set()
        for room in self.o.cfg.get(CONF_ROOMS) or []:
            st = self.hass.states.get(room)
            raw = st.attributes.get("batteries") if st else None
            try:
                keys = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except ValueError:
                keys = {}
            prefixes |= {k.split(".", 1)[1] for k in keys if k.startswith("climate.")}
        if not prefixes:
            prefixes = {
                st.entity_id.removeprefix("sensor.").removesuffix("_schedule_monday")
                for st in self.hass.states.async_all("sensor")
                if st.entity_id.endswith("_schedule_monday")
            }
        return sorted(prefixes)

    # ----------------------------------------------------------- apprentissage et météo

    async def async_learn_preheat(self) -> None:
        try:
            result = await self.o.async_recoveries(14)
        except Exception as err:  # noqa: BLE001  historique indisponible : on garde l'ancienne valeur
            _LOGGER.debug("Apprentissage de la relance impossible : %s", err)
            return
        from .analysis import Recovery  # noqa: PLC0415

        rate = preheat_rate([Recovery(**r) for r in result["recoveries"]])
        if rate:
            self.o.data["preheat_rate"] = round(rate, 2)
            self.o._save()

    async def _async_refresh_forecast(self, _now=None) -> None:
        weather = self.o.cfg.get(CONF_WEATHER)
        if not weather:
            return
        try:
            response = await self.hass.services.async_call(
                "weather", "get_forecasts", {"entity_id": weather, "type": "hourly"},
                blocking=True, return_response=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Prévisions indisponibles : %s", err)
            return
        hours = (response or {}).get(weather, {}).get("forecast", [])[:6]
        self._forecast = {
            "temps": [f.get("temperature") for f in hours if f.get("temperature") is not None],
            "clouds": [f.get("cloud_coverage") for f in hours if f.get("cloud_coverage") is not None],
            "at": time.time(),
        }

    # ----------------------------------------------------------- boucle de décision

    @callback
    def _on_room_change(self, event: Event) -> None:
        old, new = event.data.get("old_state"), event.data.get("new_state")
        was = old and old.attributes.get("hvac_action") == "heating"
        now = new and new.attributes.get("hvac_action") == "heating"
        if was != now:
            self.hass.async_create_task(self.async_tick())

    def _any_demand(self) -> tuple[bool, bool]:
        rooms = self.o.cfg.get(CONF_ROOMS) or []
        demand = False
        for entity_id in rooms:
            st = self.hass.states.get(entity_id)
            if st and st.state not in ("off", "unavailable") and st.attributes.get("hvac_action") == "heating":
                demand = True
        return bool(rooms), demand

    def decide(self):
        o = self.o
        now_dt = dt_util.now()
        now = time.time()
        configured, demand = self._any_demand()
        if demand or not configured:
            self._no_demand_since = None
        elif self._no_demand_since is None:
            self._no_demand_since = now
        climate = self.hass.states.get(o.cfg[CONF_CLIMATE])
        room = None
        if climate:
            from .optimizer import _float  # noqa: PLC0415

            room = _float(climate.attributes.get("room_temperature"))
        outside = o._entity_float(o.cfg.get("outside_temperature"))
        temps = self._forecast.get("temps") or []
        sun = self.hass.states.get("sun.sun")
        elevation = sun.attributes.get("elevation") if sun else None
        inputs = ControlInputs(
            weekday=now_dt.weekday(),
            minute=now_dt.hour * 60 + now_dt.minute,
            schedule=self.schedule,
            comfort_temp=self.temps["comfort"],
            reduced_temp=self.temps["reduced"],
            standby_temp=float(o.cfg[CONF_STANDBY_TEMP]),
            rooms_configured=configured,
            any_demand=demand,
            no_demand_minutes=(now - self._no_demand_since) / 60 if self._no_demand_since else 0.0,
            demand_delay_minutes=float(o.cfg[CONF_DEMAND_DELAY]),
            room=room,
            preheat_rate=o.data["preheat_rate"],
            forecast_factor=forecast_factor(self.temps["comfort"], outside, min(temps[:4]) if temps else None),
            sun_expected=bool(o.cfg.get(CONF_SUN_ANTICIPATION))
            and sun_expected(elevation, (self._forecast.get("clouds") or [])[:3]),
        )
        return decide_setpoint(inputs)

    async def async_tick(self, _now=None) -> None:
        if self.mode == "off":
            if self.o.data["control_state"]:
                self.o.data["control_state"] = None
                self.o._save()
                self.o._set_status(self.o.status)
            return
        climate = self.hass.states.get(self.o.cfg[CONF_CLIMATE])
        if climate is not None and climate.state == "off":
            # Chaudière arrêtée (mode vacances, veille manuelle) : ne rien écrire
            state = self.o.data["control_state"] or {}
            if state.get("mode") != "pause":
                self.o.data["control_state"] = {
                    "mode": "pause", "setpoint": None, "since": time.time(), "at": time.time(), "rooms": {},
                    "reason": "chaudière à l'arrêt (vacances ou veille) : pilotage en pause",
                }
                self.o._save()
                self.o._set_status(self.o.status)
            return
        decision = self.decide()
        now = time.time()
        state = self.o.data["control_state"] or {}
        if state.get("mode") != decision.mode:
            self._log_transition(state.get("mode"), decision.mode, now)
            state = {"mode": decision.mode, "since": now}
        rooms_plan = self._room_plan(decision.mode)
        state.update({"setpoint": decision.setpoint, "reason": decision.reason, "at": now, "rooms": rooms_plan})
        self.o.data["control_state"] = state
        log = self.o.data["decision_log"]
        if not log or log[-1][1] != decision.mode or log[-1][2] != decision.setpoint or now - log[-1][0] > 1800:
            log.append([now, decision.mode, decision.setpoint])
            self.o.data["decision_log"] = [x for x in log if x[0] >= now - 2 * 86400]
        if self.mode == "active":
            await self._async_apply(decision.setpoint, now)
            await self._async_apply_rooms(rooms_plan, now)
        self.o._save()
        self.o._set_status(self.o.status)

    def _log_transition(self, old: str | None, new: str, now: float) -> None:
        """Mémorise les périodes de veille (pour le rapport et le panneau)."""
        log = self.o.data["standby_log"]
        if new == "veille":
            log.append([now, None])
        elif old == "veille" and log and log[-1][1] is None:
            log[-1][1] = now
        self.o.data["standby_log"] = [p for p in log if (p[1] or now) >= now - 14 * 86400]

    def standby_hours(self, since: float) -> float:
        now = time.time()
        total = 0.0
        for start, end in self.o.data["standby_log"]:
            s, e = max(start, since), (end or now)
            if e > s:
                total += e - s
        return total / 3600

    async def _async_apply(self, setpoint: float, now: float) -> None:
        climate = self.hass.states.get(self.o.cfg[CONF_CLIMATE])
        if climate is None or climate.state == "unavailable":
            return
        current = climate.attributes.get("temperature")
        if current is None:
            program = str(climate.attributes.get("active_vicare_program", ""))
            current = self.o._program_temperature(program)
        if current is not None and abs(float(current) - setpoint) < 0.5:
            return
        writes = [t for t in self.o.data["writes"] if t >= now - 86400]
        if now - self._last_write < MIN_WRITE_INTERVAL or len(writes) >= MAX_WRITES_PER_DAY:
            return
        await self.hass.services.async_call(
            "climate", "set_temperature",
            {"entity_id": self.o.cfg[CONF_CLIMATE], "temperature": setpoint}, blocking=True,
        )
        self._last_write = now
        self.o.data["writes"] = writes + [now]
        _LOGGER.info("Pilotage : consigne %s → %s °C", current, setpoint)

    # ----------------------------------------------------------- panneau

    def snapshot(self) -> dict:
        return {
            "mode": self.mode,
            "schedule": self.schedule,
            "temps": self.temps,
            "standby_temp": float(self.o.cfg[CONF_STANDBY_TEMP]),
            "demand_delay": float(self.o.cfg[CONF_DEMAND_DELAY]),
            "state": self.o.data["control_state"],
            "decision_log": self.o.data["decision_log"],
            "preheat_rate": self.o.data["preheat_rate"],
            "standby_hours_7d": round(self.standby_hours(time.time() - 7 * 86400), 1),
            "trv_suggestion": self.trv_schedule_suggestion(),
            "forecast": self._forecast,
            "originals": self.o.data["control_originals"],
            "room_targets": self.room_targets(),
        }
