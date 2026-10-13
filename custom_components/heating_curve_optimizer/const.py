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
CONF_ROOMS = "rooms"  # thermostats de pièces (Better Thermostat…) pour le mode multi-pièces
CONF_WEATHER = "weather"
CONF_SOLAR_FILTER = "solar_filter"
CONF_SOLAR_CLOUD_MAX = "solar_cloud_max"
CONF_SOLAR_MIN_ELEVATION = "solar_min_elevation"
CONF_MIN_PRESSURE = "min_pressure"
CONF_SHORT_CYCLE_MINUTES = "short_cycle_minutes"
CONF_LEGIONELLA_WEEKDAY = "legionella_weekday"  # 0 = lundi … 6 = dimanche
CONF_LEGIONELLA_TIME = "legionella_time"
CONF_LEGIONELLA_TEMP = "legionella_temp"
CONF_LEGIONELLA_MINUTES = "legionella_minutes"
CONF_STANDBY_TEMP = "standby_temp"  # consigne de veille quand aucune pièce ne demande
CONF_DEMAND_DELAY = "demand_delay_minutes"
CONF_SUN_ANTICIPATION = "sun_anticipation"
CONF_GAS_PRICE = "gas_price"  # €/kWh
CONF_KWH_PER_M3 = "kwh_per_m3"
CONF_WEEKLY_REPORT = "weekly_report"
CONF_REPORT_WEEKDAY = "report_weekday"
CONF_REPORT_TIME = "report_time"

CONF_MAINTENANCE_MONTHS = "maintenance_months"
CONF_OVERCONSUMPTION_RATIO = "overconsumption_ratio"
CONF_DAILY_CHECK_TIME = "daily_check_time"

CONTROL_MODES = ("off", "simulation", "active")
NOTIFY_ACTION_APPLY = "HCO_APPLY"
NOTIFY_ACTION_IGNORE = "HCO_IGNORE"

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
    CONF_ROOMS: [],
    CONF_WEATHER: "",
    CONF_SOLAR_FILTER: True,
    CONF_SOLAR_CLOUD_MAX: 60.0,
    CONF_SOLAR_MIN_ELEVATION: 10.0,
    CONF_MIN_PRESSURE: 1.0,
    CONF_SHORT_CYCLE_MINUTES: 10.0,
    CONF_LEGIONELLA_WEEKDAY: "6",
    CONF_LEGIONELLA_TIME: "14:00:00",
    CONF_LEGIONELLA_TEMP: 60.0,
    CONF_LEGIONELLA_MINUTES: 90.0,
    CONF_STANDBY_TEMP: 15.0,
    CONF_DEMAND_DELAY: 20.0,
    CONF_SUN_ANTICIPATION: True,
    CONF_GAS_PRICE: 0.11,
    CONF_KWH_PER_M3: 11.0,
    CONF_WEEKLY_REPORT: True,
    CONF_REPORT_WEEKDAY: "0",
    CONF_REPORT_TIME: "08:00:00",
    CONF_MAINTENANCE_MONTHS: 12.0,
    CONF_OVERCONSUMPTION_RATIO: 1.3,
    CONF_DAILY_CHECK_TIME: "06:30:00",
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
