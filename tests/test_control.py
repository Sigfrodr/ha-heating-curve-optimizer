import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "heating_curve_optimizer"))

from analysis import Recovery  # noqa: E402
from control import (  # noqa: E402
    ControlInputs,
    balance_rooms,
    comfort_periods_from_trv,
    decide_setpoint,
    forecast_factor,
    gas_cost,
    in_comfort,
    minutes_to_next_comfort,
    normalize_schedule,
    parse_trv_schedule,
    preheat_rate,
    schedule_from_trvs,
    sun_expected,
    thermal_balance,
    weekly_report,
)

TRV = "06:00/17 12:00/21 14:00/17 17:00/21 24:00/17"


def test_parse_and_comfort_periods_of_real_trv_schedule():
    pts = parse_trv_schedule(TRV)
    assert pts[0] == (360, 17.0)
    # 21 °C de 12 h à 14 h et de 17 h à minuit
    assert comfort_periods_from_trv(pts) == [(720, 840), (1020, 1440)]


def test_trv_schedule_wrapping_morning():
    # 22:00/17 en dernier point : la nuit jusqu'à 06:00 est à 17 ; 06:00/20 → confort
    pts = parse_trv_schedule("06:00/20 22:00/17")
    assert comfort_periods_from_trv(pts) == [(360, 1320)]
    # dernier point confort → la période avant le premier point est aussi confort
    pts = parse_trv_schedule("08:00/17 20:00/21")
    assert comfort_periods_from_trv(pts) == [(0, 480), (1200, 1440)]


def test_schedule_union_of_trvs():
    a = {d: TRV for d in range(7)}
    b = {d: "06:00/21 08:00/17" for d in range(5)}
    s = schedule_from_trvs([a, b])
    assert s[0] == [["06:00", "08:00"], ["12:00", "14:00"], ["17:00", "24:00"]]
    assert s[6] == [["12:00", "14:00"], ["17:00", "24:00"]]


def test_in_comfort_and_next_start():
    s = normalize_schedule({"0": [["06:00", "08:00"]], "1": [["06:00", "08:00"]]})
    assert in_comfort(s, 0, 7 * 60)
    assert not in_comfort(s, 0, 9 * 60)
    assert minutes_to_next_comfort(s, 0, 5 * 60) == 60
    assert minutes_to_next_comfort(s, 0, 23 * 60) == 7 * 60  # lendemain 06:00
    assert minutes_to_next_comfort(s, 3, 0) is None


def _inputs(**kw):
    base = dict(
        weekday=0, minute=10 * 60, schedule={0: [["06:00", "22:00"]]}, comfort_temp=19,
        reduced_temp=17, standby_temp=15, rooms_configured=True, any_demand=True,
        no_demand_minutes=0, demand_delay_minutes=20, room=19.5, preheat_rate=1.0,
    )
    base.update(kw)
    return ControlInputs(**base)


def test_decide_comfort_standby_reduced():
    assert decide_setpoint(_inputs()).mode == "confort"
    d = decide_setpoint(_inputs(any_demand=False, no_demand_minutes=30))
    assert (d.mode, d.setpoint) == ("veille", 15)
    # délai pas encore écoulé
    assert decide_setpoint(_inputs(any_demand=False, no_demand_minutes=5)).mode == "confort"
    # sans pièces configurées, jamais de veille
    assert decide_setpoint(_inputs(rooms_configured=False, any_demand=False, no_demand_minutes=99)).mode == "confort"
    assert decide_setpoint(_inputs(minute=23 * 60, room=18.8)).mode == "réduit"


def test_decide_optimal_start():
    # 05:00, 2 K à rattraper à 1 K/h → 120 min nécessaires, confort dans 60 min → relance
    d = decide_setpoint(_inputs(minute=5 * 60, room=17.0))
    assert d.mode == "relance" and d.setpoint == 19
    # maison déjà chaude → pas de relance anticipée
    assert decide_setpoint(_inputs(minute=5 * 60, room=18.9)).mode == "réduit"
    # froid annoncé : relance plus tôt
    assert decide_setpoint(_inputs(minute=4 * 60, room=17.5, forecast_factor=0.5)).mode == "relance"
    assert decide_setpoint(_inputs(minute=4 * 60, room=17.5, forecast_factor=1.0)).mode == "réduit"


def test_decide_sun():
    d = decide_setpoint(_inputs(sun_expected=True))
    assert (d.mode, d.setpoint) == ("soleil", 18)


def test_preheat_rate_median():
    recs = [Recovery(0, 17.0, 19.0, 60, 1.5), Recovery(0, 18.0, 19.0, 30, 1), Recovery(0, 17.0, 19.0, 120, 2),
            Recovery(0, 18.9, 19.0, 5, 0), Recovery(0, 17.0, 19.0, None, 2)]
    assert preheat_rate(recs) == 2.0
    assert preheat_rate([]) is None


def test_forecast_factor_and_sun():
    assert forecast_factor(19, 9, -1) == 0.5
    assert forecast_factor(19, 5, 5) == 1.0
    assert forecast_factor(19, None, 3) == 1.0
    assert sun_expected(30, [10, 20])
    assert not sun_expected(30, [80, 90])
    assert not sun_expected(5, [0])


def test_cost_and_thermal_balance():
    kwh, eur = gas_cost(10, 11.0, 0.10)
    assert abs(kwh - 110) < 1e-9 and abs(eur - 11) < 1e-9
    # maison à 200 W/K (rendement 0,95) : kWh/j = 200 × 24 / 1000 / 0,95 × ΔT + 3
    days = [((200 * 24 / 1000 / 0.95) * (19 - t) + 3, t) for t in range(-5, 15)]
    tb = thermal_balance(days)
    assert abs(tb.loss_w_per_k - 200) < 0.5 and abs(tb.base_kwh_per_day - 3) < 1e-6 and tb.r2 > 0.999
    assert thermal_balance(days[:5]) is None


def test_balance_rooms():
    res = {r.entity_id: r for r in balance_rooms([("a", 0.02), ("b", 0.01), ("c", 0.011), ("d", None)])}
    assert set(res) == {"a", "b", "c"}
    assert "refermer" in res["a"].advice
    assert res["b"].advice == "équilibrée"
    assert balance_rooms([("a", 0.02)]) == []


def test_weekly_report():
    txt = weekly_report(20.0, 22.5, 80, 0.3, 1, 12, [])
    assert "20.0 m³" in txt and "22.50 €" in txt and "0.250 m³ par degré-jour (-17 %" in txt
    assert "veille faute de demande : 12 h" in txt and "Alertes : aucune." in txt


def test_balance_rooms_internal_gains():
    rooms = [("parents", 0.010), ("eliana", 0.0067), ("cuisine", 0.0169)]
    res = {r.entity_id: r for r in balance_rooms(rooms, {"cuisine"})}
    # cuisine exclue de la médiane (moyenne des deux autres), conseil à confirmer
    assert abs(res["parents"].relative - 0.010 / 0.00835) < 1e-9
    assert res["cuisine"].internal_gains and "à confirmer" in res["cuisine"].advice
    assert "refermer" in {r.entity_id: r for r in balance_rooms(rooms)}["cuisine"].advice
