"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const host = (u) => esc(u.replace(/^https?:\/\/(www\.)?/, "").split("/")[0]);
const STATUS = { works: "Works", setup: "Works with setup", community: "Community fixes only", broken: "Doesn't run" };
const RUNTIME = { native: "Native Linux", proton: "Proton", none: "Doesn't run" };
const TELEMETRY = { good: "Full", basic: "Basic", partial: "Partial", untested: "Untested", experimental: "Experimental", planned: "Planned" };
const LABELS = {
  rotation: ["Rotation", "°"], road_sensitivity: ["Road sensitivity", ""], ffb_strength: ["Game FFB intensity", "%"],
  speed: ["Max wheel speed", "%"], spring: ["Wheel spring", "%"], damper: ["Wheel damper", "%"], torque: ["Max output torque", "%"],
  inertia: ["Natural inertia", "%"], friction: ["Wheel friction", "%"], speed_damping: ["Speed-dependent damping", "%"],
  speed_damping_point: ["Speed damping starts at", " km/h"],
};
let DATA = null;

fetch("data.json").then((r) => r.json()).then((d) => { DATA = d; init(); });

function init() {
  games(); wheels(); moza(); fuel(); tools(); dayOne();
  $("srcs").innerHTML = DATA.sources.map((s) => `<a href="${esc(s.url)}">${esc(s.name)}</a>`).join(", ")
    + `, <a href="${esc(DATA.wheels.source)}">linux-steering-wheels</a>, <a href="${esc(DATA.tools.source)}">awesome-linux-simracing</a>`;
}

// ------------------------------------------------------------- games
function games() {
  let filter = "all";
  const render = () => {
    const q = $("gq").value.trim().toLowerCase();
    const list = DATA.games.filter((g) => (filter === "all" || g.status === filter) && (!q || g.name.toLowerCase().includes(q)));
    $("glist").innerHTML = list.map((g) => {
      const t = g.telemetry || {};
      const tel = t.adapter && t.adapter !== "none" ? `Pitwall telemetry: ${TELEMETRY[t.quality] || t.quality}` : "No telemetry";
      const links = g.steam_appid ? ` · <a href="https://store.steampowered.com/app/${g.steam_appid}">Steam</a> · <a href="https://www.protondb.com/app/${g.steam_appid}">ProtonDB</a>` : "";
      const issues = (g.known_issues || []).map((k) => `<li>${esc(k.text)} <span class="src">(<a href="${esc(k.source)}">${host(k.source)}</a>)</span></li>`).join("");
      const ing = g.ffb_ingame ? `<p><b>In-game force feedback</b></p><ol>${g.ffb_ingame.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol><p>${esc(g.ffb_ingame.starting_points)}</p>` : "";
      return `<details class="card"><summary><span><span class="name">${esc(g.name)}</span><br><span class="meta">${RUNTIME[g.runtime] || ""} · ${tel}</span></span><span class="status ${g.status}">${STATUS[g.status]}</span></summary>
        <p><b>Setup</b></p><ol>${g.install.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>${ing}
        ${issues ? `<p><b>Known issues</b></p><ul>${issues}</ul>` : ""}<p class="src">Links${links || ": none"}</p></details>`;
    }).join("") || `<p class="small">No match. Not listed? <a href="https://github.com/crspytopgn/pitwall/issues/new?template=game_report.yml">Report a game</a>.</p>`;
  };
  $("gq").addEventListener("input", render);
  $("gfilter").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    filter = b.dataset.f;
    [...$("gfilter").children].forEach((x) => x.classList.toggle("on", x === b));
    render();
  });
  render();
}

// ------------------------------------------------------------ wheels
function wheels() {
  const W = DATA.wheels;
  const brands = [...new Set(W.wheels.map((w) => w.brand))];
  $("wbrand").innerHTML = brands.map((b) => `<option>${esc(b)}</option>`).join("");
  const render = () => {
    const b = $("wbrand").value;
    const ctl = W.pitwall_control[b];
    $("wlist").innerHTML = (ctl ? `<div class="card"><span class="name">Pitwall controls</span><br><span class="meta">${esc(ctl)}</span></div>` : "")
      + W.wheels.filter((w) => w.brand === b).map((w) => `<div class="card"><span class="name">${esc(w.model)}</span>
        <span class="rank ${esc(w.rank || "")}" style="float:right">${esc(w.rank || "Not ranked")}</span><br>
        <span class="meta">Driver: ${esc(w.driver)}${w.in_kernel && !/Linux/.test(w.driver) ? " (included in Linux)" : ""}</span>
        ${w.notes ? `<br><span class="meta">${esc(w.notes)}</span>` : ""}</div>`).join("");
  };
  $("wbrand").addEventListener("change", render);
  $("wsource").innerHTML = `Support ranks summarised from <a href="${esc(W.source)}">linux-steering-wheels</a> by JacKeTUs and contributors (as of ${esc(W.source_date)}). Platinum is best.`;
  render();
}

// -------------------------------------------------------------- MOZA
function moza() {
  const render = () => {
    const base = $("mbase").value;
    const p = DATA.presets.find((x) => (x.bases || []).includes(base)) || DATA.presets.find((x) => x.id === "pure");
    const rows = Object.entries(p.values).map(([k, v]) => {
      const [label, unit] = LABELS[k] || [k, ""];
      return `<tr><td>${esc(label)}</td><td>${esc(v)}${unit}</td></tr>`;
    }).join("");
    $("mout").innerHTML = `<div class="card"><span class="name">${esc(p.name)}</span><br><span class="meta">${esc(p.summary)}</span>
      <table><tr><th>Pit House setting</th><th>Value</th></tr>${rows}</table>
      <p class="src">${esc(p.source_note || "")} Source: <a href="${esc(p.source)}">${host(p.source)}</a>. With the Pitwall plugin, auto setup applies this for you.</p></div>`;
  };
  $("mbase").addEventListener("change", render);
  render();
  $("symptoms").innerHTML = DATA.symptoms.map((s) => `<div class="card"><span class="name">${esc(s.label)}</span>
    <ul>${s.changes.map(([k, d, why]) => `<li>${esc((LABELS[k] || [k])[0])} ${d > 0 ? "+" : ""}${esc(d)}: ${esc(why)}</li>`).join("")}</ul>
    ${s.source ? `<span class="src">Source: <a href="${esc(s.source)}">${host(s.source)}</a></span>` : ""}</div>`).join("");
}

// -------------------------------------------------------------- fuel
function fuel() {
  const ids = ["fpl", "fnow", "fcap", "flen", "funit", "flap", "fmargin"];
  try { const saved = JSON.parse(localStorage.getItem("pitwall-fuel") || "{}"); ids.forEach((i) => { if (saved[i] != null) $(i).value = saved[i]; }); } catch (e) {}
  const calc = () => {
    const v = (i) => parseFloat($(i).value);
    const per = v("fpl"), now = v("fnow"), cap = v("fcap"), lap = v("flap"), margin = v("fmargin") || 0;
    let laps = v("flen");
    if ($("funit").value === "min") laps = Math.ceil((laps * 60) / lap);
    if (!(per > 0) || !(laps > 0)) { $("fresult").textContent = "Enter fuel per lap and race length."; return; }
    const need = (laps + margin) * per;
    const add = Math.max(0, need - (now || 0));
    const stops = cap > 0 && add > 0 ? Math.ceil(add / cap) : 0;
    $("fresult").innerHTML = `${laps} laps to go. You need <b>${need.toFixed(1)}</b> in total`
      + (add > 0 ? `, so add <b>${add.toFixed(1)}</b>${stops > 1 ? ` over ${stops} stops` : ""}.` : `. You have enough with ${margin} lap(s) of margin.`)
      + (now > 0 ? `<br><span class="small">Current fuel lasts ${(now / per).toFixed(1)} laps.</span>` : "");
    try { localStorage.setItem("pitwall-fuel", JSON.stringify(Object.fromEntries(ids.map((i) => [i, $(i).value])))); } catch (e) {}
  };
  ids.forEach((i) => $(i).addEventListener("input", calc));
  calc();
}

// ------------------------------------------------------------- tools
function tools() {
  const T = DATA.tools;
  $("tlist").innerHTML = [...T.community.map((c) => ({ ...c, category: "Community" })), ...T.tools].map((t) =>
    `<div class="card"><span class="meta">${esc(t.category)}</span><br><a class="name" href="${esc(t.url)}">${esc(t.name)}</a>
     <br><span>${esc(t.what)}</span>${t.steamos ? `<br><span class="meta">SteamOS: ${esc(t.steamos)}</span>` : ""}</div>`).join("");
  $("tsource").innerHTML = `Adapted from <a href="${esc(T.source)}">awesome-linux-simracing</a> by Lukas Lichten and contributors (CC BY-SA 4.0) and the projects themselves.`;
}

// ----------------------------------------------------------- day one
function dayOne() {
  const steps = [
    "Check your sims in the game list above.",
    "If your MOZA base needs a firmware update, do it on Windows with Pit House first.",
    "Update SteamOS (Settings, System). MOZA force feedback needs the hid-universal-pidff driver; Pitwall's pre-race checks tell you if it's missing.",
    "Install Decky Loader from decky.xyz (Desktop Mode).",
    "Install the Pitwall zip: Decky, cog, Developer mode, Install Plugin from ZIP File.",
    "Plug in the wheel and pedals, open Pitwall and run auto setup.",
    "Install your sims and follow each game's setup steps.",
    "Run pre-race checks with a game running.",
    "Scan the dashboard QR code with your phone.",
    "Drive. If Pitwall asks for a start line, set one; coaching starts from lap two.",
  ];
  let done = {};
  try { done = JSON.parse(localStorage.getItem("pitwall-dayone") || "{}"); } catch (e) {}
  $("checklist").innerHTML = steps.map((s, i) => `<li class="${done[i] ? "done" : ""}"><input type="checkbox" data-i="${i}" ${done[i] ? "checked" : ""} aria-label="Step ${i + 1}"><span>${esc(s)}</span></li>`).join("");
  $("checklist").addEventListener("change", (e) => {
    const i = e.target.dataset.i; done[i] = e.target.checked;
    e.target.parentElement.classList.toggle("done", e.target.checked);
    try { localStorage.setItem("pitwall-dayone", JSON.stringify(done)); } catch (err) {}
  });
}
