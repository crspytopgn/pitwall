import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  TextField,
  Router,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useRef, useState, ReactNode } from "react";
import { GiCheckeredFlag } from "react-icons/gi";

// ---------------------------------------------------------------- backend
type SettingDef = { min: number; max: number; step: number; label: string; suffix: string; toggle: boolean };
type WheelStatus = { connected: boolean; name?: string; brand?: string; error?: string; settings?: Record<string, SettingDef>; can_center?: boolean };
type Profiles = { auto_apply: boolean; has_default: boolean; games: Record<string, string> };
type Session = {
  receiving: boolean; sim: string | null; car: string | null; track: string | null; needs_start_line: boolean;
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
const getSettings = callable<[], { target_fps: number; anthropic_api_key: boolean }>("get_settings");
const setSetting = callable<[key: string, value: any], boolean>("set_setting");

declare const SteamClient: any;

const toast = (body: string) => toaster.toast({ title: "Pitwall", body });
const fmt = (s: number | null | undefined) => {
  if (s == null || !isFinite(s) || s <= 0) return "–";
  const m = Math.floor(s / 60), r = s - m * 60;
  return (m ? `${m}:${r < 10 ? "0" : ""}` : "") + r.toFixed(3);
};
const STATUS: Record<string, string> = { works: "✅ Works", setup: "🛠️ Works with setup", community: "⚠️ Community fixes only", broken: "⛔ Doesn't run" };
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

function Back({ go }: { go: (p: string) => void }) {
  return <Row><ButtonItem layout="below" onClick={() => go("home")}>‹ Back</ButtonItem></Row>;
}

// ------------------------------------------------------------------ pages
function Home({ go }: { go: (p: string) => void }) {
  const s = usePoll(sessionStatus, 1000);
  const game = runningApp();
  return (
    <>
      <PanelSection title="Session">
        {!s ? <Row>Starting…</Row> : (
          <>
            <Row>
              <div style={small}>
                {s.receiving ? <>📡 Telemetry: <b>{s.sim}</b>{s.track ? ` · ${s.track}` : ""}</> : <>📡 Waiting for telemetry{game ? ` from ${game.name}` : ""}</>}
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
            {s.tips.length > 0 && <Row><div style={small}>{s.tips.map((t) => <div key={t}>💡 {t}</div>)}</div></Row>}
            <Row>
              <div style={dim}>
                {s.dashboard_url ? <>📱 Dashboard: <b>{s.dashboard_url}</b> (open on a phone on the same Wi-Fi)</> : s.dashboard_error}
              </div>
            </Row>
          </>
        )}
      </PanelSection>
      <PanelSection title="Tools">
        <Row><ButtonItem layout="below" onClick={() => go("wheel")}>🛞 Wheel settings &amp; profiles</ButtonItem></Row>
        <Row><ButtonItem layout="below" onClick={() => go("games")}>📖 Game guide &amp; compatibility</ButtonItem></Row>
        <Row><ButtonItem layout="below" onClick={() => go("checks")}>✅ Pre-race checks</ButtonItem></Row>
        <Row><ButtonItem layout="below" onClick={() => go("perf")}>⚡ Performance</ButtonItem></Row>
        <Row><ButtonItem layout="below" onClick={() => go("debrief")}>🎧 Engineer debrief</ButtonItem></Row>
      </PanelSection>
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

function Wheel({ go }: { go: (p: string) => void }) {
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
    <PanelSection title="Wheel"><Back go={go} />
      <Row><div style={small}>{st.error}</div></Row>
      <Row><ButtonItem layout="below" onClick={refresh}>Retry</ButtonItem></Row>
    </PanelSection>
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
        {Object.keys(defs).some((k) => !CORE_KEYS.includes(k)) && (
          <Row><ToggleField label="Effect settings" checked={more} onChange={setMore} /></Row>
        )}
        {more && Object.keys(defs).filter((k) => !CORE_KEYS.includes(k)).map(render)}
      </PanelSection>
      <PanelSection title="Profiles">
        <Row><ToggleField label="Auto-apply per game" checked={prof?.auto_apply ?? true} onChange={async (c: boolean) => { await setAutoApply(c); setProf(await getProfiles()); }} /></Row>
        {game && <Row><ButtonItem layout="below" onClick={() => save(game.appid, game.name)}>{hasProfile ? "Update" : "Save"} profile for {game.name}</ButtonItem></Row>}
        {game && hasProfile && <Row><ButtonItem layout="below" onClick={async () => { await deleteProfile(game.appid); setProf(await getProfiles()); }}>Delete profile for {game.name}</ButtonItem></Row>}
        <Row><ButtonItem layout="below" onClick={() => save("default", "Default")}>{prof?.has_default ? "Update" : "Save"} default (outside games)</ButtonItem></Row>
        {prof && Object.keys(prof.games).length > 0 && <Row><div style={dim}>Saved: {Object.values(prof.games).join(", ")}</div></Row>}
      </PanelSection>
    </>
  );
}

function Games({ go, open }: { go: (p: string) => void; open: (id: string) => void }) {
  const list = usePoll(compatList, 30000);
  return (
    <PanelSection title="Game guide">
      <Back go={go} />
      {!list ? <Row>Loading…</Row> : list.map((g) => (
        <Row key={g.id}>
          <ButtonItem layout="below" onClick={() => open(g.id)}>
            <div style={{ textAlign: "left" }}>
              <div>{g.name}{g.installed ? " · installed" : ""}</div>
              <div style={dim}>{STATUS[g.status] ?? g.status}{g.telemetry && g.telemetry !== "planned" ? ` · telemetry: ${g.telemetry}` : g.telemetry === "planned" ? " · telemetry planned" : ""}</div>
            </div>
          </ButtonItem>
        </Row>
      ))}
    </PanelSection>
  );
}

function GamePage({ id, go }: { id: string; go: (p: string) => void }) {
  const [g, setG] = useState<GameDetail | null>(null);
  useEffect(() => { compatDetail(id).then(setG); }, [id]);
  if (!g) return <PanelSection><Back go={go} /><Row>Fetching live ratings…</Row></PanelSection>;
  return (
    <>
      <PanelSection title={g.name}>
        <Row><ButtonItem layout="below" onClick={() => go("games")}>‹ All games</ButtonItem></Row>
        <Row>
          <div style={small}>
            <b>{STATUS[g.status]}</b> ({g.runtime === "native" ? "native Linux" : g.runtime === "proton" ? "Proton" : "not runnable"})<br />
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
        {g.wheel && <Row><div style={small}>🛞 Suggested rotation {g.wheel.rotation}°. {g.wheel.note}</div></Row>}
      </PanelSection>
      {g.known_issues.length > 0 && (
        <PanelSection title="Known issues">
          {g.known_issues.map((k, i) => <Row key={i}><div style={small}>• {k.text}<div style={dim}>{k.source.replace(/^https:\/\/(www\.)?/, "")}</div></div></Row>)}
        </PanelSection>
      )}
    </>
  );
}

function Checks({ go }: { go: (p: string) => void }) {
  const [res, setRes] = useState<Check[] | null>(null);
  const run = async () => { setRes(null); setRes(await healthCheck()); };
  useEffect(() => { run(); }, []);
  return (
    <PanelSection title="Pre-race checks">
      <Back go={go} />
      {!res ? <Row>Checking…</Row> : res.map((c) => (
        <Row key={c.id}><div style={small}>{c.ok === true ? "✅" : c.ok === false ? "❌" : "ℹ️"} <b>{c.title}</b>{c.detail && <div style={dim}>{c.detail}</div>}</div></Row>
      ))}
      <Row><ButtonItem layout="below" onClick={run}>Run again</ButtonItem></Row>
    </PanelSection>
  );
}

const LS_KEY = "pitwall-saved-launch-options";
function savedOpts(): Record<string, string> { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; } }
function storeOpts(v: Record<string, string>) { try { localStorage.setItem(LS_KEY, JSON.stringify(v)); } catch { /* ignore */ } }
function currentLaunchOptions(appid: string): string | null {
  try {
    const d = (window as any).appDetailsStore?.GetAppDetails?.(Number(appid));
    return typeof d?.strLaunchOptions === "string" ? d.strLaunchOptions : null;
  } catch { return null; }
}

function PerfPage({ go }: { go: (p: string) => void }) {
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
    const cur = currentLaunchOptions(app.appid);
    if (cur === null) { toast("Couldn't read this game's launch options; benchmark not set to avoid overwriting them"); return; }
    const saved = savedOpts(); saved[app.appid] = cur; storeOpts(saved);
    const opts = await benchmarkOptions(90);
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
    <PanelSection title="Performance">
      <Back go={go} />
      <Row><SliderField label="Target FPS" value={target} min={30} max={144} step={1} showValue onChange={(v: number) => { setTarget(v); setSetting("target_fps", v); }} notchTicksVisible={false} /></Row>
      <Row><div style={dim}>Match your TV: usually 60 or 120.</div></Row>
      <Row><ButtonItem layout="below" onClick={startBench}>Arm 90 s benchmark{pickApp() ? ` for ${pickApp()!.name}` : ""}</ButtonItem></Row>
      {benchFor.map((a) => <Row key={a}><ButtonItem layout="below" onClick={() => restore(a)}>Restore launch options (app {a})</ButtonItem></Row>)}
      <Row><ButtonItem layout="below" onClick={async () => { const a = pickApp(); setRes(await perfAnalyse(a?.appid ?? "", a?.name ?? "")); }}>Analyse latest benchmark</ButtonItem></Row>
      {res && (!res.ok ? <Row><div style={small}>{res.message}</div></Row> : (
        <Row>
          <div style={small}>
            <b>{res.verdict === "great" ? "✅ Smooth" : res.verdict === "stutters" ? "⚠️ Stuttering" : "❌ Below target"}</b><br />
            Average {res.avg_fps} FPS · 1% low {res.low1_fps} · {res.stutters_per_min} stutters/min
            {res.advice?.map((a) => <div key={a} style={{ marginTop: 4 }}>• {a}</div>)}
          </div>
        </Row>
      ))}
    </PanelSection>
  );
}

function DebriefPage({ go }: { go: (p: string) => void }) {
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

function Content() {
  const [page, setPage] = useState("home");
  const [gameId, setGameId] = useState<string | null>(null);
  const go = (p: string) => setPage(p);
  switch (page) {
    case "wheel": return <Wheel go={go} />;
    case "games": return <Games go={go} open={(id) => { setGameId(id); setPage("game"); }} />;
    case "game": return gameId ? <GamePage id={gameId} go={go} /> : <Home go={go} />;
    case "checks": return <Checks go={go} />;
    case "perf": return <PerfPage go={go} />;
    case "debrief": return <DebriefPage go={go} />;
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
        const r = await gameChanged(String(e.unAppID), name, e.bRunning);
        if (r.applied) toast(`Applied wheel profile: ${r.applied}`);
        if (e.bRunning && r.game?.status === "broken") toast(`${r.game.name} is known not to run on SteamOS. See Pitwall's game guide.`);
      }
    );
  } catch (err) {
    console.error("Pitwall: game notifications unavailable", err);
  }
  return {
    name: "Pitwall",
    titleView: <div className={staticClasses.Title}>Pitwall</div>,
    content: <Content />,
    icon: <GiCheckeredFlag />,
    onDismount() { reg?.unregister(); },
  };
});
