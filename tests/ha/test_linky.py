"""Compteur Linky via Conso API : jeton, découpage des périodes, import dans les statistiques."""

import base64
import json
from datetime import date, timedelta

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_last_statistics
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.heating_curve_optimizer.linky import (
    API_URL, CURVE_URL, LinkyImporter, chunks, hourly_power, parse_daily, parse_load_curve, token_prms,
)
from custom_components.heating_curve_optimizer.settings_spec import validate

PRM = "12345678901234"


def _token(sub) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{enc({'alg': 'HS256'})}.{enc({'sub': sub})}.signature"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def fake_frontend(recorder_mock, hass):
    hass.config.components.update({"frontend", "panel_custom", "websocket_api"})
    hass.config.language = "fr"


def test_token_and_parsing():
    assert token_prms(_token([PRM])) == [PRM]
    assert token_prms(_token(PRM)) == [PRM]
    assert token_prms("pas-un-jeton") == []
    data = {"grandeur": [{"unite": "Wh", "points": [{"v": "8200", "d": "2026-10-02"}, {"v": "7500", "d": "2026-10-01"},
                                                     {"v": None, "d": "2026-10-03"}]}]}
    assert parse_daily(data) == [(date(2026, 10, 1), 7.5), (date(2026, 10, 2), 8.2)]
    parts = chunks(date(2024, 1, 1), date(2026, 1, 10))
    assert parts[0] == (date(2024, 1, 1), date(2024, 12, 31)) and parts[-1][1] == date(2026, 1, 10)
    assert all(b - a <= timedelta(days=365) for a, b in parts)
    with pytest.raises(ValueError):
        validate({"linky_token": "n'importe quoi"})
    assert validate({"linky_token": " " + _token([PRM]) + " "})["linky_token"] == _token([PRM])


async def test_import_history_then_daily(hass: HomeAssistant, aioclient_mock):
    today = dt_util.now().date()
    days = [today - timedelta(days=i) for i in (3, 2, 1)]

    def answer(start, end):
        pts = [{"v": str(1000 * (i + 1)), "d": d.isoformat()} for i, d in enumerate(days) if start <= d < end]
        return {"grandeur": [{"unite": "Wh", "points": pts}]}

    # historique : seules les deux dernières années existent (périodes plus anciennes refusées)
    for a, b in chunks(today - timedelta(days=3 * 365), today):
        if b < today - timedelta(days=400):
            aioclient_mock.get(API_URL, params={"dateDebut": a.isoformat(), "dateFin": b.isoformat(), "pointId": PRM},
                               status=400, text='{"error":"ADAM-ERR0123"}')
        else:
            aioclient_mock.get(API_URL, params={"dateDebut": a.isoformat(), "dateFin": b.isoformat(), "pointId": PRM},
                               json=answer(a, b))
    importer = LinkyImporter(hass, "heating_curve_optimizer", _token([PRM]))
    result = await importer.async_update()
    assert result["imported"] == 3 and result["last_day"] == days[-1].isoformat()
    await async_wait_recording_done(hass)
    sid = importer.statistic_id
    last = await get_instance(hass).async_add_executor_job(get_last_statistics, hass, 1, sid, True, {"sum"})
    assert abs(last[sid][0]["sum"] - 6.0) < 1e-9  # 1 + 2 + 3 kWh
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {_token([PRM])}"

    # coût pour le tableau Énergie : kWh × prix, sans rechiffrer les jours déjà comptés
    assert await importer.async_update_cost(0.2) == 3
    await async_wait_recording_done(hass)
    cid = importer.cost_statistic_id
    cost = await get_instance(hass).async_add_executor_job(get_last_statistics, hass, 1, cid, True, {"sum"})
    assert abs(cost[cid][0]["sum"] - 1.2) < 1e-9
    assert await importer.async_update_cost(0.3) == 0

    # jour suivant : seule la période manquante est demandée, la somme continue
    aioclient_mock.clear_requests()
    result = await importer.async_update()
    assert result["imported"] == 0 and not aioclient_mock.mock_calls  # rien de nouveau avant demain


async def test_yesterday_not_published_yet(hass: HomeAssistant, aioclient_mock):
    """Juste après minuit, la veille n'est pas encore publiée : Enedis répond 404, ce n'est pas une erreur."""
    today = dt_util.now().date()
    two_days = today - timedelta(days=2)
    for a, b in chunks(today - timedelta(days=3 * 365), today):
        pts = [{"v": "5000", "d": two_days.isoformat()}] if a <= two_days < b else []
        aioclient_mock.get(API_URL, params={"dateDebut": a.isoformat(), "dateFin": b.isoformat(), "pointId": PRM},
                           json={"grandeur": [{"unite": "Wh", "points": pts}]})
    importer = LinkyImporter(hass, "heating_curve_optimizer", _token([PRM]))
    await importer.async_update()
    await async_wait_recording_done(hass)

    aioclient_mock.clear_requests()
    yesterday = today - timedelta(days=1)
    aioclient_mock.get(API_URL, params={"dateDebut": yesterday.isoformat(), "dateFin": today.isoformat(), "pointId": PRM},
                       status=404, text='{"status":404,"error":{"error_description":"La sous-ressource demandée n existe pas."}}')
    result = await importer.async_update()
    assert result["imported"] == 0 and result["last_day"] == two_days.isoformat()
    assert len(aioclient_mock.mock_calls) == 1


async def test_rejected_token_is_reported(hass: HomeAssistant, aioclient_mock):
    from custom_components.heating_curve_optimizer.linky import LinkyError

    aioclient_mock.get(API_URL, status=401, text="unauthorized")
    importer = LinkyImporter(hass, "heating_curve_optimizer", _token([PRM]))
    with pytest.raises(LinkyError) as err:
        await importer.async_update()
    assert err.value.status == 401


async def test_retry_only_when_needed(hass: HomeAssistant):
    from unittest.mock import AsyncMock, MagicMock

    from custom_components.heating_curve_optimizer.optimizer import HeatingCurveOptimizer

    fake = MagicMock()
    fake.data = {"linky": {"status": "ok", "last_day": (dt_util.now().date() - timedelta(days=1)).isoformat()}}
    fake._async_linky_update = AsyncMock()
    await HeatingCurveOptimizer._async_linky_retry(fake)
    fake._async_linky_update.assert_not_awaited()  # à jour : pas d'appel
    fake.data["linky"] = {"status": "Conso API : erreur 429", "last_day": "2026-10-18"}
    await HeatingCurveOptimizer._async_linky_retry(fake)
    fake._async_linky_update.assert_awaited_once()


def test_load_curve_parsing():
    data = {"grandeur": [{"unite": "W", "points": [
        {"v": "300", "d": "2026-10-20T00:30:00+02:00", "p": "PT30M"},
        {"v": "500", "d": "2026-10-20T01:00:00+02:00", "p": "PT30M"},
        {"v": "400", "d": "2026-10-20 01:30:00"},  # sans fuseau ni durée : heure locale, 30 min
        {"v": None, "d": "2026-10-20T02:00:00+02:00"},
    ]}]}
    points = parse_load_curve(data)
    assert [w for _, w in points] == [300.0, 500.0, 400.0]
    assert points[0][0].hour == 0 and points[0][0].minute == 0  # horodaté à la fin : début = 00:00
    hours = hourly_power(points)
    assert len(hours) == 1  # 01:00–02:00 n'a qu'un point : incomplète, ignorée
    assert hours[0]["mean"] == 400.0 and hours[0]["min"] == 300.0 and hours[0]["max"] == 500.0


async def test_import_load_curve(hass: HomeAssistant, aioclient_mock):
    await hass.config.async_set_time_zone("Europe/Paris")
    today = dt_util.now().date()
    tz = dt_util.get_default_time_zone()
    from datetime import datetime

    def answer(start, end):
        pts = []
        day = start
        while day < end:
            for half in range(1, 49):
                stamp = datetime(day.year, day.month, day.day, tzinfo=tz) + timedelta(minutes=30 * half)
                pts.append({"v": "250" if (stamp - timedelta(minutes=30)).hour < 6 else "900", "d": stamp.isoformat(), "p": "PT30M"})
            day += timedelta(days=1)
        return {"grandeur": [{"unite": "W", "points": pts}]}

    for a, b in chunks(today - timedelta(days=28), today, 7):
        aioclient_mock.get(CURVE_URL, params={"dateDebut": a.isoformat(), "dateFin": b.isoformat(), "pointId": PRM},
                           json=answer(a, b))
    importer = LinkyImporter(hass, "heating_curve_optimizer", _token([PRM]))
    result = await importer.async_update_curve()
    assert len(aioclient_mock.mock_calls) == 4 and result["imported"] > 600
    await async_wait_recording_done(hass)
    sid = importer.power_statistic_id
    last = await get_instance(hass).async_add_executor_job(get_last_statistics, hass, 1, sid, True, {"mean"})
    assert last[sid][0]["mean"] in (250.0, 900.0)
