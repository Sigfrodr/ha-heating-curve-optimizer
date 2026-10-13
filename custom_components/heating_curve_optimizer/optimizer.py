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
    TUNING_KEYS,
)
from .heating_curve import Proposal, Sample, Settings, compute_proposal

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SHIFT_RETRY_SECONDS = 300
SHIFT_MAX_ATTEMPTS = 6


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
        }
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
        errors = [s["room"] - s["target"] for s in self.data["samples"]]
        return round(sum(errors) / len(errors), 2) if errors else None

    # -------------------------------------------------------------- collecte

    async def _async_sample(self, _now=None) -> None:
        state = self.hass.states.get(self.cfg[CONF_CLIMATE])
        if state is None:
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

        if state.state == "off":
            status = "chauffage arrêté"
        elif program.lower() not in programs:
            status = f"programme {program} non surveillé"
        elif None in (target, room, outside):
            status = "mesure manquante"
        elif outside >= float(self.cfg[CONF_HEATING_LIMIT]):
            status = f"T° ext. ≥ {float(self.cfg[CONF_HEATING_LIMIT]):g} °C"
        elif now - self._regime_since < settle:
            status = "stabilisation (programme/consigne)"
        elif now - self.data["last_change"] < settle:
            status = "stabilisation (après ajustement)"
        else:
            cutoff = now - float(self.cfg[CONF_MAX_AGE_DAYS]) * 86400
            self.data["samples"] = [s for s in self.data["samples"] if s["t"] >= cutoff] + [
                {"t": now, "outside": outside, "room": room, "target": target}
            ]
            self._save()
            status = "collecte"
        self._set_status(status)

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
            Sample(outside=s["outside"], room=s["room"], target=s["target"])
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
            },
            "program_targets": {
                base: self._device_entity("number", f"{base}_temperature")
                for base in ("comfort", "normal", "reduced")
            },
            "own": {
                key: er.async_get(self.hass).async_get_entity_id(
                    domain, DOMAIN, f"{self.entry.entry_id}_{key}"
                )
                for domain, key in (("sensor", "status"), ("switch", "auto"), ("button", "evaluate"))
            },
            "settings": {
                "min_samples": int(self.cfg[CONF_MIN_SAMPLES]),
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

    async def _async_notify(self, title: str, message: str) -> None:
        persistent_notification.async_create(
            self.hass, message, title=title, notification_id=f"{DOMAIN}_{self.entry.entry_id}"
        )
        if service := self.cfg.get(CONF_NOTIFY):
            await self.hass.services.async_call(
                "notify", service.removeprefix("notify."), {"title": title, "message": message}
            )
