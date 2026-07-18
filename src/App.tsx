import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  Clipboard,
  Cpu,
  GripVertical,
  History,
  Keyboard,
  Mic,
  Mic2,
  Pencil,
  Play,
  Plus,
  RefreshCcw,
  Settings as SettingsIcon,
  SlidersHorizontal,
  Square,
  Terminal,
  Trash2
} from "lucide-react";
import { AppState, DeviceInfo, LogEntry, Mode, Settings, Skill, api, autostart, ensureSidecar, hideMainWindow } from "./api";
import deepseekLogo from "./assets/deepseek-logo.svg";

type Tab = "main" | "general" | "speech" | "llm" | "modes" | "skills" | "shortcuts" | "logs" | "history";

const emptySettings: Settings = {
  app_name: "Aura",
  mode_id: "professional",
  auto_copy: true,
  save_history: true,
  auto_launch: false,
  keep_window_on_top: false,
  hotkey: "<ctrl>+<shift>+<space>",
  push_to_talk_key: "space",
  input_device_index: null,
  stt_provider: "sensevoice-small",
  model_cache_dir: "",
  llm_provider: "deepseek",
  llm_base_url: "https://api.deepseek.com",
  llm_api_key: "",
  llm_model: "deepseek-v4-flash",
  llm_thinking_enabled: false,
  llm_temperature: 0.2,
  llm_timeout_seconds: 60,
  history_path: null,
  skills: [],
  skill_scan_dir: ""
};

function compactText(value: string, limit = 34) {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function shortTime(value: string) {
  if (!value) return "";
  return new Date(value).toLocaleString([], {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function stateSkills(state: AppState) {
  return state.skills || state.settings.skills || [];
}

const deepseekModels = ["deepseek-v4-flash", "deepseek-v4-pro"];
const apiKeyMask = "********";

function isDeepSeekEndpoint(value: string) {
  const normalized = value.trim().toLowerCase().replace(/\/+$/, "");
  return normalized === "https://api.deepseek.com" || normalized === "https://api.deepseek.com/v1";
}

export default function App() {
  const [state, setState] = useState<AppState | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("main");
  const [transcript, setTranscript] = useState("");
  const [compiled, setCompiled] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Settings>(emptySettings);
  const [deepseekApiKeyDraft, setDeepseekApiKeyDraft] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [micTestCountdown, setMicTestCountdown] = useState(0);
  const [micTestActive, setMicTestActive] = useState(false);
  const [modeDrafts, setModeDrafts] = useState<Mode[]>([]);
  const [skillDrafts, setSkillDrafts] = useState<Skill[]>([]);
  const [skillScanDir, setSkillScanDir] = useState("");
  const [speechTestResult, setSpeechTestResult] = useState("");
  const [bootProgress, setBootProgress] = useState(0);
  const [bootStatus, setBootStatus] = useState("正在连接 Aura sidecar");
  const [bootStage, setBootStage] = useState("connecting");
  const [bootElapsedSeconds, setBootElapsedSeconds] = useState(0);
  const [transcriptEditing, setTranscriptEditing] = useState(false);
  const [compiledEditing, setCompiledEditing] = useState(false);
  const recordingRef = useRef(false);
  const transcriptEditedByUser = useRef(false);
  const historySelectRef = useRef<HTMLSelectElement>(null);

  const status = error || state?.runtime.status || "启动中";
  const selectedMode = state?.current_mode;

  useEffect(() => {
    if (state || error) return;
    const startedAt = Date.now();
    const updateElapsed = () => {
      setBootElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    };
    updateElapsed();
    const id = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(id);
  }, [error, state]);

  useEffect(() => {
    const draftIsDeepSeek = draft.llm_provider === "deepseek" || isDeepSeekEndpoint(draft.llm_base_url);
    if (draftIsDeepSeek && draft.llm_api_key !== deepseekApiKeyDraft) {
      setDeepseekApiKeyDraft(draft.llm_api_key);
    }
  }, [deepseekApiKeyDraft, draft.llm_api_key, draft.llm_base_url, draft.llm_provider]);

  const refresh = useCallback(async () => {
    const next = await api.state();
    setState(next);
    setDraft(next.settings);
    return next;
  }, []);

  const loadDevices = useCallback(async () => {
    const payload = await api.devices();
    setDevices(payload.devices);
  }, []);

  const loadLogs = useCallback(async () => {
    const payload = await api.logs();
    setLogs(payload.logs);
    setState(payload.state);
    return payload.logs;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      try {
        await ensureSidecar();
        if (cancelled) return;
        setBootStatus("正在准备语音识别模型");
        setBootStage("checking");
        let initial = await api.state();
        setBootProgress(initial.service.transcriber_progress);
        setBootStage(initial.service.transcriber_status);
        setBootStatus(
          initial.service.transcriber_ready
            ? "语音识别模型已就绪"
            : "正在检查本地语音模型"
        );
        if (!initial.service.transcriber_ready) {
          await api.warmupStt();
          while (!cancelled) {
            initial = await api.state();
            setBootProgress(initial.service.transcriber_progress);
            setBootStage(initial.service.transcriber_status);
            setBootStatus(initial.runtime.status || "正在加载语音识别模型");
            if (initial.service.transcriber_ready) break;
            if (initial.service.transcriber_status === "error") {
              throw new Error(initial.service.transcriber_error || initial.runtime.status || "语音识别模型加载失败");
            }
            await new Promise((resolve) => window.setTimeout(resolve, 200));
          }
        }
        if (cancelled) return;
        setBootProgress(100);
        setBootStage("ready");
        setBootStatus("语音识别模型已就绪");
        const latestHistory = initial.history[0];
        const restored = latestHistory ? await api.loadSession(latestHistory.id) : null;
        const next = restored?.state || (await api.newSession(initial.current_mode?.id || initial.settings.mode_id)).state;
        if (!cancelled) {
          setState(next);
          setDraft(next.settings);
          setModeDrafts(next.modes);
          setSkillDrafts(stateSkills(next));
          setSkillScanDir(next.settings.skill_scan_dir || "");
          setTranscript(restored?.transcript || "");
          setCompiled(restored?.compiled || "");
          setCopied(false);
        }
        const devicePayload = await api.devices().catch(() => ({ devices: [] }));
        if (!cancelled) setDevices(devicePayload.devices);
        const logPayload = await api.logs().catch(() => ({ logs: [] }));
        if (!cancelled) setLogs(logPayload.logs);

        // Sync autostart state: ensure OS setting matches user preference
        try {
          const osEnabled = await autostart.isEnabled();
          if (osEnabled !== next.settings.auto_launch) {
            if (next.settings.auto_launch) {
              await autostart.enable();
            } else {
              await autostart.disable();
            }
          }
        } catch { /* ignore on unsupported platforms */ }
      } catch (exc) {
        if (!cancelled) setError(exc instanceof Error ? exc.message : String(exc));
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (activeTab !== "logs") return;
    void loadLogs().catch(() => undefined);
    const id = window.setInterval(() => {
      void loadLogs().catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(id);
  }, [activeTab, loadLogs]);

  useEffect(() => {
    if (!state?.runtime.recording) return;
    const id = window.setInterval(async () => {
      try {
        const runtime = await api.status();
        setState((current) => (current ? { ...current, runtime } : current));
      } catch {
        window.clearInterval(id);
      }
    }, 220);
    return () => window.clearInterval(id);
  }, [state?.runtime.recording]);

  useEffect(() => {
    if (!micTestActive) return;
    setMicTestCountdown(3);
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      const remaining = Math.max(0, 3 - Math.floor((Date.now() - startedAt) / 1000));
      setMicTestCountdown(remaining);
      if (remaining === 0) window.clearInterval(id);
    }, 200);
    return () => window.clearInterval(id);
  }, [micTestActive]);

  useEffect(() => {
    if (!micTestActive) return;
    const id = window.setInterval(async () => {
      try {
        const runtime = await api.status();
        setState((current) => (current ? { ...current, runtime } : current));
      } catch {
        window.clearInterval(id);
      }
    }, 120);
    return () => window.clearInterval(id);
  }, [micTestActive]);

  const startRecording = useCallback(async () => {
    historySelectRef.current?.blur();
    if (recordingRef.current) return;
    if (!state) {
      setBootStatus("语音模型仍在加载，完成后即可按住空格录音");
      return;
    }
    if (!state.service.transcriber_ready) {
      setError("语音识别模型尚未就绪，请稍候再录音。");
      return;
    }
    if (busy) {
      setError("上一段录音仍在处理中，请完成后再录音。");
      return;
    }
    try {
      setError("");
      setCopied(false);
      setTranscript("");
      setCompiled("");
      setTranscriptEditing(false);
      setCompiledEditing(false);
      transcriptEditedByUser.current = false;
      recordingRef.current = true;
      const payload = await api.startRecording();
      setState(payload.state);
    } catch (exc) {
      recordingRef.current = false;
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [busy, state]);

  const stopRecording = useCallback(async () => {
    if (!recordingRef.current) return;
    recordingRef.current = false;
    setBusy(true);
    try {
      const payload = await api.stopRecording();
      if (!payload.job) {
        const legacyPayload = payload as unknown as { transcript?: string; compiled?: string; state?: AppState };
        setTranscript(legacyPayload.transcript || "");
        setCompiled(legacyPayload.compiled || "");
        if (legacyPayload.state) setState(legacyPayload.state);
        setBusy(false);
        setError("Aura sidecar 协议过旧，请重启应用。");
        return;
      }
      setTranscript(payload.job.transcript);
      setCompiled(payload.job.compiled);
      setState(payload.state);
      setActiveJobId(payload.job.id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      await refresh().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;
    let copiedJob = false;

    async function poll() {
      try {
        const payload = await api.job(activeJobId);
        if (cancelled) return;
        setState(payload.state);
        setError(payload.job.error);
        if (!transcriptEditedByUser.current) {
          setTranscript(payload.job.transcript);
        }
        setCompiled(payload.job.compiled);
        if (payload.job.done) {
          setBusy(false);
          setActiveJobId("");
          if (!payload.job.error && payload.state.settings.auto_copy && payload.job.compiled && !copiedJob) {
            copiedJob = true;
            if (!cancelled) setCopied(true);
            await navigator.clipboard.writeText(payload.job.compiled).catch(() => undefined);
          }
          return;
        }
        window.setTimeout(poll, 180);
      } catch (exc) {
        if (!cancelled) {
          setBusy(false);
          setActiveJobId("");
          setError(exc instanceof Error ? exc.message : String(exc));
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [activeJobId]);

  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => {
      setCopied(false);
      setState((current) => {
        if (!current || current.runtime.status !== "已复制") return current;
        return { ...current, runtime: { ...current.runtime, status: "整理完成" } };
      });
    }, 1500);
    return () => window.clearTimeout(id);
  }, [copied]);

  const keyboardContextRef = useRef({
    activeTab,
    startRecording,
    stopRecording,
    newSession,
    shiftMode
  });
  keyboardContextRef.current = {
    activeTab,
    startRecording,
    stopRecording,
    newSession,
    shiftMode
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const context = keyboardContextRef.current;
      const editing = ["textarea", "input"].includes(
        (document.activeElement?.tagName || "").toLowerCase()
      );
      if (event.code === "Space" && !event.repeat && context.activeTab === "main" && !editing) {
        event.preventDefault();
        void context.startRecording();
      }
      if (event.ctrlKey && event.key.toLowerCase() === "n") {
        event.preventDefault();
        void context.newSession();
      }
      if (event.ctrlKey && event.key === "ArrowUp") {
        event.preventDefault();
        void context.shiftMode(-1);
      }
      if (event.ctrlKey && event.key === "ArrowDown") {
        event.preventDefault();
        void context.shiftMode(1);
      }
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        void hideMainWindow().catch((exc) => {
          setError(exc instanceof Error ? exc.message : String(exc));
        });
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      const context = keyboardContextRef.current;
      const editing = ["textarea", "input"].includes(
        (document.activeElement?.tagName || "").toLowerCase()
      );
      if (event.code === "Space" && context.activeTab === "main" && !editing) {
        event.preventDefault();
        void context.stopRecording();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  async function setMode(modeId: string) {
    const payload = await api.setMode(modeId);
    setState(payload.state);
  }

  async function loadHistorySession(sessionId: string) {
    historySelectRef.current?.blur();
    if (!sessionId || sessionId === state?.current_session.id) return;
    const payload = await api.loadSession(sessionId);
    setState(payload.state);
    setDraft(payload.state.settings);
    setTranscript(payload.transcript);
    setCompiled(payload.compiled);
    setCopied(false);
    setActiveJobId("");
    setTranscriptEditing(false);
    setCompiledEditing(false);
  }

  async function shiftMode(delta: number) {
    if (!state?.modes.length || !state.current_mode) return;
    const index = state.modes.findIndex((mode) => mode.id === state.current_mode.id);
    const nextIndex = (Math.max(index, 0) + delta + state.modes.length) % state.modes.length;
    await setMode(state.modes[nextIndex].id);
  }

  async function newSession() {
    const modeId = state?.current_mode.id || draft.mode_id;
    const payload = await api.newSession(modeId);
    setState(payload.state);
    setTranscript("");
    setCompiled("");
    setCopied(false);
    setTranscriptEditing(false);
    setCompiledEditing(false);
  }

  async function copyCompiled() {
    if (!compiled.trim()) return;
    await navigator.clipboard.writeText(compiled);
    setCopied(true);
  }

  async function recompile() {
    if (!transcript.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.updateTurn(transcript, compiled);
      const payload = await api.compile(transcript);
      setCompiled(payload.compiled);
      setState(payload.state);
      setTranscriptEditing(false);
      setCompiledEditing(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function finishEditing(area: "transcript" | "compiled") {
    if (area === "transcript") {
      await recompile();
      return;
    }
    try {
      const payload = await api.updateTurn(transcript, compiled);
      setState(payload.state);
      setCompiledEditing(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function saveSpeech() {
    const payload = await api.saveSpeech(draft);
    setState(payload.state);
  }

  async function saveLlm() {
    const payload = await api.saveLlm(draft);
    setState(payload.state);
    setDraft(payload.state.settings);
  }

  async function saveModes() {
    const payload = await api.saveModes(modeDrafts);
    setState(payload.state);
    setDraft(payload.state.settings);
    setModeDrafts(payload.state.modes);
  }

  async function scanSkills() {
    try {
      setError("");
      const payload = await api.scanSkills(skillScanDir);
      setState(payload.state);
      setDraft(payload.state.settings);
      setSkillDrafts(stateSkills(payload.state));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function saveSkills() {
    try {
      setError("");
      const payload = await api.saveSkills(skillDrafts, skillScanDir);
      setState(payload.state);
      setDraft(payload.state.settings);
      setSkillDrafts(stateSkills(payload.state));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function warmup() {
    const payload = await api.warmupStt();
    setState(payload.state);
  }

  async function testMicrophone() {
    setBusy(true);
    setError("");
    setMicTestActive(true);
    setTranscript("");
    setSpeechTestResult("");
    try {
      const payload = await api.testMicrophone();
      setState(payload.state);
      setTranscript(
        `时长: ${payload.recording.duration_seconds.toFixed(2)}s\n平均音量: ${payload.recording.average_volume.toFixed(0)}\n最大音量: ${payload.recording.max_volume}`
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setMicTestActive(false);
      setMicTestCountdown(0);
      setBusy(false);
    }
  }

  async function transcribeTest() {
    setBusy(true);
    setError("");
    try {
      const payload = await api.transcribeTest();
      setState(payload.state);
      setSpeechTestResult(payload.transcript || "未识别到内容");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function clearHistory() {
    const payload = await api.clearHistory();
    setState(payload.state);
  }

  async function deleteHistory(sessionId: string) {
    if (!window.confirm("删除这条历史记录？此操作无法撤销。")) return;
    const payload = await api.deleteHistory(sessionId);
    setState(payload.state);
    if (payload.deleted_current) {
      setTranscript("");
      setCompiled("");
      setCopied(false);
      setActiveJobId("");
      setTranscriptEditing(false);
      setCompiledEditing(false);
    }
  }

  async function clearLogs() {
    const payload = await api.clearLogs();
    setLogs(payload.logs);
    setState(payload.state);
  }

  const volumePercent = useMemo(() => {
    const value = state?.runtime.volume || 0;
    return Math.max(0, Math.min(100, (value / 1800) * 100));
  }, [state?.runtime.volume]);

  const micTestLevel = useMemo(() => {
    const value = state?.runtime.volume || 0;
    return Math.max(0, Math.min(1, value / 1800));
  }, [state?.runtime.volume]);

  function openSettings(tab: Tab = "general") {
    if (state) {
      setModeDrafts(state.modes);
      setSkillDrafts(stateSkills(state));
      setSkillScanDir(state.settings.skill_scan_dir || "");
    }
    setActiveTab(tab);
  }

  function closeSettings() {
    setActiveTab("main");
  }

  if (!state) {
    return (
      <main className="boot">
        <div className="boot-mark"><Cpu size={24} /></div>
        <div className="boot-copy">
          <strong>{error ? "启动失败" : "正在启动 Aura"}</strong>
          <span>{error || bootStatus}</span>
          <div
            className={`boot-progress ${!error && bootProgress < 100 ? "active" : ""}`}
            role="progressbar"
            aria-label="STT 模型加载进度"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={bootProgress}
          >
            <i style={{ width: `${error ? bootProgress : Math.max(bootProgress, 5)}%` }} />
          </div>
          <small>
            {error
              ? "启动未完成，请根据上方信息检查配置"
              : bootStage === "downloading"
                ? `模型正在下载 · 已等待 ${bootElapsedSeconds} 秒 · 下载速度取决于网络`
                : `${Math.round(bootProgress)}% · 已等待 ${bootElapsedSeconds} 秒 · 后台仍在工作`}
          </small>
        </div>
      </main>
    );
  }

  if (activeTab !== "main") {
    return (
      <main className="app-shell settings-shell">
        <section className="settings-view">
          <header className="settings-header">
            <button title="返回" onClick={closeSettings}>
              <ArrowLeft size={16} />
              <span>返回</span>
            </button>
            <div>
              <strong>设置</strong>
              <span>{selectedMode?.name || "Mode"}</span>
            </div>
          </header>
          <div className="settings-content">
            <nav className="settings-tabs">
              <button className={activeTab === "general" ? "active" : ""} onClick={() => setActiveTab("general")}>
                <SettingsIcon size={15} />
                <span>通用</span>
              </button>
              <button className={activeTab === "speech" ? "active" : ""} onClick={() => setActiveTab("speech")}>
                <Mic size={15} />
                <span>语音</span>
              </button>
              <button className={activeTab === "llm" ? "active" : ""} onClick={() => setActiveTab("llm")}>
                <SlidersHorizontal size={15} />
                <span>LLM</span>
              </button>
              <button className={activeTab === "modes" ? "active" : ""} onClick={() => setActiveTab("modes")}>
                <GripVertical size={15} />
                <span>模式</span>
              </button>
              <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}>
                <Cpu size={15} />
                <span>Skill 配置</span>
              </button>
              <button className={activeTab === "shortcuts" ? "active" : ""} onClick={() => setActiveTab("shortcuts")}>
                <Keyboard size={15} />
                <span>快捷键</span>
              </button>
              <button className={activeTab === "logs" ? "active" : ""} onClick={() => setActiveTab("logs")}>
                <Terminal size={15} />
                <span>日志</span>
              </button>
              <button className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>
                <History size={15} />
                <span>历史</span>
              </button>
            </nav>
            <div className="settings-page">
            {activeTab === "general" ? (
              <GeneralSettings draft={draft} onDraft={setDraft} onStateChange={setState} />
            ) : null}
            {activeTab === "speech" ? (
              <SpeechSettings
                draft={draft}
                devices={devices}
                busy={busy}
                micTestActive={micTestActive}
                micTestCountdown={micTestCountdown}
                micTestLevel={micTestLevel}
                speechTestResult={speechTestResult}
                onDraft={setDraft}
                onRefreshDevices={loadDevices}
                onSave={saveSpeech}
                onWarmup={warmup}
                onTestMic={testMicrophone}
                onTranscribeTest={transcribeTest}
              />
            ) : null}
            {activeTab === "llm" ? (
              <LlmSettings
                draft={draft}
                deepseekApiKey={deepseekApiKeyDraft}
                onDeepseekApiKeyChange={setDeepseekApiKeyDraft}
                onDraft={setDraft}
                onSaveLlm={saveLlm}
              />
            ) : null}
            {activeTab === "modes" ? (
              <ModeSettings modes={modeDrafts} onModes={setModeDrafts} onSave={saveModes} />
            ) : null}
            {activeTab === "skills" ? (
              <SkillSettings
                skills={skillDrafts}
                skillScanDir={skillScanDir}
                onSkillScanDir={setSkillScanDir}
                onSkills={setSkillDrafts}
                onScan={scanSkills}
                onSave={saveSkills}
              />
            ) : null}
            {activeTab === "shortcuts" ? <ShortcutsPanel /> : null}
            {activeTab === "logs" ? <LogsPanel logs={logs} onRefresh={loadLogs} onClear={clearLogs} /> : null}
            {activeTab === "history" ? <HistoryPanel state={state} onClear={clearHistory} onDelete={deleteHistory} /> : null}
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Mic2 size={22} />
          <div>
            <strong>Aura</strong>
            <span>{selectedMode?.name || "Mode"}</span>
          </div>
        </div>
        <select value={selectedMode?.id || ""} onChange={(event) => setMode(event.target.value)}>
          {state.modes.map((mode) => (
            <option key={mode.id} value={mode.id}>
              {mode.name}
            </option>
          ))}
        </select>
        <select
          key={state.current_session.id}
          ref={historySelectRef}
          aria-label="历史会话"
          value={state.current_session.id}
          disabled={state.runtime.recording || busy}
          onChange={(event) => {
            const sessionId = event.currentTarget.value;
            event.currentTarget.blur();
            void loadHistorySession(sessionId);
          }}
          onKeyDown={(event) => {
            if (event.code === "Space") {
              event.preventDefault();
              event.currentTarget.blur();
            }
          }}
        >
          <option value={state.current_session.id}>历史会话</option>
          {state.history.filter((item) => item.id !== state.current_session.id).map((item) => (
            <option key={item.id} value={item.id}>
              {shortTime(item.updated_at)} · {compactText(item.last_transcript || item.last_compiled || item.title, 42)}
            </option>
          ))}
        </select>
        <div className={`status ${state.runtime.recording ? "recording" : ""} ${copied ? "copied" : ""}`}>
          <span>{status}</span>
          <div className="meter">
            <i style={{ width: `${volumePercent}%` }} />
          </div>
        </div>
        <button title="新会话" onClick={newSession}>
          <RefreshCcw size={16} />
        </button>
        <button title="设置" onClick={() => openSettings("general")}>
          <SettingsIcon size={16} />
        </button>
      </header>

      <section className="workspace">
        <div className="editor-column">
          <div className="text-pane">
            <div className="pane-head">
              <span>原始转录</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                {state.runtime.recording ? <Mic size={16} /> : null}
                <button
                  title={transcriptEditing ? "完成编辑" : "编辑原始转录"}
                  disabled={busy || state.runtime.recording}
                  onClick={() => transcriptEditing ? void finishEditing("transcript") : setTranscriptEditing(true)}
                >
                  {transcriptEditing ? <Check size={14} /> : <Pencil size={14} />}
                  <span>{transcriptEditing ? "完成" : "编辑"}</span>
                </button>
              </div>
            </div>
            <textarea
              value={transcript}
              readOnly={!transcriptEditing}
              aria-label="原始转录"
              onChange={(e) => { setTranscript(e.target.value); transcriptEditedByUser.current = true; }}
              placeholder=" "
            />
          </div>
          <div className={`text-pane result-pane ${copied ? "copied" : ""}`}>
            <div className="pane-head">
              <span>AI 编译结果</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <button
                  title={compiledEditing ? "完成编辑" : "编辑 AI 编译结果"}
                  disabled={busy}
                  onClick={() => compiledEditing ? void finishEditing("compiled") : setCompiledEditing(true)}
                >
                  {compiledEditing ? <Check size={14} /> : <Pencil size={14} />}
                  <span>{compiledEditing ? "完成" : "编辑"}</span>
                </button>
                <button className={copied ? "copy-button copied" : "copy-button"} title={copied ? "已复制" : "复制"} onClick={copyCompiled}>
                  {copied ? <Check size={15} /> : <Clipboard size={15} />}
                  <span>{copied ? "已复制" : "复制"}</span>
                </button>
              </div>
            </div>
            <textarea
              value={compiled}
              readOnly={!compiledEditing}
              aria-label="AI 编译结果"
              onChange={(e) => setCompiled(e.target.value)}
              placeholder=" "
            />
          </div>
        </div>

      </section>

      <footer>
        <button className={`record-button ${state.runtime.recording ? "active" : ""}`} onMouseDown={startRecording} onMouseUp={stopRecording} disabled={busy || !state.service.transcriber_ready}>
          {state.runtime.recording ? <Square size={17} /> : <Play size={17} />}
          <span>{!state.service.transcriber_ready ? "模型准备中" : busy ? "处理中" : state.runtime.recording ? "松开完成" : "按住录音"}</span>
        </button>
        <span>{copied ? "已自动复制" : `${state.current_session.turn_count} turns`}</span>
      </footer>
    </main>
  );
}

function SpeechSettings(props: {
  draft: Settings;
  devices: DeviceInfo[];
  busy: boolean;
  micTestActive: boolean;
  micTestCountdown: number;
  micTestLevel: number;
  speechTestResult: string;
  onDraft: (settings: Settings) => void;
  onRefreshDevices: () => void;
  onSave: () => void;
  onWarmup: () => void;
  onTestMic: () => void;
  onTranscribeTest: () => void;
}) {
  const { draft, devices, busy, onDraft } = props;
  return (
    <div className="settings-body">
      <label>
        <span>麦克风</span>
        <select
          value={draft.input_device_index ?? ""}
          onChange={(event) =>
            onDraft({
              ...draft,
              input_device_index: event.target.value === "" ? null : Number(event.target.value)
            })
          }
        >
          <option value="">默认输入设备</option>
          {devices.map((device) => (
            <option key={device.index} value={device.index}>
              {device.index}: {device.name}
              {device.is_default_input ? " 默认" : ""}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>模型缓存目录</span>
        <input value={draft.model_cache_dir || ""} onChange={(event) => onDraft({ ...draft, model_cache_dir: event.target.value })} />
      </label>
      <div className="button-row">
        <button onClick={props.onRefreshDevices}>
          <RefreshCcw size={15} />
          <span>刷新</span>
        </button>
        <button onClick={props.onSave}>
          <Check size={15} />
          <span>保存</span>
        </button>
      </div>
      <div className="button-row">
        <button disabled={busy} onClick={props.onTestMic}>
          <Mic size={15} />
          <span>测试麦克风</span>
        </button>
        <button disabled={busy} onClick={props.onTranscribeTest}>
          <Play size={15} />
          <span>测试转录</span>
        </button>
      </div>
      <button onClick={props.onWarmup}>
        <Cpu size={15} />
        <span>预加载模型</span>
      </button>
      {props.micTestActive ? (
        <div className="mic-test-feedback" aria-live="polite">
          <strong>{props.micTestCountdown}</strong>
          <div className="wave-meter" aria-hidden="true">
            {Array.from({ length: 14 }, (_, index) => {
              const center = 6.5;
              const distance = Math.abs(index - center);
              const shape = Math.max(0.35, 1 - distance / 8);
              const height = 6 + props.micTestLevel * shape * 24;
              return (
                <i
                  key={index}
                  style={{
                    height: `${height}px`,
                    opacity: 0.35 + props.micTestLevel * 0.65
                  }}
                />
              );
            })}
          </div>
        </div>
      ) : null}
      {props.speechTestResult ? (
        <div className="speech-test-result">
          <strong>测试转录结果</strong>
          <p>{props.speechTestResult}</p>
        </div>
      ) : null}
    </div>
  );
}

function ModeSettings({
  modes,
  onModes,
  onSave
}: {
  modes: Mode[];
  onModes: (modes: Mode[]) => void;
  onSave: () => void;
}) {
  const [selectedId, setSelectedId] = useState(modes[0]?.id || "");
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const selectedMode = modes.find((mode) => mode.id === selectedId) || modes[0];

  useEffect(() => {
    if (!modes.length) return;
    if (!selectedId || !modes.some((mode) => mode.id === selectedId)) {
      setSelectedId(modes[0].id);
    }
  }, [modes, selectedId]);

  function nextId(name: string, excludeId = "") {
    const base = (name || "custom_mode")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/^_+|_+$/g, "") || "custom_mode";
    let candidate = base;
    let index = 2;
    while (modes.some((mode) => mode.id === candidate && mode.id !== excludeId)) {
      candidate = `${base}_${index}`;
      index += 1;
    }
    return candidate;
  }

  function addMode() {
    const id = nextId("custom_mode");
    const mode: Mode = {
      id,
      name: "custom_mode",
      target: id,
      description: "",
      system_prompt: "请将用户的语音转录整理成清晰、可执行的提示词。",
      output_hint: ""
    };
    onModes([...modes, mode]);
    setSelectedId(id);
  }

  function updateMode(patch: Partial<Mode>) {
    if (!selectedMode) return;
    onModes(modes.map((mode) => (mode.id === selectedMode.id ? { ...mode, ...patch } : mode)));
  }

  function deleteMode(id: string) {
    if (modes.length <= 1) return;
    const nextModes = modes.filter((mode) => mode.id !== id);
    onModes(nextModes);
    setSelectedId(nextModes[0]?.id || "");
  }

  function dropMode(targetIndex: number) {
    if (dragIndex === null || dragIndex === targetIndex) return;
    const nextModes = [...modes];
    const [moved] = nextModes.splice(dragIndex, 1);
    nextModes.splice(targetIndex, 0, moved);
    onModes(nextModes);
    setDragIndex(null);
  }

  function moveMode(fromIndex: number, delta: number) {
    const targetIndex = fromIndex + delta;
    if (targetIndex < 0 || targetIndex >= modes.length) return;
    const nextModes = [...modes];
    const [moved] = nextModes.splice(fromIndex, 1);
    nextModes.splice(targetIndex, 0, moved);
    onModes(nextModes);
  }

  if (!selectedMode) {
    return (
      <div className="settings-body">
        <button onClick={addMode}>
          <Plus size={15} />
          <span>添加模式</span>
        </button>
      </div>
    );
  }

  return (
    <div className="mode-manager">
      <section className="mode-list">
        <div className="button-row">
          <button onClick={addMode}>
            <Plus size={15} />
            <span>添加</span>
          </button>
          <button onClick={onSave}>
            <Check size={15} />
            <span>保存</span>
          </button>
        </div>
        {modes.map((mode, index) => (
          <button
            className={`mode-list-item ${mode.id === selectedMode.id ? "active" : ""}`}
            draggable
            key={mode.id}
            onClick={() => setSelectedId(mode.id)}
            onDragStart={() => setDragIndex(index)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => dropMode(index)}
          >
            <GripVertical size={15} />
            <span>
              <strong>{mode.name}</strong>
              <small>{index === 0 ? "默认模式" : mode.id}</small>
            </span>
            <em>
              <b onClick={(event) => { event.stopPropagation(); moveMode(index, -1); }}>↑</b>
              <b onClick={(event) => { event.stopPropagation(); moveMode(index, 1); }}>↓</b>
            </em>
          </button>
        ))}
      </section>

      <section className="mode-editor settings-body">
        <label>
          <span>模式名称</span>
          <input
            value={selectedMode.name}
            onChange={(event) => {
              const name = event.target.value;
              const id = nextId(name, selectedMode.id);
              updateMode({ id, name, target: name, output_hint: name });
              setSelectedId(id);
            }}
          />
        </label>
        <label>
          <span>描述</span>
          <input value={selectedMode.description} onChange={(event) => updateMode({ description: event.target.value })} />
        </label>
        <label>
          <span>Prompt</span>
          <textarea value={selectedMode.system_prompt} onChange={(event) => updateMode({ system_prompt: event.target.value })} />
        </label>
        <div className="button-row">
          <button onClick={onSave}>
            <Check size={15} />
            <span>保存模式</span>
          </button>
          <button disabled={modes.length <= 1} onClick={() => deleteMode(selectedMode.id)}>
            <Trash2 size={15} />
            <span>删除</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function SkillSettings({
  skills,
  skillScanDir,
  onSkillScanDir,
  onSkills,
  onScan,
  onSave
}: {
  skills: Skill[];
  skillScanDir: string;
  onSkillScanDir: (value: string) => void;
  onSkills: (skills: Skill[]) => void;
  onScan: () => void;
  onSave: () => void;
}) {
  const [selectedId, setSelectedId] = useState(skills[0]?.id || "");
  const selectedSkill = skills.find((skill) => skill.id === selectedId) || skills[0];

  useEffect(() => {
    if (!skills.length) return;
    if (!selectedId || !skills.some((skill) => skill.id === selectedId)) {
      setSelectedId(skills[0].id);
    }
  }, [skills, selectedId]);

  function nextSkillId(name: string) {
    const base = (name || "custom_skill").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") || "custom_skill";
    let candidate = base;
    let index = 2;
    while (skills.some((skill) => skill.id === candidate)) {
      candidate = `${base}_${index}`;
      index += 1;
    }
    return candidate;
  }

  function addSkill() {
    const skill: Skill = {
      id: nextSkillId("custom_skill"),
      name: "custom_skill",
      description: "",
      example: "",
      category: "Custom",
      enabled: true,
      source_path: ""
    };
    onSkills([...skills, skill]);
    setSelectedId(skill.id);
  }

  function updateSkill(patch: Partial<Skill>) {
    if (!selectedSkill) return;
    onSkills(skills.map((skill) => (skill.id === selectedSkill.id ? { ...skill, ...patch } : skill)));
  }

  function deleteSkill(id: string) {
    const nextSkills = skills.filter((skill) => skill.id !== id);
    onSkills(nextSkills);
    setSelectedId(nextSkills[0]?.id || "");
  }

  return (
    <div className="skill-manager">
      <section className="skill-toolbar">
        <label>
          <span>Skill 目录</span>
          <input value={skillScanDir} onChange={(event) => onSkillScanDir(event.target.value)} placeholder="例如 C:\\Users\\kg\\.codex\\skills" />
        </label>
        <p className="skill-match-hint">AI 会结合 Skill 的名称、描述和使用示例自动判断；匹配时引用，未匹配时不会添加。</p>
        <div className="button-row">
          <button onClick={onScan}>
            <RefreshCcw size={15} />
            <span>自动提取</span>
          </button>
          <button onClick={addSkill}>
            <Plus size={15} />
            <span>手动添加</span>
          </button>
        </div>
      </section>

      <section className="skill-list">
        {skills.length === 0 ? <p>暂无 Skill，可输入目录自动提取，或手动添加。</p> : null}
        {skills.map((skill) => (
          <button className={skill.id === selectedSkill?.id ? "active" : ""} key={skill.id} onClick={() => setSelectedId(skill.id)}>
            <input
              type="checkbox"
              checked={skill.enabled}
              onChange={(event) => {
                event.stopPropagation();
                onSkills(skills.map((item) => (item.id === skill.id ? { ...item, enabled: event.target.checked } : item)));
              }}
              onClick={(event) => event.stopPropagation()}
            />
            <span>
              <strong>{skill.name}</strong>
              <small>{skill.category}</small>
            </span>
          </button>
        ))}
      </section>

      {selectedSkill ? (
        <section className="skill-editor settings-body">
          <label>
            <span>名称</span>
            <input value={selectedSkill.name} onChange={(event) => updateSkill({ name: event.target.value })} />
          </label>
          <label>
            <span>分类</span>
            <input value={selectedSkill.category} onChange={(event) => updateSkill({ category: event.target.value })} />
          </label>
          <label>
            <span>描述</span>
            <textarea value={selectedSkill.description} onChange={(event) => updateSkill({ description: event.target.value })} />
          </label>
          <label>
            <span>使用示例</span>
            <textarea
              value={selectedSkill.example}
              onChange={(event) => updateSkill({ example: event.target.value })}
              placeholder="例如：当用户要求制作演示文稿时使用"
            />
          </label>
          <div className="button-row">
            <button onClick={onSave}>
              <Check size={15} />
              <span>保存 Skill</span>
            </button>
            <button onClick={() => deleteSkill(selectedSkill.id)}>
              <Trash2 size={15} />
              <span>删除</span>
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function GeneralSettings(props: {
  draft: Settings;
  onDraft: (settings: Settings) => void;
  onStateChange: (state: AppState) => void;
}) {
  const { draft, onDraft, onStateChange } = props;

  async function setAutoCopy(checked: boolean) {
    onDraft({ ...draft, auto_copy: checked });
    const payload = await api.saveGeneral({ auto_copy: checked });
    onStateChange(payload.state);
  }

  async function setAutoLaunch(checked: boolean) {
    onDraft({ ...draft, auto_launch: checked });
    try {
      if (checked) await autostart.enable();
      else await autostart.disable();
    } catch { /* ignore */ }
    const payload = await api.saveGeneral({ auto_launch: checked });
    onStateChange(payload.state);
  }

  async function setSaveHistory(checked: boolean) {
    onDraft({ ...draft, save_history: checked });
    const payload = await api.saveGeneral({ save_history: checked });
    onStateChange(payload.state);
  }

  return (
    <div className="settings-body">
      <div className="checks">
        <label>
          <input type="checkbox" checked={draft.auto_copy} onChange={(event) => setAutoCopy(event.target.checked)} />
          <span>自动复制</span>
        </label>
        <label>
          <input type="checkbox" checked={draft.auto_launch} onChange={(event) => setAutoLaunch(event.target.checked)} />
          <span>开机自启动</span>
        </label>
        <label>
          <input type="checkbox" checked={draft.save_history} onChange={(event) => setSaveHistory(event.target.checked)} />
          <span>保存历史</span>
        </label>
      </div>
    </div>
  );
}

function LlmSettings(props: {
  draft: Settings;
  deepseekApiKey: string;
  onDeepseekApiKeyChange: (value: string) => void;
  onDraft: (settings: Settings) => void;
  onSaveLlm: () => void;
}) {
  const { draft, deepseekApiKey, onDeepseekApiKeyChange, onDraft } = props;
  const isDeepSeek = draft.llm_provider === "deepseek" || isDeepSeekEndpoint(draft.llm_base_url);
  const isCustom = !isDeepSeek;
  const deepseekApiKeyCache = useRef(deepseekApiKey);
  const deepseekModel = deepseekModels.includes(draft.llm_model)
    ? draft.llm_model
    : "deepseek-v4-flash";

  useEffect(() => {
    if (!isCustom) {
      deepseekApiKeyCache.current = draft.llm_api_key;
    }
  }, [draft.llm_api_key, isCustom]);

  useEffect(() => {
    if (deepseekApiKey !== "") {
      deepseekApiKeyCache.current = deepseekApiKey;
    }
  }, [deepseekApiKey]);

  function useDeepSeek() {
    const keepKey = isDeepSeekEndpoint(draft.llm_base_url);
    const cachedKey = deepseekApiKeyCache.current;
    onDraft({
      ...draft,
      llm_provider: "deepseek",
      llm_base_url: "https://api.deepseek.com",
      llm_model: "deepseek-v4-flash",
      llm_api_key: keepKey ? draft.llm_api_key : cachedKey,
      llm_thinking_enabled: false
    });
  }

  function useCustom() {
    if (isCustom) return;
    deepseekApiKeyCache.current = draft.llm_api_key;
    onDeepseekApiKeyChange(draft.llm_api_key);
    onDraft({
      ...draft,
      llm_provider: "openai_compatible",
      llm_base_url: "",
      llm_model: "",
      llm_api_key: "",
      llm_thinking_enabled: false
    });
  }

  return (
    <div className="settings-body llm-settings">
      <div className="llm-source-switch" role="group" aria-label="大模型来源">
        <button className={!isCustom ? "active" : ""} onClick={useDeepSeek}>
          <img src={deepseekLogo} alt="DeepSeek" />
          <span><strong>DeepSeek</strong><small>默认</small></span>
        </button>
        <button className={isCustom ? "active" : ""} onClick={useCustom}>
          <SlidersHorizontal size={20} />
          <span><strong>自定义接口</strong><small>OpenAI Compatible</small></span>
        </button>
      </div>

      <label>
        <span>API 端点</span>
        <input
          value={draft.llm_base_url}
          onChange={(event) => onDraft({ ...draft, llm_base_url: event.target.value })}
          placeholder={isCustom ? "例如 http://127.0.0.1:11434/v1" : "https://api.deepseek.com"}
        />
      </label>
      <label>
        <span>模型名称</span>
        {!isCustom ? (
          <select
            value={deepseekModel}
            onChange={(event) => onDraft({
              ...draft,
              llm_provider: "deepseek",
              llm_model: event.target.value
            })}
          >
            <option value="deepseek-v4-flash">deepseek-v4-flash</option>
            <option value="deepseek-v4-pro">deepseek-v4-pro</option>
          </select>
        ) : (
          <input
            value={draft.llm_model}
            onChange={(event) => onDraft({ ...draft, llm_model: event.target.value })}
            placeholder="服务提供的模型 ID"
          />
        )}
      </label>
      <label>
        <span>{isCustom ? "API Key（可选）" : "DeepSeek API Key"}</span>
        <input
          type="password"
          value={draft.llm_api_key}
          onChange={(event) => {
            const value = event.target.value;
            if (!isCustom) onDeepseekApiKeyChange(value);
            onDraft({ ...draft, llm_api_key: value });
          }}
          onFocus={(event) => {
            if (draft.llm_api_key === apiKeyMask) event.currentTarget.select();
          }}
          placeholder={isCustom ? "无鉴权的本地服务可留空" : "仅保存在本地 config.local.json"}
        />
      </label>
      {!isCustom ? (
        <label className="thinking-toggle">
          <input
            type="checkbox"
            checked={draft.llm_thinking_enabled}
            onChange={(event) => onDraft({ ...draft, llm_thinking_enabled: event.target.checked })}
          />
          <span><strong>思考模式</strong><small>默认关闭；开启后会提高复杂任务质量，但响应更慢。</small></span>
        </label>
      ) : (
        <p className="setting-hint">支持 OpenAI-compatible 接口，包括用户自建服务、Ollama、vLLM 或第三方网关。</p>
      )}
      <div className="split-fields">
        <label>
          <span>Temperature</span>
          <input type="number" min="0" max="2" step="0.1" value={draft.llm_temperature} onChange={(event) => onDraft({ ...draft, llm_temperature: Number(event.target.value) })} />
        </label>
        <label>
          <span>Timeout</span>
          <input type="number" min="5" max="600" value={draft.llm_timeout_seconds} onChange={(event) => onDraft({ ...draft, llm_timeout_seconds: Number(event.target.value) })} />
        </label>
      </div>
      <button onClick={props.onSaveLlm}>
        <Check size={15} />
        <span>保存 LLM</span>
      </button>
    </div>
  );
}

function ShortcutsPanel() {
  const shortcuts = [
    ["Ctrl+Shift+Space", "打开或隐藏 Aura"],
    ["Space", "模型就绪且主界面聚焦时按住录音，松开后转录"],
    ["Ctrl+N", "新建会话"],
    ["Ctrl+Up / Ctrl+Down", "切换模式"],
    ["Esc", "隐藏 Aura"]
  ];

  return (
    <div className="settings-body shortcut-list">
      {shortcuts.map(([keys, action]) => (
        <article key={keys}>
          <kbd>{keys}</kbd>
          <span>{action}</span>
        </article>
      ))}
    </div>
  );
}

function LogsPanel({
  logs,
  onRefresh,
  onClear
}: {
  logs: LogEntry[];
  onRefresh: () => Promise<LogEntry[]>;
  onClear: () => void;
}) {
  return (
    <div className="settings-body log-list">
      <div className="button-row">
        <button onClick={() => void onRefresh()}>
          <RefreshCcw size={15} />
          <span>刷新</span>
        </button>
        <button onClick={onClear}>
          <Trash2 size={15} />
          <span>清空</span>
        </button>
      </div>
      {logs.length === 0 ? <p>暂无日志</p> : null}
      {logs.map((entry) => (
        <article className={`log-entry ${entry.level}`} key={entry.id}>
          <div>
            <strong>{entry.level.toUpperCase()}</strong>
            <span>{entry.source}</span>
            <time>{new Date(entry.timestamp).toLocaleTimeString()}</time>
          </div>
          <p>{entry.message}</p>
          {entry.details ? <pre>{entry.details}</pre> : null}
        </article>
      ))}
    </div>
  );
}

function HistoryPanel({
  state,
  onClear,
  onDelete
}: {
  state: AppState;
  onClear: () => void;
  onDelete: (sessionId: string) => void;
}) {
  return (
    <div className="settings-body history-list">
      <button onClick={onClear}>
        <Trash2 size={15} />
        <span>清空历史</span>
      </button>
      {state.history.length === 0 ? <p>暂无历史</p> : null}
      {state.history.map((item) => (
        <article key={item.id}>
          <div className="history-item-head">
            <strong>{item.title}</strong>
            <button title="删除这条历史记录" onClick={() => onDelete(item.id)}>
              <Trash2 size={14} />
            </button>
          </div>
          <span>{item.mode_id} · {item.turn_count} turns</span>
          <time>{shortTime(item.updated_at)}</time>
          <p>{compactText(item.last_transcript || item.last_compiled || "无内容", 90)}</p>
        </article>
      ))}
    </div>
  );
}
