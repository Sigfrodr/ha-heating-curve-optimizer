import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "heating_curve_optimizer"))

from heating_curve import (  # noqa: E402
    Sample,
    Settings,
    compute_proposal,
    decision_settled,
    room_gain,
    supply_temperature,
)

TARGET = 20.0


def simulate_house(slope, shift, ideal_slope, ideal_shift, outsides, noise=0.0, seed=0):
    """Maison dont la courbe idéale est (ideal_slope, ideal_shift)."""
    rng = random.Random(seed)
    samples = []
    for ot in outsides:
        excess = supply_temperature(ot, TARGET, slope, shift) - supply_temperature(
            ot, TARGET, ideal_slope, ideal_shift
        )
        room = TARGET + excess / room_gain(ot, TARGET, ideal_slope) + rng.gauss(0, noise)
        samples.append(Sample(outside=ot, room=room, target=TARGET))
    return samples


def week_of_weather(lo=-5.0, hi=10.0, n=400):
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def test_supply_temperature_reference_point():
    # À T° ext. = consigne, le départ vaut consigne + décalage
    assert supply_temperature(20, 20, 1.4, 0) == 20
    assert 60 < supply_temperature(-10, 20, 1.4, 0) < 66


def test_converges_to_ideal_curve():
    slope, shift = 1.6, 0.0
    for day in range(30):
        samples = simulate_house(slope, shift, 1.1, 3.0, week_of_weather(), noise=0.2, seed=day)
        p = compute_proposal(samples, slope, shift)
        slope, shift = p.new_slope, p.new_shift
    assert abs(slope - 1.1) <= 0.1 + 1e-9
    for ot in (-5, 0, 5, 10):
        assert abs(
            supply_temperature(ot, TARGET, slope, shift) - supply_temperature(ot, TARGET, 1.1, 3.0)
        ) < 2.5


def test_too_cold_everywhere_raises_shift():
    samples = [Sample(outside=5 + i % 3 * 0.3, room=19.0, target=20.0) for i in range(50)]
    p = compute_proposal(samples, 1.4, 0)
    assert p.new_shift > 0
    assert p.new_slope == 1.4  # amplitude ext. trop faible pour toucher à la pente


def test_too_cold_only_when_freezing_raises_slope():
    # Courbe idéale (1.2, -3) : bonne vers +8 °C, ~1,4 K trop froid à -8 °C
    samples = simulate_house(1.0, 0, 1.2, -3, week_of_weather(-8, 8))
    assert abs(samples[-1].room - TARGET) < 0.2
    p = compute_proposal(samples, 1.0, 0)
    assert p.new_slope > 1.0
    assert p.new_shift < 0  # compense la pente là où il faisait déjà bon


def test_within_deadband_no_change():
    samples = [Sample(outside=ot, room=20.1, target=20.0) for ot in week_of_weather()]
    p = compute_proposal(samples, 1.4, 0)
    assert not p.changed


def test_steps_are_bounded():
    samples = [Sample(outside=ot, room=15.0, target=20.0) for ot in week_of_weather()]
    s = Settings()
    p = compute_proposal(samples, 1.4, 0, s)
    assert abs(p.new_slope - 1.4) <= s.max_slope_step + 1e-9
    assert abs(p.new_shift) <= s.max_shift_step


def test_current_value_outside_limits_does_not_jump():
    samples = [Sample(outside=5 + i % 2, room=20.5, target=20.0) for i in range(50)]
    p = compute_proposal(samples, 3.0, 0, Settings(slope_max=2.0))
    assert p.new_slope == 3.0


def test_no_data():
    p = compute_proposal([], 1.4, 0)
    assert not p.changed


def test_damping_does_not_block_one_step():
    # Relevé réel du 26/10 : +0,57 K en moyenne, la moitié de la correction (−0,38 K) s'arrondissait à 0
    bins = [(4.2, 0.3, 3), (6.5, 0.1, 4), (7.7, 0.5, 4), (9.7, 0.7, 3), (10.4, 0.7, 6),
            (11.4, 0.4, 8), (12.7, 0.8, 10), (13.2, 0.6, 4), (14.7, 1.0, 15)]
    samples = [Sample(outside=o, room=TARGET + e, target=TARGET) for o, e, n in bins for _ in range(n)]
    s = Settings(shift_min=-13, shift_max=40, slope_min=0.2, slope_max=3.5)
    p = compute_proposal(samples, 0.3, 23, s)
    # surchauffe plus forte par temps doux : la pente monte d'un cran, le décalage compense
    assert p.new_slope == 0.4 and p.new_shift == 21
    # après ce cran, l'écart résiduel (< ½ cran) ne déclenche plus rien : pas d'oscillation
    samples = [Sample(outside=o, room=TARGET + 0.32, target=TARGET) for o, _, n in bins for _ in range(n)]
    assert not compute_proposal(samples, 0.4, 21, s).changed


def test_decision_settled():
    hour = 3600
    steady = [(h * hour + m * 600, 0.6 + (m % 2) * 0.05) for h in range(8) for m in range(3)]
    assert decision_settled(steady, 0.3)
    assert not decision_settled(steady[:12], 0.3)  # 4 heures seulement
    noisy = [(h * hour, 0.3 + (1.0 if h % 2 else -1.0)) for h in range(8)]
    assert not decision_settled(noisy, 0.3)
    fine = [(h * hour, 0.05 * (h % 3)) for h in range(8)]
    assert decision_settled(fine, 0.3)
