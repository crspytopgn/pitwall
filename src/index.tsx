import {
  ButtonItem,
  Navigation,
  SidebarNavigation,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  TextField,
  Router,
  staticClasses,
} from "@decky/ui";
import { addEventListener, callable, definePlugin, removeEventListener, routerHook, toaster } from "@decky/api";
import qrcode from "qrcode-generator";
import { useEffect, useRef, useState, ReactNode } from "react";
import { GiCheckeredFlag, GiSteeringWheel, GiBookCover, GiStopwatch, GiLightningArc, GiCheckMark, GiHeadphones, GiSpeedometer, GiFuelTank, GiFirstAidKit } from "react-icons/gi";

// ---------------------------------------------------------------- backend
type SettingDef = { min: number; max: number; step: number; label: string; suffix: string; toggle: boolean };
type WheelStatus = { connected: boolean; name?: string; brand?: string; error?: string; settings?: Record<string, SettingDef>; can_center?: boolean; leds?: boolean; rev_lights?: boolean };
type Profiles = { auto_apply: boolean; has_default: boolean; games: Record<string, string>; cars: Record<string, string>;
  current_car: { key: string; name: string; sim: string } | null };
type Strat = {
  sim: string | null; target_laps: number | null; target_minutes: number | null;
  fuel: { unit: string; now: number | null; per_lap: number | null; laps_measured: number; laps_left: number | null;
    to_finish?: number; to_add?: number; stops?: number; advice?: string } | null;
  tyres: { temps: Record<string, number | null> | null; window?: [number, number, number] | null; front_rear?: number; left_right?: number;
    notes?: string[]; wear_per_lap_pct?: Record<string, number>; worst?: string; laps_per_10pct?: number } | null;
};
type Diag = { path: string; summary: string; download_url: string | null; issue_url: string };
type Session = {
  receiving: boolean; sim: string | null; sim_name?: string | null; car: string | null; track: string | null; needs_start_line: boolean;
  has_position: boolean; live: { lap_time: number | null; delta: number | null }; best: number | null;
  last_lap: { time: number; best: boolean } | null; tips: string[]; session_laps: number;
  dashboard_url: string | null; dashboard_error: string | null;
};
type GameRow = { id: string; name: string; status: string; installed: boolean; telemetry: string };
type Issue = { text: string; source: string };
type GameDetail = GameRow & {
  install: string[]; known_issues: Issue[]; auto_setup?: string; runtime: string;
  live_protondb?: { tier?: string; trendingTier?: string; total?: number } | null;
  live_deck?: { category: string; notes: string[] } | null;
  live_anticheat?: { status: string; anticheats: string[] } | null;
  wheel?: { rotation: number; note: string };
};
type Check = { id: string; ok: boolean | null; title: string; detail: string };
type Perf = { ok: boolean; message?: string; verdict?: string; avg_fps?: number; low1_fps?: number; stutters_per_min?: number; advice?: string[] };
type Debrief = { lines: string[]; claude: string | null; error: string | null };

const wheelStatus = callable<[], WheelStatus>("wheel_status");
const wheelRead = callable<[], Record<string, number> | null>("wheel_read");
const wheelSet = callable<[key: string, value: number], boolean>("wheel_set");
const wheelCenter = callable<[], boolean>("wheel_center");
const getProfiles = callable<[], Profiles>("get_profiles");
const setAutoApply = callable<[enabled: boolean], void>("set_auto_apply");
const saveProfile = callable<[appid: string, name: string], boolean>("save_profile");
const deleteProfile = callable<[appid: string], void>("delete_profile");
const gameChanged = callable<[appid: string, name: string, running: boolean], { applied: string | null; game: { id: string; name: string; status: string } | null }>("game_changed");
const sessionStatus = callable<[], Session>("session_status");
const setStartLine = callable<[], boolean>("set_start_line");
const compatList = callable<[], GameRow[]>("compat_list");
const compatDetail = callable<[id: string], GameDetail | null>("compat_detail");
const compatAutoSetup = callable<[id: string], { ok: boolean; message: string }>("compat_auto_setup");
const healthCheck = callable<[], Check[]>("health_check");
const benchmarkOptions = callable<[seconds: number], string>("benchmark_options");
const perfAnalyse = callable<[appid: string, name: string], Perf>("perf_analyse");
const debrief = callable<[], Debrief>("debrief");
const getSettings = callable<[], { target_fps: number; anthropic_api_key: boolean; setup_done: boolean }>("get_settings");
const setSetting = callable<[key: string, value: any], boolean>("set_setting");

type FfbCat = {
  presets: { id: string; name: string; summary: string; source: string; source_note: string }[];
  symptoms: { id: string; label: string }[];
  ingame: { steps: string[]; starting_points: string; sources: string[] } | null;
  game: string | null; can_undo: boolean;
};
type FfbResult = { ok: boolean; message?: string; changes?: { label: string; from: number; to: number; why: string }[]; tip?: string | null; source?: string | null };
const ffbCatalogue = callable<[], FfbCat>("ffb_catalogue");
const ffbApplyPreset = callable<[id: string], FfbResult>("ffb_apply_preset");
const ffbNudge = callable<[symptom: string], FfbResult>("ffb_nudge");
const ffbUndo = callable<[], FfbResult>("ffb_undo");
type LapRow = { id: number; created: number; sim: string; track_key: string; car: string | null; track: string | null; time: number; length: number };
const recentLaps = callable<[], LapRow[]>("recent_laps");
const strategyReport = callable<[], Strat>("strategy_report");
const strategySetTarget = callable<[laps: number, minutes: number], Strat>("strategy_set_target");
const diagnosticsCreate = callable<[], Diag>("diagnostics_create");
type PlanStep = { id: string; title: string; detail: string };
type Plan = { device: { kind: string; product: string | null; os: string | null; cpus: number; ram_gb: number | null; vram_gb: number | null };
  preset: string | null; target_fps: number; steps: PlanStep[]; first_run: boolean };
const autoSetupPlan = callable<[], Plan>("auto_setup_plan");
const autoSetupApply = callable<[], { results: { step: string; ok: boolean; detail: string }[]; bridge_games: string[] }>("auto_setup_apply");
const dismissFirstRun = callable<[], void>("dismiss_first_run");
const bridgeStatus = callable<[appid: string], { supported: boolean; installed: boolean; prefix: string }>("bridge_status");
const bridgeInstall = callable<[], { ok: boolean; message: string }>("bridge_install");
type UpdateItem = { kind: "driver" | "bridge"; id: string; name: string; current: string | null; latest: string | null; date: string | null; update: boolean; error: string | null };
type Updates = { checked: number; items: UpdateItem[]; available: string[]; enabled?: boolean; has_anything?: boolean };
const updatesStatus = callable<[force: boolean], Updates>("updates_status");
const bridgeLaunchOptions = callable<[current: string, enable: boolean], string>("bridge_launch_options");
type Detection = { wheels: { name: string; vid: string; pid: string; joystick: boolean | null; model?: string; brand: string }[]; needs_hwdb: boolean; sdl_value: string };
const wheelDetection = callable<[], Detection>("wheel_detection");
const wheelDetectionFix = callable<[], { ok: boolean; changed: boolean; message: string }>("wheel_detection_fix");
const wheelLaunchOptions = callable<[current: string, enable: boolean], string>("wheel_launch_options");
type FfbDevice = { event: string; name: string; brand: string; model?: string; rank?: string; ffb: boolean; driver?: string;
  caps: { effects: string[]; missing: string[]; verdict: string }; need: null | { id: string; name: string; repo: string; for: string } };
type DriverJob = { driver: string; action: string; state: string; step: string; log: string[]; message?: string } | null;
type FfbStatus = { devices: FfbDevice[]; steamos: boolean; kernel: string; installed: Record<string, { present: boolean; stale: boolean; commit?: string; kernel?: string }>; job: DriverJob };
const ffbStatus = callable<[], FfbStatus>("ffb_status");
const ffbTest = callable<[event: string, strength: number], { ok: boolean; message: string }>("ffb_test");
const driverInstall = callable<[id: string], { ok: boolean; message: string }>("driver_install");
const driverRemove = callable<[id: string], { ok: boolean; message: string }>("driver_remove");
const driverJob = callable<[], DriverJob>("driver_job");
const hidrawLaunchOptions = callable<[current: string, enable: boolean], string>("hidraw_launch_options");
type BtnRow = { action: string; label: string; control: string | null; button: string | null; auto?: boolean };
type BtnStatus = {
  devices: { id: string; name: string; buttons: number; hats: number }[]; pressed: string[];
  recent: { control: string; label: string; steam: string | null; game: string | null }[];
  in_game: boolean; game: string | null; uinput: boolean;
  nav: { enabled: boolean; active: boolean; error: string | null; custom: boolean; rows: BtnRow[] };
  layout: { rows: BtnRow[]; paddles: boolean };
  beamng: { found: boolean; applied: boolean; auto: boolean };
  learning: { kind: string; action: string } | null;
};
const buttonsStatus = callable<[], BtnStatus>("buttons_status");
const buttonsLearn = callable<[kind: string, action: string], { ok: boolean }>("buttons_learn");
const buttonsLearned = callable<[], { state: string; label?: string; beamng?: { ok: boolean; error: string | null } | null }>("buttons_learned");
const buttonsCancelLearn = callable<[], void>("buttons_cancel_learn");
const buttonsReset = callable<[kind: string], { ok: boolean }>("buttons_reset");
const beamngBind = callable<[enable: boolean], { ok: boolean; error?: string | null }>("beamng_bind");
const DRIVER_NAMES: Record<string, string> = { "universal-pidff": "hid-universal-pidff", "new-lg4ff": "new-lg4ff", "hid-fanatecff": "hid-fanatecff", "hid-tmff2": "hid-tmff2", "simagic-ff": "simagic-ff" };

declare const SteamClient: any;
const ROUTE = "/pitwall";

const toast = (body: string) => toaster.toast({ title: "Pitwall", body });
const fmt = (s: number | null | undefined) => {
  if (s == null || !isFinite(s) || s <= 0) return "–";
  const m = Math.floor(s / 60), r = s - m * 60;
  return (m ? `${m}:${r < 10 ? "0" : ""}` : "") + r.toFixed(3);
};
const STATUS: Record<string, string> = { works: "Works", setup: "Works with setup", community: "Community fixes only", broken: "Doesn't run" };
const STATUS_COLOUR: Record<string, string> = { works: "#3ddc84", setup: "#4da3ff", community: "#ffb020", broken: "#ff6b6b" };
const small = { fontSize: "12px", lineHeight: 1.35 } as const;
const dim = { ...small, opacity: 0.7 } as const;

function runningApp(): { appid: string; name: string } | null {
  const app = (Router as any).MainRunningApp;
  return app ? { appid: String(app.appid), name: app.display_name ?? `App ${app.appid}` } : null;
}

function usePoll<T>(fn: () => Promise<T>, ms: number): T | null {
  const [v, setV] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    const tick = async () => { try { const r = await fn(); if (live) setV(r); } catch { /* backend busy */ } };
    tick();
    const id = setInterval(tick, ms);
    return () => { live = false; clearInterval(id); };
  }, []);
  return v;
}

function Row({ children }: { children: ReactNode }) {
  return <PanelSectionRow>{children}</PanelSectionRow>;
}

type Go = ((p: string) => void) | undefined;
function Back({ go }: { go: Go }) {
  return go ? <Row><ButtonItem layout="below" onClick={() => go("home")}>‹ Back</ButtonItem></Row> : null;
}
const src = (u: string) => u.replace(/^https:\/\/(www\.)?/, "").replace(/\/$/, "");

// ------------------------------------------------------------------ pages
function QR({ value, size = 168 }: { value: string; size?: number }) {
  const qr = qrcode(0, "M");
  qr.addData(value);
  qr.make();
  const n = qr.getModuleCount(), q = 4, total = n + q * 2;
  const cells: string[] = [];
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) cells.push(`M${c + q} ${r + q}h1v1h-1z`);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${total} ${total}`} shapeRendering="crispEdges" style={{ display: "block", margin: "6px auto", borderRadius: 8 }}>
      <rect width={total} height={total} fill="#fff" />
      <path d={cells.join("")} fill="#000" />
    </svg>
  );
}

function DashQR({ url }: { url: string }) {
  const [show, setShow] = useState(false);
  return (
    <>
      <Row><ToggleField label="Show QR code" checked={show} onChange={setShow} /></Row>
      {show && <Row><QR value={url} /></Row>}
    </>
  );
}

function Strategy({ go }: { go?: Go }) {
  const r = usePoll(strategyReport, 2000);
  const [laps, setLaps] = useState(0);
  const [mins, setMins] = useState(0);
  useEffect(() => { if (r && laps === 0 && mins === 0) { setLaps(r.target_laps ?? 0); setMins(r.target_minutes ?? 0); } }, [r]);
  const push = (l: number, m: number) => strategySetTarget(l, m);
  const f = r?.fuel, t = r?.tyres;
  const temp = (k: string) => {
    const v = t?.temps?.[k];
    if (v == null) return "–";
    const w = t?.window;
    const col = w ? (v < w[0] ? "#4da3ff" : v > w[2] ? "#ff6b6b" : "#3ddc84") : undefined;
    return <span style={{ color: col }}>{Math.round(v)}°</span>;
  };
  return (
    <>
      <PanelSection title="Fuel">
        <Back go={go} />
        {!f ? <Row><div style={small}>Waiting for fuel data from the sim.</div></Row> : (
          <Row><div style={small}>
            In tank: <b>{f.now ?? "–"} {f.unit}</b><br />
            Per lap: <b>{f.per_lap != null ? `${f.per_lap} ${f.unit}` : `measuring (${f.laps_measured} laps)`}</b><br />
            Laps of fuel left: <b>{f.laps_left ?? "–"}</b>
            {f.to_add != null && <><br />To finish: {f.to_finish} {f.unit} · <b>add {f.to_add} {f.unit}</b>{f.stops ? ` · ${f.stops} stop(s)` : ""}</>}
            {f.advice && <div style={{ marginTop: 4 }}>{f.advice}</div>}
          </div></Row>
        )}
        <Row><SliderField label="Race laps remaining" value={laps} min={0} max={200} step={1} showValue
          onChange={(v: number) => { setLaps(v); setMins(0); push(v, 0); }} /></Row>
        <Row><SliderField label="…or minutes remaining" value={mins} min={0} max={360} step={5} showValue
          onChange={(v: number) => { setMins(v); setLaps(0); push(0, v); }} /></Row>
        <Row><div style={dim}>Fuel per lap uses the median of your last 5 clean laps; refuelling laps are ignored. Advice includes one lap of margin.</div></Row>
      </PanelSection>
      <PanelSection title="Tyres">
        {!t ? <Row><div style={small}>This sim doesn't report tyre data, or no data yet.</div></Row> : (
          <>
            {t.temps && (
              <Row><div style={{ ...small, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, textAlign: "center" }}>
                <div>FL {temp("FL")}</div><div>FR {temp("FR")}</div><div>RL {temp("RL")}</div><div>RR {temp("RR")}</div>
              </div></Row>
            )}
            {t.window && <Row><div style={dim}>Window: {t.window[0]}°C to {t.window[2]}°C (ideal {t.window[1]}°C)</div></Row>}
            {t.notes?.map((n) => <Row key={n}><div style={small}>• {n}</div></Row>)}
            {t.wear_per_lap_pct && (
              <Row><div style={small}>Wear per lap: {Object.entries(t.wear_per_lap_pct).map(([k, v]) => `${k} ${v}%`).join(" · ")}
                {t.laps_per_10pct && <><br />Worst ({t.worst}): about {t.laps_per_10pct} laps per 10% wear</>}</div></Row>
            )}
          </>
        )}
      </PanelSection>
    </>
  );
}

function Diagnostics({ go }: { go?: Go }) {
  const [d, setD] = useState<Diag | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <PanelSection title="Send diagnostics">
      <Back go={go} />
      <Row><div style={small}>Creates a zip with your setup, wheel and telemetry status, check results and Pitwall's recent logs (your API key is removed). Nothing is sent automatically.</div></Row>
      <Row><ButtonItem layout="below" disabled={busy} onClick={async () => { setBusy(true); try { setD(await diagnosticsCreate()); } finally { setBusy(false); } }}>
        {busy ? "Collecting…" : d ? "Create again" : "Create diagnostics"}
      </ButtonItem></Row>
      {d && (
        <>
          <Row><div style={{ ...small, whiteSpace: "pre-wrap" }}>{d.summary}</div></Row>
          <Row><div style={dim}>Saved to {d.path}</div></Row>
          {d.download_url && (
            <Row><div style={small}><b>1. Scan to download the zip on your phone</b> (link works once, for 10 minutes)<QR value={d.download_url} /></div></Row>
          )}
          <Row><div style={small}><b>2. Scan to open a pre-filled bug report</b>, then attach the zip<QR value={d.issue_url} size={200} /></div></Row>
        </>
      )}
    </PanelSection>
  );
}

const DEVICE: Record<string, string> = { steam_machine: "Steam Machine", steam_deck: "Steam Deck", pc: "PC" };

function AutoSetup({ go }: { go?: Go }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [res, setRes] = useState<{ step: string; ok: boolean; detail: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { autoSetupPlan().then(setPlan); }, []);
  if (!plan) return <PanelSection><Back go={go} /><Row>Checking your setup…</Row></PanelSection>;
  const d = plan.device;
  return (
    <PanelSection title="Auto setup">
      <Back go={go} />
      <Row><div style={small}>
        <b>{DEVICE[d.kind] ?? "PC"}</b>{d.product ? ` (${d.product})` : ""} · {d.cpus} CPU threads{d.ram_gb ? ` · ${d.ram_gb} GB RAM` : ""}{d.vram_gb ? ` · ${d.vram_gb} GB VRAM` : ""}
        <div style={dim}>{d.os}</div>
      </div></Row>
      <Row><div style={small}><b>Pitwall will:</b></div></Row>
      {plan.steps.map((s) => <Row key={s.id}><div style={small}>• <b>{s.title}</b><div style={dim}>{s.detail}</div></div></Row>)}
      {!res && (
        <Row><ButtonItem layout="below" disabled={busy} onClick={async () => {
          setBusy(true);
          try { const r = await autoSetupApply(); setRes(r.results); toast("Auto setup done"); } finally { setBusy(false); }
        }}>{busy ? "Setting up…" : "Do it"}</ButtonItem></Row>
      )}
      {res && res.map((r) => <Row key={r.step}><div style={small}><span style={{ color: r.ok ? "#3ddc84" : "#ffb020", fontWeight: 700 }}>{r.ok ? "Done" : "Check"}</span> {r.detail}</div></Row>)}
      {res && <Row><div style={dim}>Next: open the Game guide for each sim you play, then run Pre-race checks with the game running.</div></Row>}
      <Row><div style={dim}>Graphics settings aren't changed automatically: use Performance check to measure, and Pitwall will say what to change.</div></Row>
    </PanelSection>
  );
}

function Home({ go }: { go?: Go }) {
  const s = usePoll(sessionStatus, 1000);
  const game = runningApp();
  const [firstRun, setFirstRun] = useState(false);
  const [upd, setUpd] = useState<Updates | null>(null);
  useEffect(() => { getSettings().then((x: any) => setFirstRun(!x.setup_done)); updatesStatus(false).then(setUpd); }, []);
  return (
    <>
      {go && upd && upd.available.length > 0 && (
        <PanelSection title="Update available">
          <Row><div style={small}>{upd.items.filter((i) => i.update).map((i) => i.name).join(", ")}</div></Row>
          <Row><ButtonItem layout="below" onClick={() => go("updates")}>See updates</ButtonItem></Row>
        </PanelSection>
      )}
      {firstRun && go && (
        <PanelSection title="Welcome to Pitwall">
          <Row><div style={small}>Let Pitwall check your device and wheel and apply the best starting settings. Takes a few seconds.</div></Row>
          <Row><ButtonItem layout="below" onClick={() => go("auto")}>Run auto setup</ButtonItem></Row>
          <Row><ButtonItem layout="below" onClick={async () => { await dismissFirstRun(); setFirstRun(false); }}>Not now</ButtonItem></Row>
        </PanelSection>
      )}
      <PanelSection title="Session">
        {!s ? <Row>Starting…</Row> : (
          <>
            <Row>
              <div style={small}>
                {s.receiving ? <>Telemetry: <b>{s.sim_name ?? s.sim}</b>{s.track ? ` · ${s.track}` : ""}</> : <>Waiting for telemetry{game ? ` from ${game.name}` : ""}</>}
              </div>
            </Row>
            {s.receiving && (
              <Row>
                <div style={small}>
                  Lap {fmt(s.live.lap_time)} {s.live.delta != null && <b style={{ color: s.live.delta > 0 ? "#ff6b6b" : "#3ddc84" }}>{s.live.delta > 0 ? "+" : ""}{s.live.delta.toFixed(2)}</b>}
                  <br />Last {fmt(s.last_lap?.time)} · Best {fmt(s.best)} · {s.session_laps} laps
                </div>
              </Row>
            )}
            {s.has_position && (
              <Row>
                <ButtonItem layout="below" onClick={async () => toast((await setStartLine()) ? "Start line set here" : "No position data yet")}>
                  {s.needs_start_line ? "Set start line here (needed for laps)" : "Move start line here"}
                </ButtonItem>
              </Row>
            )}
            {s.tips.length > 0 && <Row><div style={small}>{s.tips.map((t) => <div key={t}>{t}</div>)}</div></Row>}
            <Row>
              <div style={dim}>
                {s.dashboard_url ? <>Dashboard: <b>{s.dashboard_url}</b> (scan with a phone on the same Wi-Fi)</> : s.dashboard_error}
              </div>
            </Row>
            {s.dashboard_url && (go ? <DashQR url={s.dashboard_url} /> : <Row><QR value={s.dashboard_url} size={200} /></Row>)}
          </>
        )}
      </PanelSection>
      {go && (
        <>
          <PanelSection title="Set up">
            <Row><ButtonItem layout="below" onClick={() => go("auto")}>Auto setup</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("games")}>Game guide</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("checks")}>Pre-race checks</ButtonItem></Row>
          </PanelSection>
          <PanelSection title="Drive">
            <Row><ButtonItem layout="below" onClick={() => go("wheel")}>Wheel</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("buttons")}>Wheel buttons</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("feel")}>Force feedback feel</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("strategy")}>Fuel and tyres</ButtonItem></Row>
          </PanelSection>
          <PanelSection title="More">
            <Row><ButtonItem layout="below" onClick={() => { Navigation.Navigate(`${ROUTE}/session`); Navigation.CloseSideMenus(); }}>Open full screen</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("perf")}>Performance check</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("debrief")}>Engineer debrief</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("updates")}>Updates</ButtonItem></Row>
            <Row><ButtonItem layout="below" onClick={() => go("diag")}>Send diagnostics</ButtonItem></Row>
          </PanelSection>
        </>
      )}
    </>
  );
}

function useDebounced(delay = 200) {
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  useEffect(() => () => Object.values(timers.current).forEach(clearTimeout), []);
  return (key: string, v: number) => {
    clearTimeout(timers.current[key]);
    timers.current[key] = setTimeout(() => wheelSet(key, v), delay);
  };
}

const CORE_KEYS = ["rotation", "ffb_strength", "torque", "road_sensitivity", "ffb_enabled"];

function Wheel({ go }: { go?: Go }) {
  const [st, setSt] = useState<WheelStatus | null>(null);
  const [vals, setVals] = useState<Record<string, number>>({});
  const [prof, setProf] = useState<Profiles | null>(null);
  const [more, setMore] = useState(false);
  const write = useDebounced();
  const game = runningApp();

  const refresh = async () => {
    const s = await wheelStatus();
    setSt(s);
    setProf(await getProfiles());
    if (s.connected) { const v = await wheelRead(); if (v) setVals(v); }
  };
  useEffect(() => { refresh(); }, []);
  const change = (k: string, v: number) => { setVals((o) => ({ ...o, [k]: v })); write(k, v); };
  const save = async (appid: string, name: string) => {
    toast((await saveProfile(appid, name)) ? `Saved wheel profile: ${name}` : "Couldn't read settings from the wheel");
    setProf(await getProfiles());
  };

  if (!st) return <PanelSection><Back go={go} /><Row>Looking for wheel…</Row></PanelSection>;
  if (!st.connected) return (
    <>
      <PanelSection title="Wheel"><Back go={go} />
        <Row><div style={small}>{st.error}</div></Row>
        <Row><ButtonItem layout="below" onClick={refresh}>Retry</ButtonItem></Row>
      </PanelSection>
      <FfbSetup />
      <WheelDetection />
    </>
  );
  const defs = st.settings ?? {};
  const render = (k: string) => {
    const d = defs[k];
    if (!d || vals[k] === undefined) return null;
    if (d.toggle) return <Row key={k}><ToggleField label={d.label} checked={vals[k] === 1} onChange={(c: boolean) => change(k, c ? 1 : 0)} /></Row>;
    return <Row key={k}><SliderField label={d.label} value={vals[k]} min={d.min} max={d.max} step={d.step} showValue valueSuffix={d.suffix} onChange={(v: number) => change(k, v)} /></Row>;
  };
  const hasProfile = game && prof?.games[game.appid] !== undefined;
  return (
    <>
      <PanelSection title={st.name}>
        <Back go={go} />
        {CORE_KEYS.map(render)}
        {st.can_center && (
          <Row><ButtonItem layout="below" onClick={async () => toast((await wheelCenter()) ? "Centre set" : "Centre failed")}>Set centre (hold wheel straight)</ButtonItem></Row>
        )}
        {st.leds && (
          <Row><ToggleField label="Rev lights from telemetry" description="Drive the wheel's RPM LEDs from the game" checked={!!st.rev_lights}
            onChange={async (c: boolean) => { await setSetting("rev_lights", c); setSt({ ...st, rev_lights: c }); }} /></Row>
        )}
        {Object.keys(defs).some((k) => !CORE_KEYS.includes(k)) && (
          <Row><ToggleField label="Show more settings" checked={more} onChange={setMore} /></Row>
        )}
        {more && Object.keys(defs).filter((k) => !CORE_KEYS.includes(k)).map(render)}
      </PanelSection>
      <PanelSection title="Profiles">
        <Row><ToggleField label="Apply profiles automatically" checked={prof?.auto_apply ?? true} onChange={async (c: boolean) => { await setAutoApply(c); setProf(await getProfiles()); }} /></Row>
        {game && <Row><ButtonItem layout="below" onClick={() => save(game.appid, game.name)}>{hasProfile ? "Update" : "Save"} profile for {game.name}</ButtonItem></Row>}
        {game && hasProfile && <Row><ButtonItem layout="below" onClick={async () => { await deleteProfile(game.appid); setProf(await getProfiles()); }}>Delete profile for {game.name}</ButtonItem></Row>}
        {prof?.current_car && (
          <Row><ButtonItem layout="below" onClick={() => save(`car:${prof.current_car!.key}`, prof.current_car!.name)}>
            {prof.cars[prof.current_car.key] !== undefined ? "Update" : "Save"} profile for this car ({prof.current_car.name})
          </ButtonItem></Row>
        )}
        {prof?.current_car && prof.cars[prof.current_car.key] !== undefined && (
          <Row><ButtonItem layout="below" onClick={async () => { await deleteProfile(`car:${prof.current_car!.key}`); setProf(await getProfiles()); }}>Delete profile for {prof.current_car.name}</ButtonItem></Row>
        )}
        <Row><ButtonItem layout="below" onClick={() => save("default", "Default")}>{prof?.has_default ? "Update" : "Save"} default (outside games)</ButtonItem></Row>
        <Row><div style={dim}>A car profile overrides the game profile when that car is on track. Car names come from telemetry (not available in BeamNG).</div></Row>
        {prof && Object.keys(prof.games).length > 0 && <Row><div style={dim}>Games: {Object.values(prof.games).join(", ")}</div></Row>}
        {prof && Object.keys(prof.cars).length > 0 && <Row><div style={dim}>Cars: {Object.values(prof.cars).join(", ")}</div></Row>}
      </PanelSection>
      <FfbSetup />
      <WheelDetection />
    </>
  );
}

function Games({ go, open }: { go?: Go; open: (id: string) => void }) {
  const list = usePoll(compatList, 30000);
  return (
    <PanelSection title="Game guide">
      <Back go={go} />
      {!list ? <Row>Loading…</Row> : list.map((g) => (
        <Row key={g.id}>
          <ButtonItem layout="below" onClick={() => open(g.id)}>
            <div style={{ textAlign: "left" }}>
              <div>{g.name}{g.installed ? " · installed" : ""}</div>
              <div style={dim}><span style={{ color: STATUS_COLOUR[g.status] }}>{STATUS[g.status] ?? g.status}</span>{g.telemetry && g.telemetry !== "planned" ? ` · telemetry: ${g.telemetry}` : g.telemetry === "planned" ? " · telemetry planned" : ""}</div>
            </div>
          </ButtonItem>
        </Row>
      ))}
    </PanelSection>
  );
}

function GamePage({ id, go, back }: { id: string; go?: Go; back: () => void }) {
  const [g, setG] = useState<GameDetail | null>(null);
  useEffect(() => { compatDetail(id).then(setG); }, [id]);
  if (!g) return <PanelSection><Back go={go} /><Row>Fetching live ratings…</Row></PanelSection>;
  const ing = (g as any).ffb_ingame as FfbCat["ingame"];
  return (
    <>
      <PanelSection title={g.name}>
        <Row><ButtonItem layout="below" onClick={back}>‹ All games</ButtonItem></Row>
        <Row>
          <div style={small}>
            <b style={{ color: STATUS_COLOUR[g.status] }}>{STATUS[g.status]}</b> ({g.runtime === "native" ? "native Linux" : g.runtime === "proton" ? "Proton" : "not runnable"})<br />
            Steam Deck rating (Valve): <b>{g.live_deck?.category ?? "unavailable"}</b><br />
            ProtonDB: <b>{g.live_protondb?.tier ?? "unavailable"}</b>{g.live_protondb?.trendingTier && g.live_protondb.trendingTier !== g.live_protondb.tier ? ` (trending ${g.live_protondb.trendingTier})` : ""}{g.live_protondb?.total ? ` · ${g.live_protondb.total} reports` : ""}<br />
            {g.live_anticheat && <>Anti-cheat: <b>{g.live_anticheat.status}</b> ({g.live_anticheat.anticheats?.join(", ")})</>}
          </div>
        </Row>
      </PanelSection>
      <PanelSection title="Setup">
        {g.install.map((s, i) => <Row key={i}><div style={small}>{i + 1}. {s}</div></Row>)}
        {g.auto_setup && (
          <Row><ButtonItem layout="below" onClick={async () => toast((await compatAutoSetup(g.id)).message)}>Do this for me</ButtonItem></Row>
        )}
        {(g as any).bridge_auto && (g as any).steam_appid && <BridgeSetup appid={String((g as any).steam_appid)} name={g.name} />}
        {g.wheel && <Row><div style={small}>Suggested rotation {g.wheel.rotation}°. {g.wheel.note}</div></Row>}
      </PanelSection>
      {ing && (
        <PanelSection title="In-game force feedback">
          {ing.steps.map((t, i) => <Row key={i}><div style={small}>{i + 1}. {t}</div></Row>)}
          <Row><div style={small}>{ing.starting_points}<div style={dim}>{ing.sources.map(src).join(" · ")}</div></div></Row>
        </PanelSection>
      )}
      {(g as any).steam_appid && g.runtime !== "none" && <WheelDetection appid={String((g as any).steam_appid)} name={g.name} />}
      {g.known_issues.length > 0 && (
        <PanelSection title="Known issues">
          {g.known_issues.map((k, i) => <Row key={i}><div style={small}>• {k.text}<div style={dim}>{src(k.source)}</div></div></Row>)}
        </PanelSection>
      )}
    </>
  );
}

function BridgeSetup({ appid, name }: { appid: string; name: string }) {
  const [st, setSt] = useState<{ supported: boolean; installed: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cur, setCur] = useState<string | null>(null);
  const enabled = cur !== null && cur.includes("winecarte-run");
  useEffect(() => { bridgeStatus(appid).then(setSt); getLaunchOptions(appid).then(setCur); }, [appid]);
  if (!st?.supported) return null;
  const apply = async (enable: boolean) => {
    if (cur === null) { toast("Couldn't read this game's launch options; nothing was changed"); return; }
    setBusy(true);
    try {
      if (enable && !st.installed) {
        const r = await bridgeInstall();
        if (!r.ok) { toast(r.message); return; }
        setSt({ ...st, installed: true });
      }
      const next = await bridgeLaunchOptions(cur, enable);
      SteamClient.Apps.SetAppLaunchOptions(Number(appid), next);
      setCur(next);
      toast(enable ? `Telemetry bridge added to ${name}. Restart the game.` : `Bridge removed from ${name}'s launch options`);
    } finally { setBusy(false); }
  };
  return (
    <>
      <Row><ButtonItem layout="below" disabled={busy} onClick={() => apply(!enabled)}>
        {busy ? "Working…" : enabled ? "Remove telemetry bridge" : "Set up telemetry bridge"}
      </ButtonItem></Row>
      <Row><div style={dim}>Uses winecarte (github.com/srounce/winecarte). It's added to the game's launch options; your existing options are kept.</div></Row>
    </>
  );
}

// Force feedback setup: is FFB there, which effects the driver offers, a test pull,
// and the driver Pitwall can build and install when the wheel needs one.
function FfbSetup() {
  const [st, setSt] = useState<FfbStatus | null>(null);
  const [job, setJob] = useState<DriverJob>(null);
  const [testing, setTesting] = useState(false);
  const [strength, setStrength] = useState(20);
  const load = async () => { const s = await ffbStatus(); setSt(s); setJob(s.job); };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (job?.state !== "running") return;
    const t = setInterval(async () => {
      const j = await driverJob(); setJob(j);
      if (j && j.state !== "running") { clearInterval(t); toast(j.message || (j.state === "done" ? "Done" : "Failed")); load(); }
    }, 1500);
    return () => clearInterval(t);
  }, [job?.state]);
  if (!st) return <PanelSection title="Force feedback"><Row>Checking…</Row></PanelSection>;
  const bases = st.devices.filter((d) => d.ffb || d.need || d.caps.effects.length);
  const start = async (id: string, remove = false) => {
    const r = await (remove ? driverRemove(id) : driverInstall(id));
    if (!r.ok) { toast(r.message); return; }
    setJob(await driverJob());
  };
  const test = async (ev: string) => { setTesting(true); try { toast((await ffbTest(ev, strength / 100)).message); } finally { setTesting(false); } };
  const effects = (d: FfbDevice) => d.caps.effects.filter((e) => e !== "gain" && e !== "autocentre").join(", ");
  const stale = Object.entries(st.installed).filter(([, r]) => r.stale);
  return (
    <PanelSection title="Force feedback">
      {stale.map(([id]) => (
        <Row key={"stale" + id}><div style={small}><b style={{ color: "#ffb020" }}>{DRIVER_NAMES[id] ?? id} needs reinstalling.</b> A SteamOS update replaced the kernel ({st.kernel}) and removed it.</div></Row>
      ))}
      {stale.map(([id]) => (
        <Row key={"re" + id}><ButtonItem layout="below" disabled={job?.state === "running"} onClick={() => start(id)}>Reinstall {DRIVER_NAMES[id] ?? id}</ButtonItem></Row>
      ))}
      {bases.length === 0 && <Row><div style={dim}>No wheel base found. Plug it in and switch it on, then open this page again.</div></Row>}
      {bases.map((d) => (
        <div key={d.event}>
          <Row><div style={small}>
            <b>{d.model ? `${d.brand} ${d.model}` : d.name}</b>{": "}
            {d.ffb
              ? (d.caps.verdict === "full" ? <span style={{ color: "#3ddc84" }}>force feedback ready</span>
                : d.caps.verdict === "no_constant" ? <span style={{ color: "#ff6b6b" }}>force feedback without constant force, which most sims need</span>
                : <span style={{ color: "#ffb020" }}>force feedback, some effects missing ({d.caps.missing.join(", ")})</span>)
              : <span style={{ color: "#ff6b6b" }}>no force feedback</span>}
            {d.ffb && <div style={dim}>Driver offers: {effects(d) || "none"}</div>}
            {!d.ffb && d.driver && <div style={dim}>Needs {d.driver}.</div>}
          </div></Row>
          {d.need && (st.steamos ? (
            <>
              <Row><div style={dim}>
                Pitwall can build and install <b>{d.need.name}</b> ({d.need.repo.replace("https://", "")}) for your kernel. It needs internet and takes a few minutes. SteamOS updates remove it; Pitwall will offer to reinstall.
                {d.need.id === "new-lg4ff" && d.ffb ? " Your wheel works already; this adds the missing effects (spring, damper, friction) and wheel settings." : ""}
              </div></Row>
              <Row><ButtonItem layout="below" disabled={job?.state === "running"} onClick={() => start(d.need!.id)}>Install {d.need.name}</ButtonItem></Row>
            </>
          ) : (
            <Row><div style={dim}>Install {d.need.name} with your distribution's package manager or from {d.need.repo.replace("https://", "")}.</div></Row>
          ))}
          {d.ffb && <Row><ButtonItem layout="below" disabled={testing} onClick={() => test(d.event)}>{testing ? "Testing… hold the wheel lightly" : "Test force feedback"}</ButtonItem></Row>}
        </div>
      ))}
      {bases.some((d) => d.ffb) && (
        <>
          <Row><SliderField label="Test strength" value={strength} min={5} max={40} step={5} showValue valueSuffix="%" onChange={setStrength} /></Row>
          <Row><div style={dim}>The test pulls the wheel left, then right, through Linux's force feedback interface, the same one games use. Keep hands near the wheel; 20% is gentle even on strong bases.</div></Row>
        </>
      )}
      {job && (
        <>
          <Row><div style={small}><b>{job.action === "install" ? "Installing" : "Removing"} {DRIVER_NAMES[job.driver] ?? job.driver}:</b> {job.state === "running" ? job.step : job.message}</div></Row>
          <Row><div style={{ ...dim, fontFamily: "monospace", fontSize: "10px", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{job.log.slice(-6).join("\n")}</div></Row>
        </>
      )}
      {Object.entries(st.installed).filter(([, r]) => r.present).map(([id, r]) => (
        <Row key={"rm" + id}><ButtonItem layout="below" disabled={job?.state === "running"} onClick={() => start(id, true)}>Remove {DRIVER_NAMES[id] ?? id} ({r.commit})</ButtonItem></Row>
      ))}
    </PanelSection>
  );
}

// "The game doesn't see my wheel": the two fixes Pitwall can apply, plus the settings to check.
function WheelDetection({ appid, name }: { appid?: string; name?: string }) {
  const [det, setDet] = useState<Detection | null>(null);
  const [cur, setCur] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = async () => { setDet(await wheelDetection()); if (appid) setCur(await getLaunchOptions(appid)); };
  useEffect(() => { load(); }, [appid]);
  if (!det) return null;
  const hasEnv = cur !== null && cur.includes("SDL_JOYSTICK_WHEEL_DEVICES=");
  const hasHidraw = cur !== null && cur.includes("PROTON_ENABLE_HIDRAW=");
  const toggleHidraw = async () => {
    if (!appid || cur === null) { toast("Couldn't read this game's launch options; nothing was changed"); return; }
    const next = await hidrawLaunchOptions(cur, !hasHidraw);
    SteamClient.Apps.SetAppLaunchOptions(Number(appid), next);
    setCur(next);
    toast(hasHidraw ? `Raw HID access removed from ${name}` : `Raw HID access added to ${name}. Restart the game.`);
  };
  const fixSystem = async () => { setBusy(true); try { toast((await wheelDetectionFix()).message); await load(); } finally { setBusy(false); } };
  const toggleGame = async () => {
    if (!appid || cur === null) { toast("Couldn't read this game's launch options; nothing was changed"); return; }
    const next = await wheelLaunchOptions(cur, !hasEnv);
    SteamClient.Apps.SetAppLaunchOptions(Number(appid), next);
    setCur(next);
    toast(hasEnv ? `Wheel ID removed from ${name}'s launch options` : `Wheel ID added to ${name}. Restart the game.`);
  };
  return (
    <PanelSection title={appid ? "Game doesn't see your wheel?" : "Wheel detection"}>
      {det.wheels.length === 0 && <Row><div style={dim}>No wheel, pedals or shifter recognised.</div></Row>}
      {det.wheels.map((w) => (
        <Row key={w.vid + w.pid}><div style={small}>
          <b>{w.model ? `${w.brand} ${w.model}` : w.name}</b>: {w.joystick === true ? "recognised as a game controller" : w.joystick === false ? "not recognised as a game controller, so games may ignore it" : "detection unknown"}
        </div></Row>
      ))}
      {det.needs_hwdb && (
        <Row><ButtonItem layout="below" disabled={busy} onClick={fixSystem}>{busy ? "Working…" : "Fix wheel and pedal detection"}</ButtonItem></Row>
      )}
      {appid && det.sdl_value && (
        <Row><ButtonItem layout="below" onClick={toggleGame}>{hasEnv ? "Remove wheel ID from launch options" : "Add wheel ID to launch options"}</ButtonItem></Row>
      )}
      {appid && det.sdl_value && (hasEnv || hasHidraw) && (
        <Row><ButtonItem layout="below" onClick={toggleHidraw}>{hasHidraw ? "Remove raw HID access" : "Still not seen: try raw HID access (last resort)"}</ButtonItem></Row>
      )}
      <Row><div style={dim}>
        {det.needs_hwdb ? "This tells Linux these devices are game controllers (a udev rule, kept across reboots). Unplug and replug them afterwards. " : ""}
        {appid ? "Adding the wheel ID tells Steam's input layer to treat it as a wheel in this game; your other launch options are kept. Raw HID access (PROTON_ENABLE_HIDRAW) is a last resort: some Proton versions don't pass force feedback through it. " : ""}
        Also check: Steam Input off for the game (Properties, Controller), and a recent Proton such as Proton 10 or Experimental.
      </div></Row>
    </PanelSection>
  );
}

function Checks({ go }: { go?: Go }) {
  const [res, setRes] = useState<Check[] | null>(null);
  const run = async () => { setRes(null); setRes(await healthCheck()); };
  useEffect(() => { run(); }, []);
  const ffbIssue = res?.some((c) => c.id === "ffb" && c.ok === false);
  return (
    <>
      <PanelSection title="Pre-race checks">
        <Back go={go} />
        {!res ? <Row>Checking…</Row> : res.map((c) => (
          <Row key={c.id}><div style={small}><span style={{ color: c.ok === true ? "#3ddc84" : c.ok === false ? "#ff6b6b" : "#9aa6b2", fontWeight: 700 }}>{c.ok === true ? "OK" : c.ok === false ? "FIX" : "INFO"}</span> <b>{c.title}</b>{c.detail && <div style={dim}>{c.detail}</div>}</div></Row>
        ))}
        <Row><ButtonItem layout="below" onClick={run}>Run again</ButtonItem></Row>
      </PanelSection>
      {ffbIssue && <FfbSetup />}
    </>
  );
}

const LS_KEY = "pitwall-saved-launch-options";
function savedOpts(): Record<string, string> { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; } }
function storeOpts(v: Record<string, string>) { try { localStorage.setItem(LS_KEY, JSON.stringify(v)); } catch { /* ignore */ } }
async function getLaunchOptions(appid: string): Promise<string | null> {
  // Steam only keeps details for apps it has loaded, so ask for them if needed.
  try {
    const d = (window as any).appDetailsStore?.GetAppDetails?.(Number(appid));
    if (typeof d?.strLaunchOptions === "string") return d.strLaunchOptions;
  } catch { /* fall through */ }
  return new Promise((resolve) => {
    let done = false;
    let reg: { unregister: () => void } | undefined;
    const finish = (v: string | null) => { if (!done) { done = true; reg?.unregister(); resolve(v); } };
    try {
      reg = SteamClient.Apps.RegisterForAppDetails(Number(appid), (det: any) => {
        if (typeof det?.strLaunchOptions === "string") finish(det.strLaunchOptions);
      });
    } catch { finish(null); }
    setTimeout(() => finish(null), 3000);
  });
}

function PerfPage({ go }: { go?: Go }) {
  const [target, setTarget] = useState(60);
  const [res, setRes] = useState<Perf | null>(null);
  const [lastApp, setLastApp] = useState<{ appid: string; name: string } | null>(null);
  const [benchFor, setBenchFor] = useState<string[]>(Object.keys(savedOpts()));
  const game = runningApp();
  useEffect(() => { getSettings().then((s) => setTarget(s.target_fps)); }, []);

  const pickApp = () => game ?? lastApp;
  const startBench = async () => {
    const app = pickApp();
    if (!app) { toast("Open a game's page or launch it first"); return; }
    const cur = await getLaunchOptions(app.appid);
    if (cur === null) { toast("Couldn't read this game's launch options; benchmark not set to avoid overwriting them"); return; }
    const saved = savedOpts(); saved[app.appid] = cur; storeOpts(saved);
    // Keep the game's own launch options (e.g. a telemetry bridge): MangoHud's
    // environment variables just go in front.
    const env = (await benchmarkOptions(90)).replace(/\s*%command%\s*$/, "");
    const opts = cur.includes("%command%") ? `${env} ${cur}` : `${env} %command%${cur ? " " + cur : ""}`;
    SteamClient.Apps.SetAppLaunchOptions(Number(app.appid), opts);
    setBenchFor(Object.keys(saved)); setLastApp(app);
    toast(`Benchmark armed for ${app.name}. Restart the game and drive for 90 s.`);
  };
  const restore = (appid: string) => {
    const saved = savedOpts();
    if (appid in saved) { SteamClient.Apps.SetAppLaunchOptions(Number(appid), saved[appid]); delete saved[appid]; storeOpts(saved); }
    setBenchFor(Object.keys(saved));
    toast("Launch options restored");
  };

  return (
    <PanelSection title="Performance check">
      <Back go={go} />
      <Row><SliderField label="Target FPS" value={target} min={30} max={144} step={1} showValue onChange={(v: number) => { setTarget(v); setSetting("target_fps", v); }} notchTicksVisible={false} /></Row>
      <Row><div style={dim}>Match your TV: usually 60 or 120.</div></Row>
      <Row><ButtonItem layout="below" onClick={startBench}>Arm 90 s benchmark{pickApp() ? ` for ${pickApp()!.name}` : ""}</ButtonItem></Row>
      {benchFor.map((a) => <Row key={a}><ButtonItem layout="below" onClick={() => restore(a)}>Restore launch options (app {a})</ButtonItem></Row>)}
      <Row><ButtonItem layout="below" onClick={async () => { const a = pickApp(); setRes(await perfAnalyse(a?.appid ?? "", a?.name ?? "")); }}>Analyse latest benchmark</ButtonItem></Row>
      {res && (!res.ok ? <Row><div style={small}>{res.message}</div></Row> : (
        <Row>
          <div style={small}>
            <b style={{ color: res.verdict === "great" ? "#3ddc84" : res.verdict === "stutters" ? "#ffb020" : "#ff6b6b" }}>{res.verdict === "great" ? "Smooth" : res.verdict === "stutters" ? "Stuttering" : "Below target"}</b><br />
            Average {res.avg_fps} FPS · 1% low {res.low1_fps} · {res.stutters_per_min} stutters/min
            {res.advice?.map((a) => <div key={a} style={{ marginTop: 4 }}>• {a}</div>)}
          </div>
        </Row>
      ))}
    </PanelSection>
  );
}

function DebriefPage({ go }: { go?: Go }) {
  const [d, setD] = useState<Debrief | null>(null);
  const [hasKey, setHasKey] = useState(false);
  const [key, setKey] = useState("");
  const run = async () => { setD(null); setD(await debrief()); };
  useEffect(() => { run(); getSettings().then((s) => setHasKey(s.anthropic_api_key)); }, []);
  return (
    <PanelSection title="Engineer debrief">
      <Back go={go} />
      {!d ? <Row>Analysing session…</Row> : (
        <>
          {d.lines.map((l) => <Row key={l}><div style={small}>{l}</div></Row>)}
          {d.claude && <Row><div style={small}><b>Claude:</b> {d.claude}</div></Row>}
          {d.error && <Row><div style={dim}>{d.error}</div></Row>}
        </>
      )}
      <Row><ButtonItem layout="below" onClick={run}>Refresh</ButtonItem></Row>
      <Row><div style={dim}>{hasKey ? "Claude debriefs are on." : "Optional: add an Anthropic API key for Claude-written debriefs. Lap data is sent to Anthropic when you open this page."}</div></Row>
      <Row><TextField label="Anthropic API key" bIsPassword value={key} onChange={(e: any) => setKey(e?.target?.value ?? "")} /></Row>
      <Row><ButtonItem layout="below" onClick={async () => { await setSetting("anthropic_api_key", key.trim()); setHasKey(!!key.trim()); setKey(""); toast(key.trim() ? "API key saved" : "API key removed"); }}>{key.trim() ? "Save key" : "Remove key"}</ButtonItem></Row>
    </PanelSection>
  );
}

function Feel({ go }: { go?: Go }) {
  const [cat, setCat] = useState<FfbCat | null>(null);
  const [last, setLast] = useState<FfbResult | null>(null);
  const load = async () => setCat(await ffbCatalogue());
  useEffect(() => { load(); }, []);
  const show = async (r: FfbResult, label: string) => {
    setLast(r);
    toast(r.ok ? (r.changes && r.changes.length === 0 ? "Already at the limit for this" : `${label} applied`) : r.message ?? "Failed");
    load();
  };
  if (!cat) return <PanelSection><Back go={go} /><Row>Loading…</Row></PanelSection>;
  return (
    <>
      <PanelSection title="Force feedback feel">
        <Back go={go} />
        <Row><div style={dim}>Change one thing at a time and drive a few corners before changing the next. Every change can be undone.</div></Row>
        <Row><div style={small}><b>What feels wrong?</b></div></Row>
        {cat.symptoms.map((x) => (
          <Row key={x.id}><ButtonItem layout="below" onClick={async () => show(await ffbNudge(x.id), "Adjustment")}>{x.label}</ButtonItem></Row>
        ))}
        {last?.changes && last.changes.length > 0 && (
          <Row><div style={small}>{last.changes.map((c) => <div key={c.label}>• {c.label}: {c.from} → {c.to} ({c.why})</div>)}</div></Row>
        )}
        {last?.tip && <Row><div style={small}>{last.tip}</div></Row>}
        {cat.can_undo && <Row><ButtonItem layout="below" onClick={async () => show(await ffbUndo(), "Undo")}>↩ Undo last change</ButtonItem></Row>}
      </PanelSection>
      <PanelSection title="Starting presets">
        {cat.presets.map((p) => (
          <Row key={p.id}>
            <ButtonItem layout="below" onClick={async () => show(await ffbApplyPreset(p.id), p.name)}>
              <div style={{ textAlign: "left" }}>
                <div>{p.name}</div>
                <div style={dim}>{p.summary}</div>
                <div style={{ ...dim, fontSize: "10px" }}>Source: {src(p.source)}</div>
              </div>
            </ButtonItem>
          </Row>
        ))}
      </PanelSection>
      {cat.ingame && (
        <PanelSection title={`In ${cat.game}`}>
          {cat.ingame.steps.map((t, i) => <Row key={i}><div style={small}>{i + 1}. {t}</div></Row>)}
          <Row><div style={small}>{cat.ingame.starting_points}</div></Row>
        </PanelSection>
      )}
    </>
  );
}

function Laps() {
  const laps = usePoll(recentLaps, 5000);
  return (
    <PanelSection title="Recent laps">
      {!laps ? <Row>Loading…</Row> : laps.length === 0 ? <Row><div style={small}>No laps yet.</div></Row> : laps.map((l) => (
        <Row key={l.id}>
          <div style={small}><b>{fmt(l.time)}</b> · {l.sim}{l.track ? ` · ${l.track}` : ""}{l.car ? ` · ${l.car}` : ""}
            <div style={dim}>{new Date(l.created * 1000).toLocaleString()} · {Math.round(l.length)} m</div></div>
        </Row>
      ))}
    </PanelSection>
  );
}

// Wheel buttons: what each one does in Steam and in games, and changing it by pressing it.
function ButtonsPage({ go }: { go?: Go }) {
  const st = usePoll(buttonsStatus, 400);
  const [learning, setLearning] = useState<string | null>(null);
  const learn = async (kind: string, r: BtnRow) => {
    if (learning) return;
    setLearning(`${kind}:${r.action}`);
    await buttonsLearn(kind, r.action);
    try {
      for (;;) {
        await new Promise((res) => setTimeout(res, 250));
        const x = await buttonsLearned();
        if (x.state === "waiting") continue;
        if (x.state === "done") toast(`${r.label}: ${x.label}${x.beamng && !x.beamng.ok && x.beamng.error ? `. ${x.beamng.error}` : ""}`);
        else if (x.state === "timeout") toast("No button pressed, nothing changed");
        break;
      }
    } finally { setLearning(null); }
  };
  if (!st) return <PanelSection title="Wheel buttons"><Back go={go} /><Row>Loading…</Row></PanelSection>;
  const last = st.recent[0];
  const rowItem = (kind: string, r: BtnRow) => (
    <Row key={kind + r.action}>
      <ButtonItem layout="inline" label={r.label} disabled={learning !== null && learning !== `${kind}:${r.action}`}
        onClick={() => learn(kind, r)}>
        {learning === `${kind}:${r.action}` ? "Press a button…" : r.button || "Not set"}
      </ButtonItem>
    </Row>
  );
  return (
    <>
      <PanelSection title="Wheel buttons">
        <Back go={go} />
        {st.devices.length === 0
          ? <Row><div style={dim}>No wheel found. Plug it in and switch it on; buttons show up here when Pitwall can see them.</div></Row>
          : <Row><div style={small}>
              {st.devices.map((d) => <div key={d.id}>{d.name}: {d.buttons} buttons{d.hats ? ", D-pad" : ""}</div>)}
              <div style={{ marginTop: "6px" }}>
                {last ? <>Last pressed: <b>{last.label}</b>
                  <div style={dim}>In Steam: {last.steam || "nothing"} · In game: {last.game || "not set by Pitwall"}</div></>
                  : <span style={dim}>Press any button on your wheel to see what it does.</span>}
              </div>
            </div></Row>}
        {learning && <Row><ButtonItem layout="below" onClick={async () => { await buttonsCancelLearn(); }}>Cancel</ButtonItem></Row>}
      </PanelSection>
      <PanelSection title="In Steam">
        <Row><ToggleField label="Use wheel buttons in Steam menus" checked={st.nav.enabled}
          description="Move around Steam with your wheel's D-pad and buttons. Turns itself off while a game runs, so games get the wheel to themselves."
          onChange={async (v) => { await setSetting("nav_enabled", v); }} /></Row>
        {st.nav.error && <Row><div style={{ ...small, color: "#ffb020" }}>{st.nav.error}</div></Row>}
        {st.nav.enabled && st.nav.rows.map((r) => rowItem("nav", r))}
        {st.nav.enabled && st.nav.custom && <Row><ButtonItem layout="below" onClick={() => buttonsReset("nav")}>Back to the automatic layout</ButtonItem></Row>}
      </PanelSection>
      <PanelSection title="In games">
        {!st.layout.paddles && st.devices.length > 0 && <Row><div style={{ ...small, color: "#4da3ff" }}>
          Set your shift paddles first: choose Shift up and press the right paddle, then Shift down and the left one. Brands number them differently, so Pitwall asks once.</div></Row>}
        {st.layout.rows.map((r) => rowItem("game", r))}
        <Row><ButtonItem layout="below" onClick={() => buttonsReset("game")}>Back to the automatic layout</ButtonItem></Row>
        <Row><ToggleField label="Set these up in BeamNG.drive" checked={st.beamng.auto}
          description={!st.beamng.found ? "BeamNG.drive's user folder wasn't found yet. Start the game once."
            : st.beamng.applied ? "Done. Buttons you bound yourself in BeamNG are kept. Takes effect next time BeamNG starts."
            : "Adds these to BeamNG's controls for your wheel. Your own bindings are kept."}
          onChange={async (v) => { const r = await beamngBind(v); if (!r.ok && r.error) toast(r.error); }} /></Row>
        <Row><div style={dim}>Other games: set the same buttons in the game's controls menu. When you press a button, your phone dashboard shows what it's set to.</div></Row>
      </PanelSection>
    </>
  );
}

function GuideBrowser({ go }: { go?: Go }) {
  const [id, setId] = useState<string | null>(null);
  return id ? <GamePage id={id} go={go} back={() => setId(null)} /> : <Games go={go} open={setId} />;
}

function FullScreen() {
  return (
    <div style={{ marginTop: "40px", height: "calc(100% - 40px)" }}>
      <SidebarNavigation
        title="Pitwall"
        showTitle
        pages={[
          { title: "Session", icon: <GiStopwatch />, content: <Home />, route: `${ROUTE}/session` },
          { title: "Laps", icon: <GiSpeedometer />, content: <Laps />, route: `${ROUTE}/laps` },
          "separator",
          { title: "Auto setup", icon: <GiCheckMark />, content: <AutoSetup />, route: `${ROUTE}/auto` },
          { title: "Game guide", icon: <GiBookCover />, content: <GuideBrowser />, route: `${ROUTE}/guide` },
          { title: "Pre-race checks", icon: <GiCheckMark />, content: <Checks />, route: `${ROUTE}/checks` },
          "separator",
          { title: "Wheel", icon: <GiSteeringWheel />, content: <Wheel />, route: `${ROUTE}/wheel` },
          { title: "Wheel buttons", icon: <GiSteeringWheel />, content: <ButtonsPage />, route: `${ROUTE}/buttons` },
          { title: "Force feedback feel", icon: <GiSteeringWheel />, content: <Feel />, route: `${ROUTE}/feel` },
          { title: "Fuel and tyres", icon: <GiFuelTank />, content: <Strategy />, route: `${ROUTE}/strategy` },
          "separator",
          { title: "Performance check", icon: <GiLightningArc />, content: <PerfPage />, route: `${ROUTE}/perf` },
          { title: "Engineer debrief", icon: <GiHeadphones />, content: <DebriefPage />, route: `${ROUTE}/engineer` },
          { title: "Updates", icon: <GiCheckMark />, content: <UpdatesPage />, route: `${ROUTE}/updates` },
          { title: "Send diagnostics", icon: <GiFirstAidKit />, content: <Diagnostics />, route: `${ROUTE}/diagnostics` },
        ]}
      />
    </div>
  );
}

// Updates for the third-party software Pitwall installed: force feedback drivers and the telemetry bridge.
function UpdatesPage({ go }: { go?: Go }) {
  const [u, setU] = useState<Updates | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [auto, setAuto] = useState(true);
  const load = async (force = false) => { setU(await updatesStatus(force)); };
  useEffect(() => { load(); getSettings().then((x: any) => setAuto(x.check_updates !== false)); }, []);
  const update = async (i: UpdateItem) => {
    setBusy(i.id);
    try {
      if (i.kind === "bridge") {
        toast((await bridgeInstall()).message);
      } else {
        const r = await driverInstall(i.id);
        if (!r.ok) { toast(r.message); return; }
        toast(`Updating ${i.name}. This takes a few minutes; progress is on the Wheel page.`);
        for (;;) {
          await new Promise((res) => setTimeout(res, 2000));
          const j = await driverJob();
          if (!j || j.state !== "running") { toast(j?.message || "Done"); break; }
        }
      }
      await load();
    } finally { setBusy(null); }
  };
  const when = u?.checked ? new Date(u.checked * 1000).toLocaleString() : "never";
  return (
    <PanelSection title="Updates">
      <Back go={go} />
      {!u ? <Row>Loading…</Row> : (
        <>
          {!u.has_anything && <Row><div style={dim}>Pitwall hasn't installed any drivers or the telemetry bridge, so there's nothing to update.</div></Row>}
          {u.items.map((i) => (
            <div key={i.id}>
              <Row><div style={small}>
                <b>{i.name}</b>: {i.error ? <span style={{ color: "#ffb020" }}>{i.error}</span>
                  : i.update ? <span style={{ color: "#4da3ff" }}>update available</span>
                  : <span style={{ color: "#3ddc84" }}>up to date</span>}
                <div style={dim}>Installed: {i.current || "unknown version"}{i.latest ? ` · latest: ${i.latest}${i.date ? ` (${i.date})` : ""}` : ""}</div>
              </div></Row>
              {i.update && <Row><ButtonItem layout="below" disabled={busy !== null} onClick={() => update(i)}>{busy === i.id ? "Updating…" : `Update ${i.name}`}</ButtonItem></Row>}
            </div>
          ))}
          <Row><ButtonItem layout="below" onClick={() => load(true)}>Check now</ButtonItem></Row>
          <Row><ToggleField label="Check daily" checked={auto} onChange={async (c: boolean) => { setAuto(c); await setSetting("check_updates", c); }} /></Row>
          <Row><div style={dim}>Last checked: {when}. Pitwall compares what it installed with each project's latest version on GitHub and tells you when there's something new. Nothing updates without you pressing Update. Game ratings and compatibility data refresh on their own.</div></Row>
        </>
      )}
    </PanelSection>
  );
}

function Content() {
  const [page, setPage] = useState("home");
  const [gameId, setGameId] = useState<string | null>(null);
  const go = (p: string) => setPage(p);
  switch (page) {
    case "wheel": return <Wheel go={go} />;
    case "games": return <Games go={go} open={(id) => { setGameId(id); setPage("game"); }} />;
    case "game": return gameId ? <GamePage id={gameId} go={go} back={() => setPage("games")} /> : <Home go={go} />;
    case "buttons": return <ButtonsPage go={go} />;
    case "feel": return <Feel go={go} />;
    case "strategy": return <Strategy go={go} />;
    case "auto": return <AutoSetup go={go} />;
    case "diag": return <Diagnostics go={go} />;
    case "checks": return <Checks go={go} />;
    case "perf": return <PerfPage go={go} />;
    case "debrief": return <DebriefPage go={go} />;
    case "updates": return <UpdatesPage go={go} />;
    default: return <Home go={go} />;
  }
}

export default definePlugin(() => {
  let reg: { unregister: () => void } | undefined;
  try {
    reg = SteamClient.GameSessions.RegisterForAppLifetimeNotifications(
      async (e: { unAppID: number; bRunning: boolean }) => {
        const app = runningApp();
        const name = app && app.appid === String(e.unAppID) ? app.name : "";
        try {
          const r = await gameChanged(String(e.unAppID), name, e.bRunning);
          if (r.applied) toast(`Applied wheel profile: ${r.applied}`);
          if (e.bRunning && r.game?.status === "broken") toast(`${r.game.name} is known not to run on SteamOS. See Pitwall's game guide.`);
        } catch (err) {
          console.error("Pitwall: game change handling failed", err);
        }
      }
    );
  } catch (err) {
    console.error("Pitwall: game notifications unavailable", err);
  }
  routerHook.addRoute(ROUTE, FullScreen);
  const toastListener = addEventListener<[msg: string]>("pitwall_toast", (msg) => toast(msg));
  return {
    name: "Pitwall",
    titleView: <div className={staticClasses.Title}>Pitwall</div>,
    content: <Content />,
    icon: <GiCheckeredFlag />,
    onDismount() { reg?.unregister(); routerHook.removeRoute(ROUTE); removeEventListener("pitwall_toast", toastListener); },
  };
});
