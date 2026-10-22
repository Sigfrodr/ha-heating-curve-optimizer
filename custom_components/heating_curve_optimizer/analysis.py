"""Analyses pures (sans dépendance HA) : multi-pièces, cycles brûleur, alertes, relance."""

from __future__ import annotations

from dataclasses import dataclass


# ------------------------------------------------------------------ multi-pièces


@dataclass
class RoomReading:
    entity_id: str
    error: float  # ambiance - consigne (K)
    demand: bool  # la pièce demande de la chaleur (vanne ouverte)


def effective_error(rooms: list[RoomReading]) -> tuple[float, str] | None:
    """Écart qui pilote la courbe quand plusieurs pièces sont suivies.

    La bonne courbe est la plus basse qui satisfait encore la pièce la plus
    difficile à chauffer :
    - des pièces demandent de la chaleur → la plus froide d'entre elles décide
      (négatif : elle n'y arrive pas, il faut monter) ;
    - aucune ne demande → toutes les vannes se ferment, la marge est celle de la
      pièce la moins au-dessus de sa consigne (positif : on peut descendre).
    Retourne (écart, entité limitante).
    """
    if not rooms:
        return None
    pool = [r for r in rooms if r.demand] or rooms
    worst = min(pool, key=lambda r: r.error)
    return worst.error, worst.entity_id


# ------------------------------------------------------------------ cycles brûleur


@dataclass
class BurnerStats:
    starts: int
    hours: float
    span_hours: float

    @property
    def cycle_minutes(self) -> float | None:
        """Durée moyenne d'un cycle brûleur (minutes de flamme par démarrage)."""
        if self.starts <= 0:
            return None
        return self.hours * 60 / self.starts

    @property
    def starts_per_hour(self) -> float | None:
        return self.starts / self.span_hours if self.span_hours > 0 else None


def burner_stats(snapshots: list[dict], now: float, window_hours: float = 24) -> BurnerStats | None:
    """Démarrages et heures brûleur sur la fenêtre, à partir de relevés {t, starts, hours}."""
    recent = [s for s in snapshots if s["t"] >= now - window_hours * 3600]
    if len(recent) < 2:
        return None
    first, last = recent[0], recent[-1]
    span = (last["t"] - first["t"]) / 3600
    if span < window_hours / 2:
        return None
    return BurnerStats(
        starts=max(0, int(last["starts"] - first["starts"])),
        hours=max(0.0, float(last["hours"] - first["hours"])),
        span_hours=span,
    )


# ------------------------------------------------------------------ alertes


@dataclass
class AlertInputs:
    pressure: float | None
    min_pressure: float
    climate_unavailable_minutes: float
    frost_protection: bool
    burner: BurnerStats | None
    short_cycle_minutes: float
    min_starts_for_cycle_alert: int = 12
    room_frozen: tuple[float, float, int] | None = None  # (valeur, heures, démarrages brûleur)


def evaluate_alerts(i: AlertInputs) -> dict[str, str]:
    """Problèmes actifs : {code: message}."""
    alerts: dict[str, str] = {}
    if i.pressure is not None and i.pressure < i.min_pressure:
        alerts["pressure"] = (
            f"Pression d'eau basse : {i.pressure:.1f} bar (minimum {i.min_pressure:.1f} bar). "
            "Remettre de l'eau dans le circuit."
        )
    if i.climate_unavailable_minutes >= 30:
        alerts["unavailable"] = (
            f"Chaudière injoignable via ViCare depuis {int(i.climate_unavailable_minutes)} min."
        )
    if i.frost_protection:
        alerts["frost"] = "Protection antigel de la chaudière active."
    b = i.burner
    if b and b.starts >= i.min_starts_for_cycle_alert and b.cycle_minutes is not None:
        if b.cycle_minutes < i.short_cycle_minutes:
            alerts["short_cycling"] = (
                f"Cycles courts : {b.starts} démarrages en {b.span_hours:.0f} h, "
                f"{b.cycle_minutes:.0f} min de flamme en moyenne par démarrage."
            )
    if i.room_frozen:
        value, hours, starts = i.room_frozen
        alerts["room_frozen"] = (
            f"Température ambiante figée à {value:g} °C depuis {hours:.0f} h alors que le brûleur a démarré "
            f"{starts} fois : thermostat d'ambiance à vérifier (le redémarrer s'il est éteint). "
            "Les mesures sont ignorées en attendant."
        )
    return alerts


# ------------------------------------------------------------------ sonde d'ambiance figée

FROZEN_ROOM_HOURS = 4.0
FROZEN_ROOM_STARTS = 3


def room_frozen(unchanged_hours: float, burner_starts: float | None) -> bool:
    """Sonde d'ambiance figée : même valeur depuis des heures alors que le brûleur tourne.

    Une pièce chauffée bouge d'au moins 0,1 K en quelques cycles brûleur. Au repos (nuit, mi-saison),
    la valeur peut rester stable près de 5 h : sans démarrages du brûleur, rien n'est conclu.
    """
    return (
        burner_starts is not None
        and unchanged_hours >= FROZEN_ROOM_HOURS
        and burner_starts >= FROZEN_ROOM_STARTS
    )



def drop_frozen_samples(samples: list[dict], max_gap_hours: float = 3.0) -> list[dict]:
    """Retire les mesures prises pendant une sonde figée (avant la détection, ou avant v0.7.8).

    Les mesures ne sont collectées que chauffage en marche : une même valeur d'ambiance sur
    FROZEN_ROOM_HOURS ou plus de mesures consécutives est une sonde figée.
    """
    kept: list[dict] = []
    run: list[dict] = []
    for s in [*samples, None]:
        if s is not None and run and s["room"] == run[-1]["room"] and s["t"] - run[-1]["t"] <= max_gap_hours * 3600:
            run.append(s)
            continue
        if run and (run[-1]["t"] - run[0]["t"]) / 3600 < FROZEN_ROOM_HOURS:
            kept.extend(run)
        run = [s] if s is not None else []
    return kept

# ------------------------------------------------------------------ relance du matin


@dataclass
class Recovery:
    start: float  # horodatage du passage réduit → normal/confort
    room_start: float
    target: float
    minutes: float | None  # None : consigne pas atteinte dans la fenêtre
    night_drop: float  # baisse de température pendant le réduit (K)


def _target_at(spec: float | list[tuple[float, float]], t: float) -> float | None:
    """Consigne valable à l'instant t (valeur fixe, ou historique [(t, valeur)] trié)."""
    if isinstance(spec, (int, float)):
        return float(spec)
    value = None
    for ts, v in spec:
        if ts > t:
            break
        value = v
    return value if value is not None else (spec[0][1] if spec else None)


def find_recoveries(
    points: list[tuple[float, str, float | None]],
    targets: dict[str, float | list[tuple[float, float]]],
    tolerance: float = 0.3,
    max_minutes: float = 240,
) -> list[Recovery]:
    """Relances après réduit, à partir de (t, programme, T° ambiante) triés par t."""
    def base(program: str) -> str:
        return program.removesuffix("EnergySaving").lower()

    recoveries: list[Recovery] = []
    reduced_since: int | None = 0 if points and base(points[0][1]) == "reduced" else None
    for i in range(1, len(points)):
        prev_prog, prog = base(points[i - 1][1]), base(points[i][1])
        if prog == "reduced" and prev_prog != "reduced":
            reduced_since = i
        if prev_prog != "reduced" or prog not in ("normal", "comfort") or prog not in targets:
            continue
        t0, _, room0 = points[i]
        if room0 is None:
            continue
        target = _target_at(targets[prog], t0)  # consigne de l'époque, pas l'actuelle
        if target is None:
            continue
        start_night = reduced_since if reduced_since is not None else i
        night = [p[2] for p in points[start_night:i] if p[2] is not None]
        drop = (night[0] - min(night)) if night else 0.0
        minutes = None
        for t, p, room in points[i:]:
            if t - t0 > max_minutes * 60 or base(p) == "reduced":
                break
            if room is not None and room >= target - tolerance:
                minutes = (t - t0) / 60
                break
        recoveries.append(Recovery(t0, room0, target, minutes, drop))
        reduced_since = None
    return recoveries


def recovery_advice(recoveries: list[Recovery]) -> str:
    if not recoveries:
        return "Aucune relance après réduit détectée : la chaudière ne passe peut-être jamais en réduit."
    done = sorted(r.minutes for r in recoveries if r.minutes is not None)
    missed = sum(1 for r in recoveries if r.minutes is None)
    drop = sorted(r.night_drop for r in recoveries)[len(recoveries) // 2]
    if missed > len(recoveries) / 2:
        return ("La consigne n'est souvent pas atteinte après la relance : avancer l'heure de relance "
                "ou remonter la consigne réduite.")
    med = done[len(done) // 2]
    if med > 120:
        return (f"Relance longue ({med:.0f} min en médiane) : avancer la relance d'environ "
                f"{med - 60:.0f} min ou remonter la consigne réduite d'1 °C.")
    if med <= 30 and drop < 1.0:
        return (f"La maison perd peu la nuit ({drop:.1f} K) et remonte vite ({med:.0f} min) : "
                "on peut baisser la consigne réduite d'1 °C ou retarder la relance pour économiser.")
    return f"Réduit bien réglé : {drop:.1f} K perdus la nuit, consigne atteinte en {med:.0f} min."
