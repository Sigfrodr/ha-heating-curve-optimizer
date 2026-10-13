"""Modèle de la courbe de chauffe Viessmann et calcul des corrections.

Module pur (sans dépendance à AppDaemon / Home Assistant) pour pouvoir être
testé hors de HA.

Formule Viessmann (Vitotronic / Vitodens) :

    T_départ = T_consigne + décalage - pente * DAR * (1.4347 + 0.021*DAR + 247.9e-6*DAR²)
    avec DAR = T_extérieure - T_consigne
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median


def curve_term(dar: float) -> float:
    """h(DAR) = DAR * (1.4347 + 0.021*DAR + 247.9e-6*DAR²)."""
    return dar * (1.4347 + 0.021 * dar + 247.9e-6 * dar * dar)


def curve_term_derivative(dar: float) -> float:
    """h'(DAR)."""
    return 1.4347 + 0.042 * dar + 743.7e-6 * dar * dar


def supply_temperature(outside: float, room_set: float, slope: float, shift: float) -> float:
    """Température de départ calculée par la courbe de chauffe."""
    return room_set + shift - slope * curve_term(outside - room_set)


def room_gain(outside: float, room_set: float, slope: float) -> float:
    """Kelvins de départ nécessaires pour gagner 1 K en ambiance.

    C'est la dérivée de la courbe par rapport à la consigne d'ambiance :
    la courbe Viessmann modélise justement combien il faut monter le départ
    quand on monte la consigne d'1 K.
    """
    return 1.0 + slope * curve_term_derivative(outside - room_set)


@dataclass
class Sample:
    outside: float  # °C
    room: float  # °C mesurée
    target: float  # °C consigne active


@dataclass
class Settings:
    damping: float = 0.5  # fraction de la correction calculée appliquée à chaque fois
    max_shift_step: float = 3.0  # K max de variation du décalage par ajustement
    max_slope_step: float = 0.1  # variation max de la pente par ajustement
    shift_min: float = -10.0
    shift_max: float = 15.0
    slope_min: float = 0.3
    slope_max: float = 2.5
    shift_step: float = 1.0  # résolution du régulateur
    slope_step: float = 0.1
    deadband: float = 0.3  # K d'écart toléré sans rien toucher
    error_clip: float = 3.0  # écrête les écarts aberrants (soleil, cheminée, fenêtre ouverte…)
    bin_width: float = 1.0  # K, regroupement par température extérieure
    min_bin_samples: int = 3
    min_outside_spread: float = 5.0  # K d'amplitude ext. nécessaire pour toucher à la pente


@dataclass
class Bin:
    outside: float
    target: float
    error: float  # médiane de (ambiance - consigne)
    count: int


@dataclass
class Proposal:
    slope: float
    shift: float
    new_slope: float
    new_shift: float
    mean_error: float
    reason: str
    bins: list[Bin] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return abs(self.new_slope - self.slope) > 1e-6 or abs(self.new_shift - self.shift) > 1e-6

    def as_dict(self) -> dict:
        return {
            "slope": self.slope,
            "shift": self.shift,
            "new_slope": self.new_slope,
            "new_shift": self.new_shift,
            "mean_error": round(self.mean_error, 2),
            "reason": self.reason,
            "bins": [
                {"outside": round(b.outside, 1), "error": round(b.error, 2), "count": b.count}
                for b in self.bins
            ],
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _round_to(value: float, step: float) -> float:
    return round(round(value / step) * step, 6)


def bin_samples(samples: list[Sample], settings: Settings) -> list[Bin]:
    groups: dict[int, list[Sample]] = {}
    for s in samples:
        groups.setdefault(math.floor(s.outside / settings.bin_width), []).append(s)
    bins = []
    for key in sorted(groups):
        group = groups[key]
        if len(group) < settings.min_bin_samples:
            continue
        clip = settings.error_clip
        bins.append(
            Bin(
                outside=median(s.outside for s in group),
                target=median(s.target for s in group),
                error=median(_clamp(s.room - s.target, -clip, clip) for s in group),
                count=len(group),
            )
        )
    return bins


def compute_proposal(
    samples: list[Sample], slope: float, shift: float, settings: Settings | None = None
) -> Proposal:
    """Calcule la nouvelle pente / le nouveau décalage à partir des échantillons.

    Pour chaque tranche de température extérieure, on calcule de combien il
    faudrait bouger le départ pour annuler l'écart d'ambiance, puis on ajuste
    par moindres carrés : Δdépart = Δdécalage + Δpente * (-h(DAR)).
    """
    settings = settings or Settings()
    bins = bin_samples(samples, settings)

    def keep(reason: str, mean_error: float = 0.0) -> Proposal:
        return Proposal(slope, shift, slope, shift, mean_error, reason, bins)

    if not bins:
        return keep("pas assez de données exploitables")

    mean_error = sum(b.error for b in bins) / len(bins)
    if max(abs(b.error) for b in bins) < settings.deadband:
        return keep("écart dans la tolérance", mean_error)

    # Chaque tranche pèse pareil, pour ne pas laisser les températures
    # extérieures les plus fréquentes dominer l'ajustement.
    xs = [-curve_term(b.outside - b.target) for b in bins]
    ys = [-b.error * room_gain(b.outside, b.target, slope) for b in bins]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)

    spread = max(b.outside for b in bins) - min(b.outside for b in bins)
    fit_slope = len(bins) >= 3 and spread >= settings.min_outside_spread
    d_slope = 0.0
    if fit_slope:
        var_x = sum((x - x_mean) ** 2 for x in xs)
        if var_x > 1e-9:
            cov_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
            d_slope = settings.damping * cov_xy / var_x
            d_slope = _clamp(d_slope, -settings.max_slope_step, settings.max_slope_step)

    slope_lo = min(settings.slope_min, slope)
    slope_hi = max(settings.slope_max, slope)
    new_slope = _clamp(_round_to(slope + d_slope, settings.slope_step), slope_lo, slope_hi)
    d_slope = new_slope - slope

    # Le décalage compense l'effet (arrondi compris) du changement de pente
    # à la température extérieure moyenne, pour viser la bonne correction moyenne.
    d_shift = settings.damping * y_mean - d_slope * x_mean
    d_shift = _clamp(d_shift, -settings.max_shift_step, settings.max_shift_step)
    shift_lo = min(settings.shift_min, shift)
    shift_hi = max(settings.shift_max, shift)
    new_shift = _clamp(_round_to(shift + d_shift, settings.shift_step), shift_lo, shift_hi)

    if fit_slope:
        reason = f"ajustement pente + décalage (amplitude ext. {spread:.1f} K)"
    else:
        reason = f"ajustement du décalage seul (amplitude ext. {spread:.1f} K insuffisante pour la pente)"
    proposal = Proposal(slope, shift, new_slope, new_shift, mean_error, reason, bins)
    if not proposal.changed:
        proposal.reason = "correction inférieure à la résolution du régulateur"
    return proposal
