"""Pilotage, planning, coûts et diagnostics — logique pure (sans dépendance HA)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import réel inutile : permet de tester ce module seul
    from .analysis import Recovery

# ------------------------------------------------------------------ planning


def to_minutes(hhmm: str) -> int:
    h, m = str(hhmm).split(":")[:2]
    return int(h) * 60 + int(m)


def fmt_minutes(minutes: int) -> str:
    return "24:00" if minutes >= 1440 else f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_trv_schedule(text: str) -> list[tuple[int, float]]:
    """« 06:00/17 12:00/21 … » → [(minute de début, température)]."""
    points = []
    for part in str(text).split():
        if "/" not in part:
            continue
        hhmm, temp = part.split("/", 1)
        try:
            points.append((to_minutes(hhmm), float(temp.rstrip("°C"))))
        except ValueError:
            continue
    return sorted(points)


def merge_periods(periods: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(p for p in periods if p[1] > p[0]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def comfort_periods_from_trv(points: list[tuple[int, float]]) -> list[tuple[int, int]]:
    """Périodes où la tête vise plus que sa température la plus basse du jour.

    Chaque point « HH:MM/T » fixe la température T à partir de HH:MM ; avant le
    premier point, la dernière température de la journée s'applique.
    """
    if not points:
        return []
    low = min(t for _, t in points)
    ends = [m for m, _ in points[1:]] + [1440]
    periods = [(start, min(end, 1440)) for (start, temp), end in zip(points, ends) if temp > low]
    if points[0][0] > 0 and points[-1][1] > low:
        periods.append((0, points[0][0]))
    return merge_periods(periods)


def schedule_from_trvs(trv_schedules: list[dict[int, str]]) -> dict[int, list[list[str]]]:
    """Union des périodes confort de plusieurs têtes → planning {jour: [[début, fin]]}."""
    schedule: dict[int, list[list[str]]] = {}
    for day in range(7):
        periods: list[tuple[int, int]] = []
        for trv in trv_schedules:
            if day in trv:
                periods += comfort_periods_from_trv(parse_trv_schedule(trv[day]))
        schedule[day] = [[fmt_minutes(s), fmt_minutes(e)] for s, e in merge_periods(periods)]
    return schedule


def normalize_schedule(schedule: dict) -> dict[int, list[list[str]]]:
    """Clés en entiers, périodes triées et fusionnées (le JSON stocke les clés en texte)."""
    out: dict[int, list[list[str]]] = {}
    for day in range(7):
        raw = schedule.get(day, schedule.get(str(day), []))
        periods = merge_periods([(to_minutes(s), to_minutes(e)) for s, e in raw])
        out[day] = [[fmt_minutes(s), fmt_minutes(e)] for s, e in periods]
    return out


VICARE_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def vicare_schedule(
    schedule: dict,
    preheat_minutes: int = 0,
    max_entries: int = 4,
    resolution: int = 10,
    modes: tuple[str, ...] | list[str] = ("normal", "comfort"),
) -> dict[str, list[dict]]:
    """Planning du panneau (périodes confort, lundi = 0) → planning de la chaudière ViCare.

    La chaudière limite le nombre de plages par jour : les périodes confort les plus proches sont
    fusionnées jusqu'à tenir. S'il reste une plage libre, un palier « normal » de `preheat_minutes`
    précède la première période confort (montée en deux temps, départ moins chaud). Hors plages :
    réduit (mode par défaut de la chaudière).
    """
    out: dict[str, list[dict]] = {}
    for day, name in enumerate(VICARE_DAYS):
        raw = schedule.get(day, schedule.get(str(day), []))
        periods = [list(p) for p in merge_periods([(to_minutes(s), to_minutes(e)) for s, e in raw])]
        while len(periods) > max(1, max_entries):
            i = min(range(len(periods) - 1), key=lambda k: periods[k + 1][0] - periods[k][1])
            periods[i][1] = periods.pop(i + 1)[1]
        entries = [{"start": s, "end": e, "mode": "comfort"} for s, e in periods]
        if preheat_minutes > 0 and "normal" in modes and entries and len(entries) < max_entries:
            first = entries[0]["start"]
            if first > 0:
                entries.insert(0, {"start": max(0, first - preheat_minutes), "end": first, "mode": "normal"})

        def rounded(minutes: int) -> int:
            return min(1440, round(minutes / resolution) * resolution)

        out[name] = [
            {"start": fmt_minutes(rounded(x["start"])), "end": fmt_minutes(rounded(x["end"])),
             "mode": x["mode"], "position": i}
            for i, x in enumerate(entries)
            if rounded(x["end"]) > rounded(x["start"])
        ]
    return out


def dhw_schedule(schedule: dict, max_entries: int = 2, resolution: int = 10, mode: str = "on") -> dict[str, list[dict]]:
    """Plages d'eau chaude {jour: [[début, fin]]} → planning ViCare, en refusant ce que la chaudière n'accepte pas."""
    out: dict[str, list[dict]] = {}
    for day in VICARE_DAYS:
        periods = sorted((to_minutes(s), to_minutes(e)) for s, e in schedule.get(day) or [])
        if len(periods) > max_entries:
            raise ValueError(f"{day} : {max_entries} plages au plus")
        for i, (s, e) in enumerate(periods):
            if not 0 <= s < e <= 1440:
                raise ValueError(f"{day} : plage {fmt_minutes(s)}–{fmt_minutes(e)} invalide")
            if s % resolution or e % resolution:
                raise ValueError(f"{day} : horaires par pas de {resolution} min")
            if i and s < periods[i - 1][1]:
                raise ValueError(f"{day} : plages qui se chevauchent")
        out[day] = [{"start": fmt_minutes(s), "end": fmt_minutes(e), "mode": mode, "position": i}
                    for i, (s, e) in enumerate(periods)]
    return out


def in_comfort(schedule: dict, weekday: int, minute: int) -> bool:
    for start, end in schedule.get(weekday, schedule.get(str(weekday), [])):
        if to_minutes(start) <= minute < to_minutes(end):
            return True
    return False


def minutes_to_next_comfort(schedule: dict, weekday: int, minute: int, horizon: int = 720) -> int | None:
    """Minutes avant la prochaine période confort (0 si on y est), None au-delà de l'horizon."""
    for offset in range(0, horizon + 1, 5):
        total = minute + offset
        if in_comfort(schedule, (weekday + total // 1440) % 7, total % 1440):
            return offset
    return None


DEFAULT_SCHEDULE = {day: [["06:00", "22:00"]] for day in range(7)}

# ------------------------------------------------------------------ pilotage


@dataclass
class ControlInputs:
    weekday: int
    minute: int
    schedule: dict
    comfort_temp: float
    reduced_temp: float
    standby_temp: float
    rooms_configured: bool
    any_demand: bool
    no_demand_minutes: float
    demand_delay_minutes: float
    room: float | None
    preheat_rate: float | None  # K/h appris sur les relances passées
    forecast_factor: float = 1.0  # < 1 : il fera plus froid, la maison chauffera moins vite
    sun_expected: bool = False


@dataclass
class ControlDecision:
    setpoint: float
    mode: str  # confort, réduit, veille, relance, soleil
    reason: str


def decide_setpoint(i: ControlInputs) -> ControlDecision:
    if not in_comfort(i.schedule, i.weekday, i.minute):
        wait = minutes_to_next_comfort(i.schedule, i.weekday, i.minute, horizon=360)
        if wait is not None and i.preheat_rate and i.room is not None:
            rate = i.preheat_rate * i.forecast_factor
            needed = max(0.0, i.comfort_temp - i.room) / rate * 60 if rate > 0 else 0.0
            if needed >= wait:
                return ControlDecision(
                    i.comfort_temp, "relance",
                    f"relance anticipée : {needed:.0f} min de chauffe estimées, confort dans {wait} min",
                )
        return ControlDecision(i.reduced_temp, "réduit", "période réduite du planning")
    if i.rooms_configured and not i.any_demand and i.no_demand_minutes >= i.demand_delay_minutes:
        return ControlDecision(
            i.standby_temp, "veille",
            f"aucune pièce ne demande de chaleur depuis {i.no_demand_minutes:.0f} min",
        )
    if i.sun_expected:
        return ControlDecision(i.comfort_temp - 1, "soleil", "soleil franc attendu : on le laisse chauffer")
    return ControlDecision(i.comfort_temp, "confort", "période confort du planning")


def preheat_rate(recoveries: list[Recovery]) -> float | None:
    """Vitesse de remontée médiane (K/h) sur les relances exploitables."""
    rates = sorted(
        (r.target - r.room_start) / (r.minutes / 60)
        for r in recoveries
        if r.minutes and r.minutes >= 10 and r.target - r.room_start >= 0.3
    )
    return rates[len(rates) // 2] if rates else None


def forecast_factor(indoor: float, outside_now: float | None, outside_forecast: float | None) -> float:
    """Ralentissement attendu de la relance si la météo se refroidit (borné 0,5–1,5)."""
    if outside_now is None or outside_forecast is None:
        return 1.0
    now_gap = max(1.0, indoor - outside_now)
    future_gap = max(1.0, indoor - outside_forecast)
    return max(0.5, min(1.5, now_gap / future_gap))


def sun_expected(elevation: float | None, clouds_next: list[float], max_cloud: float = 30.0) -> bool:
    """Soleil assez haut et ciel dégagé sur les prochaines heures prévues."""
    if elevation is None or elevation < 15 or not clouds_next:
        return False
    return sum(clouds_next) / len(clouds_next) < max_cloud


def cloud_cover_at(hours: list, now: datetime) -> float | None:
    """Couverture nuageuse (%) de l'heure en cours, sinon de la suivante, d'une prévision horaire
    [(début du créneau, %)]. Créneaux repérés par leur heure de début, jamais par leur rang :
    la prévision peut commencer avant l'heure en cours ou dater de la dernière actualisation."""
    hour = timedelta(hours=1)
    best = None
    for start, cloud in hours:
        if cloud is None or start is None:
            continue
        try:
            start = start if isinstance(start, datetime) else datetime.fromisoformat(str(start))
            cloud = float(cloud)
        except (TypeError, ValueError):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start <= now < start + hour:
            return cloud  # heure en cours
        if now < start <= now + hour and (best is None or start < best[0]):
            best = (start, cloud)  # heure suivante
    return best[1] if best else None


# ------------------------------------------------------------------ coûts et bilan thermique


def gas_cost(m3: float, kwh_per_m3: float, price_per_kwh: float) -> tuple[float, float]:
    kwh = m3 * kwh_per_m3
    return kwh, kwh * price_per_kwh


@dataclass
class ThermalBalance:
    loss_w_per_k: float  # déperditions de la maison (W/K)
    base_kwh_per_day: float
    r2: float
    days: int
    internal_gains_w: float | None = None  # apports de l'électricité consommée dans la maison


ELEC_TO_HEAT = 0.9  # part de l'électricité consommée qui finit en chaleur dans la maison


def thermal_balance(
    days: list[tuple], indoor: float = 19.0, efficiency: float = 0.95
) -> ThermalBalance | None:
    """Régression gaz (kWh/j) = a × (T int − T ext) + b sur les jours de chauffe.

    days : [(kWh de gaz de chauffage, T ext moyenne)] ou [(kWh de gaz, T ext, kWh d'électricité)].
    Avec l'électricité (compteur Linky), la chaleur apportée = gaz × rendement + électricité × 0,9 :
    les déperditions (W/K) ne sont plus faussées par les apports des appareils. Le talon est rendu
    en kWh de gaz, avec l'électricité moyenne, pour garder le même modèle (seuil de chauffe, prévision).
    """
    heating = [d for d in days if d[0] > 0 and indoor - d[1] > 2]
    with_elec = [d for d in heating if len(d) > 2 and d[2] is not None]
    use_elec = len(with_elec) >= max(10, 0.8 * len(heating))
    if use_elec:
        pts = [(indoor - t, kwh * efficiency + elec * ELEC_TO_HEAT) for kwh, t, elec in with_elec]
    else:
        pts = [(indoor - d[1], d[0]) for d in heating]
    if len(pts) < 10:
        return None
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx < 1e-9:
        return None
    a = sum((x - mx) * (y - my) for x, y in pts) / sxx
    b = my - a * mx
    ss_tot = sum((y - my) ** 2 for _, y in pts)
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in pts)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if use_elec:
        gains = sum(e for _, _, e in with_elec) / len(with_elec) * ELEC_TO_HEAT
        return ThermalBalance(a * 1000 / 24, (b - gains) / efficiency, r2, n, round(gains * 1000 / 24))
    return ThermalBalance(a * efficiency * 1000 / 24, b, r2, n)


# ------------------------------------------------------------------ équilibrage


@dataclass
class RoomBalance:
    entity_id: str
    heating_power: float
    relative: float  # par rapport à la médiane des pièces
    advice: str
    internal_gains: bool = False


def balance_rooms(
    rooms: list[tuple[str, float | None]], internal_gains: set[str] | frozenset[str] = frozenset()
) -> list[RoomBalance]:
    """Compare la puissance de chauffe apprise (Better Thermostat) de chaque pièce.

    Pièces « avec apports internes » (cuisine, poêle…) : leur vitesse de chauffe est gonflée par ces
    apports ; elles sont exclues de la médiane (s'il reste au moins deux autres pièces) et un écart
    vers le haut n'est qu'à confirmer.
    """
    known = [(e, p) for e, p in rooms if p and p > 0]
    if len(known) < 2:
        return []
    reference = [p for e, p in known if e not in internal_gains]
    powers = sorted(reference if len(reference) >= 2 else [p for _, p in known])
    mid = len(powers) // 2
    med = powers[mid] if len(powers) % 2 else (powers[mid - 1] + powers[mid]) / 2
    result = []
    for entity_id, p in known:
        rel = p / med
        gains = entity_id in internal_gains
        if rel >= 1.6 and gains:
            advice = "à confirmer : la cuisson ou une autre source de chaleur peut gonfler la mesure"
        elif rel >= 1.6:
            advice = "chauffe bien plus vite que les autres : refermer un peu son té de réglage"
        elif rel <= 0.6:
            advice = "chauffe bien plus lentement : ouvrir son té de réglage, purger, ou radiateur trop petit"
        else:
            advice = "équilibrée"
        result.append(RoomBalance(entity_id, p, rel, advice, gains))
    return result


# ------------------------------------------------------------------ rapport hebdomadaire


def weekly_report(
    gas_m3: float | None,
    cost_eur: float | None,
    dju: float | None,
    ratio_prev: float | None,
    adjustments: int,
    standby_hours: float,
    alerts: list[str],
) -> str:
    lines = []
    if gas_m3 is not None:
        line = f"Gaz chauffage : {gas_m3:.1f} m³"
        if cost_eur is not None:
            line += f" (≈ {cost_eur:.2f} €)"
        lines.append(line + ".")
    if gas_m3 and dju and dju >= 5:
        ratio = gas_m3 / dju
        line = f"{ratio:.3f} m³ par degré-jour"
        if ratio_prev:
            line += f" ({(ratio - ratio_prev) / ratio_prev * 100:+.0f} % par rapport à la semaine précédente)"
        lines.append(line + ".")
    lines.append(f"Ajustements de courbe : {adjustments}.")
    if standby_hours:
        lines.append(f"Chaudière mise en veille faute de demande : {standby_hours:.0f} h.")
    lines.append("Alertes : " + ("; ".join(a.rstrip(".") for a in alerts) if alerts else "aucune") + ".")
    return "\n".join(lines)
