"""Consommation électrique Linky via Conso API (conso.boris.sh), importée dans les statistiques de HA.

L'API d'Enedis est réservée aux entreprises ; Conso API la relaie pour les particuliers qui ont donné leur
accord sur conso.boris.sh. Le jeton (JWT) contient le ou les numéros de compteur (PRM) autorisés.
La consommation journalière est importée comme statistique externe, utilisable dans le tableau Énergie.
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
USER_AGENT = "heating-curve-optimizer (github.com/Sigfrodr/ha-heating-curve-optimizer)"
HISTORY_DAYS = 3 * 365  # Enedis garde 3 ans de relevés journaliers
CHUNK_DAYS = 365  # période maximale par appel


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

    async def async_fetch(self, start: date, end: date) -> list[tuple[date, float]]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                API_URL,
                params={"dateDebut": start.isoformat(), "dateFin": end.isoformat(), "pointId": self.prm},
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "User-Agent": USER_AGENT},
                timeout=ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    raise LinkyError(resp.status, (await resp.text())[:200])
                return parse_daily(await resp.json(content_type=None))
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
