"""Consommation électrique Linky via Conso API (conso.boris.sh), importée dans les statistiques de HA.

L'API d'Enedis est réservée aux entreprises ; Conso API la relaie pour les particuliers qui ont donné leur
accord sur conso.boris.sh. Le jeton (JWT) contient le ou les numéros de compteur (PRM) autorisés.
La consommation journalière est importée comme statistique externe, utilisable dans le tableau Énergie.
La courbe de charge (puissance moyenne par demi-heure, si elle est activée dans l'espace Enedis) est importée
en puissance moyenne horaire : elle mesure le talon de consommation (la nuit) au lieu de l'estimer.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import date, datetime, timedelta

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

API_URL = "https://conso.boris.sh/api/consommation_quotidienne"
CURVE_URL = "https://conso.boris.sh/api/courbe_de_charge_consommation"
USER_AGENT = "heating-curve-optimizer (github.com/Sigfrodr/ha-heating-curve-optimizer)"
HISTORY_DAYS = 3 * 365  # Enedis garde 3 ans de relevés journaliers
CHUNK_DAYS = 365  # période maximale par appel
CURVE_CHUNK_DAYS = 7  # courbe de charge : une semaine au plus par appel
CURVE_FIRST_DAYS = 28  # premier import : 4 appels, pour ménager le quota Enedis


class LinkyError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Conso API : erreur {status} {detail}".strip())
        self.status = status


def token_prms(token: str) -> list[str]:
    """Numéros de compteur (PRM) autorisés par le jeton, lus dans sa charge utile JWT (sans vérifier la signature)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        sub = json.loads(base64.urlsafe_b64decode(payload)).get("sub")
    except (IndexError, ValueError, AttributeError):
        return []
    if isinstance(sub, list):
        return [str(x) for x in sub if x]
    return [str(sub)] if sub else []


def parse_daily(data: dict) -> list[tuple[date, float]]:
    """Réponse Conso API → [(jour, kWh)] triés."""
    out: list[tuple[date, float]] = []
    for grandeur in data.get("grandeur") or []:
        factor = 0.001 if str(grandeur.get("unite") or "Wh").lower() == "wh" else 1.0
        for point in grandeur.get("points") or []:
            value = point.get("v")
            if value in (None, ""):
                continue
            out.append((date.fromisoformat(str(point["d"])[:10]), float(value) * factor))
    return sorted(out)


def parse_load_curve(data: dict) -> list[tuple[datetime, float]]:
    """Réponse Conso API (courbe de charge) → [(début de l'intervalle, puissance moyenne en W)] triés.

    Enedis horodate chaque point à la *fin* de son intervalle (30 min par défaut).
    """
    out: list[tuple[datetime, float]] = []
    tz = dt_util.get_default_time_zone()
    for grandeur in data.get("grandeur") or []:
        factor = 1000.0 if str(grandeur.get("unite") or "W").lower() == "kw" else 1.0
        for point in grandeur.get("points") or []:
            value = point.get("v")
            if value in (None, ""):
                continue
            end = datetime.fromisoformat(str(point["d"]).replace(" ", "T"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=tz)
            minutes = _minutes(point.get("p") or grandeur.get("p") or "PT30M")
            out.append((end - timedelta(minutes=minutes), float(value) * factor))
    return sorted(out)


def _minutes(period: str) -> int:
    """Durée ISO 8601 courte (PT30M, PT1H, PT10M) → minutes."""
    p = str(period).upper().removeprefix("PT")
    try:
        if p.endswith("H"):
            return int(p[:-1]) * 60
        return int(p.removesuffix("M"))
    except ValueError:
        return 30


def hourly_power(points: list[tuple[datetime, float]]) -> list[dict]:
    """Points de courbe de charge → statistiques horaires (moyenne, min, max en W), heures complètes seulement."""
    hours: dict[datetime, list[float]] = {}
    for start, watts in points:
        hour = dt_util.as_utc(start).replace(minute=0, second=0, microsecond=0)
        hours.setdefault(hour, []).append(watts)
    return [
        {"start": hour, "mean": sum(v) / len(v), "min": min(v), "max": max(v)}
        for hour, v in sorted(hours.items()) if len(v) >= 2
    ]


def chunks(start: date, end: date, days: int = CHUNK_DAYS) -> list[tuple[date, date]]:
    """Découpe [start, end[ en périodes acceptées par l'API."""
    out = []
    cur = start
    while cur < end:
        nxt = min(end, cur + timedelta(days=days))
        out.append((cur, nxt))
        cur = nxt
    return out


class LinkyImporter:
    """Importe la consommation journalière dans une statistique externe `<domaine>:linky_<prm>`."""

    def __init__(self, hass: HomeAssistant, domain: str, token: str) -> None:
        self.hass = hass
        self.domain = domain
        self.token = token.strip()
        prms = token_prms(self.token)
        self.prm = prms[0] if prms else None

    @property
    def statistic_id(self) -> str | None:
        return f"{self.domain}:linky_{self.prm}" if self.prm else None

    @property
    def cost_statistic_id(self) -> str | None:
        return f"{self.domain}:linky_{self.prm}_cout" if self.prm else None

    @property
    def power_statistic_id(self) -> str | None:
        return f"{self.domain}:linky_{self.prm}_puissance" if self.prm else None

    async def async_fetch(self, start: date, end: date) -> list[tuple[date, float]]:
        return parse_daily(await self._async_get(API_URL, start, end))

    async def _async_get(self, url: str, start: date, end: date) -> dict:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                url,
                params={"dateDebut": start.isoformat(), "dateFin": end.isoformat(), "pointId": self.prm},
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "User-Agent": USER_AGENT},
                timeout=ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    raise LinkyError(resp.status, (await resp.text())[:200])
                return await resp.json(content_type=None)
        except (ClientError, TimeoutError) as err:
            raise LinkyError(0, str(err)) from err

    async def async_update(self) -> dict:
        """Importe les jours manquants (tout l'historique disponible au premier passage)."""
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.models import StatisticMeanType  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            async_add_external_statistics,
            get_last_statistics,
        )

        if not self.prm:
            raise LinkyError(0, "jeton invalide (aucun compteur)")
        sid = self.statistic_id
        last = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, sid, True, {"sum"}
        )
        rows = last.get(sid) or []
        today = dt_util.now().date()
        if rows:
            begin = dt_util.as_local(dt_util.utc_from_timestamp(rows[0]["start"])).date() + timedelta(days=1)
            total = float(rows[0].get("sum") or 0)
        else:
            begin, total = today - timedelta(days=HISTORY_DAYS), 0.0
        if begin >= today:
            return {"prm": self.prm, "imported": 0, "last_day": (today - timedelta(days=1)).isoformat()}

        points: list[tuple[date, float]] = []
        for start, end in chunks(begin, today):
            try:
                points += await self.async_fetch(start, end)
            except LinkyError as err:
                # Historique initial : les périodes antérieures au compteur ou à l'accord sont refusées
                if err.status in (401, 403) or rows or end >= today:
                    raise
                _LOGGER.debug("Période %s → %s indisponible : %s", start, end, err)
        tz = dt_util.get_default_time_zone()
        stats = []
        for day, kwh in points:
            if day < begin:
                continue
            total += kwh
            stats.append({"start": datetime(day.year, day.month, day.day, tzinfo=tz), "state": total, "sum": total})
        if stats:
            async_add_external_statistics(self.hass, {
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
                "name": "Linky – consommation",
                "source": self.domain,
                "statistic_id": sid,
                "unit_class": "energy",
                "unit_of_measurement": "kWh",
            }, stats)
        return {
            "prm": self.prm,
            "imported": len(stats),
            "last_day": points[-1][0].isoformat() if points else ((begin - timedelta(days=1)).isoformat() if rows else None),
        }

    async def async_update_curve(self) -> dict:
        """Importe la courbe de charge manquante en puissance moyenne horaire (4 semaines au premier passage)."""
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.models import StatisticMeanType  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            async_add_external_statistics,
            get_last_statistics,
        )

        if not self.prm:
            raise LinkyError(0, "jeton invalide (aucun compteur)")
        sid = self.power_statistic_id
        last = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, sid, True, {"mean"}
        )
        rows = last.get(sid) or []
        today = dt_util.now().date()
        if rows:
            begin = dt_util.as_local(dt_util.utc_from_timestamp(rows[0]["start"])).date()
            after = dt_util.utc_from_timestamp(rows[0]["start"])
        else:
            begin, after = today - timedelta(days=CURVE_FIRST_DAYS), None
        if begin >= today:
            return {"imported": 0}
        points: list[tuple[datetime, float]] = []
        for start, end in chunks(begin, today, CURVE_CHUNK_DAYS):
            points += parse_load_curve(await self._async_get(CURVE_URL, start, end))
        stats = [h for h in hourly_power(points) if after is None or h["start"] > after]
        if stats:
            async_add_external_statistics(self.hass, {
                "has_sum": False,
                "mean_type": StatisticMeanType.ARITHMETIC,
                "name": "Linky – puissance moyenne",
                "source": self.domain,
                "statistic_id": sid,
                "unit_class": "power",
                "unit_of_measurement": "W",
            }, stats)
        return {"imported": len(stats), "last": stats[-1]["start"].isoformat() if stats else None}

    async def async_update_cost(self, price: float) -> int:
        """Coût de la consommation (kWh importés × prix du kWh des Réglages), pour le tableau Énergie de HA
        qui n'accepte pas de prix fixe sur une statistique externe. Les jours déjà chiffrés ne changent pas."""
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.models import StatisticMeanType  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
            async_add_external_statistics,
            get_last_statistics,
            statistics_during_period,
        )

        sid, cid = self.statistic_id, self.cost_statistic_id
        if not sid:
            return 0
        recorder = get_instance(self.hass)
        await recorder.async_block_till_done()  # consommation qui vient d'être importée
        last = (await recorder.async_add_executor_job(get_last_statistics, self.hass, 1, cid, True, {"sum"})).get(cid)
        after = dt_util.utc_from_timestamp(last[0]["start"]) if last else None
        total = float(last[0].get("sum") or 0) if last else 0.0
        start = after + timedelta(hours=1) if after else dt_util.utcnow() - timedelta(days=HISTORY_DAYS + 10)
        rows = (await recorder.async_add_executor_job(
            statistics_during_period, self.hass, start, None, {sid}, "hour", {"energy": "kWh"}, {"change"}
        )).get(sid, [])
        stats = []
        for row in rows:
            if row.get("change") is None:
                continue
            total += max(0.0, float(row["change"])) * price
            stats.append({"start": dt_util.utc_from_timestamp(row["start"]), "state": total, "sum": total})
        if stats:
            async_add_external_statistics(self.hass, {
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
                "name": "Linky – coût",
                "source": self.domain,
                "statistic_id": cid,
                "unit_class": None,
                "unit_of_measurement": "EUR",
            }, stats)
        return len(stats)
