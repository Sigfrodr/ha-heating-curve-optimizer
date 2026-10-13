// Panneau « Courbe de chauffe » — composant web autonome (sans dépendance).
const DOMAIN = "heating_curve_optimizer";
const X_MIN = -15;
const X_MAX = 20;
const CHART_H = 300;
const MARGIN = { l: 44, r: 16, t: 14, b: 30 };
const SERIES = {
  light: { s1: "#2a78d6", s2: "#eb6834" },
  dark: { s1: "#3987e5", s2: "#d95926" },
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
      error: median(g.map((s) => clamp(s.room - s.target, -deadClip, deadClip))),
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
td { padding:8px; border-bottom:1px solid var(--divider-color); font-variant-numeric:tabular-nums; }
tr:last-child td { border-bottom:none; }
.table-wrap { overflow-x:auto; }
.msg { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:var(--primary-text-color); color:var(--card-background-color, #fff);
  padding:10px 16px; border-radius:8px; font-size:14px; z-index:10; box-shadow:0 4px 12px rgba(0,0,0,.25); }
.err { color:var(--error-color, #db4437); }
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
    return Object.values(e)
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
  }

  _body() {
    const d = this._data;
    const live = this._live();
    const pal = this._palette();
    const proposal = this._pendingProposal(live);
    const s = d.settings;
    const mean = d.samples.length
      ? d.samples.reduce((acc, x) => acc + x.room - x.target, 0) / d.samples.length
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
            <small>Programme ${esc(live.program || "—")} · évaluation chaque jour à ${esc(String(s.evaluate_at).slice(0, 5))}</small></div>
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

    return `${status}${tiles}
      <div class="main">${curveCard}${control}</div>
      ${errorCard}
      <div class="card"><h2>Historique des ajustements</h2>${history}</div>`;
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
    const pts = samples.map((p) => ({ outside: p.outside, error: clamp(p.room - p.target, -3, 3) }));
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
        if (id === "curve") {
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

customElements.define("heating-curve-panel", HeatingCurvePanel);
