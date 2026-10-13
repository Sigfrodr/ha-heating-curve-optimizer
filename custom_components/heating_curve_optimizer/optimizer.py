"""Collecte des mesures, évaluation et application de la courbe de chauffe."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLIMATE,
    CONF_EVALUATE_AT,
    CONF_HEATING_LIMIT,
    CONF_MAX_AGE_DAYS,
    CONF_LEGIONELLA_MINUTES,
    CONF_LEGIONELLA_TEMP,
    CONF_LEGIONELLA_TIME,
    CONF_LEGIONELLA_WEEKDAY,
    CONF_MIN_PRESSURE,
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
    DEFAULT_OPTIONS,
    CONF_GAS_PRICE,
    CONF_KWH_PER_M3,
    CONF_REPORT_TIME,
    CONF_REPORT_WEEKDAY,
    CONF_WEEKLY_REPORT,
    CONF_DAILY_CHECK_TIME,
    CONF_MAINTENANCE_MONTHS,
    CONF_OVERCONSUMPTION_RATIO,
    NOTIFY_ACTION_APPLY,
    NOTIFY_ACTION_IGNORE,
    DOMAIN,
    TUNING_KEYS,
)
from .analysis import (
    AlertInputs,
    BurnerStats,
    RoomReading,
    burner_stats,
    effective_error,
    evaluate_alerts,
    find_recoveries,
    recovery_advice,
)
from .control import balance_rooms, gas_cost, thermal_balance, weekly_report
from .heating_curve import Proposal, Sample, Settings, bin_samples, compute_proposal
from .messages import translate
from .settings_spec import EMPTY, FIELDS, SECTIONS, validate
from .insights import (
    bill_forecast,
    expected_gas_kwh,
    heating_limit,
    maintenance_status,
    overconsumption,
    physical_curve,
    pressure_trend,
    slow_leak,
)
from .pilot import HeatingPilot

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SHIFT_RETRY_SECONDS = 300
SHIFT_MAX_ATTEMPTS = 6


def _sample_error(sample: dict) -> float:
    """Écart retenu : pièce limitante en multi-pièces, sinon sonde de la chaudière."""
    if "eff" in sample:
        return sample["eff"]
    return sample["room"] - sample["target"]


def _ts(value) -> float:
    """Horodatage (s) d'une ligne de statistiques, quel que soit son format."""
    return value if isinstance(value, (int, float)) else value.timestamp()


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class HeatingCurveOptimizer:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.cfg = {**DEFAULT_OPTIONS, **entry.data, **entry.options}
        self.settings = Settings(**{k: float(self.cfg[k]) for k in TUNING_KEYS})
        self.status = "démarrage"
        self.data: dict = {
            "samples": [],
            "last_change": 0,
            "history": [],
            "last_proposal": None,
            "auto": False,
            "burner": [],
            "alerts": {},
            "legionella": False,
            "legionella_restore": None,
            "legionella_last": None,
            "daily_alerts": {},
            "pressure_days": {},
            "maintenance": None,
            "overconsumption_log": [],
        }
        self._unavailable_since: float | None = None
        self.pilot = HeatingPilot(self)
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._regime = None
        self._regime_since = time.time()
        self._pending = None
        self._unsubs: list[Callable[[], None]] = []
        self._listeners: list[Callable[[], None]] = []

    # ---------------------------------------------------------- cycle de vie

    async def async_start(self) -> None:
        if stored := await self._store.async_load():
            self.data.update(stored)
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_sample, timedelta(minutes=int(self.cfg[CONF_SAMPLE_MINUTES]))
            )
        )
        hour, minute, second = (int(x) for x in str(self.cfg[CONF_EVALUATE_AT]).split(":"))
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_scheduled_evaluate, hour=hour, minute=minute, second=second
            )
        )
        self._unsubs.append(async_call_later(self.hass, 120, self._async_sample))
        hour, minute, second = (int(x) for x in str(self.cfg[CONF_LEGIONELLA_TIME]).split(":"))
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_legionella_tick, hour=hour, minute=minute, second=second
            )
        )
        # Montée anti-légionelle interrompue par un redémarrage : remettre la consigne
        self._schedule_legionella_restore()
        hour, minute, second = (int(x) for x in str(self.cfg[CONF_REPORT_TIME]).split(":"))
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_report_tick, hour=hour, minute=minute, second=second
            )
        )
        hour, minute, second = (int(x) for x in str(self.cfg[CONF_DAILY_CHECK_TIME]).split(":"))
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_daily_checks, hour=hour, minute=minute, second=second
            )
        )
        self._unsubs.append(
            self.hass.bus.async_listen("mobile_app_notification_action", self._async_on_notify_action)
        )
        await self.pilot.async_start()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self.data)

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 30)

    # -------------------------------------------------------------- entités

    def tr(self, text: str) -> str:
        """Message traduit dans la langue de Home Assistant."""
        return translate(text, self.hass.config.language)

    @property
    def auto(self) -> bool:
        return bool(self.data["auto"])

    async def async_set_auto(self, value: bool) -> None:
        self.data["auto"] = value
        self._save()
        self._set_status(self.status)

    @callback
    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _set_status(self, status: str) -> None:
        self.status = status
        for listener in list(self._listeners):
            listener()

    @property
    def mean_error(self) -> float | None:
        errors = [_sample_error(s) for s in self.data["samples"]]
        return round(sum(errors) / len(errors), 2) if errors else None

    # -------------------------------------------------------------- collecte

    async def _async_sample(self, _now=None) -> None:
        state = self.hass.states.get(self.cfg[CONF_CLIMATE])
        await self._async_monitor(state)
        if state is None or state.state == "unavailable":
            self._set_status("climate indisponible")
            return
        attrs = state.attributes
        program = str(attrs.get("active_vicare_program", ""))
        target = _float(attrs.get("temperature"))
        if target is None:
            target = self._program_temperature(program)
        if room_entity := self.cfg.get(CONF_ROOM):
            room_state = self.hass.states.get(room_entity)
            room = _float(room_state.state) if room_state else None
        else:
            room = _float(attrs.get("room_temperature"))
        outside_state = self.hass.states.get(self.cfg[CONF_OUTSIDE])
        outside = _float(outside_state.state) if outside_state else None

        now = time.time()
        regime = (state.state, program, target)
        if regime != self._regime:
            self._regime = regime
            self._regime_since = now
        settle = float(self.cfg[CONF_SETTLE_MINUTES]) * 60
        programs = {p.lower() for p in self.cfg[CONF_PROGRAMS]}
        multi = self._multi_room_error(room, target)

        if state.state == "off":
            status = "chauffage arrêté"
        elif program.lower() not in programs:
            status = f"programme {program} non surveillé"
        elif target is None or outside is None or (room is None and multi is None):
            status = "mesure manquante"
        elif outside >= float(self.cfg[CONF_HEATING_LIMIT]):
            status = f"T° ext. ≥ {float(self.cfg[CONF_HEATING_LIMIT]):g} °C"
        elif now - self._regime_since < settle:
            status = "stabilisation (programme/consigne)"
        elif now - self.data["last_change"] < settle:
            status = "stabilisation (après ajustement)"
        elif self.pilot.mode == "active" and (self.data.get("control_state") or {}).get("mode") != "confort":
            status = "pilotage hors confort (mesure ignorée)"
        elif self._solar_gain():
            status = "gains solaires (mesure ignorée)"
        else:
            cutoff = now - float(self.cfg[CONF_MAX_AGE_DAYS]) * 86400
            sample = {"t": now, "outside": outside, "room": room, "target": target}
            if multi is not None:
                sample["eff"], sample["lim"] = round(multi[0], 2), multi[1]
            self.data["samples"] = [s for s in self.data["samples"] if s["t"] >= cutoff] + [sample]
            self._save()
            status = "collecte"
        self._set_status(status)

    def _multi_room_error(self, room: float | None, target: float | None) -> tuple[float, str] | None:
        """Écart de la pièce limitante (mode multi-pièces), None si non configuré."""
        rooms = self.cfg.get(CONF_ROOMS) or []
        if not rooms:
            return None
        readings: list[RoomReading] = []
        if room is not None and target is not None:
            readings.append(RoomReading(self.cfg[CONF_CLIMATE], room - target, room < target))
        for entity_id in rooms:
            st = self.hass.states.get(entity_id)
            if st is None or st.state in ("off", "unavailable", "unknown"):
                continue
            a = st.attributes
            if a.get("window_open") or a.get("window_state") == "on":
                continue  # fenêtre ouverte : pièce non représentative
            cur, tgt = _float(a.get("current_temperature")), _float(a.get("temperature"))
            if cur is None or tgt is None:
                continue
            readings.append(RoomReading(entity_id, cur - tgt, a.get("hvac_action") == "heating"))
        return effective_error(readings)

    def _solar_gain(self) -> bool:
        """Soleil assez haut et ciel assez dégagé pour fausser la mesure."""
        if not self.cfg.get(CONF_SOLAR_FILTER) or not self.cfg.get(CONF_WEATHER):
            return False
        sun = self.hass.states.get("sun.sun")
        weather = self.hass.states.get(self.cfg[CONF_WEATHER])
        elevation = _float(sun.attributes.get("elevation")) if sun else None
        if elevation is None or elevation < float(self.cfg[CONF_SOLAR_MIN_ELEVATION]):
            return False
        cloud = _float(weather.attributes.get("cloud_coverage")) if weather else None
        return cloud is None or cloud < float(self.cfg[CONF_SOLAR_CLOUD_MAX])

    # ------------------------------------------------- surveillance chaudière

    async def _async_monitor(self, climate_state) -> None:
        now = time.time()
        # Relevés brûleur (un par heure, 3 jours) pour le suivi des cycles
        starts = self._entity_float(self._device_entity("sensor", "burner_starts"))
        hours = self._entity_float(self._device_entity("sensor", "burner_hours"))
        snaps = self.data["burner"]
        if starts is not None and hours is not None and (not snaps or now - snaps[-1]["t"] >= 3000):
            snaps.append({"t": now, "starts": starts, "hours": hours})
            self.data["burner"] = [s for s in snaps if s["t"] >= now - 3 * 86400]
            self._save()

        if climate_state is None or climate_state.state == "unavailable":
            self._unavailable_since = self._unavailable_since or now
        else:
            self._unavailable_since = None
        pressure = self._entity_float(self._device_entity("sensor", "supply_pressure"))
        if pressure is not None:
            day = dt_util.now().date().isoformat()
            days = self.data["pressure_days"]
            if day not in days or pressure < days[day]:
                days[day] = pressure
                # 60 jours glissants
                self.data["pressure_days"] = dict(sorted(days.items())[-60:])
        frost = self.hass.states.get(self._device_entity("binary_sensor", "frost_protection") or "")
        alerts = evaluate_alerts(
            AlertInputs(
                pressure=self._entity_float(self._device_entity("sensor", "supply_pressure")),
                min_pressure=float(self.cfg[CONF_MIN_PRESSURE]),
                climate_unavailable_minutes=(now - self._unavailable_since) / 60
                if self._unavailable_since else 0,
                frost_protection=bool(frost and frost.state == "on"),
                burner=self.burner,
                short_cycle_minutes=float(self.cfg[CONF_SHORT_CYCLE_MINUTES]),
            )
        )
        alerts.update(self.data["daily_alerts"])
        if self.writes_24h >= self.write_budget:
            alerts["write_budget"] = (
                f"Budget d'écritures ViCare atteint ({self.writes_24h}/{self.write_budget} sur 24 h) : "
                "plus de changement de consigne avant demain, pour ne pas dépasser le quota Viessmann."
            )
        previous = self.data["alerts"]
        for code, message in alerts.items():
            if code not in previous:
                await self._async_notify("Chaudière : alerte", message, f"alert_{code}")
        for code in previous:
            if code not in alerts:
                persistent_notification.async_dismiss(
                    self.hass, f"{DOMAIN}_{self.entry.entry_id}_alert_{code}"
                )
        if alerts != previous:
            self.data["alerts"] = alerts
            self._save()

    @property
    def burner(self) -> BurnerStats | None:
        return burner_stats(self.data["burner"], time.time())

    def _entity_float(self, entity_id: str | None) -> float | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        return _float(state.state) if state else None

    # ---------------------------------------------------- anti-légionelle ECS

    @property
    def legionella(self) -> bool:
        return bool(self.data["legionella"])

    async def async_set_legionella(self, value: bool) -> None:
        self.data["legionella"] = value
        self._save()
        self._set_status(self.status)

    async def _async_legionella_tick(self, now) -> None:
        if not self.legionella or now.weekday() != int(self.cfg[CONF_LEGIONELLA_WEEKDAY]):
            return
        if self.data["legionella_restore"]:
            return  # déjà en cours
        dhw = self._device_entity("number", "dhw_temperature")
        previous = self._entity_float(dhw)
        temp = float(self.cfg[CONF_LEGIONELLA_TEMP])
        if dhw is None or previous is None or previous >= temp:
            return
        end = time.time() + float(self.cfg[CONF_LEGIONELLA_MINUTES]) * 60
        self.data["legionella_restore"] = {"end": end, "value": previous}
        self._save()
        await self._async_set_number(dhw, temp)
        _LOGGER.info("Anti-légionelle : ECS %s → %s °C", previous, temp)
        self._schedule_legionella_restore()

    def _schedule_legionella_restore(self) -> None:
        restore = self.data["legionella_restore"]
        if not restore:
            return
        self._unsubs.append(
            async_call_later(
                self.hass, max(1, restore["end"] - time.time()), self._async_legionella_restore
            )
        )

    async def _async_legionella_restore(self, _now=None) -> None:
        restore = self.data["legionella_restore"]
        dhw = self._device_entity("number", "dhw_temperature")
        if not restore or dhw is None:
            return
        await self._async_set_number(dhw, restore["value"])
        _LOGGER.info("Anti-légionelle terminée : ECS → %s °C", restore["value"])
        self.data["legionella_restore"] = None
        self.data["legionella_last"] = time.time()
        self._save()
        self._set_status(self.status)

    def _program_temperature(self, program: str) -> float | None:
        """Consigne du programme actif lue sur les entités number ViCare.

        ViCare ne renvoie pas toujours la consigne courante dans le climate ;
        « comfortEnergySaving » utilise la consigne du programme « comfort », etc.
        """
        registry = er.async_get(self.hass)
        climate = registry.async_get(self.cfg[CONF_CLIMATE])
        if climate is None or not program:
            return None
        base = program.removesuffix("EnergySaving").lower()
        for entry in er.async_entries_for_device(registry, climate.device_id):
            if entry.domain == "number" and entry.translation_key == f"{base}_temperature":
                state = self.hass.states.get(entry.entity_id)
                return _float(state.state) if state else None
        return None

    # ------------------------------------------------------------ évaluation

    async def _async_scheduled_evaluate(self, _now=None) -> None:
        await self.async_evaluate()

    async def async_evaluate(self) -> None:
        samples = [
            Sample(outside=s["outside"], room=s["target"] + _sample_error(s), target=s["target"])
            for s in self.data["samples"]
        ]
        min_samples = int(self.cfg[CONF_MIN_SAMPLES])
        if len(samples) < min_samples:
            _LOGGER.info("Évaluation reportée : %s/%s échantillons", len(samples), min_samples)
            self._set_status(f"en attente de données ({len(samples)}/{min_samples})")
            return

        slope_state = self.hass.states.get(self.cfg[CONF_SLOPE])
        shift_state = self.hass.states.get(self.cfg[CONF_SHIFT])
        slope = _float(slope_state.state) if slope_state else None
        shift = _float(shift_state.state) if shift_state else None
        if slope is None or shift is None:
            self._set_status("pente/décalage indisponibles")
            return

        proposal = compute_proposal(samples, slope, shift, self.settings)
        self.data["last_proposal"] = {"t": time.time(), **proposal.as_dict()}
        self._save()
        summary = (
            f"Pente {slope} → {proposal.new_slope}, décalage {shift} → {proposal.new_shift} "
            f"(écart moyen {proposal.mean_error:+.2f} K, {len(samples)} échantillons). "
            f"{proposal.reason}."
        )
        _LOGGER.info(summary)

        if not proposal.changed:
            self._set_status("évalué, rien à changer")
        elif not self.auto:
            await self._async_notify(
                "Courbe de chauffe : proposition", summary,
                actions=[
                    {"action": NOTIFY_ACTION_APPLY, "title": "Appliquer"},
                    {"action": NOTIFY_ACTION_IGNORE, "title": "Ignorer"},
                ],
            )
            self._set_status("proposition (simulation)")
        else:
            await self._async_apply(proposal, summary)

    def _current_curve(self) -> tuple[float | None, float | None]:
        slope_state = self.hass.states.get(self.cfg[CONF_SLOPE])
        shift_state = self.hass.states.get(self.cfg[CONF_SHIFT])
        return (
            _float(slope_state.state) if slope_state else None,
            _float(shift_state.state) if shift_state else None,
        )

    async def async_set_curve(self, new_slope: float, new_shift: float, reason: str) -> None:
        """Applique une courbe choisie depuis le panneau (réglage manuel ou proposition)."""
        slope, shift = self._current_curve()
        if slope is None or shift is None:
            raise ValueError("pente/décalage indisponibles")
        proposal = Proposal(slope, shift, new_slope, new_shift, self.mean_error or 0.0, reason)
        if not proposal.changed:
            return
        summary = f"Pente {slope} → {new_slope}, décalage {shift} → {new_shift} ({reason})."
        await self._async_apply(proposal, summary)

    def _device_entity(self, domain: str, translation_key: str) -> str | None:
        registry = er.async_get(self.hass)
        climate = registry.async_get(self.cfg[CONF_CLIMATE])
        if climate is None or climate.device_id is None:
            return None
        for entry in er.async_entries_for_device(registry, climate.device_id):
            if entry.domain == domain and entry.translation_key == translation_key:
                return entry.entity_id
        return None

    async def async_recoveries(self, days: int = 7) -> dict:
        """Relances du matin après réduit, à partir de l'historique du climate."""
        from homeassistant.components.recorder import get_instance, history  # noqa: PLC0415
        from homeassistant.util import dt as dt_util  # noqa: PLC0415

        climate_id = self.cfg[CONF_CLIMATE]
        start = dt_util.utcnow() - timedelta(days=days)
        states = await get_instance(self.hass).async_add_executor_job(
            lambda: history.get_significant_states(
                self.hass,
                start,
                None,
                [climate_id],
                include_start_time_state=True,
                significant_changes_only=False,
                minimal_response=False,
                no_attributes=False,
            )
        )
        points = [
            (
                st.last_updated.timestamp(),
                str(st.attributes.get("active_vicare_program", "")),
                _float(st.attributes.get("room_temperature")),
            )
            for st in states.get(climate_id, [])
            if hasattr(st, "attributes")
        ]
        targets = {
            base: value
            for base in ("comfort", "normal")
            if (value := self._entity_float(self._device_entity("number", f"{base}_temperature")))
            is not None
        }
        recoveries = find_recoveries(points, targets)
        return {
            "days": days,
            "recoveries": [r.__dict__ for r in recoveries],
            "advice": self.tr(recovery_advice(recoveries)),
        }

    # ------------------------------------------------------- statistiques

    async def async_daily_stats(self, days: int) -> list[tuple[float, float | None, float | None]]:
        """[(début du jour, m³ de gaz chauffage, T ext moyenne)] depuis les statistiques long terme."""
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            statistics_during_period,
        )

        gas, factor = self.gas_source
        outside = self.cfg[CONF_OUTSIDE]
        start = dt_util.start_of_local_day() - timedelta(days=days)
        ids = {i for i in (gas, outside) if i}
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, start, None, ids, "day", None, {"change", "mean"}
        )
        gas_by_day = (
            {r["start"]: (r.get("change") * factor if r.get("change") is not None else None)
             for r in stats.get(gas, [])}
            if gas else {}
        )
        return [(r["start"], gas_by_day.get(r["start"]), r.get("mean")) for r in stats.get(outside, [])]

    @property
    def gas_source(self) -> tuple[str | None, float]:
        """(entité de gaz pour les statistiques, facteur vers des m³).

        Un compteur (Gazpar…) est prioritaire sur l'estimation ViCare ; s'il compte en kWh,
        on revient en m³ avec le coefficient de conversion de la facture.
        """
        meter = self.cfg.get("gas_meter")
        if meter:
            st = self.hass.states.get(meter)
            unit = (st.attributes.get("unit_of_measurement") or "") if st else ""
            return meter, (1 / float(self.cfg[CONF_KWH_PER_M3]) if "wh" in unit.lower() else 1.0)
        return self._device_entity("sensor", "gas_summary_consumption_heating_currentday"), 1.0

    async def async_gas_kwh_since(self, start_day) -> float:
        """kWh de gaz (chauffage + eau chaude, ou compteur) consommés depuis une date."""
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            statistics_during_period,
        )

        kwh_per_m3 = float(self.cfg[CONF_KWH_PER_M3])
        if self.cfg.get("gas_meter"):
            sources = [self.gas_source]
        else:
            sources = [
                (self._device_entity("sensor", "gas_summary_consumption_heating_currentday"), 1.0),
                (self._device_entity("sensor", "hotwater_gas_summary_consumption_heating_currentday"), 1.0),
            ]
        ids = {e for e, _ in sources if e}
        if not ids:
            return 0.0
        start = dt_util.as_utc(dt_util.start_of_local_day(start_day))
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, start, None, ids, "day", None, {"change"}
        )
        m3 = sum((r.get("change") or 0) * f for e, f in sources if e for r in stats.get(e, []))
        return m3 * kwh_per_m3

    async def async_bill_forecast(self) -> dict | None:
        from datetime import date as _date  # noqa: PLC0415

        cfg = self.cfg
        if not cfg.get("billing_start") or not float(cfg.get("reference_annual_kwh") or 0):
            return None
        start = _date.fromisoformat(cfg["billing_start"])
        today = dt_util.now().date()
        while _date(start.year + 1, start.month, min(start.day, 28)) <= today:  # période en cours
            start = _date(start.year + 1, start.month, min(start.day, 28))
        consumed = await self.async_gas_kwh_since(start)
        f = bill_forecast(
            start, today, consumed, float(cfg["reference_annual_kwh"]), float(cfg[CONF_GAS_PRICE]),
            float(cfg.get("fixed_annual_cost") or 0), float(cfg.get("monthly_payment") or 0),
            int(cfg.get("payments_count") or 11),
        )
        return {**{k: (v.isoformat() if hasattr(v, "isoformat") else round(v, 2)) for k, v in f.__dict__.items()},
                "period_start": start.isoformat()}

    # ------------------------------------------------------------ réglages (panneau)

    async def async_settings(self) -> dict:
        """Champs, libellés traduits, valeurs et listes de choix pour l'onglet Réglages."""
        from homeassistant.helpers.translation import async_get_translations  # noqa: PLC0415

        lang = self.hass.config.language
        tr_opts = await async_get_translations(self.hass, lang, "options", {DOMAIN})
        tr_sel = await async_get_translations(self.hass, lang, "selector", {DOMAIN})
        base = f"component.{DOMAIN}.options.step.init"

        def label(field):
            sec = field["section"]
            key = f"{base}.data.{field['key']}" if sec is None else f"{base}.sections.{sec}.data.{field['key']}"
            return tr_opts.get(key, field["key"])

        sections = [
            {"key": s, "name": tr_opts.get(f"{base}.sections.{s}.name", s),
             "description": tr_opts.get(f"{base}.sections.{s}.description", "")}
            for s in SECTIONS
        ]
        weekdays = [tr_sel.get(f"component.{DOMAIN}.selector.weekday.options.{i}", str(i)) for i in range(7)]
        states = self.hass.states
        climate = states.get(self.cfg[CONF_CLIMATE])
        own = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(self.hass), self.entry.entry_id)}

        def entity_choices(domain, pred=lambda st: True):
            return sorted(
                ({"value": st.entity_id, "label": st.attributes.get("friendly_name", st.entity_id)}
                 for st in states.async_all(domain) if st.entity_id not in own and pred(st)),
                key=lambda c: c["label"].lower(),
            )

        return {
            "title": tr_opts.get(f"{base}.title", ""),
            "sections": sections,
            "fields": [{**f, "label": label(f)} for f in FIELDS],
            "values": {f["key"]: self.cfg.get(f["key"], EMPTY.get(f["key"])) for f in FIELDS},
            "choices": {
                "weekday": [{"value": str(i), "label": d} for i, d in enumerate(weekdays)],
                "programs": sorted(set(climate.attributes.get("vicare_programs", [])) if climate else set()
                                   | set(self.cfg.get(CONF_PROGRAMS, []))),
                "climate": entity_choices("climate", lambda st: st.entity_id != self.cfg[CONF_CLIMATE]),
                "weather": entity_choices("weather"),
                "sensor": entity_choices(
                    "sensor",
                    lambda st: st.attributes.get("device_class") in ("gas", "energy")
                    and st.attributes.get("state_class") in ("total", "total_increasing"),
                ),
                "notify": sorted(s for s in self.hass.services.async_services().get("notify", {})
                                 if s.startswith("mobile_app_") or s in ("phones",)),
            },
        }

    async def async_save_settings(self, values: dict) -> None:
        options = {**self.entry.options, **validate(values)}
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_diagnostics(self) -> dict:
        """Bilan thermique par saison de chauffe et équilibrage des pièces."""
        rows = await self.async_daily_stats(400)
        kwh_per_m3 = float(self.cfg[CONF_KWH_PER_M3])
        seasons: dict[str, list[tuple[float, float]]] = {}
        for start, gas, outside in rows:
            if gas is None or outside is None:
                continue
            day = dt_util.as_local(dt_util.utc_from_timestamp(start)) if isinstance(start, (int, float)) else start
            year = day.year if day.month >= 9 else day.year - 1
            seasons.setdefault(f"{year}-{year + 1}", []).append((gas * kwh_per_m3, outside))
        balances = {}
        for season, days in sorted(seasons.items()):
            indoor = float(self.pilot.temps["comfort"])
            tb = thermal_balance(days, indoor=indoor)
            if tb:
                balances[season] = {
                    **tb.__dict__,
                    "heating_limit": heating_limit(tb.loss_w_per_k, tb.base_kwh_per_day, indoor),
                }
            else:
                balances[season] = {"days": len([d for d in days if d[0] > 0])}
        rooms = []
        for entity_id in self.cfg.get(CONF_ROOMS) or []:
            st = self.hass.states.get(entity_id)
            rooms.append((entity_id, _float(st.attributes.get("heating_power")) if st else None))
        return {
            "thermal": balances,
            "rooms": [{**r.__dict__, "advice": self.tr(r.advice)} for r in balance_rooms(rooms)],
            "kwh_per_m3": kwh_per_m3,
        }

    # ---------------------------------------------------- rapport hebdomadaire

    async def _async_report_tick(self, now) -> None:
        if self.cfg.get(CONF_WEEKLY_REPORT) and now.weekday() == int(self.cfg[CONF_REPORT_WEEKDAY]):
            await self.async_send_weekly_report()

    async def async_weekly_report_text(self) -> str:
        rows = await self.async_daily_stats(15)
        now = time.time()

        def week(lo: float, hi: float) -> tuple[float | None, float]:
            sel = [r for r in rows if lo <= _ts(r[0]) < hi]
            gas = [r[1] for r in sel if r[1] is not None]
            dju = sum(max(0.0, 18 - r[2]) for r in sel if r[2] is not None)
            return (sum(gas) if gas else None), dju

        gas, dju = week(now - 7 * 86400, now)
        gas_prev, dju_prev = week(now - 14 * 86400, now - 7 * 86400)
        cost = None
        if gas is not None:
            _, cost = gas_cost(gas, float(self.cfg[CONF_KWH_PER_M3]), float(self.cfg[CONF_GAS_PRICE]))
        ratio_prev = gas_prev / dju_prev if gas_prev and dju_prev >= 5 else None
        adjustments = sum(1 for h in self.data["history"] if h["t"] >= now - 7 * 86400)
        return self.tr(weekly_report(
            gas, cost, dju, ratio_prev, adjustments,
            self.pilot.standby_hours(now - 7 * 86400), list(self.data["alerts"].values()),
        ))

    async def async_send_weekly_report(self) -> str:
        text = await self.async_weekly_report_text()
        await self._async_notify("Chauffage : bilan de la semaine", text, "weekly")
        return text

    def snapshot(self) -> dict:
        """Données pour le panneau."""
        tr = self.tr
        pilot = self.pilot.snapshot()
        if pilot.get("state"):
            pilot["state"] = {**pilot["state"], "reason": tr(pilot["state"]["reason"])}
        return {
            "language": self.hass.config.language,
            "entry_id": self.entry.entry_id,
            "status": tr(self.status),
            "auto": self.auto,
            "entities": {
                "climate": self.cfg[CONF_CLIMATE],
                "outside": self.cfg[CONF_OUTSIDE],
                "slope": self.cfg[CONF_SLOPE],
                "shift": self.cfg[CONF_SHIFT],
                "room": self.cfg.get(CONF_ROOM),
                "supply": self._device_entity("sensor", "supply_temperature"),
                "burner": self._device_entity("binary_sensor", "burner"),
                "burner_starts": self._device_entity("sensor", "burner_starts"),
                "burner_hours": self._device_entity("sensor", "burner_hours"),
                "modulation": self._device_entity("sensor", "burner_modulation"),
                "pressure": self._device_entity("sensor", "supply_pressure"),
                "gas_heating_day": self._device_entity(
                    "sensor", "gas_summary_consumption_heating_currentday"
                ),
                "gas_dhw_day": self._device_entity(
                    "sensor", "hotwater_gas_summary_consumption_heating_currentday"
                ),
                "dhw_target": self._device_entity("number", "dhw_temperature"),
                "dhw_storage": self._device_entity("sensor", "dhw_storage_temperature"),
                "weather": self.cfg.get(CONF_WEATHER) or None,
            },
            "rooms": list(self.cfg.get(CONF_ROOMS) or []),
            "alerts": {k: tr(v) for k, v in self.data["alerts"].items()},
            "burner_24h": (
                {
                    "starts": b.starts,
                    "hours": b.hours,
                    "span_hours": round(b.span_hours, 1),
                    "cycle_minutes": b.cycle_minutes,
                }
                if (b := self.burner)
                else None
            ),
            "pilot": pilot,
            "computed_curve": self.computed_curve(),
            "writes": {"used": self.writes_24h, "budget": self.write_budget},
            "gas_source": {"entity": self.gas_source[0], "to_m3": self.gas_source[1],
                           "meter": bool(self.cfg.get("gas_meter"))},
            "pressure_trend": self.pressure_trend,
            "pressure_days": self.data["pressure_days"],
            "maintenance": {
                **{k: (v.isoformat() if hasattr(v, "isoformat") else v)
                   for k, v in self.maintenance.__dict__.items()},
                "months": int(self.cfg[CONF_MAINTENANCE_MONTHS]),
            },
            "overconsumption_log": self.data["overconsumption_log"],
            "costs": {
                "gas_price": float(self.cfg[CONF_GAS_PRICE]),
                "kwh_per_m3": float(self.cfg[CONF_KWH_PER_M3]),
            },
            "report": {
                "enabled": bool(self.cfg.get(CONF_WEEKLY_REPORT)),
                "weekday": int(self.cfg[CONF_REPORT_WEEKDAY]),
                "time": self.cfg[CONF_REPORT_TIME],
                "notify": self.cfg.get(CONF_NOTIFY) or "",
            },
            "legionella": {
                "enabled": self.legionella,
                "weekday": int(self.cfg[CONF_LEGIONELLA_WEEKDAY]),
                "time": self.cfg[CONF_LEGIONELLA_TIME],
                "temp": float(self.cfg[CONF_LEGIONELLA_TEMP]),
                "minutes": float(self.cfg[CONF_LEGIONELLA_MINUTES]),
                "running": self.data["legionella_restore"],
                "last": self.data["legionella_last"],
            },
            "program_targets": {
                base: self._device_entity("number", f"{base}_temperature")
                for base in ("comfort", "normal", "reduced")
            },
            "own": {
                key: er.async_get(self.hass).async_get_entity_id(
                    domain, DOMAIN, f"{self.entry.entry_id}_{key}"
                )
                for domain, key in (
                    ("select", "control_mode"),
                    ("sensor", "status"),
                    ("switch", "auto"),
                    ("button", "evaluate"),
                    ("switch", "legionella"),
                    ("binary_sensor", "alert"),
                )
            },
            "settings": {
                "min_samples": int(self.cfg[CONF_MIN_SAMPLES]),
                "min_pressure": float(self.cfg[CONF_MIN_PRESSURE]),
                "short_cycle_minutes": float(self.cfg[CONF_SHORT_CYCLE_MINUTES]),
                "solar_filter": bool(self.cfg.get(CONF_SOLAR_FILTER)),
                "heating_limit": float(self.cfg[CONF_HEATING_LIMIT]),
                "evaluate_at": self.cfg[CONF_EVALUATE_AT],
                "programs": list(self.cfg[CONF_PROGRAMS]),
                **{k: float(self.cfg[k]) for k in TUNING_KEYS},
            },
            "samples": self.data["samples"],
            "last_proposal": (
                {**self.data["last_proposal"], "reason": tr(self.data["last_proposal"]["reason"])}
                if self.data["last_proposal"] else None
            ),
            "history": [{**h, "reason": tr(h["reason"])} for h in self.data["history"]],
            "last_change": self.data["last_change"],
        }

    # ----------------------------------------------------------- application

    async def _async_apply(self, proposal, summary: str) -> None:
        now = time.time()
        self.data["samples"] = []  # les mesures décrivaient l'ancienne courbe
        self.data["last_change"] = now
        self.data["history"] = (self.data["history"] + [{"t": now, **proposal.as_dict()}])[-30:]
        self._save()
        self._pending = proposal
        await self._async_notify("Courbe de chauffe ajustée", summary)

        if proposal.new_slope != proposal.slope:
            await self._async_set_number(self.cfg[CONF_SLOPE], proposal.new_slope)
            if proposal.new_shift != proposal.shift:
                # ViCare écrit pente ET décalage à chaque appel en relisant l'autre
                # valeur dans son cache : attendre que la nouvelle pente soit relue,
                # sinon l'écriture du décalage remettrait l'ancienne pente.
                self._schedule_shift(1)
        elif proposal.new_shift != proposal.shift:
            await self._async_apply_shift(1)
        self._set_status("ajustement appliqué")

    def _schedule_shift(self, attempt: int) -> None:
        async def _run(_now) -> None:
            await self._async_apply_shift(attempt)

        self._unsubs.append(async_call_later(self.hass, SHIFT_RETRY_SECONDS, _run))

    async def _async_apply_shift(self, attempt: int) -> None:
        proposal = self._pending
        if proposal is None:
            return
        slope_state = self.hass.states.get(self.cfg[CONF_SLOPE])
        current = _float(slope_state.state) if slope_state else None
        if current is None or abs(current - proposal.new_slope) > 0.05:
            if attempt < SHIFT_MAX_ATTEMPTS:
                self._schedule_shift(attempt + 1)
            else:
                _LOGGER.warning("Pente non confirmée par ViCare, décalage non appliqué")
                await self._async_notify(
                    "Courbe de chauffe", "Pente non confirmée par ViCare, décalage non appliqué."
                )
            return
        await self._async_set_number(self.cfg[CONF_SHIFT], proposal.new_shift)
        self._pending = None

    async def _async_set_number(self, entity_id: str, value: float) -> None:
        await self.hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True
        )
        self.register_write()

    # ---------------------------------------------------- budget d'écritures ViCare

    @property
    def write_budget(self) -> int:
        return int(self.cfg.get("write_budget", 8))

    @property
    def writes_24h(self) -> int:
        now = time.time()
        return sum(1 for t in self.data.get("writes", []) if t >= now - 86400)

    def register_write(self) -> None:
        now = time.time()
        self.data["writes"] = [t for t in self.data.get("writes", []) if t >= now - 86400] + [now]
        self._save()

    async def _async_notify(
        self, title: str, message: str, suffix: str = "", actions: list[dict] | None = None
    ) -> None:
        notification_id = f"{DOMAIN}_{self.entry.entry_id}" + (f"_{suffix}" if suffix else "")
        title, message = self.tr(title), self.tr(message)
        actions = [{**a, "title": self.tr(a["title"])} for a in actions or []]
        persistent_notification.async_create(
            self.hass, message, title=title, notification_id=notification_id
        )
        if service := self.cfg.get(CONF_NOTIFY):
            payload = {"title": title, "message": message}
            if actions and service.removeprefix("notify.").startswith("mobile_app_"):
                payload["data"] = {"actions": actions, "tag": notification_id}
            await self.hass.services.async_call("notify", service.removeprefix("notify."), payload)

    async def _async_on_notify_action(self, event) -> None:
        """Bouton « Appliquer » / « Ignorer » d'une notification de l'appli mobile."""
        action = event.data.get("action")
        if action == NOTIFY_ACTION_APPLY:
            proposal = self.data["last_proposal"]
            if not proposal or proposal["t"] <= self.data["last_change"]:
                return
            await self.async_set_curve(
                proposal["new_slope"], proposal["new_shift"], "proposition validée depuis le téléphone"
            )
        elif action == NOTIFY_ACTION_IGNORE:
            persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{self.entry.entry_id}")

    # ------------------------------------------------------- contrôles quotidiens

    async def _async_daily_checks(self, _now=None) -> None:
        """Surconsommation de la veille, baisse lente de pression, échéance d'entretien."""
        alerts: dict[str, str] = {}
        try:
            alerts.update(await self._async_check_overconsumption())
        except Exception as err:  # noqa: BLE001  statistiques indisponibles
            _LOGGER.debug("Contrôle de consommation impossible : %s", err)
        trend = self.pressure_trend
        if slow_leak(trend):
            alerts["slow_leak"] = (
                f"La pression baisse lentement ({trend:+.2f} bar/semaine sur 4 semaines) : "
                "petite fuite ou vase d'expansion à vérifier."
            )
        m = self.maintenance
        if m.days_left is not None and m.days_left <= 30:
            alerts["maintenance"] = (
                f"Entretien annuel de la chaudière {'dépassé' if m.days_left < 0 else 'à prévoir'} "
                f"(échéance {m.due.strftime('%d/%m/%Y')})."
            )
        self.data["daily_alerts"] = alerts
        self._save()

    async def _async_check_overconsumption(self) -> dict[str, str]:
        diag = await self.async_diagnostics()
        model = next(
            (t for _, t in sorted(diag["thermal"].items(), reverse=True)
             if t.get("loss_w_per_k") and t.get("r2", 0) >= 0.5 and t.get("days", 0) >= 15),
            None,
        )
        rows = await self.async_daily_stats(2)
        if model is None or len(rows) < 2:
            return {}
        start, gas, outside = rows[-2]  # veille complète
        if gas is None or outside is None:
            return {}
        kwh_per_m3 = float(self.cfg[CONF_KWH_PER_M3])
        indoor = float(self.pilot.temps["comfort"])
        expected = expected_gas_kwh(model["loss_w_per_k"], model["base_kwh_per_day"], indoor, outside)
        excess = overconsumption(gas * kwh_per_m3, expected, float(self.cfg[CONF_OVERCONSUMPTION_RATIO]))
        if excess is None:
            return {}
        self.data["overconsumption_log"] = (self.data["overconsumption_log"] + [
            {"t": _ts(start), "kwh": round(gas * kwh_per_m3, 1), "expected": round(expected, 1)}
        ])[-30:]
        return {"overconsumption": (
            f"Consommation d'hier {excess:.0f} % au-dessus de la normale pour la météo "
            f"({gas * kwh_per_m3:.0f} kWh au lieu de {expected:.0f}) : fenêtre ouverte, réglage, encrassement ?"
        )}

    @property
    def pressure_trend(self) -> float | None:
        from datetime import date as _date  # noqa: PLC0415

        pts = [
            (_date.fromisoformat(d).toordinal() * 86400.0, p)
            for d, p in sorted(self.data["pressure_days"].items())[-28:]
        ]
        return pressure_trend(pts)

    @property
    def maintenance(self):
        from datetime import date as _date  # noqa: PLC0415

        m = self.data["maintenance"] or {}
        last = _date.fromisoformat(m["date"]) if m.get("date") else None
        hours_now = self._entity_float(self._device_entity("sensor", "burner_hours"))
        return maintenance_status(
            last, dt_util.now().date(), int(self.cfg[CONF_MAINTENANCE_MONTHS]), hours_now, m.get("hours")
        )

    async def async_set_maintenance(self, day: str | None = None) -> None:
        """Enregistre un entretien (aujourd'hui par défaut) avec le compteur d'heures brûleur."""
        self.data["maintenance"] = {
            "date": day or dt_util.now().date().isoformat(),
            "hours": self._entity_float(self._device_entity("sensor", "burner_hours")),
        }
        self.data["daily_alerts"].pop("maintenance", None)
        self._save()
        self._set_status(self.status)

    # ------------------------------------------------------- courbe calculée et seuil

    def computed_curve(self) -> dict | None:
        slope, shift = self._current_curve()
        samples = [
            Sample(outside=s["outside"], room=s["target"] + _sample_error(s), target=s["target"])
            for s in self.data["samples"]
        ]
        bins = bin_samples(samples, self.settings)
        if slope is None or shift is None or not bins:
            return None
        cc = physical_curve(bins, slope, shift)
        return cc.__dict__ if cc else None

    async def async_set_heating_limit(self, value: float) -> None:
        options = {**self.entry.options, CONF_HEATING_LIMIT: float(value)}
        self.hass.config_entries.async_update_entry(self.entry, options=options)
