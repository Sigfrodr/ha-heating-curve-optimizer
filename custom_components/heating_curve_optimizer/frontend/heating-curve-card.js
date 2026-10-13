// Carte de tableau de bord « Courbe de chauffe » : état compact + actions rapides.
// Lit uniquement les entités de l'intégration (fonctionne aussi pour les non-administrateurs).
const PLATFORM = "heating_curve_optimizer";

const fmt = (v, d = 1, signed = false) => {
  const n = parseFloat(v);
  if (!Number.isFinite(n)) return "—";
  const s = n.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  return signed && n > 0 ? `+${s}` : s;
};
const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

class HeatingCurveCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return {};
  }

  set hass(hass) {
    this._hass = hass;
    const ids = this._ids();
    const key = Object.values(ids).map((id) => hass.states[id]?.last_updated).join("|");
    if (key !== this._key) {
      this._key = key;
      this._render();
    }
  }

  _ids() {
    if (this._idCache) return this._idCache;
    const ents = Object.values(this._hass.entities || {}).filter((e) => e.platform === PLATFORM);
    const find = (domain, suffix) => ents.find((e) => e.entity_id.startsWith(`${domain}.`) && e.entity_id.endsWith(suffix))?.entity_id;
    const ids = {
      status: find("sensor", "_etat"),
      error: find("sensor", "_ecart_moyen_ambiance_consigne"),
      setpoint: find("sensor", "_consigne_pilotee"),
      auto: find("switch", "_ajustement_automatique"),
      pilot: find("select", "_pilotage_de_la_consigne"),
      alert: find("binary_sensor", "_alerte_chaudiere"),
      evaluate: find("button", "_evaluer_maintenant"),
    };
    if (ids.status) this._idCache = ids;
    return ids;
  }

  _render() {
    if (!this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const h = this._hass;
    const ids = this._ids();
    const st = (k) => (ids[k] ? h.states[ids[k]] : undefined);
    if (!st("status")) {
      this.shadowRoot.innerHTML = `<ha-card header="Courbe de chauffe"><div style="padding:16px">Intégration « Optimiseur de courbe de chauffe » introuvable.</div></ha-card>`;
      return;
    }
    const alert = st("alert");
    const alerts = alert?.state === "on" ? alert.attributes.alertes || [] : [];
    const sp = st("setpoint");
    const pilot = st("pilot")?.state;
    const auto = st("auto")?.state === "on";
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding:16px; }
        .head { display:flex; align-items:center; gap:10px; }
        .head ha-icon { color:var(--primary-color); }
        .title { font-size:16px; font-weight:500; flex:1; }
        .status { color:var(--secondary-text-color); font-size:13px; margin-top:2px; }
        .kpis { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin:14px 0; }
        .kpi .v { font-size:20px; font-weight:500; font-variant-numeric:tabular-nums; }
        .kpi .l { font-size:12px; color:var(--secondary-text-color); }
        .alert { display:flex; gap:8px; align-items:flex-start; font-size:13px; padding:8px 10px; border-radius:8px; margin-bottom:12px;
          background:color-mix(in srgb, var(--error-color, #db4437) 12%, transparent); }
        .alert ha-icon { color:var(--error-color, #db4437); --mdc-icon-size:18px; }
        .actions { display:flex; gap:8px; flex-wrap:wrap; }
        button { font:inherit; font-size:13px; font-weight:500; border-radius:8px; padding:6px 12px; cursor:pointer;
          border:1px solid var(--divider-color); background:transparent; color:var(--primary-color); }
        button.on { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
        a { color:inherit; text-decoration:none; }
      </style>
      <ha-card>
        <a href="/courbe-de-chauffe" class="head"><ha-icon icon="mdi:chart-bell-curve-cumulative"></ha-icon>
          <div style="flex:1"><div class="title">Courbe de chauffe</div><div class="status">${esc(st("status").state)}</div></div></a>
        <div class="kpis">
          <div class="kpi"><div class="v">${fmt(st("error")?.state, 2, true)} K</div><div class="l">écart moyen</div></div>
          <div class="kpi"><div class="v">${sp && sp.state !== "unknown" ? `${fmt(sp.state, 0)} °C` : "—"}</div>
            <div class="l">${pilot ? `pilotage : ${esc(pilot.toLowerCase())}` : "consigne pilotée"}${sp?.attributes.mode ? ` · ${esc(sp.attributes.mode)}` : ""}</div></div>
          <div class="kpi"><div class="v">${auto ? "Auto" : "Simulation"}</div><div class="l">réglage de la courbe</div></div>
        </div>
        ${alerts.map((m) => `<div class="alert"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${esc(m)}</div></div>`).join("")}
        <div class="actions">
          <button data-action="evaluate">Évaluer maintenant</button>
          <button data-action="auto" class="${auto ? "on" : ""}">Ajustement auto</button>
        </div>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => this._action(b.dataset.action, auto)),
    );
  }

  _action(action, auto) {
    const ids = this._ids();
    if (action === "evaluate") this._hass.callService("button", "press", { entity_id: ids.evaluate });
    if (action === "auto") this._hass.callService("switch", auto ? "turn_off" : "turn_on", { entity_id: ids.auto });
  }
}

if (!customElements.get("heating-curve-card")) customElements.define("heating-curve-card", HeatingCurveCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "heating-curve-card")) {
  window.customCards.push({
    type: "heating-curve-card",
    name: "Courbe de chauffe",
    description: "État de l'optimiseur de courbe de chauffe, pilotage et alertes chaudière.",
  });
}
