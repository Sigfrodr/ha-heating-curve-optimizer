import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "heating_curve_optimizer"))

from analysis import (  # noqa: E402
    AlertInputs,
    BurnerStats,
    RoomReading,
    burner_stats,
    effective_error,
    evaluate_alerts,
    find_recoveries,
    recovery_advice,
)


def test_effective_error_coldest_demanding_room_wins():
    rooms = [
        RoomReading("cuisine", +1.5, False),
        RoomReading("chambre", -0.8, True),
        RoomReading("salon", -0.2, True),
    ]
    assert effective_error(rooms) == (-0.8, "chambre")


def test_effective_error_nobody_demanding_gives_margin():
    rooms = [RoomReading("a", 0.6, False), RoomReading("b", 1.4, False)]
    assert effective_error(rooms) == (0.6, "a")


def test_effective_error_ignores_warm_room_that_is_closed():
    # Une pièce surchauffée vanne fermée ne doit pas faire baisser la courbe
    # tant qu'une autre pièce réclame.
    rooms = [RoomReading("a", 3.0, False), RoomReading("b", 0.1, True)]
    assert effective_error(rooms)[0] == 0.1


def test_effective_error_empty():
    assert effective_error([]) is None


def test_burner_stats_window():
    snaps = [{"t": i * 3600, "starts": 100 + 3 * i, "hours": 50 + 0.25 * i} for i in range(30)]
    b = burner_stats(snaps, now=29 * 3600, window_hours=24)
    assert b.starts == 72 and abs(b.hours - 6) < 1e-9
    assert abs(b.cycle_minutes - 5) < 1e-9


def test_burner_stats_needs_enough_history():
    snaps = [{"t": 0, "starts": 1, "hours": 1}, {"t": 3600, "starts": 2, "hours": 1}]
    assert burner_stats(snaps, now=3600) is None


def test_alerts():
    base = dict(pressure=1.2, min_pressure=1.0, climate_unavailable_minutes=0,
                frost_protection=False, burner=None, short_cycle_minutes=10)
    assert evaluate_alerts(AlertInputs(**base)) == {}
    low = evaluate_alerts(AlertInputs(**{**base, "pressure": 0.8}))
    assert set(low) == {"pressure"}
    cyc = evaluate_alerts(AlertInputs(**{**base, "burner": BurnerStats(40, 3, 24)}))
    assert set(cyc) == {"short_cycling"}
    ok = evaluate_alerts(AlertInputs(**{**base, "burner": BurnerStats(10, 8, 24)}))
    assert ok == {}


def _night(start_room=19.0, drop=1.5, recover_minutes=45, target=19.0):
    pts = []
    t = 0
    for i in range(8 * 6):  # réduit 8 h, une mesure / 10 min
        pts.append((t, "reducedEnergySaving", start_room - drop * i / 47))
        t += 600
    low = start_room - drop
    steps = max(1, recover_minutes // 10)
    for i in range(steps + 6):
        room = min(target, low + (target - low) * (i / steps))
        pts.append((t, "comfortEnergySaving", room))
        t += 600
    return pts


def test_find_recoveries():
    rec = find_recoveries(_night(recover_minutes=60), {"comfort": 19.0})
    assert len(rec) == 1
    assert 40 <= rec[0].minutes <= 60
    assert abs(rec[0].night_drop - 1.5) < 0.05


def test_recovery_advice():
    fast = find_recoveries(_night(drop=0.4, recover_minutes=10), {"comfort": 19.0})
    assert "baisser la consigne réduite" in recovery_advice(fast)
    slow = find_recoveries(_night(drop=3, recover_minutes=180), {"comfort": 19.0})
    assert "Relance longue" in recovery_advice(slow)
    assert "Aucune relance" in recovery_advice([])


def test_recovery_uses_setpoint_of_the_time():
    from analysis import find_recoveries  # noqa: PLC0415

    h = 3600
    points = [(0, "reduced", 17.0), (6 * h, "comfortEnergySaving", 17.5), (7 * h, "comfortEnergySaving", 19.0)]
    # consigne confort 19 °C ce jour-là, passée à 21 °C le lendemain : la relance est réussie
    rec = find_recoveries(points, {"comfort": [(0, 19.0), (30 * h, 21.0)]})
    assert rec[0].target == 19.0 and rec[0].minutes == 60
