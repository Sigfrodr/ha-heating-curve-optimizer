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
from .heating_curve import Proposal, Sample, Settings, compute_proposal

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SHIFT_RETRY_SECONDS = 300
SHIFT_MAX_ATTEMPTS = 6


def _sample_error(sample: dict) -> float:
    """Écart retenu : pièce limitante en multi-pièces, sinon sonde de la chaudière."""
    if "eff" in sample:
        return sample["eff"]
    return sample["room"] - sample["target"]


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
        }
        self._unavailable_since: float | None = None
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

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self.data)

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 30)

    # -------------------------------------------------------------- entités

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
            await self._async_notify("Courbe de chauffe : proposition", summary)
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
            "advice": recovery_advice(recoveries),
        }

    def snapshot(self) -> dict:
        """Données pour le panneau."""
        return {
            "entry_id": self.entry.entry_id,
            "status": self.status,
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
            "alerts": self.data["alerts"],
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
            "last_proposal": self.data["last_proposal"],
            "history": self.data["history"],
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

    async def _async_notify(self, title: str, message: str, suffix: str = "") -> None:
        notification_id = f"{DOMAIN}_{self.entry.entry_id}" + (f"_{suffix}" if suffix else "")
        persistent_notification.async_create(
            self.hass, message, title=title, notification_id=notification_id
        )
        if service := self.cfg.get(CONF_NOTIFY):
            await self.hass.services.async_call(
                "notify", service.removeprefix("notify."), {"title": title, "message": message}
            )
