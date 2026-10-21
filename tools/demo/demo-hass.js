// Faux Home Assistant pour les captures d'écran du README : données fictives, aucune donnée réelle.
const params = new URLSearchParams(location.search);
const LANG = params.get("lang") || "fr";
const NOW = Math.floor(Date.now() / 1000); // le panneau calcule ses fenêtres par rapport à maintenant
const DAY = 86400;
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

const ROOMS = ["climate.salon", "climate.chambre_1", "climate.cuisine"];
const names = LANG === "fr"
  ? { "climate.vicare_heating": "Chaudière", "climate.salon": "Salon", "climate.chambre_1": "Chambre 1", "climate.cuisine": "Cuisine", "weather.home": "Météo" }
  : { "climate.vicare_heating": "Boiler", "climate.salon": "Living room", "climate.chambre_1": "Bedroom 1", "climate.cuisine": "Kitchen", "weather.home": "Weather" };

const st = (state, attributes = {}) => ({ state: String(state), attributes, last_updated: "2026-01-14T09:30:00Z" });
const states = {
  "climate.vicare_heating": st("auto", { friendly_name: names["climate.vicare_heating"], room_temperature: 19.4, temperature: 19, active_vicare_program: "comfortEnergySaving" }),
  "sensor.outside": st(2.5), "sensor.supply": st(44.6), "binary_sensor.burner": st("on"),
  "number.slope": st(0.9), "number.shift": st(4), "number.comfort": st(19), "number.normal": st(18), "number.reduced": st(17),
  "sensor.pressure": st(1.4), "number.dhw": st(55), "sensor.dhw_storage": st(51.8),
  "sensor.optimizer_status": st("collecte"),
  "climate.salon": st("heat", { friendly_name: names["climate.salon"], current_temperature: 19.2, temperature: 19.5, hvac_action: "heating", heating_power: 0.012 }),
  "climate.chambre_1": st("heat", { friendly_name: names["climate.chambre_1"], current_temperature: 18.1, temperature: 18, hvac_action: "idle", heating_power: 0.021 }),
  "climate.cuisine": st("heat", { friendly_name: names["climate.cuisine"], current_temperature: 20.3, temperature: 19, hvac_action: "idle", heating_power: 0.010 }),
  "weather.home": st("cloudy", { friendly_name: names["weather.home"] }),
};

// Mesures fictives : pièce limitante un peu froide par grand froid, un peu chaude à la mi-saison
const samples = [];
for (let i = 0; i < 240; i++) {
  const outside = -6 + rnd() * 17;
  samples.push({ t: NOW - (240 - i) * 900, outside, room: 19, target: 19,
    eff: +(0.04 * (outside - 3) + (rnd() - 0.5) * 0.5).toFixed(2), lim: ROOMS[i % 3] });
}
const schedule = {};
for (let d = 0; d < 7; d++) schedule[d] = d < 5 ? [["06:00", "08:30"], ["17:00", "22:30"]] : [["07:30", "23:00"]];
const decisionLog = [];
for (let h = 48; h >= 0; h -= 0.5) {
  const t = NOW - h * 3600;
  const hour = new Date(t * 1000).getUTCHours() + 1;
  let mode = "réduit";
  if ((hour >= 6 && hour < 9) || (hour >= 17 && hour < 23)) mode = rnd() < 0.25 ? "veille" : "confort";
  if (hour === 5) mode = "relance";
  if (hour === 13 && h < 30) mode = "soleil";
  const sp = { confort: 19, "réduit": 17, veille: 15, relance: 19, soleil: 18 }[mode];
  const last = decisionLog[decisionLog.length - 1];
  if (!last || last[1] !== mode) decisionLog.push([t, mode, sp]);
}
const pressureDays = {};
for (let i = 30; i >= 1; i--) {
  const d = new Date((NOW - i * DAY) * 1000).toISOString().slice(0, 10);
  pressureDays[d] = +(1.45 - (30 - i) * 0.002 + (rnd() - 0.5) * 0.04).toFixed(2);
}

const snapshot = () => ({
  language: LANG,
  entry_id: "demo",
  status: LANG === "fr" ? "collecte" : "collecting",
  auto: false,
  entities: { climate: "climate.vicare_heating", outside: "sensor.outside", slope: "number.slope", shift: "number.shift",
    room: null, supply: "sensor.supply", burner: "binary_sensor.burner", burner_starts: "sensor.starts", burner_hours: "sensor.hours",
    modulation: "sensor.modulation", pressure: "sensor.pressure", gas_heating_day: "sensor.gas_heating", gas_dhw_day: "sensor.gas_dhw",
    dhw_target: "number.dhw", dhw_storage: "sensor.dhw_storage", weather: "weather.home" },
  program_targets: { comfort: "number.comfort", normal: "number.normal", reduced: "number.reduced" },
  own: { status: "sensor.optimizer_status", auto: "switch.auto", evaluate: "button.evaluate", legionella: "switch.legionella",
    alert: "binary_sensor.alert", control_mode: "select.pilot" },
  rooms: ROOMS,
  settings: { min_samples: 72, heating_limit: 16, evaluate_at: "04:00:00", programs: ["comfortEnergySaving", "normalEnergySaving"],
    deadband: 0.3, max_slope_step: 0.1, max_shift_step: 3, min_pressure: 1, short_cycle_minutes: 10, solar_filter: true },
  samples,
  last_proposal: { t: NOW - 5 * 3600, slope: 0.9, shift: 4, new_slope: 1.0, new_shift: 3, mean_error: -0.04,
    reason: LANG === "fr" ? "ajustement pente + décalage (amplitude ext. 16.8 K)" : "slope and shift adjustment (outdoor range 16.8 K)" },
  history: [
    { t: NOW - 9 * DAY, slope: 0.2, shift: 25, new_slope: 0.3, new_shift: 20, mean_error: 1.8, reason: LANG === "fr" ? "réglage manuel" : "manual setting" },
    { t: NOW - 5 * DAY, slope: 0.3, shift: 20, new_slope: 0.6, new_shift: 9, mean_error: 0.9, reason: LANG === "fr" ? "proposition validée depuis le téléphone" : "proposal approved from the phone" },
    { t: NOW - 2 * DAY, slope: 0.6, shift: 9, new_slope: 0.9, new_shift: 4, mean_error: 0.5, reason: LANG === "fr" ? "ajustement pente + décalage (amplitude ext. 12.1 K)" : "slope and shift adjustment (outdoor range 12.1 K)" },
  ],
  last_change: NOW - 2 * DAY,
  alerts: {},
  burner_24h: { starts: 38, hours: 7, span_hours: 24, cycle_minutes: 11 },
  legionella: { enabled: true, weekday: 6, time: "14:00:00", temp: 60, minutes: 90, running: null, last: NOW - 3 * DAY },
  pilot: { mode: "simulation", schedule, temps: { comfort: 19, reduced: 17 }, standby_temp: 15, demand_delay: 20,
    state: { mode: "confort", setpoint: 19, reason: LANG === "fr" ? "période confort du planning" : "comfort period of the schedule", rooms: { "climate.salon": 19.5, "climate.chambre_1": 18 } },
    decision_log: decisionLog, preheat_rate: 1.4, standby_hours_7d: 23, trv_suggestion: schedule,
    forecast: { temps: [2, 1, 0, -1], clouds: [80, 70, 60, 60] }, originals: null,
    room_targets: { "climate.salon": { enabled: true, comfort: 19.5, reduced: 17 }, "climate.chambre_1": { enabled: true, comfort: 18, reduced: 16 },
      "climate.cuisine": { enabled: false, comfort: 19, reduced: 17 } } },
  costs: { gas_price: 0.11, kwh_per_m3: 11.0 },
  report: { enabled: true, weekday: 0, time: "08:00:00", notify: "mobile_app_phone" },
  computed_curve: { slope: 1.0, shift: 3, coefficient: 3.1, rms: 0.6 },
  writes: { used: 3, budget: 8 },
  gas_source: { entity: "sensor.gas_heating", to_m3: 1, meter: false },
  pressure_trend: -0.014,
  pressure_days: pressureDays,
  maintenance: { last: "2025-11-20", due: "2026-11-20", days_left: 310, burner_hours_since: 640, months: 12 },
  overconsumption_log: [{ t: NOW - 6 * DAY, kwh: 182, expected: 121 }],
});

// Statistiques long terme fictives (60 jours) : gaz ∝ degrés-jours, ajustement visible
function dailyStats() {
  const out = { "sensor.gas_heating": [], "sensor.gas_dhw": [], "sensor.outside": [], "sensor.starts": [], "sensor.hours": [] };
  for (let i = 60; i >= 1; i--) {
    const start = (Math.floor(NOW / DAY) - i) * DAY * 1000;
    const ext = 9 - (60 - i) * 0.17 + (rnd() - 0.5) * 4;
    const dju = Math.max(0, 18 - ext);
    const ratio = i > 2 * 1 + 7 ? 0.42 : 0.36;
    out["sensor.outside"].push({ start, mean: ext });
    out["sensor.gas_heating"].push({ start, change: +(dju * ratio * (0.9 + rnd() * 0.2)).toFixed(2) });
    out["sensor.gas_dhw"].push({ start, change: +(0.35 + rnd() * 0.2).toFixed(2) });
    out["sensor.starts"].push({ start, change: Math.round(20 + dju * 1.4 + rnd() * 8) });
    out["sensor.hours"].push({ start, change: Math.round(2 + dju * 0.35) });
  }
  return out;
}
function hourlyStats() {
  const out = { "sensor.supply": [], "sensor.modulation": [] };
  for (let h = 168; h >= 1; h--) {
    const start = (Math.floor(NOW / 3600) - h) * 3600 * 1000;
    out["sensor.supply"].push({ start, mean: 38 + rnd() * 20 });
    out["sensor.modulation"].push({ start, mean: rnd() < 0.6 ? 30 + rnd() * 40 : 0 });
  }
  return out;
}

window.demoHass = {
  language: LANG,
  locale: { language: LANG },
  themes: { darkMode: params.get("theme") === "dark" },
  states,
  entities: {},
  user: { is_admin: true },
  async callWS(msg) {
    switch (msg.type) {
      case "heating_curve_optimizer/get": return snapshot();
      case "recorder/statistics_during_period": return msg.period === "day" ? dailyStats() : hourlyStats();
      case "heating_curve_optimizer/recoveries":
        return { days: 7, advice: LANG === "fr"
          ? "Réduit bien réglé : 1.6 K perdus la nuit, consigne atteinte en 45 min."
          : "Night setback well tuned: 1.6 K lost overnight, setpoint reached in 45 min.",
          recoveries: [0, 1, 2, 3, 4].map((i) => ({ start: NOW - (i + 1) * DAY + 3600, room_start: 17.3 + rnd() * 0.4, target: 19, minutes: 35 + rnd() * 25, night_drop: 1.4 + rnd() * 0.5 })) };
      case "heating_curve_optimizer/diagnostics":
        return { kwh_per_m3: 11, thermal: {
            "2024-2025": { loss_w_per_k: 236, base_kwh_per_day: -18.2, r2: 0.91, days: 161, heating_limit: 15.3 },
            "2025-2026": { loss_w_per_k: 214, base_kwh_per_day: -17.0, r2: 0.88, days: 74, heating_limit: 15.5 } },
          rooms: [
            { entity_id: "climate.salon", heating_power: 0.012, relative: 1.0, advice: LANG === "fr" ? "équilibrée" : "balanced" },
            { entity_id: "climate.chambre_1", heating_power: 0.021, relative: 1.75, advice: LANG === "fr" ? "chauffe bien plus vite que les autres : refermer un peu son té de réglage" : "heats much faster than the others: close its lockshield valve a little" },
            { entity_id: "climate.cuisine", heating_power: 0.010, relative: 0.83, advice: LANG === "fr" ? "équilibrée" : "balanced" } ] };
      case "heating_curve_optimizer/weekly_report":
        return { text: LANG === "fr"
          ? "Gaz chauffage : 31.4 m³ (≈ 37.99 €).\n0.312 m³ par degré-jour (-9 % par rapport à la semaine précédente).\nAjustements de courbe : 1.\nChaudière mise en veille faute de demande : 23 h.\nAlertes : aucune."
          : "Heating gas: 31.4 m³ (≈ €37.99).\n0.312 m³ per degree-day (-9 % vs previous week).\nCurve adjustments: 1.\nBoiler in standby for lack of demand: 23 h.\nAlerts: none." };
      case "heating_curve_optimizer/bill_forecast":
        return { forecast: { consumed_kwh: 1420, remaining_kwh: 7310, total_kwh: 8730, total_cost: 1226, payments: 1284,
          balance: -58, period_start: "2026-04-11", period_end: "2027-04-11" } };
      case "heating_curve_optimizer/vicare_schedule": {
        const week = Object.fromEntries(["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => [d, [
          { start: "05:30", end: "07:00", mode: "normal", position: 0 }, { start: "07:00", end: "22:30", mode: "comfort", position: 1 }]]));
        return { current: week, constraints: { max_entries: 2, resolution: 10, modes: ["normal", "comfort"], writable: true },
          preheat_minutes: 90, proposals: { 0: week, 30: week, 60: week, 90: week, 120: week } };
      }
      case "heating_curve_optimizer/dhw_schedule": {
        const ev = (start) => [{ start: "00:00", end: "00:30", mode: "on", position: 0 }, { start, end: "24:00", mode: "on", position: 1 }];
        return { current: { mon: ev("18:00"), tue: ev("18:00"), wed: ev("18:00"), thu: ev("18:00"), fri: ev("18:00"), sat: ev("11:00"), sun: ev("11:00") },
          constraints: { max_entries: 2, resolution: 10, modes: ["on"], writable: true } };
      }
      case "scheduler": {
        const slot = (entity, start, stop, temperature) => ({ start: `${start}:00`, stop: `${stop}:00`, conditions: [],
          actions: [{ service: "climate.set_temperature", entity_id: entity, service_data: { hvac_mode: "heat", temperature } }] });
        const sched = (id, entity, name, weekdays, slots) => ({ schedule_id: id, entity_id: `switch.schedule_${id}`, name, weekdays, enabled: true,
          timeslots: slots.map(([a, b, temp]) => slot(entity, a, b, temp)) });
        return [
          sched("a1", "climate.chambre_1", "Chambre", ["workday"], [["00:00", "06:30", 17], ["06:30", "08:30", 19], ["08:30", "21:00", 17], ["21:00", "23:00", 19.5], ["23:00", "00:00", 17]]),
          sched("a2", "climate.salon", "Salon", ["daily"], [["00:00", "06:30", 18], ["06:30", "22:30", 20], ["22:30", "00:00", 18]]),
        ];
      }
      case "heating_curve_optimizer/get_settings": return demoSettings();
      case "heating_curve_optimizer/set_settings":
        (window.__calls = window.__calls || []).push(["ws", msg.type, msg.values]);
        return { saved: true };
      default: return {};
    }
  },
  callService(domain, service, data) { (window.__calls = window.__calls || []).push([domain, service, data]); return Promise.resolve(); },
  callApi() { return Promise.resolve({}); },
};

function demoSettings() {
  const fr = LANG === "fr";
  const L = (f, e) => (fr ? f : e);
  const fields = [
    { key: "programs", section: null, kind: "programs", label: L("Programmes ViCare pris en compte", "ViCare programs taken into account") },
    { key: "heating_limit", section: null, kind: "number", min: 5, max: 25, step: 0.5, unit: "°C", label: L("Pas de collecte au-dessus de cette T° extérieure", "No sampling above this outdoor temperature") },
    { key: "notify", section: null, kind: "notify", label: L("Service de notification", "Notification service") },
    { key: "rooms", section: "rooms_weather", kind: "entities", domain: "climate", label: L("Thermostats de pièces", "Room thermostats") },
    { key: "weather", section: "rooms_weather", kind: "entity", domain: "weather", label: L("Météo (couverture nuageuse)", "Weather (cloud coverage)") },
    { key: "solar_filter", section: "rooms_weather", kind: "bool", label: L("Ignorer les mesures par grand soleil", "Ignore samples in strong sunshine") },
    { key: "write_budget", section: "pilot", kind: "number", min: 2, max: 40, step: 1, label: L("Écritures ViCare autorisées par jour", "ViCare writes allowed per day") },
    { key: "standby_temp", section: "pilot", kind: "number", min: 5, max: 20, step: 1, unit: "°C", label: L("Consigne de veille", "Standby setpoint") },
    { key: "gas_price", section: "costs_report", kind: "number", min: 0.01, max: 1, step: 0.001, unit: "€/kWh", label: L("Prix du gaz", "Gas price") },
    { key: "gas_meter", section: "costs_report", kind: "entity", domain: "sensor", label: L("Compteur de gaz (Gazpar…)", "Gas meter (Gazpar…)") },
    { key: "report_weekday", section: "costs_report", kind: "weekday", label: L("Jour du bilan", "Report day") },
    { key: "billing_start", section: "billing", kind: "date", label: L("Début de la période de facturation", "Billing period start") },
    { key: "monthly_payment", section: "billing", kind: "number", min: 0, max: 1000, step: 0.01, unit: "€", label: L("Mensualité TTC", "Monthly instalment") },
    { key: "daily_check_time", section: "alerts", kind: "time", label: L("Heure des contrôles quotidiens", "Daily checks time") },
  ];
  return {
    sections: [
      { key: "rooms_weather", name: L("Pièces et météo", "Rooms and weather"), description: "" },
      { key: "pilot", name: L("Pilotage de la consigne", "Setpoint pilot"), description: "" },
      { key: "costs_report", name: L("Coûts et rapport hebdomadaire", "Costs and weekly report"), description: "" },
      { key: "billing", name: L("Facture et mensualités", "Bill and instalments"), description: "" },
      { key: "alerts", name: L("Alertes chaudière", "Boiler alerts"), description: "" },
    ],
    fields,
    values: { programs: ["comfortEnergySaving", "normalEnergySaving"], heating_limit: 16, notify: "mobile_app_phone",
      rooms: ["climate.salon", "climate.chambre_1"], weather: "weather.home", solar_filter: true, write_budget: 8, standby_temp: 15,
      gas_price: 0.1, gas_meter: "", billing_start: "2026-04-11", monthly_payment: 116.71, report_weekday: "0", daily_check_time: "06:30:00" },
    choices: {
      weekday: (fr ? ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        : ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).map((l, i) => ({ value: String(i), label: l })),
      programs: ["comfort", "comfortEnergySaving", "normal", "normalEnergySaving", "reduced"],
      climate: ROOMS.map((id) => ({ value: id, label: names[id] })),
      weather: [{ value: "weather.home", label: names["weather.home"] }],
      sensor: [{ value: "sensor.gazpar", label: "Gazpar" }],
      notify: ["mobile_app_phone", "phones"],
    },
  };
}
