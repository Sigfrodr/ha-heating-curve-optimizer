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

from custom_components.heating_curve_optimizer.linky import API_URL, LinkyImporter, chunks, parse_daily, token_prms
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

    # jour suivant : seule la période manquante est demandée, la somme continue
    aioclient_mock.clear_requests()
    result = await importer.async_update()
    assert result["imported"] == 0 and not aioclient_mock.mock_calls  # rien de nouveau avant demain


async def test_rejected_token_is_reported(hass: HomeAssistant, aioclient_mock):
    from custom_components.heating_curve_optimizer.linky import LinkyError

    aioclient_mock.get(API_URL, status=401, text="unauthorized")
    importer = LinkyImporter(hass, "heating_curve_optimizer", _token([PRM]))
    with pytest.raises(LinkyError) as err:
        await importer.async_update()
    assert err.value.status == 401
