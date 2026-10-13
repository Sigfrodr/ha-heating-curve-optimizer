import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "heating_curve_optimizer"))

from heating_curve import Bin, supply_temperature  # noqa: E402
from insights import (  # noqa: E402
    expected_gas_kwh,
    heating_limit,
    maintenance_status,
    overconsumption,
    physical_curve,
    pressure_trend,
    slow_leak,
)


def _bins_for_house(c: float, slope: float, shift: float, outsides, target=20.0):
    """Tranches mesurées pour une maison dont le besoin physique est T int + c × ΔT^(1/1,3)."""
    from heating_curve import room_gain

    bins = []
    for o in outsides:
        need = target + c * (target - o) ** (1 / 1.3)
        err = (supply_temperature(o, target, slope, shift) - need) / room_gain(o, target, slope)
        bins.append(Bin(outside=o, target=target, error=err, count=10))
    return bins


def test_physical_curve_recovers_house_from_narrow_range():
    # mesures seulement entre 6 et 12 °C, courbe actuelle très fausse (0,2 / +25)
    bins = _bins_for_house(4.0, 0.2, 25, [6, 8, 10, 12])
    cc = physical_curve(bins, 0.2, 25)
    assert abs(cc.coefficient - 4.0) < 1e-6
    # la courbe retenue suit le besoin physique à quelques K près, grands froids compris
    for o in (-10, 0, 10):
        need = 20 + 4.0 * (20 - o) ** (1 / 1.3)
        assert abs(supply_temperature(o, 20, cc.slope, cc.shift) - need) < 3.5
    assert cc.rms < 2.5


def test_physical_curve_no_data():
    assert physical_curve([], 1.0, 0) is None


def test_heating_limit_and_expected_gas():
    # 200 W/K, talon −20 kWh/j (apports gratuits) → chauffage nul à 19 − 20/5,05 ≈ 15 °C
    lim = heating_limit(200, -20, 19)
    assert 14.9 < lim < 15.2
    assert expected_gas_kwh(200, -20, 19, 20) == 0.0
    assert abs(expected_gas_kwh(200, -20, 19, 0) - (200 * 24 / 1000 / 0.95 * 19 - 20)) < 1e-9


def test_overconsumption():
    assert overconsumption(100, 60) == (100 / 60 - 1) * 100
    assert overconsumption(70, 60) is None  # sous le seuil de 30 %
    assert overconsumption(8, 4) is None  # écart absolu trop faible


def test_pressure_trend_and_leak():
    day = 86400
    falling = [(i * day, 1.5 - 0.01 * i) for i in range(28)]  # −0,07 bar/semaine
    t = pressure_trend(falling)
    assert abs(t + 0.07) < 1e-9 and slow_leak(t)
    stable = [(i * day, 1.4 + (0.02 if i % 2 else 0)) for i in range(28)]
    assert not slow_leak(pressure_trend(stable))
    assert pressure_trend(falling[:5]) is None


def test_maintenance_status():
    m = maintenance_status(date(2025, 11, 20), date(2026, 10, 13), 12, 9358, 8100)
    assert m.due == date(2026, 11, 20) and m.days_left == 38 and m.burner_hours_since == 1258
    assert maintenance_status(None, date(2026, 10, 13), 12, None, None).due is None


def test_write_budget_keeps_a_way_back():
    from insights import write_allowed

    assert write_allowed(8, 6, lowering=True)  # 2 restantes : on peut baisser puis revenir
    assert not write_allowed(8, 7, lowering=True)  # 1 seule : on ne baisse plus
    assert write_allowed(8, 7, lowering=False)  # mais on peut toujours remonter
    assert not write_allowed(8, 8, lowering=False)


def test_bill_forecast():
    from insights import MONTHLY_PROFILE, bill_forecast

    assert abs(sum(MONTHLY_PROFILE) - 1) < 1e-9
    # début de période : tout reste à consommer, la référence entière est prévue
    f = bill_forecast(date(2026, 4, 11), date(2026, 4, 11), 0, 9000, 0.1, 350, 116.71, 11)
    assert abs(f.remaining_kwh - 9000) < 20 and f.period_end == date(2027, 4, 11)
    assert abs(f.total_cost - (f.total_kwh * 0.1 + 350)) < 1e-9
    assert abs(f.balance - (f.total_cost - 116.71 * 11)) < 1e-9
    # en octobre, l'été est passé : il reste l'essentiel de l'hiver
    g = bill_forecast(date(2026, 4, 11), date(2026, 10, 14), 1200, 9000, 0.1, 350, 116.71, 11)
    assert 6500 < g.remaining_kwh < 7600 and g.total_kwh == 1200 + g.remaining_kwh
