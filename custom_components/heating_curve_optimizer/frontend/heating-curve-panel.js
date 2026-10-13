// Panneau « Courbe de chauffe » — composant web autonome (sans dépendance).
const DOMAIN = "heating_curve_optimizer";
const X_MIN = -15;
const X_MAX = 20;
const CHART_H = 300;
const MARGIN = { l: 44, r: 16, t: 14, b: 30 };
const SERIES = {
  light: { s1: "#2a78d6", s2: "#eb6834", s3: "#1baf7a", s4: "#eda100" },
  dark: { s1: "#3987e5", s2: "#d95926", s3: "#199e70", s4: "#c98500" },
};

// --- Modèle Viessmann (identique à heating_curve.py) -------------------------
const curveTerm = (d) => d * (1.4347 + 0.021 * d + 247.9e-6 * d * d);
const supplyAt = (ot, rt, slope, shift) => rt + shift - slope * curveTerm(ot - rt);

// --- Utilitaires --------------------------------------------------------------
const num = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
};
const fmt = (v, d = 1, signed = false) => {
  if (v == null) return "—";
  const s = v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  return signed && v > 0 ? `+${s}` : s;
};
const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const median = (arr) => {
  const a = [...arr].sort((x, y) => x - y);
  const m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const dateFr = (t) =>
  new Date(t * 1000).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

// Écart retenu pour une mesure : pièce limitante en multi-pièces, sinon sonde chaudière
const sampleErr = (s) => (s.eff != null ? s.eff : s.room - s.target);
const DAY = 86400000;
const dayLabel = (ms) => new Date(ms).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
const CONDENSING_MAX = 55; // °C de départ sous lesquels la condensation est assurée
const DJU_BASE = 18;
const toMin = (hhmm) => { const [h, m] = String(hhmm).split(":"); return +h * 60 + +m; };
const fromMin = (m) => (m >= 1440 ? "24:00" : `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);

function niceTicks(min, max, count = 5) {
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}

function binSamples(samples, deadClip = 3) {
  const groups = new Map();
  for (const s of samples) {
    const k = Math.floor(s.outside);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(s);
  }
  return [...groups.entries()]
    .filter(([, g]) => g.length >= 3)
    .sort((a, b) => a[0] - b[0])
    .map(([, g]) => ({
      outside: median(g.map((s) => s.outside)),
      error: median(g.map((s) => clamp(sampleErr(s), -deadClip, deadClip))),
      count: g.length,
    }));
}

const STYLE = `
:host { display:block; min-height:100vh; background:var(--primary-background-color); color:var(--primary-text-color);
  font-family:var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif); --gap:16px; }
* { box-sizing:border-box; }
.toolbar { display:flex; align-items:center; gap:8px; height:56px; padding:0 16px; background:var(--app-header-background-color, var(--primary-color));
  color:var(--app-header-text-color, #fff); font-size:20px; font-weight:400; }
.toolbar .title { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.content { max-width:1280px; margin:0 auto; padding:var(--gap); display:grid; gap:var(--gap); }
.card { background:var(--card-background-color, #fff); border-radius:var(--ha-card-border-radius, 12px);
  border:1px solid var(--divider-color); padding:16px; min-width:0; }
.card h2 { margin:0 0 4px; font-size:16px; font-weight:500; }
.card .sub { margin:0 0 12px; color:var(--secondary-text-color); font-size:13px; }
.status { display:flex; flex-wrap:wrap; align-items:center; gap:12px 20px; }
.status .state { display:flex; align-items:center; gap:10px; flex:1; min-width:220px; }
.status .state ha-icon { color:var(--secondary-text-color); }
.status .state b { font-weight:500; }
.status .state small { display:block; color:var(--secondary-text-color); font-size:13px; }
.mode { display:flex; align-items:center; gap:10px; font-size:14px; }
.mode small { display:block; color:var(--secondary-text-color); font-size:12px; }
.toggle { position:relative; width:40px; height:22px; border-radius:11px; border:none; padding:0; cursor:pointer;
  background:var(--disabled-color, #bdbdbd); transition:background .15s; flex:none; }
.toggle::after { content:""; position:absolute; top:3px; left:3px; width:16px; height:16px; border-radius:50%; background:#fff; transition:transform .15s; }
.toggle[aria-checked="true"] { background:var(--primary-color); }
.toggle[aria-checked="true"]::after { transform:translateX(18px); }
button.btn { font:inherit; font-size:14px; font-weight:500; border-radius:8px; padding:8px 14px; cursor:pointer;
  border:1px solid var(--divider-color); background:transparent; color:var(--primary-color); display:inline-flex; align-items:center; gap:6px; }
button.btn.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
button.btn:disabled { opacity:.45; cursor:default; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:var(--gap); }
.tile { display:flex; flex-direction:column; gap:2px; }
.tile .label { display:flex; align-items:center; gap:6px; color:var(--secondary-text-color); font-size:13px; }
.tile .label ha-icon { --mdc-icon-size:18px; }
.tile .value { font-size:26px; font-weight:500; font-variant-numeric:tabular-nums; }
.tile .value small { font-size:15px; font-weight:400; color:var(--secondary-text-color); }
.tile .hint { font-size:12px; color:var(--secondary-text-color); }
.main { display:grid; grid-template-columns:minmax(0, 2fr) minmax(280px, 1fr); gap:var(--gap); }
@media (max-width: 900px) { .main { grid-template-columns:1fr; } }
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:13px; color:var(--secondary-text-color); margin-bottom:8px; }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.key-line { width:18px; height:0; border-top:2px solid; }
.key-line.dashed { border-top-style:dashed; }
.key-dot { width:10px; height:10px; border-radius:50%; }
.chart { position:relative; width:100%; }
.chart svg { display:block; overflow:visible; }
.chart text { font-size:11px; fill:var(--secondary-text-color); font-variant-numeric:tabular-nums; }
.chart .grid { stroke:var(--divider-color); stroke-width:1; }
.chart .zero { stroke:var(--secondary-text-color); stroke-width:1; opacity:.6; }
.tooltip { position:absolute; pointer-events:none; background:var(--card-background-color, #fff); color:var(--primary-text-color);
  border:1px solid var(--divider-color); border-radius:8px; padding:8px 10px; font-size:12px; line-height:1.5;
  box-shadow:0 4px 12px rgba(0,0,0,.15); white-space:nowrap; display:none; z-index:2; }
.tooltip b { font-weight:500; }
.tooltip .row { display:flex; align-items:center; gap:6px; }
.tooltip .row i { width:10px; height:2px; display:inline-block; }
.empty { display:flex; align-items:center; justify-content:center; text-align:center; height:${CHART_H}px; padding:24px;
  color:var(--secondary-text-color); font-size:14px; border:1px dashed var(--divider-color); border-radius:8px; }
.ctrl { display:grid; gap:14px; }
.stepper { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.stepper .name { font-size:14px; }
.stepper .name small { display:block; color:var(--secondary-text-color); font-size:12px; }
.stepper .box { display:flex; align-items:center; border:1px solid var(--divider-color); border-radius:8px; overflow:hidden; }
.stepper button { width:36px; height:36px; border:none; background:transparent; color:var(--primary-color); font-size:20px; cursor:pointer; }
.stepper button:disabled { opacity:.35; cursor:default; }
.stepper output { min-width:56px; text-align:center; font-size:16px; font-weight:500; font-variant-numeric:tabular-nums; }
.stepper output.changed { color:var(--primary-color); }
.effect { font-size:13px; color:var(--secondary-text-color); background:var(--secondary-background-color); border-radius:8px; padding:10px 12px; line-height:1.6; }
.effect b { color:var(--primary-text-color); font-weight:500; font-variant-numeric:tabular-nums; }
.actions { display:flex; flex-wrap:wrap; gap:8px; }
.note { font-size:12px; color:var(--secondary-text-color); margin:0; }
.proposal { border-top:1px solid var(--divider-color); padding-top:14px; display:grid; gap:10px; }
.proposal p { margin:0; font-size:14px; }
.proposal small { color:var(--secondary-text-color); }
.meter { height:8px; border-radius:4px; overflow:hidden; margin:8px 0 4px; }
.meter > div { height:100%; border-radius:4px; }
.meta { display:flex; justify-content:space-between; font-size:12px; color:var(--secondary-text-color); }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; font-weight:500; color:var(--secondary-text-color); padding:6px 8px; border-bottom:1px solid var(--divider-color); }
td { padding:8px; border-bottom:1px solid var(--divider-color); font-variant-numeric:tabular-nums; white-space:nowrap; }
td:first-child { white-space:normal; }
tr:last-child td { border-bottom:none; }
.table-wrap { overflow-x:auto; }
.msg { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:var(--primary-text-color); color:var(--card-background-color, #fff);
  padding:10px 16px; border-radius:8px; font-size:14px; z-index:10; box-shadow:0 4px 12px rgba(0,0,0,.25); }
.err { color:var(--error-color, #db4437); }
.tabs { display:flex; gap:4px; overflow-x:auto; border-bottom:1px solid var(--divider-color); scrollbar-width:none; }
.tabs button { font:inherit; font-size:14px; font-weight:500; background:none; border:none; border-bottom:2px solid transparent; color:var(--secondary-text-color);
  padding:10px 14px; cursor:pointer; white-space:nowrap; display:inline-flex; align-items:center; gap:6px; }
.tabs button ha-icon { --mdc-icon-size:18px; }
.tabs button[aria-selected="true"] { color:var(--primary-color); border-bottom-color:var(--primary-color); }
.alert { display:flex; gap:12px; align-items:flex-start; border-radius:12px; padding:12px 16px; font-size:14px;
  background:color-mix(in srgb, var(--error-color, #db4437) 12%, var(--card-background-color, #fff)); border:1px solid color-mix(in srgb, var(--error-color, #db4437) 40%, transparent); }
.alert ha-icon { color:var(--error-color, #db4437); flex:none; }
.alert ul { margin:4px 0 0; padding-left:18px; }
.chip { display:inline-flex; align-items:center; gap:4px; font-size:12px; border-radius:10px; padding:2px 8px;
  background:var(--secondary-background-color); color:var(--secondary-text-color); white-space:nowrap; }
.chip.on { background:color-mix(in srgb, var(--warning-color, #ff9800) 18%, transparent); color:var(--primary-text-color); }
.chip.lim { background:color-mix(in srgb, var(--primary-color) 18%, transparent); color:var(--primary-text-color); }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:12px; margin-bottom:12px; }
.kpi .v { font-size:22px; font-weight:500; font-variant-numeric:tabular-nums; }
.kpi .v small { font-size:13px; color:var(--secondary-text-color); font-weight:400; }
.kpi .l { font-size:12px; color:var(--secondary-text-color); }
.advice { display:flex; gap:10px; align-items:flex-start; font-size:14px; background:var(--secondary-background-color); border-radius:8px; padding:10px 12px; margin-top:12px; }
.advice ha-icon { --mdc-icon-size:20px; color:var(--primary-color); flex:none; }
.seg { display:inline-flex; border:1px solid var(--divider-color); border-radius:8px; overflow:hidden; }
.seg button { font:inherit; font-size:14px; padding:8px 16px; border:none; background:transparent; color:var(--primary-text-color); cursor:pointer; }
.seg button + button { border-left:1px solid var(--divider-color); }
.seg button[aria-checked="true"] { background:var(--primary-color); color:var(--text-primary-color, #fff); }
.sched { display:grid; gap:3px; user-select:none; touch-action:none; overflow-x:auto; }
.sched-hours, .sched-row { display:grid; grid-template-columns:36px 1fr; align-items:center; min-width:520px; }
.sched-hours { grid-template-columns:36px repeat(8, 1fr); font-size:11px; color:var(--secondary-text-color); }
.sched-day { font-size:12px; color:var(--secondary-text-color); }
.sched-cells { display:grid; grid-template-columns:repeat(48, 1fr); gap:1px; }
.sched-cells .cell { height:26px; background:var(--secondary-background-color); cursor:pointer; }
.sched-cells .cell:nth-child(6n+1) { margin-left:1px; }
.sched-cells .cell.on { background:var(--primary-color); }
.sched-cells .cell:hover { outline:1px solid var(--primary-text-color); outline-offset:-1px; }
.bar { display:inline-block; width:120px; height:8px; border-radius:4px; background:var(--secondary-background-color); margin-right:8px; vertical-align:middle; overflow:hidden; }
.bar > div { height:100%; border-radius:4px; }
pre.report { white-space:pre-wrap; font-family:inherit; font-size:14px; background:var(--secondary-background-color); border-radius:8px; padding:12px; margin:0 0 12px; }
`;

class HeatingCurvePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._edit = null; // { slope, shift } en cours d'édition
    this._widths = {};
    this._charts = {};
    this._stats = null;
    this._recov = null;
    try {
      this._tab = localStorage.getItem("hco-tab") || "curve";
    } catch {
      this._tab = "curve";
    }
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
  }

  // ------------------------------------------------------------------ cycle de vie
  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._fetch();
      this._timer = setInterval(() => this._fetch(), 60000);
      return;
    }
    const statusId = this._data?.own?.status;
    const statusStamp = statusId && hass.states[statusId]?.last_updated;
    if (statusStamp && statusStamp !== this._statusStamp) {
      this._statusStamp = statusStamp;
      this._fetch();
      return;
    }
    const key = this._liveKey();
    if (key !== this._lastKey) this._render();
  }
  set narrow(v) {
    this._narrow = v;
    this._render();
  }
  set panel(_v) {}

  connectedCallback() {
    this._ro = new ResizeObserver((entries) => {
      let changed = false;
      for (const e of entries) {
        const id = e.target.dataset.chart;
        const w = Math.round(e.contentRect.width);
        if (id && Math.abs((this._widths[id] || 0) - w) > 2) {
          this._widths[id] = w;
          changed = true;
        }
      }
      if (changed) this._render();
    });
    this._render();
  }
  disconnectedCallback() {
    clearInterval(this._timer);
    this._ro?.disconnect();
  }

  async _fetch() {
    if (!this._hass) return;
    try {
      this._data = await this._hass.callWS({ type: `${DOMAIN}/get` });
      this._error = null;
    } catch (err) {
      this._error = err?.message || "Impossible de charger les données";
    }
    this._render();
  }

  // ------------------------------------------------------------------ état courant
  _state(id) {
    return id ? this._hass?.states[id] : undefined;
  }
  _liveKey() {
    const e = this._data?.entities || {};
    return [...Object.values(e), ...(this._data?.rooms || [])]
      .map((id) => this._state(id)?.last_updated)
      .join("|");
  }
  _live() {
    const e = this._data.entities;
    const climate = this._state(e.climate);
    const attrs = climate?.attributes || {};
    const program = attrs.active_vicare_program || "";
    let target = num(attrs.temperature);
    if (target == null) {
      // même repli que l'intégration : consigne du programme actif
      const base = program.replace(/EnergySaving$/, "").toLowerCase();
      target = num(this._state(this._data.program_targets?.[base])?.state);
    }
    return {
      program,
      target,
      room: e.room ? num(this._state(e.room)?.state) : num(attrs.room_temperature),
      outside: num(this._state(e.outside)?.state),
      supply: num(this._state(e.supply)?.state),
      burner: this._state(e.burner)?.state,
      slope: num(this._state(e.slope)?.state),
      shift: num(this._state(e.shift)?.state),
    };
  }
  _pendingProposal(live) {
    const p = this._data.last_proposal;
    if (!p || p.t <= (this._data.last_change || 0)) return null;
    if (p.new_slope === live.slope && p.new_shift === live.shift) return null;
    if (p.new_slope === p.slope && p.new_shift === p.shift) return null;
    return p;
  }
  _palette() {
    return SERIES[this._hass?.themes?.darkMode ? "dark" : "light"];
  }

  // ------------------------------------------------------------------ actions
  async _onClick(e) {
    const el = e.target.closest("[data-action]");
    if (!el || el.disabled) return;
    const live = this._live();
    const a = el.dataset.action;
    const s = this._data.settings;
    if (a === "toggle-auto") {
      const on = !this._data.auto;
      if (on && !confirm(
        "Activer l'ajustement automatique ?\n\nChaque nuit, l'optimiseur modifiera lui-même la courbe " +
        `de la chaudière (au plus ±${fmt(s.max_slope_step)} de pente et ±${fmt(s.max_shift_step, 0)} K de décalage).`
      )) return;
      await this._hass.callService("switch", on ? "turn_on" : "turn_off", { entity_id: this._data.own.auto });
      this._toast(on ? "Ajustement automatique activé" : "Mode simulation : plus aucune modification automatique");
      this._fetch();
    } else if (a === "evaluate") {
      await this._hass.callService("button", "press", { entity_id: this._data.own.evaluate });
      this._toast("Évaluation lancée");
      setTimeout(() => this._fetch(), 1500);
    } else if (a === "step") {
      const cur = this._edit || { slope: live.slope, shift: live.shift };
      const field = el.dataset.field;
      const delta = parseFloat(el.dataset.delta);
      const next = { ...cur };
      if (field === "slope") next.slope = +clamp(cur.slope + delta, 0.2, 3.5).toFixed(1);
      else next.shift = clamp(Math.round(cur.shift + delta), -13, 40);
      this._edit = next.slope === live.slope && next.shift === live.shift ? null : next;
      this._render();
    } else if (a === "reset") {
      this._edit = null;
      this._render();
    } else if (a === "apply-edit" && this._edit) {
      await this._setCurve(this._edit.slope, this._edit.shift, "réglage manuel", live);
    } else if (a === "apply-proposal") {
      const p = this._pendingProposal(live);
      if (p) await this._setCurve(p.new_slope, p.new_shift, "proposition validée manuellement", live);
    } else if (a === "tab") {
      this._tab = el.dataset.tab;
      try {
        localStorage.setItem("hco-tab", this._tab);
      } catch {}
      this._render();
    } else if (a === "toggle-legionella") {
      const on = !this._data.legionella.enabled;
      await this._hass.callService("switch", on ? "turn_on" : "turn_off", { entity_id: this._data.own.legionella });
      this._toast(on ? "Montée anti-légionelle hebdomadaire activée" : "Montée anti-légionelle désactivée");
      this._fetch();
    } else if (a === "set-dhw") {
      const v = parseFloat(el.dataset.value);
      if (!confirm(`Régler la consigne d'eau chaude sur ${v} °C ?`)) return;
      await this._hass.callService("number", "set_value", { entity_id: this._data.entities.dhw_target, value: v });
      this._toast(`Consigne d'eau chaude envoyée : ${v} °C`);
    } else if (a === "pilot-mode") {
      const mode = el.dataset.mode;
      if (mode === "active" && !confirm(
        "Activer le pilotage ?\n\nLe pilote écrira la consigne du programme actif de la chaudière (planning, veille sans demande, " +
        "relance anticipée). Les consignes d'origine sont mémorisées et remises si tu repasses en Désactivé ou Simulation.")) return;
      try {
        this._data = await this._hass.callWS({ type: `${DOMAIN}/set_control_mode`, mode });
        this._toast({ off: "Pilotage désactivé", simulation: "Pilotage en simulation", active: "Pilotage actif" }[mode]);
      } catch (err) {
        this._toast(`Échec : ${err?.message || err}`);
      }
      this._render();
    } else if (a === "draft-temp") {
      const k = el.dataset.key;
      this._draftTemps[k] = clamp(this._draftTemps[k] + +el.dataset.delta, k === "comfort" ? 10 : 5, k === "comfort" ? 26 : 24);
      this._draftDirty = true;
      this._render();
    } else if (a === "save-schedule") {
      try {
        this._data = await this._hass.callWS({
          type: `${DOMAIN}/set_schedule`, schedule: this._scheduleFromDraft(this._draft),
          comfort: this._draftTemps.comfort, reduced: this._draftTemps.reduced,
        });
        this._draft = null;
        this._toast("Planning enregistré");
      } catch (err) {
        this._toast(`Échec : ${err?.message || err}`);
      }
      this._render();
    } else if (a === "reset-schedule") {
      this._draft = null;
      this._render();
    } else if (a === "import-trv") {
      this._draft = this._draftFromSchedule(this._data.pilot.trv_suggestion);
      this._draftDirty = true;
      this._toast("Planning des têtes importé : vérifie puis enregistre");
      this._render();
    } else if (a === "copy-monday") {
      for (let d = 1; d < 5; d++) this._draft[d] = [...this._draft[0]];
      this._draftDirty = true;
      this._render();
    } else if (a === "send-report") {
      try {
        await this._hass.callWS({ type: `${DOMAIN}/weekly_report`, send: true });
        this._toast("Bilan envoyé");
      } catch (err) {
        this._toast(`Échec : ${err?.message || err}`);
      }
    } else if (a === "reload-diag") {
      this._diag = null;
      this._render();
    } else if (a === "reload-stats") {
      this._stats = null;
      this._recov = null;
      this._render();
    } else if (a === "load-proposal") {
      const p = this._pendingProposal(live);
      if (p) this._edit = { slope: p.new_slope, shift: p.new_shift };
      this._render();
    }
  }

  async _setCurve(slope, shift, reason, live) {
    const twoSteps = slope !== live.slope && shift !== live.shift;
    const msg =
      `Appliquer sur la chaudière ?\n\nPente ${fmt(live.slope)} → ${fmt(slope)}\n` +
      `Décalage ${fmt(live.shift, 0, true)} → ${fmt(shift, 0, true)}` +
      (twoSteps ? "\n\nLa pente est écrite tout de suite, le décalage environ 5 min après (contrainte ViCare)." : "");
    if (!confirm(msg)) return;
    try {
      this._data = await this._hass.callWS({ type: `${DOMAIN}/set_curve`, slope, shift, reason });
      this._edit = null;
      this._toast(twoSteps ? "Pente envoyée, décalage dans ~5 min" : "Courbe envoyée à la chaudière");
    } catch (err) {
      this._toast(`Échec : ${err?.message || err}`);
    }
    this._render();
  }

  _toast(text) {
    this._msgText = text;
    this._render();
    clearTimeout(this._msgTimer);
    this._msgTimer = setTimeout(() => {
      this._msgText = null;
      this._render();
    }, 4000);
  }

  // ------------------------------------------------------------------ rendu
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    this._lastKey = this._data ? this._liveKey() : null;
    const root = this.shadowRoot;
    let body;
    if (this._error) body = `<div class="card err">${esc(this._error)}</div>`;
    else if (!this._data) body = `<div class="card">Chargement…</div>`;
    else body = this._body();
    root.innerHTML = `<style>${STYLE}</style>
      <div class="toolbar"><span class="menu"></span><span class="title">Courbe de chauffe</span></div>
      <div class="content">${body}</div>
      ${this._msgText ? `<div class="msg" role="status">${esc(this._msgText)}</div>` : ""}`;

    if (this._narrow) {
      const mb = document.createElement("ha-menu-button");
      mb.hass = this._hass;
      mb.narrow = this._narrow;
      root.querySelector(".menu").appendChild(mb);
    }
    this._ro?.disconnect();
    root.querySelectorAll("[data-chart]").forEach((el) => this._ro?.observe(el));
    this._bindHover();
    this._bindSchedule();
  }

  _body() {
    const d = this._data;
    const live = this._live();
    const pal = this._palette();
    const proposal = this._pendingProposal(live);
    const s = d.settings;
    const mean = d.samples.length
      ? d.samples.reduce((acc, x) => acc + sampleErr(x), 0) / d.samples.length
      : null;
    const curveNow =
      live.outside != null && live.target != null && live.slope != null
        ? supplyAt(live.outside, live.target, live.slope, live.shift)
        : null;

    const status = `
      <div class="card status">
        <div class="state">
          <ha-icon icon="mdi:information-outline"></ha-icon>
          <div><b>${esc(d.status)}</b>
            <small>Programme ${esc(live.program || "—")} · évaluation chaque jour à ${esc(String(s.evaluate_at).slice(0, 5))}${d.pilot.mode !== "off" && d.pilot.state
              ? ` · pilotage ${d.pilot.mode === "active" ? "actif" : "simulé"} : ${esc(d.pilot.state.mode)} ${fmt(d.pilot.state.setpoint, 0)} °C` : ""}</small></div>
        </div>
        <div class="mode">
          <button class="toggle" role="switch" aria-checked="${d.auto}" aria-label="Ajustement automatique" data-action="toggle-auto"></button>
          <div>${d.auto ? "Ajustement automatique" : "Simulation"}
            <small>${d.auto ? "la courbe est modifiée chaque nuit" : "propose sans rien modifier"}</small></div>
        </div>
        <button class="btn" data-action="evaluate"><ha-icon icon="mdi:calculator-variant" style="--mdc-icon-size:18px"></ha-icon>Évaluer maintenant</button>
      </div>`;

    const tile = (icon, label, value, unit, hint) => `
      <div class="card tile">
        <span class="label"><ha-icon icon="${icon}"></ha-icon>${label}</span>
        <span class="value">${value}${unit ? ` <small>${unit}</small>` : ""}</span>
        <span class="hint">${hint}</span>
      </div>`;
    const tiles = `<div class="tiles">
      ${tile("mdi:home-thermometer-outline", "Ambiance", fmt(live.room), "°C", `consigne ${fmt(live.target, 0)} °C`)}
      ${tile("mdi:thermometer-lines", "Écart moyen mesuré", fmt(mean, 2, true), "K", `${d.samples.length} mesure${d.samples.length > 1 ? "s" : ""} en cours`)}
      ${tile("mdi:sun-thermometer-outline", "Extérieur", fmt(live.outside), "°C", `chauffe surveillée sous ${fmt(s.heating_limit, 0)} °C`)}
      ${tile("mdi:water-thermometer-outline", "Départ chaudière", fmt(live.supply), "°C", `courbe à cette T° ext. : ${fmt(curveNow)} °C`)}
      ${tile("mdi:chart-bell-curve-cumulative", "Courbe actuelle", `${fmt(live.slope)} <small>·</small> ${fmt(live.shift, 0, true)}`, "", "pente · décalage (K)")}
      ${tile("mdi:fire", "Brûleur", live.burner === "on" ? "Allumé" : live.burner === "off" ? "Éteint" : "—", "", "état en direct")}
    </div>`;

    // Courbe alternative affichée : édition en cours, sinon proposition
    const alt = this._edit
      ? { label: "Réglage en cours", ...this._edit }
      : proposal
        ? { label: "Proposition", slope: proposal.new_slope, shift: proposal.new_shift }
        : null;

    const curveCard = `
      <div class="card">
        <h2>Courbe de chauffe</h2>
        <p class="sub">Température de départ calculée selon la température extérieure (consigne ${fmt(live.target, 0)} °C)</p>
        <div class="legend">
          <span><i class="key-line" style="border-color:${pal.s1}"></i>Actuelle (pente ${fmt(live.slope)}, décalage ${fmt(live.shift, 0, true)})</span>
          ${alt ? `<span><i class="key-line dashed" style="border-color:${pal.s2}"></i>${alt.label} (pente ${fmt(alt.slope)}, décalage ${fmt(alt.shift, 0, true)})</span>`
            : `<span style="visibility:hidden" aria-hidden="true"><i class="key-line dashed"></i>Réglage en cours (pente 0,0, décalage +00)</span>`}
          ${live.supply != null && live.outside != null ? `<span><i class="key-dot" style="background:var(--primary-text-color)"></i>Départ mesuré maintenant</span>` : ""}
        </div>
        ${this._curveChart(live, alt, pal)}
      </div>`;

    const control = this._controlCard(live, proposal);

    const errorCard = `
      <div class="card">
        <h2>Écart ambiance − consigne</h2>
        <p class="sub">Mesures collectées depuis le dernier ajustement, selon la température extérieure</p>
        ${d.samples.length ? `<div class="legend">
          <span><i class="key-dot" style="background:${pal.s1};opacity:.5"></i>Mesure (toutes les 10 min)</span>
          <span><i class="key-dot" style="background:${pal.s2}"></i>Médiane par tranche de 1 °C</span>
          <span><i class="key-dot" style="background:var(--secondary-text-color);opacity:.25"></i>Tolérance ±${fmt(s.deadband)} K</span>
        </div>` : ""}
        ${this._errorChart(d.samples, s, pal)}
        ${this._progress(d, s, pal)}
      </div>`;

    const history = d.history.length
      ? `<div class="table-wrap"><table>
          <thead><tr><th>Date</th><th>Pente</th><th>Décalage</th><th>Écart moyen</th><th>Origine</th></tr></thead>
          <tbody>${[...d.history].reverse().map((h) => `<tr>
            <td>${dateFr(h.t)}</td>
            <td>${fmt(h.slope)} → ${fmt(h.new_slope)}</td>
            <td>${fmt(h.shift, 0, true)} → ${fmt(h.new_shift, 0, true)}</td>
            <td>${fmt(h.mean_error, 2, true)} K</td>
            <td>${esc(h.reason)}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="sub" style="margin:0">Aucun ajustement pour l'instant.</p>`;

    const alerts = Object.values(d.alerts || {});
    const alertBanner = alerts.length
      ? `<div class="alert" role="alert"><ha-icon icon="mdi:alert-circle"></ha-icon>
          <div><b>Alerte chaudière</b><ul>${alerts.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div></div>`
      : "";
    const tabs = [
      ["curve", "mdi:chart-bell-curve-cumulative", "Courbe"],
      ["planning", "mdi:calendar-clock", "Planning"],
      ["rooms", "mdi:home-thermometer-outline", "Pièces"],
      ["savings", "mdi:piggy-bank-outline", "Économies"],
      ["boiler", "mdi:fire", "Chaudière"],
      ["dhw", "mdi:water-boiler", "Eau chaude"],
      ["diag", "mdi:stethoscope", "Diagnostic"],
    ];
    const nav = `<nav class="tabs" role="tablist">${tabs
      .map(([k, icon, label]) =>
        `<button role="tab" aria-selected="${this._tab === k}" data-action="tab" data-tab="${k}"><ha-icon icon="${icon}"></ha-icon>${label}</button>`)
      .join("")}</nav>`;

    let content;
    if (this._tab === "planning") content = this._planningTab(pal);
    else if (this._tab === "diag") content = this._diagnosticTab(pal);
    else if (this._tab === "rooms") content = this._roomsTab(live);
    else if (this._tab === "savings") content = this._savingsTab(pal);
    else if (this._tab === "boiler") content = this._boilerTab(pal);
    else if (this._tab === "dhw") content = this._dhwTab();
    else content = `${tiles}
      <div class="main">${curveCard}${control}</div>
      ${errorCard}
      <div class="card"><h2>Historique des ajustements</h2>${history}</div>`;
    return `${status}${alertBanner}${nav}${content}`;
  }

  // ------------------------------------------------------------------ données long terme
  _ensureStats() {
    if (this._stats || this._statsLoading) return;
    this._statsLoading = true;
    const e = this._data.entities;
    const now = Date.now();
    const iso = (ms) => new Date(ms).toISOString();
    const daily = [e.gas_heating_day, e.gas_dhw_day, e.outside, e.burner_starts, e.burner_hours].filter(Boolean);
    const hourly = [e.supply, e.modulation].filter(Boolean);
    const startDay = new Date(now - 60 * DAY);
    startDay.setHours(0, 0, 0, 0);
    Promise.all([
      this._hass.callWS({
        type: "recorder/statistics_during_period", start_time: iso(startDay.getTime()), end_time: iso(now),
        statistic_ids: daily, period: "day", types: ["change", "mean"],
      }),
      this._hass.callWS({
        type: "recorder/statistics_during_period", start_time: iso(now - 7 * DAY), end_time: iso(now),
        statistic_ids: hourly, period: "hour", types: ["mean"],
      }),
    ])
      .then(([day, hour]) => {
        this._stats = { day, hour, at: now };
      })
      .catch((err) => {
        this._stats = { error: err?.message || String(err) };
      })
      .finally(() => {
        this._statsLoading = false;
        this._render();
      });
  }

  _ensureRecoveries() {
    if (this._recov || this._recovLoading) return;
    this._recovLoading = true;
    this._hass
      .callWS({ type: `${DOMAIN}/recoveries`, days: 7 })
      .then((r) => {
        this._recov = r;
      })
      .catch((err) => {
        this._recov = { error: err?.message || String(err) };
      })
      .finally(() => {
        this._recovLoading = false;
        this._render();
      });
  }

  _dailySeries(id, type) {
    const rows = (id && this._stats?.day?.[id]) || [];
    return rows.map((r) => ({ t: r.start, v: r[type] })).filter((r) => r.v != null);
  }

  // ------------------------------------------------------------------ onglet Pièces
  _roomsTab(live) {
    const d = this._data;
    const counts = {};
    for (const smp of d.samples) if (smp.lim) counts[smp.lim] = (counts[smp.lim] || 0) + 1;
    const withLim = Object.values(counts).reduce((a, b) => a + b, 0);
    const name = (id) => this._state(id)?.attributes.friendly_name || id;
    const rows = [{
      id: d.entities.climate,
      label: `${name(d.entities.climate)} (sonde chaudière)`,
      cur: live.room,
      tgt: live.target,
      demand: live.room != null && live.target != null && live.room < live.target,
      window: false,
    }];
    for (const id of d.rooms) {
      const st = this._state(id);
      const a = st?.attributes || {};
      rows.push({
        id, label: name(id), cur: num(a.current_temperature), tgt: num(a.temperature),
        demand: a.hvac_action === "heating", window: !!(a.window_open || a.window_state === "on"),
        off: !st || st.state === "off",
      });
    }
    const table = `<div class="table-wrap"><table>
      <thead><tr><th>Pièce</th><th>Ambiance</th><th>Consigne</th><th>Écart</th><th>État</th><th>Limitante</th></tr></thead>
      <tbody>${rows.map((r) => {
        const err = r.cur != null && r.tgt != null ? r.cur - r.tgt : null;
        const share = withLim ? Math.round(((counts[r.id] || 0) / withLim) * 100) : null;
        const chips = [
          r.off ? `<span class="chip">arrêt</span>`
            : r.demand ? `<span class="chip on">demande de chaleur</span>` : `<span class="chip">satisfaite</span>`,
          r.window ? `<span class="chip">fenêtre ouverte</span>` : "",
        ].join(" ");
        return `<tr><td>${esc(r.label)}</td><td>${fmt(r.cur)} °C</td><td>${fmt(r.tgt)} °C</td>
          <td>${fmt(err, 1, true)} K</td><td>${chips}</td>
          <td>${share != null ? `<span class="chip ${share >= 40 ? "lim" : ""}">${share} % du temps</span>` : "—"}</td></tr>`;
      }).join("")}</tbody></table></div>`;
    const explain = d.rooms.length
      ? `La courbe est réglée pour la pièce la plus difficile à chauffer : parmi les pièces qui demandent de la chaleur,
         c'est la plus froide qui décide. Quand plus aucune ne demande, la marge de la moins chaude permet de baisser la courbe.`
      : `Mode multi-pièces inactif : seule la sonde de la chaudière est utilisée. Ajoute tes thermostats dans
         Paramètres › Appareils et services › Optimiseur de courbe de chauffe › Configurer › Pièces et météo.`;
    return `<div class="card"><h2>Pièces suivies</h2><p class="sub">${explain}</p>${table}
      ${withLim ? `<p class="note" style="margin-top:10px">« Limitante » : part des ${withLim} mesures en cours où la pièce a fixé l'écart retenu.</p>` : ""}
      ${d.settings.solar_filter && d.entities.weather ? `<p class="note" style="margin-top:6px">Filtre solaire actif : les mesures prises par grand soleil sont ignorées (${esc(name(d.entities.weather))}).</p>` : ""}</div>`;
  }

  // ------------------------------------------------------------------ onglet Économies
  _savingsTab(pal) {
    this._ensureStats();
    this._ensureRecoveries();
    const d = this._data;
    let body;
    if (!this._stats) body = `<div class="empty">Chargement des statistiques…</div>`;
    else if (this._stats.error) body = `<div class="empty err">${esc(this._stats.error)}</div>`;
    else {
      const gas = new Map(this._dailySeries(d.entities.gas_heating_day, "change").map((r) => [r.t, r.v]));
      const days = this._dailySeries(d.entities.outside, "mean").map((r) => {
        const dju = Math.max(0, DJU_BASE - r.v);
        const g = gas.get(r.t);
        return { t: r.t, dju, gas: g ?? null, ratio: g != null && dju >= 2 ? g / dju : null, ext: r.v };
      });
      const changes = d.history.map((h) => h.t * 1000);
      const last = changes.length ? changes[changes.length - 1] : null;
      const ratioOf = (list) => {
        const ok = list.filter((x) => x.gas != null && x.dju >= 2);
        const dju = ok.reduce((a, x) => a + x.dju, 0);
        return dju >= 20 ? ok.reduce((a, x) => a + x.gas, 0) / dju : null;
      };
      const before = last ? ratioOf(days.filter((x) => x.t < last && x.t >= last - 21 * DAY)) : null;
      const after = last ? ratioOf(days.filter((x) => x.t >= last)) : null;
      const ref = ratioOf(days.slice(-30));
      const delta = before && after ? ((after - before) / before) * 100 : null;
      const totalGas = days.slice(-30).reduce((a, x) => a + (x.gas || 0), 0);
      const c = d.costs;
      const eur = (m3) => m3 * c.kwh_per_m3 * c.gas_price;
      const dju30 = days.slice(-30).reduce((a, x) => a + x.dju, 0);
      const saving = before && after && after < before ? eur((before - after) * dju30) : null;
      body = `<div class="kpis">
          <div class="kpi"><div class="v">${fmt(ref > 0 ? ref : null, 3)}</div><div class="l">m³ par degré-jour (30 j)</div></div>
          <div class="kpi"><div class="v">${fmt(totalGas, 0)} m³ <small>≈ ${fmt(eur(totalGas), 0)} €</small></div><div class="l">gaz chauffage sur 30 j (${fmt(c.gas_price, 3)} €/kWh)</div></div>
          <div class="kpi"><div class="v">${saving != null ? `${fmt(saving, 0)} €` : "—"}</div><div class="l">économie estimée sur 30 j depuis le dernier ajustement</div></div>
          <div class="kpi"><div class="v">${fmt(before, 3)}</div><div class="l">m³/DJU avant le dernier ajustement</div></div>
          <div class="kpi"><div class="v">${fmt(after, 3)}${delta != null ? ` <small>(${fmt(delta, 0, true)} %)</small>` : ""}</div><div class="l">m³/DJU depuis</div></div>
        </div>
        <div class="legend"><span><i class="key-dot" style="background:${pal.s1}"></i>m³ de gaz par degré-jour (base ${DJU_BASE} °C)</span>
          ${changes.length ? `<span><i class="key-line" style="border-color:${pal.s2}"></i>Ajustement de la courbe</span>` : ""}</div>
        ${!days.some((x) => x.gas > 0)
          ? `<div class="empty">Aucune consommation de gaz de chauffage sur la période : la saison de chauffe n'a pas encore commencé.</div>`
          : this._columnChart("dju", days.filter((x) => x.ratio != null && x.ratio > 0), (x) => x.ratio, pal.s1, {
          fmtY: (v) => fmt(v, 2),
          markers: changes,
          tip: (x) => `<b>${dayLabel(x.t)}</b><div>${fmt(x.gas, 1)} m³ · ${fmt(x.dju, 1)} DJU (ext. ${fmt(x.ext)} °C)</div><div><b>${fmt(x.ratio, 3)}</b> m³/DJU</div>`,
          empty: "Pas encore assez de jours de chauffe (au moins 2 degrés-jours par jour).",
        })}
        <p class="note" style="margin-top:8px">Un degré-jour (DJU) mesure le besoin de chauffage : ${DJU_BASE} °C moins la température extérieure moyenne du jour.
          Diviser le gaz par les DJU compare des périodes de météo différente : si le ratio baisse après un ajustement, l'économie est réelle.</p>`;
    }
    return `<div class="card"><h2>Consommation corrigée de la météo</h2>
        <p class="sub">Gaz de chauffage par degré-jour sur 60 jours
          <button class="btn" style="padding:2px 8px;margin-left:6px" data-action="reload-stats">Actualiser</button></p>${body}</div>
      ${this._recoveryCard()}`;
  }

  _recoveryCard() {
    const r = this._recov;
    let body;
    if (!r) body = `<p class="sub">Analyse de l'historique…</p>`;
    else if (r.error) body = `<p class="sub err">${esc(r.error)}</p>`;
    else {
      const rows = r.recoveries.slice(-7).reverse();
      body = rows.length
        ? `<div class="table-wrap"><table>
          <thead><tr><th>Relance</th><th>Baisse la nuit</th><th>Ambiance → consigne</th><th>Consigne atteinte en</th></tr></thead>
          <tbody>${rows.map((x) => `<tr><td>${dateFr(x.start)}</td><td>${fmt(x.night_drop, 1)} K</td>
            <td>${fmt(x.room_start)} °C → ${fmt(x.target, 0)} °C</td>
            <td>${x.minutes == null ? "non atteinte" : `${fmt(x.minutes, 0)} min`}</td></tr>`).join("")}</tbody></table></div>`
        : "";
      body += `<div class="advice"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><div>${esc(r.advice)}</div></div>`;
    }
    return `<div class="card"><h2>Réduit de nuit</h2><p class="sub">Relances du matin sur les 7 derniers jours (sonde de la chaudière)</p>${body}</div>`;
  }

  // ------------------------------------------------------------------ onglet Chaudière
  _boilerTab(pal) {
    this._ensureStats();
    const d = this._data;
    const e = d.entities;
    const b = d.burner_24h;
    const pressure = num(this._state(e.pressure)?.state);
    let cond = null;
    let daily = `<div class="empty">Chargement des statistiques…</div>`;
    if (this._stats?.error) daily = `<div class="empty err">${esc(this._stats.error)}</div>`;
    else if (this._stats) {
      const sup = this._stats.hour?.[e.supply] || [];
      const mod = new Map((this._stats.hour?.[e.modulation] || []).map((r) => [r.start, r.mean]));
      const running = sup.filter((r) => (mod.get(r.start) ?? 0) > 0 && r.mean != null);
      cond = running.length ? (running.filter((r) => r.mean < CONDENSING_MAX).length / running.length) * 100 : null;
      const hours = new Map(this._dailySeries(e.burner_hours, "change").map((r) => [r.t, r.v]));
      const days = this._dailySeries(e.burner_starts, "change").slice(-30)
        .map((r) => ({ t: r.t, starts: r.v, hours: hours.get(r.t) ?? null }));
      daily = this._columnChart("starts", days, (x) => x.starts, pal.s1, {
        fmtY: (v) => fmt(v, 0),
        tip: (x) => `<b>${dayLabel(x.t)}</b><div>${fmt(x.starts, 0)} démarrages</div>` +
          (x.hours ? `<div>${fmt(x.hours, 0)} h de flamme · ${fmt((x.hours * 60) / Math.max(1, x.starts), 0)} min par cycle</div>` : ""),
        empty: "Pas encore de statistiques de démarrage.",
      });
    }
    const cycleWarn = b?.cycle_minutes != null && b.cycle_minutes < d.settings.short_cycle_minutes;
    const advice = cycleWarn
      ? "Cycles courts : la chaudière s'allume et s'éteint souvent. Un départ moins chaud (courbe plus basse) allonge les cycles et améliore le rendement."
      : cond != null && cond < 50
        ? `Moins de la moitié du temps de chauffe se fait avec un départ sous ${CONDENSING_MAX} °C : baisser la courbe améliorerait la condensation, donc le rendement.`
        : b || cond != null ? "Fonctionnement correct." : "Les indicateurs se remplissent au fil des heures de chauffe.";
    return `<div class="card"><h2>Brûleur et rendement</h2>
        <p class="sub">Une chaudière à condensation récupère la chaleur des fumées quand l'eau revient froide : un départ sous ${CONDENSING_MAX} °C la garantit.</p>
        <div class="kpis">
          <div class="kpi"><div class="v">${b ? fmt(b.starts, 0) : "—"}</div><div class="l">démarrages sur ${b ? fmt(b.span_hours, 0) : 24} h</div></div>
          <div class="kpi"><div class="v">${b?.cycle_minutes != null ? `${fmt(b.cycle_minutes, 0)} min` : "—"}</div>
            <div class="l">de flamme par démarrage${cycleWarn ? " · <b>cycles courts</b>" : ""}</div></div>
          <div class="kpi"><div class="v">${cond != null ? `${fmt(cond, 0)} %` : "—"}</div><div class="l">du temps de chauffe en condensation (7 j)</div></div>
          <div class="kpi"><div class="v">${fmt(pressure, 1)} bar</div><div class="l">pression d'eau (alerte sous ${fmt(d.settings.min_pressure, 1)} bar)</div></div>
        </div>
        <div class="legend"><span><i class="key-dot" style="background:${pal.s1}"></i>Démarrages du brûleur par jour (30 j)</span></div>
        ${daily}
        <div class="advice"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><div>${advice}</div></div>
      </div>`;
  }

  // ------------------------------------------------------------------ onglet Eau chaude
  _dhwTab() {
    this._ensureStats();
    const d = this._data;
    const e = d.entities;
    const target = num(this._state(e.dhw_target)?.state);
    const storage = num(this._state(e.dhw_storage)?.state);
    const lg = d.legionella;
    const weekdays = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];
    let share = "";
    if (this._stats && !this._stats.error) {
      const sum = (id) => this._dailySeries(id, "change").slice(-30).reduce((a, r) => a + r.v, 0);
      const dhw = sum(e.gas_dhw_day);
      const heat = sum(e.gas_heating_day);
      share = `<div class="kpi"><div class="v">${fmt(dhw, 1)} m³</div><div class="l">gaz eau chaude sur 30 j${heat + dhw > 0 ? ` (${fmt((dhw / (heat + dhw)) * 100, 0)} % du total)` : ""}</div></div>`;
    }
    const reco = target != null && target > 50
      ? `<div class="advice"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon><div>
          Consigne à ${fmt(target, 0)} °C : 50 °C suffisent au quotidien et réduisent les pertes du ballon, à condition d'activer
          la montée hebdomadaire à ${fmt(lg.temp, 0)} °C contre la légionelle (ci-dessous).
          <div class="actions" style="margin-top:8px"><button class="btn primary" data-action="set-dhw" data-value="50">Passer à 50 °C</button></div></div></div>`
      : "";
    return `<div class="card"><h2>Eau chaude sanitaire</h2>
        <div class="kpis">
          <div class="kpi"><div class="v">${fmt(target, 0)} °C</div><div class="l">consigne</div></div>
          <div class="kpi"><div class="v">${fmt(storage)} °C</div><div class="l">ballon actuellement</div></div>
          ${share}
        </div>${reco}</div>
      <div class="card status">
        <div class="state"><ha-icon icon="mdi:bacteria-outline"></ha-icon><div><b>Montée anti-légionelle hebdomadaire</b>
          <small>Chaque ${weekdays[lg.weekday]} à ${esc(String(lg.time).slice(0, 5))} : ${fmt(lg.temp, 0)} °C pendant ${fmt(lg.minutes, 0)} min,
          puis retour à la consigne${lg.running ? " · <b>en cours</b>" : lg.last ? ` · dernière le ${dateFr(lg.last)}` : ""}</small></div></div>
        <div class="mode"><button class="toggle" role="switch" aria-checked="${lg.enabled}" aria-label="Montée anti-légionelle" data-action="toggle-legionella"></button>
          <div>${lg.enabled ? "Activée" : "Désactivée"}</div></div>
      </div>`;
  }

  // ------------------------------------------------------------------ onglet Planning
  _draftFromSchedule(schedule) {
    const draft = {};
    for (let d = 0; d < 7; d++) {
      const cells = new Array(48).fill(false);
      for (const [s, e] of schedule[d] || schedule[String(d)] || []) {
        const a = Math.round(toMin(s) / 30);
        const b = Math.round(toMin(e) / 30);
        for (let i = a; i < b && i < 48; i++) cells[i] = true;
      }
      draft[d] = cells;
    }
    return draft;
  }

  _scheduleFromDraft(draft) {
    const out = {};
    for (let d = 0; d < 7; d++) {
      const periods = [];
      let start = null;
      draft[d].forEach((on, i) => {
        if (on && start === null) start = i;
        if (!on && start !== null) { periods.push([fromMin(start * 30), fromMin(i * 30)]); start = null; }
      });
      if (start !== null) periods.push([fromMin(start * 30), "24:00"]);
      out[d] = periods;
    }
    return out;
  }

  _planningTab(pal) {
    const p = this._data.pilot;
    if (!this._draft) {
      this._draft = this._draftFromSchedule(p.schedule);
      this._draftTemps = { ...p.temps };
      this._draftDirty = false;
    }
    const st = p.state;
    const modes = [["off", "Désactivé"], ["simulation", "Simulation"], ["active", "Actif"]];
    const modeColors = { confort: pal.s1, veille: pal.s2, relance: pal.s3, soleil: pal.s4, "réduit": "var(--disabled-color, #9e9e9e)" };
    const modeLabels = { confort: "Confort", veille: "Veille (pas de demande)", relance: "Relance anticipée", soleil: "Soleil attendu", "réduit": "Réduit" };
    const seg = `<div class="seg" role="radiogroup" aria-label="Pilotage">${modes.map(([k, l]) =>
      `<button role="radio" aria-checked="${p.mode === k}" data-action="pilot-mode" data-mode="${k}">${l}</button>`).join("")}</div>`;
    const explain = {
      off: "Le planning et les consignes de la chaudière s'appliquent comme d'habitude.",
      simulation: "Le pilote calcule la consigne qu'il appliquerait, sans rien écrire sur la chaudière : regarde la frise ci-dessous pendant quelques jours.",
      active: "Le pilote écrit la consigne du programme actif de la chaudière. Les consignes d'origine seront remises si tu le désactives.",
    }[p.mode];
    const decision = st
      ? `<div class="kpis" style="margin-top:12px">
          <div class="kpi"><div class="v">${fmt(st.setpoint, 0)} °C</div><div class="l">consigne ${p.mode === "active" ? "appliquée" : "calculée"}</div></div>
          <div class="kpi"><div class="v"><span class="chip" style="font-size:14px"><i class="key-dot" style="background:${modeColors[st.mode]}"></i>${esc(modeLabels[st.mode] || st.mode)}</span></div>
            <div class="l">${esc(st.reason)}</div></div>
          <div class="kpi"><div class="v">${p.preheat_rate ? `${fmt(p.preheat_rate, 1)} K/h` : "—"}</div><div class="l">vitesse de relance apprise</div></div>
          <div class="kpi"><div class="v">${fmt(p.standby_hours_7d, 0)} h</div><div class="l">de veille sur 7 jours${p.mode === "simulation" ? " (simulées)" : ""}</div></div>
        </div>` : "";

    const days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
    const grid = `<div class="sched" role="grid" aria-label="Planning hebdomadaire">
      <div class="sched-hours"><span></span>${Array.from({ length: 8 }, (_, i) => `<span>${String(i * 3).padStart(2, "0")}h</span>`).join("")}</div>
      ${days.map((label, d) => `<div class="sched-row"><span class="sched-day">${label}</span><div class="sched-cells">${this._draft[d]
        .map((on, i) => `<div class="cell ${on ? "on" : ""}" data-day="${d}" data-cell="${i}" title="${label} ${fromMin(i * 30)}–${fromMin((i + 1) * 30)}"></div>`).join("")}</div></div>`).join("")}
    </div>`;
    const t = this._draftTemps;
    const stepper = (key, label) => `
      <div class="stepper"><span class="name">${label}</span><span class="box">
        <button data-action="draft-temp" data-key="${key}" data-delta="-1" aria-label="Diminuer">−</button>
        <output>${fmt(t[key], 0)} °C</output>
        <button data-action="draft-temp" data-key="${key}" data-delta="1" aria-label="Augmenter">+</button></span></div>`;
    const log = (p.decision_log || []);
    const timeline = log.length ? this._timeline(log, modeColors, modeLabels) : `<p class="sub">Aucune décision enregistrée pour l'instant.</p>`;
    return `<div class="card"><h2>Pilotage de la consigne</h2>
        <p class="sub">${explain}</p>${seg}${decision}
        <p class="note" style="margin-top:8px">Veille : ${fmt(p.standby_temp, 0)} °C après ${fmt(p.demand_delay, 0)} min sans demande de chaleur.
          ${p.forecast?.temps?.length ? `Prévisions : ${fmt(Math.min(...p.forecast.temps.slice(0, 4)), 0)} °C au plus bas sur 4 h.` : ""}</p></div>
      <div class="card"><h2>Planning de la semaine</h2>
        <p class="sub">Clique ou glisse sur la grille : bleu = confort, vide = réduit (pas de 30 min).</p>
        <div class="grid2" style="margin-bottom:12px">${stepper("comfort", "Consigne confort")}${stepper("reduced", "Consigne réduite")}</div>
        ${grid}
        <div class="actions" style="margin-top:12px">
          <button class="btn primary" data-action="save-schedule" ${this._draftDirty ? "" : "disabled"}>Enregistrer</button>
          <button class="btn" data-action="reset-schedule" ${this._draftDirty ? "" : "disabled"}>Annuler</button>
          <button class="btn" data-action="import-trv" ${p.trv_suggestion ? "" : "disabled"}>Importer depuis les têtes thermostatiques</button>
          <button class="btn" data-action="copy-monday">Copier le lundi sur les jours ouvrés</button>
        </div></div>
      <div class="card"><h2>Décisions des dernières 48 h</h2>${timeline}</div>`;
  }

  _timeline(log, colors, labels) {
    const w = this._widths.timeline || 600;
    const now = Date.now() / 1000;
    const t0 = now - 48 * 3600;
    const x = (t) => 40 + ((Math.max(t, t0) - t0) / (now - t0)) * (w - 52);
    const segs = log.map((e, i) => ({ t: e[0], mode: e[1], sp: e[2], end: i + 1 < log.length ? log[i + 1][0] : now }))
      .filter((s) => s.end > t0);
    const ticks = [];
    for (let k = 0; k <= 4; k++) ticks.push(t0 + (k * 12) * 3600);
    const used = [...new Set(segs.map((s) => s.mode))];
    this._charts.timeline = {
      f: { w, iw: w - 52 },
      generic: (px) => {
        const t = t0 + ((px - 40) / (w - 52)) * (now - t0);
        const s = segs.find((z) => z.t <= t && t < z.end) || segs[segs.length - 1];
        return { x: px, y: 22, html: `<b>${esc(labels[s.mode] || s.mode)}</b><div>${fmt(s.sp, 0)} °C · ${dateFr(s.t)} → ${dateFr(s.end)}</div>` };
      },
    };
    return `<div class="legend">${used.map((m) => `<span><i class="key-dot" style="background:${colors[m]}"></i>${esc(labels[m] || m)}</span>`).join("")}</div>
      <div class="chart" data-chart="timeline"><svg width="${w}" height="64" role="img" aria-label="Frise des décisions du pilote">
        ${segs.map((s) => `<rect x="${x(s.t)}" y="8" width="${Math.max(1, x(s.end) - x(s.t) - 1)}" height="28" rx="3" fill="${colors[s.mode] || "gray"}"/>`).join("")}
        ${ticks.map((t) => `<text x="${x(t)}" y="56" text-anchor="middle">${new Date(t * 1000).toLocaleString("fr-FR", { weekday: "short", hour: "2-digit" })}</text>`).join("")}
        <g class="hover" style="display:none"><circle r="4" fill="var(--primary-text-color)"/></g>
        <rect class="hit" x="40" y="4" width="${w - 52}" height="36" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }

  _bindSchedule() {
    const grid = this.shadowRoot.querySelector(".sched");
    if (!grid) return;
    const paint = (cell) => {
      const d = +cell.dataset.day;
      const i = +cell.dataset.cell;
      if (this._draft[d][i] === this._paintValue) return;
      this._draft[d][i] = this._paintValue;
      cell.classList.toggle("on", this._paintValue);
      this._draftDirty = true;
      this.shadowRoot.querySelectorAll('[data-action="save-schedule"],[data-action="reset-schedule"]').forEach((b) => { b.disabled = false; });
    };
    grid.addEventListener("pointerdown", (e) => {
      const cell = e.target.closest(".cell");
      if (!cell) return;
      e.preventDefault();
      this._painting = true;
      this._paintValue = !this._draft[+cell.dataset.day][+cell.dataset.cell];
      paint(cell);
    });
    grid.addEventListener("pointerover", (e) => {
      const cell = e.target.closest(".cell");
      if (cell && this._painting) paint(cell);
    });
    const stop = () => { this._painting = false; };
    grid.addEventListener("pointerup", stop);
    grid.addEventListener("pointerleave", stop);
  }

  // ------------------------------------------------------------------ onglet Diagnostic
  _ensureDiagnostics() {
    if (this._diag || this._diagLoading) return;
    this._diagLoading = true;
    Promise.all([
      this._hass.callWS({ type: `${DOMAIN}/diagnostics` }),
      this._hass.callWS({ type: `${DOMAIN}/weekly_report` }),
    ])
      .then(([diag, report]) => { this._diag = { ...diag, report: report.text }; })
      .catch((err) => { this._diag = { error: err?.message || String(err) }; })
      .finally(() => { this._diagLoading = false; this._render(); });
  }

  _diagnosticTab(pal) {
    this._ensureDiagnostics();
    const g = this._diag;
    if (!g) return `<div class="card"><div class="empty">Analyse en cours…</div></div>`;
    if (g.error) return `<div class="card"><div class="empty err">${esc(g.error)}</div></div>`;
    const name = (id) => this._state(id)?.attributes.friendly_name || id;
    const seasons = Object.entries(g.thermal || {});
    const thermal = seasons.length
      ? `<div class="table-wrap"><table><thead><tr><th>Saison de chauffe</th><th>Déperditions</th><th>Talon</th><th>Fiabilité (R²)</th><th>Jours</th></tr></thead>
        <tbody>${seasons.map(([season, t]) => t.loss_w_per_k != null
          ? `<tr><td>${esc(season)}</td><td><b>${fmt(t.loss_w_per_k, 0)} W/K</b></td><td>${fmt(t.base_kwh_per_day, 1)} kWh/j</td><td>${fmt(t.r2, 2)}</td><td>${t.days}</td></tr>`
          : `<tr><td>${esc(season)}</td><td colspan="4">pas assez de jours de chauffe (${t.days})</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">Pas encore de statistiques de gaz.</div>`;
    const rooms = g.rooms || [];
    const maxRel = Math.max(1.8, ...rooms.map((r) => r.relative));
    const balance = rooms.length
      ? `<div class="table-wrap"><table><thead><tr><th>Pièce</th><th>Puissance de chauffe relative</th><th>Conseil</th></tr></thead>
        <tbody>${rooms.map((r) => `<tr><td>${esc(name(r.entity_id))}</td>
          <td><div class="bar"><div style="width:${(r.relative / maxRel) * 100}%;background:${pal.s1}"></div></div>${fmt(r.relative * 100, 0)} % de la médiane</td>
          <td style="white-space:normal">${esc(r.advice)}</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">Il faut au moins deux pièces suivies avec Better Thermostat (onglet Pièces).</div>`;
    return `<div class="card"><h2>Bilan thermique de la maison</h2>
        <p class="sub">Déperditions estimées à partir du gaz consommé et de l'écart intérieur / extérieur, jour par jour (rendement supposé 95 %).
          Moins de W/K = maison mieux isolée : compare les saisons avant et après des travaux.</p>${thermal}</div>
      <div class="card"><h2>Équilibrage des radiateurs</h2>
        <p class="sub">Vitesse de chauffe apprise par Better Thermostat pour chaque pièce, comparée à la médiane. Un radiateur qui chauffe beaucoup plus vite
          que les autres « vole » l'eau chaude aux pièces lentes.</p>${balance}</div>
      <div class="card"><h2>Bilan hebdomadaire</h2>
        <p class="sub">${this._data.report.enabled ? `Envoyé chaque ${["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][this._data.report.weekday]} à ${esc(String(this._data.report.time).slice(0, 5))}` : "Envoi désactivé"}
          ${this._data.report.notify ? `sur ${esc(this._data.report.notify)} et` : ""} dans les notifications de Home Assistant.</p>
        <pre class="report">${esc(g.report || "")}</pre>
        <div class="actions"><button class="btn" data-action="send-report">Envoyer maintenant</button>
          <button class="btn" data-action="reload-diag">Actualiser</button></div></div>`;
  }

  // ------------------------------------------------------------------ graphique en colonnes (une série, par jour)
  _columnChart(id, rows, value, color, opts = {}) {
    if (!rows.length) return `<div class="chart" data-chart="${id}"><div class="empty">${esc(opts.empty || "Pas de données")}</div></div>`;
    const w = this._widths[id] || 600;
    const h = 220;
    const m = { l: 44, r: 12, t: 10, b: 28 };
    const iw = w - m.l - m.r;
    const ih = h - m.t - m.b;
    const t0 = rows[0].t;
    const t1 = rows[rows.length - 1].t;
    const span = Math.max(1, Math.round((t1 - t0) / DAY) + 1);
    const slot = iw / span;
    const bw = Math.max(2, Math.min(24, slot - 2));
    const x = (t) => m.l + ((t - t0) / DAY + 0.5) * slot;
    const max = Math.max(...rows.map(value)) || 1;
    const ticks = niceTicks(0, max * 1.1, 4);
    const yMax = ticks[ticks.length - 1] || max;
    const y = (v) => m.t + (1 - v / yMax) * ih;
    const every = Math.max(1, Math.ceil(span / Math.max(2, Math.floor(iw / 70))));
    const labels = [];
    for (let i = 0; i < span; i += every) labels.push(t0 + i * DAY);
    const bar = (r) => {
      const top = y(value(r));
      const hh = Math.max(0, m.t + ih - top);
      const rr = Math.min(4, bw / 2, hh);
      const x0 = x(r.t) - bw / 2;
      return `<path d="M${x0},${m.t + ih}V${top + rr}Q${x0},${top} ${x0 + rr},${top}H${x0 + bw - rr}Q${x0 + bw},${top} ${x0 + bw},${top + rr}V${m.t + ih}Z" fill="${color}"/>`;
    };
    const markers = (opts.markers || []).filter((t) => t >= t0 - DAY / 2 && t <= t1 + DAY);
    this._charts[id] = {
      f: { w, iw },
      generic: (px) => {
        const t = t0 + Math.floor((px - m.l) / slot) * DAY;
        const r = rows.reduce((best, z) => (Math.abs(z.t - t) < Math.abs(best.t - t) ? z : best));
        return { x: x(r.t), y: y(value(r)), html: opts.tip ? opts.tip(r) : fmt(value(r)) };
      },
    };
    return `<div class="chart" data-chart="${id}">
      <svg width="${w}" height="${h}" role="img">
        ${ticks.map((v) => `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${y(v)}" y2="${y(v)}"/>
          <text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${opts.fmtY ? opts.fmtY(v) : v}</text>`).join("")}
        ${labels.map((t) => `<text x="${x(t)}" y="${h - 8}" text-anchor="middle">${dayLabel(t)}</text>`).join("")}
        ${rows.map(bar).join("")}
        ${markers.map((t) => `<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${m.t + ih}" stroke="${this._palette().s2}" stroke-width="2"/>`).join("")}
        <g class="hover" style="display:none"><circle r="5" fill="var(--primary-text-color)" stroke="var(--card-background-color)" stroke-width="2"/></g>
        <rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }


  _controlCard(live, proposal) {
    const cur = this._edit || { slope: live.slope, shift: live.shift };
    const changed = !!this._edit;
    const t = live.target ?? 20;
    const effect = [-10, 0, 10]
      .map((ot) => {
        const a = live.slope != null ? supplyAt(ot, t, live.slope, live.shift) : null;
        const b = supplyAt(ot, t, cur.slope, cur.shift);
        return `à ${ot} °C : <b>${fmt(a, 0)}${changed ? ` → ${fmt(b, 0)}` : ""} °C</b>`;
      })
      .join("<br>");
    const stepper = (field, label, hint, value, step, min, max, signed) => `
      <div class="stepper">
        <span class="name">${label}<small>${hint}</small></span>
        <span class="box">
          <button data-action="step" data-field="${field}" data-delta="${-step}" ${value <= min ? "disabled" : ""} aria-label="Diminuer">−</button>
          <output class="${changed && value !== live[field] ? "changed" : ""}">${fmt(value, field === "slope" ? 1 : 0, signed)}</output>
          <button data-action="step" data-field="${field}" data-delta="${step}" ${value >= max ? "disabled" : ""} aria-label="Augmenter">+</button>
        </span>
      </div>`;
    const proposalBlock = proposal
      ? `<div class="proposal">
          <p><b>Proposition</b> <small>· ${dateFr(proposal.t)}</small></p>
          <p>Pente ${fmt(proposal.slope)} → <b>${fmt(proposal.new_slope)}</b>, décalage ${fmt(proposal.shift, 0, true)} → <b>${fmt(proposal.new_shift, 0, true)}</b><br>
            <small>${esc(proposal.reason)} · écart moyen ${fmt(proposal.mean_error, 2, true)} K</small></p>
          <div class="actions">
            <button class="btn primary" data-action="apply-proposal">Appliquer la proposition</button>
            <button class="btn" data-action="load-proposal">Ajuster avant</button>
          </div>
        </div>`
      : "";
    return `
      <div class="card ctrl">
        <div><h2>Réglage manuel</h2><p class="sub" style="margin:0">Modifie la courbe et visualise l'effet avant d'appliquer</p></div>
        ${stepper("slope", "Pente", "inclinaison de la courbe", cur.slope, 0.1, 0.2, 3.5, false)}
        ${stepper("shift", "Décalage", "translation verticale (K)", cur.shift, 1, -13, 40, true)}
        <div class="effect">Température de départ<br>${effect}</div>
        <div class="actions">
          <button class="btn primary" data-action="apply-edit" ${changed ? "" : "disabled"}>Appliquer à la chaudière</button>
          <button class="btn" data-action="reset" ${changed ? "" : "disabled"}>Annuler</button>
        </div>
        <p class="note">Un réglage appliqué remet à zéro les mesures en cours : elles décrivaient l'ancienne courbe.</p>
        ${proposalBlock}
      </div>`;
  }

  _progress(d, s, pal) {
    const pct = Math.min(100, (d.samples.length / s.min_samples) * 100);
    return `
      <div class="meter" style="background:${pal.s1}26"><div style="width:${pct}%;background:${pal.s1}"></div></div>
      <div class="meta"><span>${pct >= 100 ? `${d.samples.length} mesures, minimum de ${s.min_samples} atteint : évaluation possible` : `${d.samples.length} / ${s.min_samples} mesures avant la prochaine évaluation`}</span>
        <span>${pct >= 100 ? "prêt" : `${Math.round(pct)} %`}</span></div>`;
  }

  // ------------------------------------------------------------------ graphiques
  _frame(id) {
    const w = this._widths[id] || 600;
    const iw = w - MARGIN.l - MARGIN.r;
    const ih = CHART_H - MARGIN.t - MARGIN.b;
    const x = (v) => MARGIN.l + ((v - X_MIN) / (X_MAX - X_MIN)) * iw;
    return { w, iw, ih, x };
  }

  _axes(f, y, yTicks, yFmt) {
    const xTicks = niceTicks(X_MIN, X_MAX, 7);
    return `
      ${yTicks.map((v) => `<line class="grid" x1="${MARGIN.l}" x2="${f.w - MARGIN.r}" y1="${y(v)}" y2="${y(v)}"/>
        <text x="${MARGIN.l - 8}" y="${y(v) + 4}" text-anchor="end">${yFmt(v)}</text>`).join("")}
      ${xTicks.map((v) => `<text x="${f.x(v)}" y="${CHART_H - 8}" text-anchor="middle">${v} °C</text>`).join("")}`;
  }

  _curveChart(live, alt, pal) {
    const id = "curve";
    if (live.slope == null || live.target == null) {
      return `<div class="chart" data-chart="${id}"><div class="empty">Pente, décalage ou consigne indisponibles pour l'instant.</div></div>`;
    }
    const f = this._frame(id);
    const t = live.target;
    const xs = [];
    for (let v = X_MIN; v <= X_MAX + 1e-9; v += 0.5) xs.push(v);
    const curves = [{ key: "cur", label: "Actuelle", slope: live.slope, shift: live.shift, color: pal.s1, dash: "" }];
    if (alt) curves.push({ key: "alt", label: alt.label, slope: alt.slope, shift: alt.shift, color: pal.s2, dash: "6 4" });
    const all = curves.flatMap((c) => xs.map((v) => supplyAt(v, t, c.slope, c.shift)));
    if (live.supply != null) all.push(live.supply);
    const yMin = Math.floor((Math.min(...all) - 3) / 5) * 5;
    const yMax = Math.ceil((Math.max(...all) + 3) / 5) * 5;
    const y = (v) => MARGIN.t + (1 - (v - yMin) / (yMax - yMin)) * f.ih;
    const limit = this._data.settings.heating_limit;
    const path = (c) => xs.map((v, i) => `${i ? "L" : "M"}${f.x(v).toFixed(1)},${y(supplyAt(v, t, c.slope, c.shift)).toFixed(1)}`).join("");
    const op = live.outside != null && live.supply != null && live.outside >= X_MIN && live.outside <= X_MAX;

    this._charts[id] = {
      f,
      tip: (ot) => `<b>${fmt(ot)} °C extérieur</b>` +
        curves.map((c) => `<div class="row"><i style="background:${c.color}"></i>${esc(c.label)} : ${fmt(supplyAt(ot, t, c.slope, c.shift))} °C</div>`).join(""),
      dots: (ot) => curves.map((c) => ({ x: f.x(ot), y: y(supplyAt(ot, t, c.slope, c.shift)), color: c.color })),
    };
    return `<div class="chart" data-chart="${id}">
      <svg width="${f.w}" height="${CHART_H}" role="img" aria-label="Courbe de chauffe : température de départ selon la température extérieure">
        ${limit < X_MAX ? `<rect x="${f.x(limit)}" y="${MARGIN.t}" width="${f.x(X_MAX) - f.x(limit)}" height="${f.ih}" fill="var(--divider-color)" opacity=".35"/>
          <text x="${f.x(X_MAX) - 6}" y="${MARGIN.t + 14}" text-anchor="end">hors chauffe</text>` : ""}
        ${CONDENSING_MAX > yMin ? `<rect x="${MARGIN.l}" y="${y(Math.min(CONDENSING_MAX, yMax))}" width="${f.iw}" height="${y(yMin) - y(Math.min(CONDENSING_MAX, yMax))}" fill="${pal.s1}" opacity=".07"/>
          <text x="${MARGIN.l + 6}" y="${y(Math.min(CONDENSING_MAX, yMax)) + 14}">condensation assurée (départ &lt; ${CONDENSING_MAX} °C)</text>` : ""}
        ${this._axes(f, y, niceTicks(yMin, yMax, 5), (v) => `${v}°`)}
        ${curves.map((c) => `<path d="${path(c)}" fill="none" stroke="${c.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" ${c.dash ? `stroke-dasharray="${c.dash}"` : ""}/>`).join("")}
        ${op ? `<circle cx="${f.x(live.outside)}" cy="${y(live.supply)}" r="5" fill="var(--primary-text-color)" stroke="var(--card-background-color)" stroke-width="2"/>` : ""}
        <g class="hover" style="display:none">
          <line class="cross" y1="${MARGIN.t}" y2="${MARGIN.t + f.ih}" stroke="var(--secondary-text-color)" stroke-width="1" opacity=".5"/>
          ${curves.map(() => `<circle r="4.5" stroke="var(--card-background-color)" stroke-width="2"/>`).join("")}
        </g>
        <rect class="hit" x="${MARGIN.l}" y="${MARGIN.t}" width="${f.iw}" height="${f.ih}" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }

  _errorChart(samples, s, pal) {
    const id = "error";
    if (!samples.length) {
      return `<div class="chart" data-chart="${id}"><div class="empty">
        Pas encore de mesures. La collecte démarre quand il fait moins de ${fmt(s.heating_limit, 0)} °C dehors
        et que la chaudière est en programme ${esc(s.programs.join(", "))} depuis au moins 2 h.</div></div>`;
    }
    const f = this._frame(id);
    const pts = samples.map((p) => ({ outside: p.outside, error: clamp(sampleErr(p), -3, 3) }));
    const bins = binSamples(samples);
    const lim = Math.max(1, Math.ceil(Math.max(...pts.map((p) => Math.abs(p.error)), s.deadband)));
    const y = (v) => MARGIN.t + (1 - (v + lim) / (2 * lim)) * f.ih;
    const inX = (v) => v >= X_MIN && v <= X_MAX;

    this._charts[id] = {
      f,
      nearest: (ot) => {
        const pool = bins.length ? bins : pts.map((p) => ({ ...p, count: 1 }));
        return pool.reduce((best, b) => (Math.abs(b.outside - ot) < Math.abs(best.outside - ot) ? b : best));
      },
      tipFor: (b) => `<b>≈ ${fmt(b.outside)} °C extérieur</b>
        <div class="row"><i style="background:${pal.s2}"></i>Écart ${bins.length ? "médian" : ""} : ${fmt(b.error, 2, true)} K</div>
        <div>${b.count} mesure${b.count > 1 ? "s" : ""}</div>
        <div style="color:var(--secondary-text-color)">${b.error > s.deadband ? "trop chaud" : b.error < -s.deadband ? "trop froid" : "dans la tolérance"}</div>`,
      pos: (b) => ({ x: f.x(b.outside), y: y(b.error) }),
    };
    return `<div class="chart" data-chart="${id}">
      <svg width="${f.w}" height="${CHART_H}" role="img" aria-label="Écart entre température ambiante et consigne selon la température extérieure">
        <rect x="${MARGIN.l}" y="${y(s.deadband)}" width="${f.iw}" height="${y(-s.deadband) - y(s.deadband)}" fill="var(--secondary-text-color)" opacity=".12"/>
        ${this._axes(f, y, niceTicks(-lim, lim, 4), (v) => `${v > 0 ? "+" : ""}${v} K`)}
        <line class="zero" x1="${MARGIN.l}" x2="${f.w - MARGIN.r}" y1="${y(0)}" y2="${y(0)}"/>
        <text x="${f.w - MARGIN.r}" y="${y(lim) + 12}" text-anchor="end">trop chaud ↑</text>
        <text x="${f.w - MARGIN.r}" y="${y(-lim) - 6}" text-anchor="end">trop froid ↓</text>
        ${pts.filter((p) => inX(p.outside)).map((p) => `<circle cx="${f.x(p.outside).toFixed(1)}" cy="${y(p.error).toFixed(1)}" r="4" fill="${pal.s1}" opacity=".35"/>`).join("")}
        ${bins.length > 1 ? `<path d="${bins.map((b, i) => `${i ? "L" : "M"}${f.x(b.outside).toFixed(1)},${y(b.error).toFixed(1)}`).join("")}" fill="none" stroke="${pal.s2}" stroke-width="2" stroke-linejoin="round"/>` : ""}
        ${bins.map((b) => `<circle cx="${f.x(b.outside)}" cy="${y(b.error)}" r="5" fill="${pal.s2}" stroke="var(--card-background-color)" stroke-width="2"/>`).join("")}
        <g class="hover" style="display:none"><circle r="7" fill="none" stroke="var(--primary-text-color)" stroke-width="2"/></g>
        <rect class="hit" x="${MARGIN.l}" y="${MARGIN.t}" width="${f.iw}" height="${f.ih}" fill="transparent"/>
      </svg><div class="tooltip"></div></div>`;
  }

  _bindHover() {
    this.shadowRoot.querySelectorAll("[data-chart]").forEach((el) => {
      const id = el.dataset.chart;
      const chart = this._charts[id];
      const hit = el.querySelector(".hit");
      if (!chart || !hit) return;
      const g = el.querySelector(".hover");
      const tip = el.querySelector(".tooltip");
      const place = (px, py, html) => {
        tip.innerHTML = html;
        tip.style.display = "block";
        const tw = tip.offsetWidth;
        const left = px + 14 + tw > chart.f.w ? px - 14 - tw : px + 14;
        tip.style.left = `${Math.max(0, left)}px`;
        tip.style.top = `${Math.max(0, py - tip.offsetHeight / 2)}px`;
      };
      hit.addEventListener("pointermove", (e) => {
        const rect = hit.ownerSVGElement.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const ot = clamp(X_MIN + ((px - MARGIN.l) / chart.f.iw) * (X_MAX - X_MIN), X_MIN, X_MAX);
        g.style.display = "";
        if (chart.generic) {
          const hit2 = chart.generic(px);
          const c = g.querySelector("circle");
          c.setAttribute("cx", hit2.x);
          c.setAttribute("cy", hit2.y);
          place(hit2.x, hit2.y, hit2.html);
        } else if (id === "curve") {
          const r = Math.round(ot * 2) / 2;
          const dots = chart.dots(r);
          const line = g.querySelector(".cross");
          line.setAttribute("x1", dots[0].x);
          line.setAttribute("x2", dots[0].x);
          g.querySelectorAll("circle").forEach((c, i) => {
            c.setAttribute("cx", dots[i].x);
            c.setAttribute("cy", dots[i].y);
            c.setAttribute("fill", dots[i].color);
          });
          place(dots[0].x, Math.min(...dots.map((d) => d.y)), chart.tip(r));
        } else {
          const b = chart.nearest(ot);
          const p = chart.pos(b);
          const c = g.querySelector("circle");
          c.setAttribute("cx", p.x);
          c.setAttribute("cy", p.y);
          place(p.x, p.y, chart.tipFor(b));
        }
      });
      hit.addEventListener("pointerleave", () => {
        g.style.display = "none";
        tip.style.display = "none";
      });
    });
  }
}

if (!customElements.get("heating-curve-panel")) customElements.define("heating-curve-panel", HeatingCurvePanel);
