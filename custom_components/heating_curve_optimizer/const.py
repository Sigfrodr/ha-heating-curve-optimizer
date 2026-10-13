"""Constantes de l'optimiseur de courbe de chauffe."""

DOMAIN = "heating_curve_optimizer"

# Entités (data de l'entrée)
CONF_CLIMATE = "climate"
CONF_OUTSIDE = "outside_temperature"
CONF_SLOPE = "slope"
CONF_SHIFT = "shift"
CONF_ROOM = "room_temperature"

# Options
CONF_PROGRAMS = "programs"
CONF_HEATING_LIMIT = "heating_limit"
CONF_SETTLE_MINUTES = "settle_minutes"
CONF_SAMPLE_MINUTES = "sample_minutes"
CONF_MIN_SAMPLES = "min_samples"
CONF_MAX_AGE_DAYS = "max_age_days"
CONF_EVALUATE_AT = "evaluate_at"
CONF_NOTIFY = "notify"

# Les clés de réglage portent le nom des champs de heating_curve.Settings
TUNING_KEYS = (
    "damping",
    "max_shift_step",
    "max_slope_step",
    "shift_min",
    "shift_max",
    "slope_min",
    "slope_max",
    "deadband",
    "min_outside_spread",
)

DEFAULT_OPTIONS = {
    CONF_PROGRAMS: ["normal", "normalEnergySaving", "comfort", "comfortEnergySaving"],
    CONF_HEATING_LIMIT: 16.0,
    CONF_SETTLE_MINUTES: 120,
    CONF_SAMPLE_MINUTES: 10,
    CONF_MIN_SAMPLES: 72,
    CONF_MAX_AGE_DAYS: 10,
    CONF_EVALUATE_AT: "04:00:00",
    CONF_NOTIFY: "",
    "damping": 0.5,
    "max_shift_step": 3.0,
    "max_slope_step": 0.1,
    "shift_min": -13.0,
    "shift_max": 40.0,
    "slope_min": 0.2,
    "slope_max": 3.5,
    "deadband": 0.3,
    "min_outside_spread": 5.0,
}
