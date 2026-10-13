"""Analyses avancées (sans dépendance HA) : courbe calculée, seuil de chauffe,
surconsommation, tendance de pression, entretien."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

try:
    from .heating_curve import Bin, curve_term, room_gain, supply_temperature
except ImportError:  # module importé seul (tests unitaires sans Home Assistant)
    from heating_curve import Bin, curve_term, room_gain, supply_temperature

RADIATOR_EXPONENT = 1.3  # émission d'un radiateur ∝ (T moyenne − T ambiante)^1,3


# ------------------------------------------------------------------ courbe calculée


@dataclass
class ComputedCurve:
    slope: float
    shift: float
    coefficient: float  # c dans T départ = T int + c × (T int − T ext)^(1/n)
    rms: float  # écart moyen entre courbe Viessmann retenue et besoin physique (K)


def needed_supply(bins: list[Bin], slope: float, shift: float) -> list[tuple[float, float, float]]:
    """Départ qui aurait donné la consigne pour chaque tranche : [(T ext, T int, départ)]."""
    out = []
    for b in bins:
        current = supply_temperature(b.outside, b.target, slope, shift)
        out.append((b.outside, b.target, current - b.error * room_gain(b.outside, b.target, slope)))
    return out


def physical_curve(
    bins: list[Bin], slope: float, shift: float, outside_range: tuple[float, float] = (-12.0, 16.0)
) -> ComputedCurve | None:
    """Ajuste un modèle de radiateur sur les besoins mesurés, puis la courbe Viessmann la plus proche.

    Même avec une plage de températures extérieures étroite, la forme physique
    (exposant 1,3 des radiateurs) permet d'extrapoler aux grands froids.
    """
    pts = [(o, t, s) for o, t, s in needed_supply(bins, slope, shift) if t - o > 2 and s > t]
    if not pts:
        return None
    # T départ − T int = c × (T int − T ext)^(1/n) : moindres carrés à un paramètre
    k = 1 / RADIATOR_EXPONENT
    num = sum((s - t) * (t - o) ** k for o, t, s in pts)
    den = sum((t - o) ** (2 * k) for o, t, s in pts)
    if den <= 0:
        return None
    c = num / den
    indoor = sum(t for _, t, _ in pts) / len(pts)
    grid = [outside_range[0] + i for i in range(int(outside_range[1] - outside_range[0]) + 1)]
    target = {o: indoor + c * max(indoor - o, 0.0) ** k for o in grid}
    best = None
    for si in range(2, 36):  # pente 0,2 → 3,5
        sl = si / 10
        # décalage optimal (moyenne des écarts) puis arrondi au pas de 1 K
        diffs = [target[o] - supply_temperature(o, indoor, sl, 0.0) for o in grid]
        sh = max(-13, min(40, round(sum(diffs) / len(diffs))))
        rms = (sum((supply_temperature(o, indoor, sl, sh) - target[o]) ** 2 for o in grid) / len(grid)) ** 0.5
        if best is None or rms < best.rms:
            best = ComputedCurve(sl, float(sh), c, rms)
    return best


# ------------------------------------------------------------------ seuil de chauffe


def heating_limit(loss_w_per_k: float, base_kwh_per_day: float, indoor: float, efficiency: float = 0.95) -> float | None:
    """T ext au-dessus de laquelle le gaz de chauffage tombe à zéro (apports gratuits compris).

    Modèle du bilan thermique : kWh/j = a × (T int − T ext) + b, avec a dérivé des W/K.
    Le gaz s'annule pour T int − T ext = −b / a.
    """
    a = loss_w_per_k * 24 / 1000 / efficiency
    if a <= 0:
        return None
    limit = indoor + base_kwh_per_day / a
    return round(min(max(limit, 8.0), 20.0), 1)


def expected_gas_kwh(loss_w_per_k: float, base_kwh_per_day: float, indoor: float, outside: float,
                     efficiency: float = 0.95) -> float:
    a = loss_w_per_k * 24 / 1000 / efficiency
    return max(0.0, a * (indoor - outside) + base_kwh_per_day)


def overconsumption(actual_kwh: float, expected_kwh: float, ratio: float = 1.3, min_excess: float = 5.0) -> float | None:
    """Surconsommation en % si le jour dépasse nettement la prévision, sinon None."""
    if expected_kwh <= 0 or actual_kwh < expected_kwh * ratio or actual_kwh - expected_kwh < min_excess:
        return None
    return (actual_kwh / expected_kwh - 1) * 100


# ------------------------------------------------------------------ pression et entretien


def pressure_trend(daily_min: list[tuple[float, float]], min_days: int = 14) -> float | None:
    """Pente de la pression minimale quotidienne en bar par semaine ([(jour en s, bar)])."""
    if len(daily_min) < min_days:
        return None
    xs = [t / (7 * 86400) for t, _ in daily_min]
    ys = [p for _, p in daily_min]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def slow_leak(trend_bar_per_week: float | None, threshold: float = -0.05) -> bool:
    return trend_bar_per_week is not None and trend_bar_per_week <= threshold


@dataclass
class Maintenance:
    last: date | None
    due: date | None
    days_left: int | None
    burner_hours_since: float | None


def maintenance_status(last_service: date | None, today: date, interval_months: int,
                       hours_now: float | None, hours_at_service: float | None) -> Maintenance:
    if last_service is None:
        return Maintenance(None, None, None, None)
    month = last_service.month - 1 + interval_months
    year = last_service.year + month // 12
    day = min(last_service.day, 28)
    due = date(year, month % 12 + 1, day)
    since = hours_now - hours_at_service if hours_now is not None and hours_at_service is not None else None
    return Maintenance(last_service, due, (due - today).days, since)


# ------------------------------------------------------------------ budget d'écritures ViCare


def write_allowed(budget: int, used_24h: int, lowering: bool) -> bool:
    """Une écriture qui baisse la consigne garde toujours de quoi revenir au confort.

    L'API ViCare est limitée à 1 450 appels par 24 h et l'intégration HA en consomme
    déjà environ 1 440 pour ses relevés : le reste est un budget très court.
    """
    remaining = budget - used_24h
    return remaining >= (2 if lowering else 1)


# ------------------------------------------------------------------ prévision de facture

# Répartition mensuelle typique du gaz (chauffage + eau chaude) en France, janvier → décembre
MONTHLY_PROFILE = (0.18, 0.14, 0.12, 0.07, 0.04, 0.02, 0.015, 0.015, 0.03, 0.07, 0.13, 0.17)


@dataclass
class BillForecast:
    consumed_kwh: float
    remaining_kwh: float
    total_kwh: float
    total_cost: float
    payments: float
    balance: float  # > 0 : à payer à la régularisation, < 0 : remboursement
    period_end: date


def _add_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 février
        return d.replace(year=d.year + 1, day=28)


def bill_forecast(
    start: date, today: date, consumed_kwh: float, reference_annual_kwh: float,
    price_per_kwh: float, fixed_annual_cost: float, monthly_payment: float, payments_count: int,
    profile: tuple[float, ...] = MONTHLY_PROFILE,
) -> BillForecast:
    """Facture annuelle estimée : consommé depuis le début de période + reste selon le profil mensuel."""
    end = _add_year(start)
    remaining = 0.0
    day = today
    while day < end:
        month_days = (date(day.year + day.month // 12, day.month % 12 + 1, 1) - date(day.year, day.month, 1)).days
        remaining += reference_annual_kwh * profile[day.month - 1] / month_days
        day = date.fromordinal(day.toordinal() + 1)
    total = consumed_kwh + remaining
    cost = total * price_per_kwh + fixed_annual_cost
    payments = monthly_payment * payments_count
    return BillForecast(consumed_kwh, remaining, total, cost, payments, cost - payments, end)


__all__ = [
    "BillForecast", "ComputedCurve", "MONTHLY_PROFILE", "Maintenance", "bill_forecast", "write_allowed", "curve_term", "expected_gas_kwh", "heating_limit",
    "maintenance_status", "needed_supply", "overconsumption", "physical_curve", "pressure_trend", "slow_leak",
]
