/**
 * Benni Door Policy — Observability/Shadow-Panel (Vanilla Web Component, kein Build-Step).
 *
 * Holt den konsolidierten Status über die WS-API (benni_door_policy/get_status) und
 * rendert Combined-State, Live-Inputs, Szenarien, Shadow/Live-Steuerung, Pending-Action
 * (stabilisiert), Diagnose-Attribute, Safety-Regeln und den Logik-Ablauf.
 * Muster + Theme wie benni_blind_policy. Schaltet selbst nichts — alle Aktionen laufen
 * über die WS-Commands der Integration (gated an apply_enabled).
 */

const STATE_LABEL = {
  verriegelt: "Verriegelt",
  entriegelt: "Entriegelt",
  unbekannt: "Unbekannt",
  nicht_erreichbar: "Nicht erreichbar",
};
const STATES = ["entriegelt", "verriegelt", "unbekannt", "nicht_erreichbar"];
const STATE_ICON = { verriegelt: "🔒", entriegelt: "🔓", unbekannt: "❓", nicht_erreichbar: "📵" };

const EFFECTIVE_PRESENCE = ["home", "away", "arriving", "leaving", "uncertain", "stale"];
const ACTION_LABEL = { lock: "Verriegeln", unlock: "Entriegeln", none: "—" };

const esc = (s) => String(s ?? "—");
const yn = (v) => (v === true ? "true" : v === false ? "false" : "—");

const css = `
:host { display:block; font-family: ui-sans-serif, system-ui, sans-serif;
  background:#0b1020; color:#c0caf5; min-height:100vh; padding:18px 22px; box-sizing:border-box; }
.topbar { display:flex; align-items:center; gap:12px; margin-bottom:4px; }
.menu { display:none; align-items:center; justify-content:center; width:38px; height:38px;
  padding:0; font-size:20px; line-height:1; border-radius:10px; }
@media (max-width: 870px) { .menu { display:inline-flex; } }
h1 { font-size:20px; margin:0; color:#e6ecff; display:flex; align-items:center; gap:10px; }
.ver { margin-left:auto; font-size:12px; color:#9ece6a; background:#16261a; border:1px solid #9ece6a44;
  border-radius:999px; padding:4px 12px; }
.sub { color:#565f89; font-size:13px; margin:2px 0 16px; }
.grid { display:grid; gap:14px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); align-items:start; }
.card { background:#111729; border:1px solid #1e2740; border-radius:14px; padding:16px 18px; }
.card h2 { font-size:12px; margin:0 0 12px; color:#7aa2f7; text-transform:uppercase; letter-spacing:.05em;
  display:flex; align-items:center; gap:8px; }
.hero { display:flex; align-items:center; gap:18px; }
.heroIcon { width:96px; height:96px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:44px; background:radial-gradient(circle at 50% 40%, #2a2150, #141a30); border:2px solid #4d3fb0; }
.heroIcon.locked { border-color:#f7768e; }
.kpi { font-size:30px; font-weight:700; color:#bb9af7; line-height:1.1; }
.kpi.locked { color:#f7768e; }
.raw { color:#787c99; font-size:13px; margin-top:2px; }
.batt { margin-top:8px; font-size:15px; color:#9ece6a; }
.batt.crit { color:#f7768e; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
.chip { font-size:12px; padding:5px 12px; border-radius:8px; background:#161d33; border:1px solid #1e2740; color:#9aa5c4; }
.chip.on { background:#2a2150; border-color:#7d5fff; color:#cbb8ff; }
.chip.on.warn { background:#3a1f2b; border-color:#f7768e; color:#ffb3c1; }
.row { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:7px 0; font-size:13px; border-bottom:1px solid #18203a; }
.row:last-child { border-bottom:none; }
.row .k { color:#787c99; display:flex; align-items:center; gap:8px; }
.row .v { color:#c0caf5; } .row .v.good { color:#9ece6a; } .row .v.bad { color:#f7768e; }
.scenarios { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.scn { border:1px solid #1e2740; border-radius:10px; padding:10px 12px; }
.scn.on { border-color:#7d5fff66; background:#1a1640; }
.scn .t { color:#bb9af7; font-weight:600; font-size:14px; margin-bottom:4px; }
.scn .c { color:#787c99; font-size:11px; line-height:1.4; }
.scn .st { margin-top:8px; font-size:11px; padding:3px 8px; border-radius:999px; display:inline-block;
  background:#161d33; color:#787c99; }
.scn.on .st { background:#2a2150; color:#cbb8ff; }
.reason { margin-top:10px; font-size:12px; color:#9aa5c4; }
.reason b { color:#787c99; font-weight:600; }
.toggle { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.sw { width:48px; height:26px; border-radius:999px; background:#2a3350; position:relative; cursor:pointer; flex:0 0 auto; transition:background .15s; }
.sw.on { background:#3a7afe; }
.sw::after { content:""; position:absolute; top:3px; left:3px; width:20px; height:20px; border-radius:50%; background:#fff; transition:left .15s; }
.sw.on::after { left:25px; }
.mode { display:flex; align-items:center; gap:8px; font-size:13px; padding:3px 0; }
.mode .dot { width:9px; height:9px; border-radius:50%; }
.mode .d-shadow { background:#7aa2f7; } .mode .d-live { background:#9ece6a; }
.mode .lbl { width:54px; color:#c0caf5; } .mode .desc { color:#565f89; font-size:11px; }
.actions { display:flex; gap:10px; margin-top:12px; }
button { background:#161d33; color:#c0caf5; border:1px solid #1e2740; border-radius:9px;
  padding:9px 14px; font-size:13px; cursor:pointer; display:flex; align-items:center; gap:8px; }
button:hover { border-color:#7aa2f7; }
button.go { background:#241a45; border-color:#7d5fff66; color:#cbb8ff; }
.note { margin-top:10px; color:#565f89; font-size:11px; }
.pending { border:1px solid #f7768e44; background:#1c1422; border-radius:10px; padding:14px 16px; }
.pending.lock { border-color:#f7768e44; } .pending.unlock { border-color:#7aa2f744; background:#121a2b; }
.pending .h { font-size:18px; font-weight:700; color:#e6ecff; display:flex; align-items:center; gap:8px; }
.pending .meta { display:flex; justify-content:space-between; font-size:12px; color:#787c99; margin:10px 0 6px; }
.bar { height:8px; border-radius:999px; background:#222a44; overflow:hidden; }
.bar > i { display:block; height:100%; background:#f7768e; }
.bar.unlock > i { background:#7aa2f7; }
.idle { color:#787c99; font-size:13px; padding:6px 0; }
.startup { border:1px solid #e0af6844; background:#1f1a12; border-radius:10px; padding:12px 14px; color:#e0af68; font-size:13px; }
.sub2 { margin-top:10px; display:flex; justify-content:space-between; font-size:12px; color:#787c99;
  border-top:1px solid #18203a; padding-top:10px; }
.tag { font-size:11px; padding:2px 8px; border-radius:999px; background:#1f1a12; border:1px solid #e0af6844; color:#e0af68; }
table { width:100%; border-collapse:collapse; font-size:13px; }
td { padding:7px 0; border-bottom:1px solid #18203a; }
td.k { color:#9aa5c4; } td.v { text-align:right; color:#7dcfff; font-variant-numeric:tabular-nums; }
td.v.good { color:#9ece6a; } td.v.bad { color:#f7768e; }
.rule { display:flex; align-items:center; gap:10px; font-size:13px; padding:5px 0; color:#c0caf5; }
.rule .ok { color:#9ece6a; }
.banner { margin-top:12px; display:flex; align-items:center; gap:10px; font-size:13px; font-weight:600;
  color:#f7768e; background:#2a1620; border:1px solid #f7768e55; border-radius:10px; padding:11px 14px; }
.flow { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:6px 0; }
.fstep { font-size:12px; padding:8px 12px; border-radius:9px; border:1px solid #1e2740; background:#141b30; color:#c0caf5; display:flex; align-items:center; gap:7px; }
.fstep.lock { border-color:#f7768e44; } .fstep.unlock { border-color:#7aa2f744; } .fstep.green { border-color:#9ece6a44; color:#9ece6a; }
.arr { color:#565f89; }
.flow-note { color:#565f89; font-size:11px; margin-top:8px; }
.err { color:#f7768e; padding:24px; }
`;

class BdpApp extends HTMLElement {
  set hass(h) { this._hass = h; if (!this._timer) this._tick(); }

  connectedCallback() {
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${css}</style><div id="root" class="err">Lade…</div>`;
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
    this._timer = setInterval(() => this._tick(), 3000);
  }
  disconnectedCallback() { clearInterval(this._timer); this._timer = null; }

  async _tick() {
    if (!this._hass) return;
    try {
      this._status = await this._hass.callWS({ type: "benni_door_policy/get_status" });
      this._render();
    } catch (e) {
      this.shadowRoot.getElementById("root").innerHTML =
        `<div class="err">Door Policy nicht geladen: ${esc(e && e.message)}</div>`;
    }
  }

  async _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el || !this._hass) return;
    const act = el.dataset.act;
    try {
      if (act === "toggle-apply") {
        await this._hass.callWS({ type: "benni_door_policy/set_apply_enabled", enabled: !this._status.apply_enabled });
      } else if (act === "apply-now") {
        await this._hass.callWS({ type: "benni_door_policy/apply_now" });
      } else if (act === "resync") {
        await this._hass.callWS({ type: "benni_door_policy/resync" });
      }
      await this._tick();
    } catch (err) { /* require_admin / not_ready — still re-tick */ await this._tick(); }
  }

  _render() {
    const s = this._status || {};
    const c = s.context || {};
    const cs = s.combined_state;
    const locked = cs === "verriegelt";
    const root = this.shadowRoot.getElementById("root");
    root.className = "";
    root.innerHTML = `
      <div class="topbar">
        <button class="menu" data-act="menu" title="Menü">☰</button>
        <h1>🔐 Türschlosslogik</h1>
        <span class="ver">● ${esc(STATE_LABEL[cs] || cs)} · Profil ${esc(s.profile)}</span>
      </div>
      <div class="sub">Weggehen verriegelt. Heimkommen entriegelt. Öffnen bleibt immer manuell.</div>

      <div class="grid">
        ${this._heroCard(s, c, cs, locked)}
        ${this._inputsCard(s, c)}
        ${this._scenarioCard(s)}
        ${this._shadowCard(s)}
        ${this._pendingCard(s)}
        ${this._diagCard(s, c)}
        ${this._blockerCard(s)}
        ${this._flowCard()}
      </div>`;
  }

  _heroCard(s, c, cs, locked) {
    const batt = c.battery_percent;
    const crit = s.battery_critical === true;
    return `<div class="card">
      <h2>Schloss-Zustand Combined</h2>
      <div class="hero">
        <div class="heroIcon ${locked ? "locked" : ""}">${STATE_ICON[cs] || "❔"}</div>
        <div>
          <div class="kpi ${locked ? "locked" : ""}">${esc(STATE_LABEL[cs] || cs)}</div>
          <div class="raw">Raw: ${esc(c.raw_lock_state)}</div>
          ${batt != null ? `<div class="batt ${crit ? "crit" : ""}">🔋 ${esc(batt)}%${crit ? " · kritisch" : ""}</div>` : ""}
        </div>
      </div>
      <div class="chips">
        ${STATES.map((st) => `<span class="chip ${st === cs ? "on" + (st === "verriegelt" || st === "nicht_erreichbar" ? " warn" : "") : ""}">${esc(STATE_LABEL[st])}</span>`).join("")}
      </div>
    </div>`;
  }

  _inputsCard(s, c) {
    const chipRow = (label, icon, values, current, warnSet) =>
      `<div class="row"><span class="k">${icon} ${label}</span><span class="chips" style="margin:0">
        ${values.map((v) => `<span class="chip ${v === current ? "on" + (warnSet && warnSet.has(v) ? " warn" : "") : ""}">${esc(v)}</span>`).join("")}
      </span></div>`;
    return `<div class="card">
      <h2>〰 Inputs live</h2>
      <div class="row"><span class="k">🔐 Roh-Schlosszustand</span><span class="v">${esc(c.raw_lock_state)}</span></div>
      ${chipRow("Effective Presence", "🧭", EFFECTIVE_PRESENCE, c.effective_presence, new Set(["uncertain", "stale"]))}
      <div class="row"><span class="k">🎯 Presence Confidence</span><span class="v">${c.presence_confidence != null ? esc(c.presence_confidence) : "—"}</span></div>
      <div class="row"><span class="k">👤 Raw Presence</span><span class="v">${c.raw_presence != null ? esc(c.raw_presence) : "—"}</span></div>
      <div class="row"><span class="k">🔋 Batterie</span><span class="v ${s.battery_critical ? "bad" : "good"}">${c.battery_percent != null ? esc(c.battery_percent) + "%" : "—"}</span></div>
      <div class="row"><span class="k">🖥 HA-System</span><span class="v ${s.startup_ready ? "good" : ""}">${s.startup_ready ? "stabil" : "Startup " + esc(s.startup_remaining_s) + "s"}</span></div>
    </div>`;
  }

  _scenarioCard(s) {
    const al = s.auto_lock_active === true, au = s.auto_unlock_active === true;
    return `<div class="card">
      <h2>🛡 Policy & Szenario</h2>
      <div class="scenarios">
        <div class="scn ${al ? "on" : ""}">
          <div class="t">🔒 Auto-Lock</div>
          <div class="c">Effective Presence = away/leaving, Raw Presence = abwesend, Schloss = entriegelt</div>
          <div class="c" style="margin-top:6px">⏱ Stabilisierung ${esc(s.stabilize_lock_s)}s</div>
          <span class="st">${al ? "Aktiv" : "Inaktiv"}</span>
        </div>
        <div class="scn ${au ? "on" : ""}">
          <div class="t">🔓 Auto-Unlock</div>
          <div class="c">Effective Presence = home/arriving, Confidence hoch, Raw Presence &ne; zuhause, Schloss = verriegelt</div>
          <div class="c" style="margin-top:6px">⏱ Stabilisierung ${esc(s.stabilize_unlock_s)}s</div>
          <span class="st">${au ? "Aktiv" : "Inaktiv"}</span>
        </div>
      </div>
      <div class="reason"><b>Begründung:</b> ${esc(s.reason)}</div>
    </div>`;
  }

  _shadowCard(s) {
    const on = s.apply_enabled === true;
    return `<div class="card">
      <h2>⚙ Ausführung / Shadow Mode</h2>
      <div class="toggle">
        <span style="font-size:13px;color:#9aa5c4">apply_enabled</span>
        <span class="sw ${on ? "on" : ""}" data-act="toggle-apply" title="Shadow ↔ Live"></span>
      </div>
      <div class="mode"><span class="dot d-shadow"></span><span class="lbl" style="color:${on ? "#565f89" : "#c0caf5"}">Shadow</span><span class="desc">Entscheidungen werden berechnet, aber nicht ausgeführt.</span></div>
      <div class="mode"><span class="dot d-live"></span><span class="lbl" style="color:${on ? "#9ece6a" : "#565f89"}">Live</span><span class="desc">Entscheidungen werden an das Schloss übertragen.</span></div>
      <div class="actions">
        <button class="go" data-act="apply-now">⚡ Apply now</button>
        <button data-act="resync">🔄 Resync</button>
      </div>
      <div class="note">ⓘ R-07 Resync nach HA-Start / Template-Reload. Aktionen brauchen Admin.</div>
    </div>`;
  }

  _pendingCard(s) {
    let body;
    if (!s.startup_ready) {
      body = `<div class="startup">⏳ Startup-Block aktiv — ${esc(s.startup_remaining_s)}s verbleibend.
        Bis dahin wird bewusst keine Aktion geplant (R-07).</div>`;
    } else if (s.pending_action && s.pending_action !== "none" && s.pending_remaining_s != null) {
      const isLock = s.pending_action === "lock";
      const total = isLock ? s.stabilize_lock_s : s.stabilize_unlock_s;
      const rem = s.pending_remaining_s;
      const pct = total > 0 ? Math.max(0, Math.min(100, (rem / total) * 100)) : 0;
      body = `<div class="pending ${isLock ? "lock" : "unlock"}">
        <div class="h">${isLock ? "🔒" : "🔓"} ${esc(ACTION_LABEL[s.pending_action])} in ${esc(rem)}s</div>
        <div class="meta"><span>Stabilisierung (${esc(total)}s) — verbleibend</span><span>${esc(rem)}s</span></div>
        <div class="bar ${isLock ? "" : "unlock"}"><i style="width:${pct}%"></i></div>
      </div>`;
    } else {
      body = `<div class="idle">Keine ausstehende Aktion — Schloss ist im Zielzustand.</div>`;
    }
    return `<div class="card">
      <h2>⏳ Pending Action</h2>
      ${body}
      <div class="sub2"><span>HA-Start Delay: ${esc(s.ha_start_delay_s)}s</span>
        ${!s.startup_ready ? `<span class="tag">${esc(s.startup_remaining_s)}s verbleibend</span>` : `<span style="color:#9ece6a">bereit</span>`}</div>
    </div>`;
  }

  _diagCard(s, c) {
    const rows = [
      ["raw_lock_state", esc(c.raw_lock_state), ""],
      ["auto_lock_aktiv", yn(s.auto_lock_active), s.auto_lock_active ? "good" : ""],
      ["auto_unlock_aktiv", yn(s.auto_unlock_active), s.auto_unlock_active ? "good" : ""],
      ["effective_presence", esc(c.effective_presence), ""],
      ["presence_confidence", c.presence_confidence != null ? esc(c.presence_confidence) : "—", ""],
      ["raw_presence", c.raw_presence != null ? esc(c.raw_presence) : "—", ""],
      ["batterie_prozent", c.battery_percent != null ? esc(c.battery_percent) : "—", ""],
      ["batterie_kritisch", yn(s.battery_critical), s.battery_critical ? "bad" : ""],
    ];
    return `<div class="card">
      <h2>〰 Diagnose-Attribute</h2>
      <table>${rows.map(([k, v, cls]) => `<tr><td class="k">${k}</td><td class="v ${cls}">${v}</td></tr>`).join("")}</table>
      <div class="note">batterie_kritisch: Schwelle &lt; ${esc(s.battery_threshold)}%</div>
    </div>`;
  }

  _blockerCard(s) {
    const blockers = s.blockers || [];
    const safety = [
      "Keine Aktion bei unbekannt / nicht erreichbar (R-04)",
      "Keine automatische Verriegelung bei Anwesenheit zuhause (R-05)",
      "Niemals automatisch Tür öffnen (R-06)",
      "Nur entriegeln, nie Falle ziehen",
    ];
    return `<div class="card">
      <h2>🛡 Blocker / Sicherheitsregeln</h2>
      ${safety.map((t) => `<div class="rule"><span class="ok">✔</span>${t}</div>`).join("")}
      ${blockers.length ? `<div class="note">Aktive Gates: ${blockers.map(esc).join(", ")}</div>` : ""}
      <div class="banner">⚠ R-06 ABSOLUT: Kein Auto-Open</div>
    </div>`;
  }

  _flowCard() {
    return `<div class="card">
      <h2>🧭 Logik-Ablauf</h2>
      <div class="flow">
        <span class="fstep">👤 Raw abwesend</span><span class="arr">→</span>
        <span class="fstep">⏳ 60s warten</span><span class="arr">→</span>
        <span class="fstep lock">🔒 Verriegeln</span>
      </div>
      <div class="flow">
        <span class="fstep green">🏠 Effective home/arriving</span><span class="arr">→</span>
        <span class="fstep">⏳ 5s warten</span><span class="arr">→</span>
        <span class="fstep unlock">🔓 Entriegeln</span>
      </div>
      <div class="flow-note">ⓘ Entriegeln ≠ Öffnen</div>
    </div>`;
  }

  _onClickMenu() {
    this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }
}

// Mobile-Sidebar-Toggle (Custom-Panels haben < 870px sonst keinen Ausweg).
BdpApp.prototype._onClick = (function (orig) {
  return function (e) {
    if (e.target.closest('[data-act="menu"]')) { this._onClickMenu(); return; }
    return orig.call(this, e);
  };
})(BdpApp.prototype._onClick);

customElements.define("bdp-app", BdpApp);
