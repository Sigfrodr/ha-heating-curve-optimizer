"""Définition unique des options : sert au formulaire HA (config_flow) et à l'onglet Réglages du panneau."""

from __future__ import annotations

# section None = en tête du formulaire ; les autres sont des sections repliables
SECTIONS = ("rooms_weather", "pilot", "costs_report", "billing", "alerts", "dhw", "algorithm")


def _n(key, section, lo, hi, step, unit=None):
    return {"key": key, "section": section, "kind": "number", "min": lo, "max": hi, "step": step, "unit": unit}


FIELDS: list[dict] = [
    {"key": "programs", "section": None, "kind": "programs"},
    _n("heating_limit", None, 5, 25, 0.5, "°C"),
    {"key": "evaluate_at", "section": None, "kind": "time"},
    {"key": "notify", "section": None, "kind": "notify", "optional": True},
    # pièces et météo
    {"key": "rooms", "section": "rooms_weather", "kind": "entities", "domain": "climate", "optional": True},
    {"key": "weather", "section": "rooms_weather", "kind": "entity", "domain": "weather", "optional": True},
    {"key": "solar_filter", "section": "rooms_weather", "kind": "bool"},
    _n("solar_cloud_max", "rooms_weather", 0, 100, 5, "%"),
    _n("solar_min_elevation", "rooms_weather", 0, 60, 1, "°"),
    {"key": "room_reference", "section": "rooms_weather", "kind": "entity", "domain": "sensor",
     "device_class": "temperature", "choices": "temperature", "optional": True},
    _n("room_reference_offset", "rooms_weather", -3, 3, 0.1, "K"),
    # pilotage
    _n("standby_temp", "pilot", 5, 20, 1, "°C"),
    _n("demand_delay_minutes", "pilot", 5, 120, 5, "min"),
    {"key": "sun_anticipation", "section": "pilot", "kind": "bool"},
    _n("write_budget", "pilot", 2, 40, 1),
    _n("vicare_refresh_minutes", "pilot", 0, 30, 1, "min"),
    # coûts et rapport
    _n("gas_price", "costs_report", 0.01, 1, 0.001, "€/kWh"),
    _n("kwh_per_m3", "costs_report", 8, 13, 0.01, "kWh/m³"),
    _n("elec_price", "costs_report", 0.01, 1, 0.001, "€/kWh"),
    {"key": "electric_gas_priority", "section": "costs_report", "kind": "bool"},
    {"key": "linky_token", "section": "costs_report", "kind": "secret", "optional": True},
    {"key": "gas_meter", "section": "costs_report", "kind": "entity", "domain": "sensor", "optional": True},
    {"key": "weekly_report", "section": "costs_report", "kind": "bool"},
    {"key": "report_weekday", "section": "costs_report", "kind": "weekday"},
    {"key": "report_time", "section": "costs_report", "kind": "time"},
    # facture et mensualités
    {"key": "billing_start", "section": "billing", "kind": "date", "optional": True},
    _n("monthly_payment", "billing", 0, 1000, 0.01, "€"),
    _n("payments_count", "billing", 1, 12, 1),
    _n("fixed_annual_cost", "billing", 0, 2000, 1, "€"),
    _n("reference_annual_kwh", "billing", 0, 100000, 1, "kWh"),
    # alertes
    _n("min_pressure", "alerts", 0.3, 2.5, 0.1, "bar"),
    _n("short_cycle_minutes", "alerts", 2, 30, 1, "min"),
    _n("overconsumption_ratio", "alerts", 1.1, 3, 0.05),
    _n("maintenance_months", "alerts", 6, 36, 1, "mois"),
    {"key": "daily_check_time", "section": "alerts", "kind": "time"},
    {"key": "boiler_switch", "section": "alerts", "kind": "entity", "domain": "switch", "choices": "switch",
     "optional": True},
    {"key": "auto_restart", "section": "alerts", "kind": "bool"},
    {"key": "boiler_power", "section": "alerts", "kind": "entity", "domain": "sensor", "device_class": "power",
     "choices": "power", "optional": True},
    {"key": "boiler_energy", "section": "alerts", "kind": "entity", "domain": "sensor", "device_class": "energy",
     "optional": True},
    # eau chaude
    {"key": "legionella_weekday", "section": "dhw", "kind": "weekday"},
    {"key": "legionella_time", "section": "dhw", "kind": "time"},
    _n("legionella_temp", "dhw", 55, 70, 1, "°C"),
    _n("legionella_minutes", "dhw", 30, 240, 10, "min"),
    # algorithme
    _n("settle_minutes", "algorithm", 0, 720, 10, "min"),
    _n("sample_minutes", "algorithm", 5, 60, 1, "min"),
    _n("min_samples", "algorithm", 6, 2000, 1),
    _n("max_age_days", "algorithm", 1, 60, 1, "j"),
    _n("damping", "algorithm", 0.1, 1, 0.05),
    _n("max_shift_step", "algorithm", 1, 10, 1, "K"),
    _n("max_slope_step", "algorithm", 0.1, 1, 0.1),
    _n("shift_min", "algorithm", -13, 40, 1, "K"),
    _n("shift_max", "algorithm", -13, 40, 1, "K"),
    _n("slope_min", "algorithm", 0.2, 3.5, 0.1),
    _n("slope_max", "algorithm", 0.2, 3.5, 0.1),
    _n("deadband", "algorithm", 0, 2, 0.1, "K"),
    _n("min_outside_spread", "algorithm", 0, 20, 1, "K"),
]

# Valeur vide des champs facultatifs (les entrées existantes n'ont pas toujours la clé)
EMPTY = {"notify": "", "weather": "", "rooms": [], "gas_meter": "", "room_reference": "", "boiler_switch": "", "boiler_power": "",
         "boiler_energy": "", "billing_start": "", "linky_token": ""}
SECRETS = {f["key"] for f in FIELDS if f["kind"] == "secret"}


def validate(values: dict) -> dict:
    """Contrôle et normalise des options venant du panneau ; lève ValueError sinon."""
    out: dict = {}
    by_key = {f["key"]: f for f in FIELDS}
    for key, value in values.items():
        field = by_key.get(key)
        if field is None:
            raise ValueError(f"option inconnue : {key}")
        kind = field["kind"]
        if kind == "number":
            v = float(value)
            if not field["min"] <= v <= field["max"]:
                raise ValueError(f"{key} hors limites ({field['min']} – {field['max']})")
            out[key] = v
        elif kind == "bool":
            out[key] = bool(value)
        elif kind in ("time",):
            h, m, *sec = str(value).split(":")
            out[key] = f"{int(h):02d}:{int(m):02d}:{int(sec[0]) if sec else 0:02d}"
        elif kind == "weekday":
            if str(value) not in {str(i) for i in range(7)}:
                raise ValueError(f"{key} : jour invalide")
            out[key] = str(value)
        elif kind == "date":
            from datetime import date  # noqa: PLC0415

            out[key] = date.fromisoformat(str(value)).isoformat() if value else ""
        elif kind == "secret":
            token = str(value or "").strip()
            if token:
                from .linky import token_prms  # noqa: PLC0415

                if not token_prms(token):
                    raise ValueError(f"{key} : jeton Conso API invalide")
            out[key] = token
        elif kind in ("entities", "programs"):
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ValueError(f"{key} : liste attendue")
            out[key] = value
        else:  # entity, notify, text
            out[key] = str(value or "")
    return out
