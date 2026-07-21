import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { getVersion } from "@tauri-apps/api/app";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Check,
  ChevronDown,
  Clipboard,
  Cpu,
  FileCheck2,
  FolderOpen,
  Github,
  GripVertical,
  GitMerge,
  History,
  Keyboard,
  ListChecks,
  Mic,
  Moon,
  Palette,
  Pencil,
  Play,
  Plus,
  RefreshCcw,
  Scale,
  Settings as SettingsIcon,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Terminal,
  Trash2
} from "lucide-react";
import { AppState, DeviceInfo, LogEntry, Mode, Settings, Skill, api, autostart, ensureSidecar, hideMainWindow, setTrayLanguage } from "./api";
import deepseekLogo from "./assets/deepseek-logo.svg";
import { setUiLanguage, storedLanguage, UI_LANGUAGES, UiLanguage } from "./i18n";
import { AURA_GITHUB_URL, checkGitHubUpdate, UpdateCheckResult } from "./update";

type Tab = "main" | "general" | "speech" | "llm" | "modes" | "skills" | "shortcuts" | "logs" | "history";
type ThemeId = "morning" | "night";

function storedTheme(): ThemeId {
  return window.localStorage.getItem("aura-ui-theme") === "night" ? "night" : "morning";
}

function applyTheme(theme: ThemeId) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme === "night" ? "dark" : "light";
  window.localStorage.setItem("aura-ui-theme", theme);
}

applyTheme(storedTheme());

const emptySettings: Settings = {
  app_name: "Aura",
  mode_id: "coding_agent",
  auto_copy: true,
  save_history: true,
  auto_launch: false,
  keep_window_on_top: false,
  hotkey: "<ctrl>+<shift>+<space>",
  push_to_talk_key: "space",
  input_device_index: null,
  stt_provider: "sensevoice-small",
  model_cache_dir: "",
  ui_theme: storedTheme(),
  ui_language: storedLanguage(),
  llm_provider: "deepseek",
  llm_base_url: "https://api.deepseek.com",
  deepseek_api_key: "",
  custom_api_key: "",
  deepseek_api_key_source: "unset",
  custom_api_key_source: "unset",
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

function shortTime(value: string, locale?: string) {
  if (!value) return "";
  return new Date(value).toLocaleString(locale, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function stateSkills(state: AppState) {
  return state.skills || state.settings.skills || [];
}

function localizeRuntimeStatus(value: string | undefined, t: TFunction): string {
  if (!value) return "";
  const exact: Record<string, string> = {
    "准备就绪": "runtime.ready",
    "正在录音": "runtime.recording",
    "正在转录": "runtime.transcribing",
    "正在整理": "runtime.organizing",
    "已复制": "runtime.copied",
    "整理完成": "runtime.organized",
    "新会话": "runtime.newSession",
    "合并需求输出已开启": "runtime.mergeOn",
    "仅输出本次需求": "runtime.mergeOff",
    "设置已保存": "runtime.settingsSaved",
    "语音设置已保存": "runtime.speechSaved",
    "LLM 设置已保存": "runtime.llmSaved",
    "Skill 配置已保存": "runtime.skillsSaved",
    "正在预加载转录模型": "runtime.preloading",
    "正在测试麦克风": "runtime.micTesting",
    "麦克风测试完成": "runtime.micDone",
    "正在转录测试音频": "runtime.testTranscribing",
    "测试转录完成": "runtime.testDone",
    "重新编译完成": "runtime.recompiled",
    "历史已清空": "runtime.historyCleared",
    "历史记录已删除": "runtime.historyDeleted",
    "SenseVoice-Small 模型已就绪": "runtime.sensevoiceReady",
    "正在使用 SenseVoice-Small 识别语音": "runtime.sensevoiceUsing",
    "正在使用 Whisper Large V3 识别语音": "runtime.whisperUsing",
    "CUDA 运行库不完整，已自动切换到 CPU 模式": "runtime.cudaFallback",
    "Whisper 下载失败，已自动切换回 SenseVoice Small": "runtime.whisperFallback"
  };
  if (exact[value]) return t(exact[value]);
  const recording = value.match(/^录音中\s+(.+)$/);
  if (recording) return t("runtime.recordingLevel", { volume: recording[1] });
  const extracted = value.match(/^已提取\s+(\d+)\s+个 Skill$/);
  if (extracted) return t("runtime.extracted", { count: Number(extracted[1]) });
  const mode = value.match(/^模式:\s*(.+)$/);
  if (mode) return t("runtime.mode", { name: mode[1] });
  const defaultMode = value.match(/^默认模式:\s*(.+)$/);
  if (defaultMode) return t("runtime.defaultMode", { name: defaultMode[1] });
  const history = value.match(/^已切换历史:\s*(.+)$/);
  if (history) return t("runtime.historyLoaded", { name: history[1] });
  return value;
}

const deepseekModels = ["deepseek-v4-flash", "deepseek-v4-pro"];

const builtinModeKeys: Record<string, "action" | "decision" | "creative"> = {
  coding_agent: "action",
  decision_partner: "decision",
  creative_studio: "creative"
};

function modeDisplayName(mode: Mode, t: TFunction) {
  const key = mode.source === "official" ? builtinModeKeys[mode.id] : undefined;
  return key ? t(`modePresets.${key}.name`) : mode.name;
}

function modeDisplayDescription(mode: Mode, t: TFunction) {
  const key = mode.source === "official" ? builtinModeKeys[mode.id] : undefined;
  return key ? t(`modePresets.${key}.description`) : mode.description;
}

function ModeGlyph({ mode, size = 14 }: { mode: Mode; size?: number }) {
  if (mode.source !== "official") return <Sparkles size={size} />;
  if (mode.icon === "list-checks") return <ListChecks size={size} />;
  if (mode.icon === "scale") return <Scale size={size} />;
  if (mode.icon === "palette") return <Palette size={size} />;
  return <Sparkles size={size} />;
}

function ModeSelect({
  modes,
  selectedMode,
  onSelect
}: {
  modes: Mode[];
  selectedMode: Mode | undefined;
  onSelect: (modeId: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="mode-select" ref={rootRef}>
      <button
        className="mode-select-trigger"
        aria-label={t("main.currentMode")}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {selectedMode ? <ModeGlyph mode={selectedMode} size={15} /> : <Sparkles size={15} />}
        <span>{selectedMode ? modeDisplayName(selectedMode, t) : t("main.currentMode")}</span>
        <ChevronDown className={open ? "open" : ""} size={14} />
      </button>
      {open ? (
        <div className="mode-select-menu" role="listbox" aria-label={t("main.currentMode")}>
          {modes.map((mode) => {
            const selected = selectedMode?.id === mode.id;
            return (
              <button
                key={mode.id}
                className={selected ? "active" : ""}
                role="option"
                aria-selected={selected}
                onClick={() => {
                  setOpen(false);
                  onSelect(mode.id);
                }}
              >
                <span className={`mode-select-icon ${mode.source}`}><ModeGlyph mode={mode} size={15} /></span>
                <span className="mode-select-copy">
                  <strong>{modeDisplayName(mode, t)}</strong>
                  <small>{modeDisplayDescription(mode, t)}</small>
                </span>
                {selected ? <Check size={14} /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function isDeepSeekEndpoint(value: string) {
  const normalized = value.trim().toLowerCase().replace(/\/+$/, "");
  return normalized === "https://api.deepseek.com" || normalized === "https://api.deepseek.com/v1";
}

export default function App() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<AppState | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("main");
  const [transcript, setTranscript] = useState("");
  const [compiled, setCompiled] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Settings>(emptySettings);
  const [activeJobId, setActiveJobId] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [micTestCountdown, setMicTestCountdown] = useState(0);
  const [micTestActive, setMicTestActive] = useState(false);
  const [modeDrafts, setModeDrafts] = useState<Mode[]>([]);
  const [skillDrafts, setSkillDrafts] = useState<Skill[]>([]);
  const [skillScanDir, setSkillScanDir] = useState("");
  const [speechTestResult, setSpeechTestResult] = useState("");
  const [warmupActive, setWarmupActive] = useState(false);
  const [warmupProgress, setWarmupProgress] = useState(0);
  const [warmupFallback, setWarmupFallback] = useState(false);
  const [bootProgress, setBootProgress] = useState(0);
  const [bootStatus, setBootStatus] = useState(() => i18n.t("boot.connecting"));
  const [bootStage, setBootStage] = useState("connecting");
  const [bootElapsedSeconds, setBootElapsedSeconds] = useState(0);
  const [transcriptEditing, setTranscriptEditing] = useState(false);
  const [compiledEditing, setCompiledEditing] = useState(false);
  const recordingRef = useRef(false);
  const transcriptEditedByUser = useRef(false);
  const historySelectRef = useRef<HTMLSelectElement>(null);
  const speechSaveVersion = useRef(0);

  const status = error || localizeRuntimeStatus(state?.runtime.status, t) || t("boot.loading");
  const selectedMode = state?.current_mode;
  const enabledModes = state?.modes.filter((mode) => mode.enabled) || [];

  useEffect(() => {
    applyTheme(draft.ui_theme || "morning");
  }, [draft.ui_theme]);

  useEffect(() => {
    if (!draft.ui_language) return;
    if (i18n.language !== draft.ui_language) void setUiLanguage(draft.ui_language);
    void setTrayLanguage(draft.ui_language).catch(() => undefined);
  }, [draft.ui_language, i18n.language]);

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
        setBootStatus(i18n.t("boot.startingSpeech"));
        setBootStage("checking");
        let initial = await api.state();
        setBootProgress(initial.service.transcriber_progress);
        setBootStage(initial.service.transcriber_status);
        setBootStatus(
          initial.service.transcriber_ready
            ? i18n.t("boot.speechReady")
            : i18n.t("boot.checkingSpeech")
        );
        if (!initial.service.transcriber_ready) {
          let trackedProvider = initial.settings.stt_provider;
          await api.warmupStt();
          while (!cancelled) {
            initial = await api.state();
            setBootProgress(initial.service.transcriber_progress);
            setBootStage(initial.service.transcriber_status);
            setBootStatus(localizeRuntimeStatus(initial.runtime.status, i18n.t.bind(i18n)) || i18n.t("boot.loadingSpeech"));
            if (initial.service.transcriber_ready) break;
            // Detect fallback: provider changed → backend switched models automatically.
            // The status bar will show the fallback message naturally via runtime.status.
            if (initial.settings.stt_provider !== trackedProvider) {
              trackedProvider = initial.settings.stt_provider;
              setBootStatus(localizeRuntimeStatus(initial.runtime.status, i18n.t.bind(i18n)) || i18n.t("boot.loadingSpeech"));
              continue;
            }
            if (initial.service.transcriber_status === "error") {
              throw new Error(initial.service.transcriber_error || initial.runtime.status || i18n.t("boot.speechFailed"));
            }
            await new Promise((resolve) => window.setTimeout(resolve, 200));
          }
        }
        if (cancelled) return;
        setBootProgress(100);
        setBootStage("ready");
        setBootStatus(i18n.t("boot.speechReady"));
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
    if (activeTab !== "speech") return;
    void loadDevices().catch((exc) => {
      setError(exc instanceof Error ? exc.message : String(exc));
    });
  }, [activeTab, loadDevices]);

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
      setBootStatus(t("main.speechLoading"));
      return;
    }
    if (!state.service.transcriber_ready) {
      setError(t("main.speechNotReady"));
      return;
    }
    if (busy) {
      setError(t("main.busy"));
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
        setError(t("main.oldSidecar"));
        return;
      }
      setTranscript(payload.job.transcript);
      setCompiled(payload.job.compiled);
      setState(payload.state);
      setActiveJobId(payload.job.id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      await refresh().catch(() => undefined);
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
        if (!current || current.runtime.status !== t("common.copied")) return current;
        return { ...current, runtime: { ...current.runtime, status: t("main.organized") } };
      });
    }, 1500);
    return () => window.clearTimeout(id);
  }, [copied]);

  const keyboardContextRef = useRef({
    activeTab,
    textEditing: transcriptEditing || compiledEditing,
    startRecording,
    stopRecording,
    newSession,
    shiftMode
  });
  keyboardContextRef.current = {
    activeTab,
    textEditing: transcriptEditing || compiledEditing,
    startRecording,
    stopRecording,
    newSession,
    shiftMode
  };

  useEffect(() => {
    let dispose: (() => void) | undefined;
    void listen("aura://shown", () => {
      keyboardContextRef.current.textEditing = false;
      setTranscriptEditing(false);
      setCompiledEditing(false);
      window.requestAnimationFrame(() => {
        const focused = document.activeElement;
        if (focused instanceof HTMLElement) focused.blur();
        window.focus();
      });
    }).then((unlisten) => {
      dispose = unlisten;
    });
    return () => dispose?.();
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const context = keyboardContextRef.current;
      const isPlainSpace =
        event.code === "Space" && !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey;
      if (isPlainSpace && !event.repeat && context.activeTab === "main" && !context.textEditing) {
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
      if (event.code === "Space" && context.activeTab === "main" && !context.textEditing) {
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
    if (!enabledModes.length || !state?.current_mode) return;
    const index = enabledModes.findIndex((mode) => mode.id === state.current_mode.id);
    const nextIndex = (Math.max(index, 0) + delta + enabledModes.length) % enabledModes.length;
    await setMode(enabledModes[nextIndex].id);
  }

  async function newSession() {
    if (busy || state?.runtime.recording || activeJobId) return;
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

  async function saveSpeech(next: Settings) {
    const version = speechSaveVersion.current + 1;
    speechSaveVersion.current = version;
    setDraft(next);
    setError("");
    try {
      const payload = await api.saveSpeech(next);
      if (version !== speechSaveVersion.current) return;
      setState(payload.state);
      setDraft(payload.state.settings);
    } catch (exc) {
      if (version !== speechSaveVersion.current) return;
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function saveLlm() {
    const payload = await api.saveLlm(draft);
    setState(payload.state);
    setDraft(payload.state.settings);
  }

  async function toggleMergeOutput() {
    if (!state || busy || state.runtime.recording || activeJobId) return;
    try {
      setError("");
      const payload = await api.setMergeOutput(!state.current_session.merge_output);
      setState(payload.state);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function saveModes() {
    const payload = await api.saveModes(modeDrafts);
    setState(payload.state);
    setDraft(payload.state.settings);
    setModeDrafts(payload.state.modes);
  }

  async function scanSkills(directory = skillScanDir) {
    try {
      setError("");
      const payload = await api.scanSkills(directory);
      setState(payload.state);
      setDraft(payload.state.settings);
      setSkillScanDir(payload.state.settings.skill_scan_dir || directory);
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
    setWarmupActive(true);
    setWarmupProgress(0);
    setWarmupFallback(false);
    setError("");
    try {
      const payload = await api.warmupStt();
      setState(payload.state);
      if (payload.state.service.transcriber_ready) {
        setWarmupProgress(100);
        setWarmupActive(false);
        return;
      }
      let trackedProvider = payload.state.settings.stt_provider;
      while (true) {
        const current = await api.state();
        setState(current);
        setWarmupProgress(current.service.transcriber_progress);
        if (current.service.transcriber_ready) {
          setWarmupProgress(100);
          break;
        }
        // Detect fallback: provider changed → backend switched models automatically.
        if (current.settings.stt_provider !== trackedProvider) {
          trackedProvider = current.settings.stt_provider;
          setWarmupFallback(true);
          setDraft(current.settings);
          continue;
        }
        if (current.service.transcriber_status === "error") {
          throw new Error(current.service.transcriber_error || t("speech.preloadError"));
        }
        await new Promise((resolve) => window.setTimeout(resolve, 200));
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setWarmupActive(false);
    }
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
      setTranscript(t("speech.duration", {
        duration: payload.recording.duration_seconds.toFixed(2),
        average: payload.recording.average_volume.toFixed(0),
        maximum: payload.recording.max_volume
      }));
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
      setSpeechTestResult(payload.transcript || t("speech.noResult"));
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
    if (!window.confirm(t("history.confirmDelete"))) return;
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
      // Sync stt_provider in case backend fell back to another model in the background.
      setDraft((prev) => ({ ...prev, stt_provider: state.settings.stt_provider }));
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
        <div className="boot-mark"><Sparkles size={28} /></div>
        <div className="boot-copy">
          <strong>{error ? t("boot.failed") : t("boot.starting")}</strong>
          <span>{error || bootStatus}</span>
          <div
            className={`boot-progress ${!error && bootProgress < 100 ? "active" : ""}`}
            role="progressbar"
            aria-label={t("boot.progress")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={bootProgress}
          >
            <i style={{ width: `${error ? bootProgress : Math.max(bootProgress, 5)}%` }} />
          </div>
          <small>
            {error
              ? t("boot.incomplete")
              : bootStage === "downloading"
                ? t("boot.downloading", { seconds: bootElapsedSeconds })
                : t("boot.working", { progress: Math.round(bootProgress), seconds: bootElapsedSeconds })}
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
            <button title={t("common.back")} onClick={closeSettings}>
              <ArrowLeft size={16} />
              <span>{t("common.back")}</span>
            </button>
          </header>
          <div className="settings-content">
            <nav className="settings-tabs">
              <button className={activeTab === "general" ? "active" : ""} onClick={() => setActiveTab("general")}>
                <SettingsIcon size={15} />
                <span>{t("tabs.general")}</span>
              </button>
              <button className={activeTab === "speech" ? "active" : ""} onClick={() => setActiveTab("speech")}>
                <Mic size={15} />
                <span>{t("tabs.speech")}</span>
              </button>
              <button className={activeTab === "llm" ? "active" : ""} onClick={() => setActiveTab("llm")}>
                <SlidersHorizontal size={15} />
                <span>LLM</span>
              </button>
              <button className={activeTab === "modes" ? "active" : ""} onClick={() => setActiveTab("modes")}>
                <GripVertical size={15} />
                <span>{t("tabs.modes")}</span>
              </button>
              <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}>
                <Cpu size={15} />
                <span>{t("tabs.skills")}</span>
              </button>
              <button className={activeTab === "shortcuts" ? "active" : ""} onClick={() => setActiveTab("shortcuts")}>
                <Keyboard size={15} />
                <span>{t("tabs.shortcuts")}</span>
              </button>
              <button className={activeTab === "logs" ? "active" : ""} onClick={() => setActiveTab("logs")}>
                <Terminal size={15} />
                <span>{t("tabs.logs")}</span>
              </button>
              <button className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>
                <History size={15} />
                <span>{t("tabs.history")}</span>
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
                warmupActive={warmupActive}
                warmupProgress={warmupProgress}
                warmupFallback={warmupFallback}
                onDraft={setDraft}
                onSave={saveSpeech}
                onWarmup={warmup}
                onTestMic={testMicrophone}
                onTranscribeTest={transcribeTest}
              />
            ) : null}
            {activeTab === "llm" ? (
              <LlmSettings
                draft={draft}
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
        <ModeSelect modes={enabledModes} selectedMode={selectedMode} onSelect={(modeId) => void setMode(modeId)} />
        <select
          key={state.current_session.id}
          ref={historySelectRef}
          aria-label={t("main.historySessions")}
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
          <option value={state.current_session.id}>{t("main.historySessions")}</option>
          {state.history.filter((item) => item.id !== state.current_session.id).map((item) => (
            <option key={item.id} value={item.id}>
              {shortTime(item.updated_at, i18n.language)} · {compactText(item.last_transcript || item.last_compiled || item.title, 42)}
            </option>
          ))}
        </select>
        <div className={`status ${state.runtime.recording ? "recording" : ""} ${copied ? "copied" : ""}`}>
          <span>{status}</span>
          <div className="meter">
            <i style={{ width: `${volumePercent}%` }} />
          </div>
        </div>
        <button title={t("main.newSession")} disabled={busy || state.runtime.recording || Boolean(activeJobId)} onClick={newSession}>
          <RefreshCcw size={16} />
        </button>
        <button title={t("main.settings")} onClick={() => openSettings("general")}>
          <SettingsIcon size={16} />
        </button>
      </header>

      <section className="workspace">
        <div className="editor-column">
          <div className="text-pane">
            <div className="pane-head">
              <span className="pane-title"><Mic size={14} />{t("main.rawTranscript")}</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                {state.runtime.recording ? <Mic size={16} /> : null}
                <button
                  title={transcriptEditing ? t("main.finishEdit") : t("main.editTranscript")}
                  disabled={busy || state.runtime.recording}
                  onClick={() => transcriptEditing ? void finishEditing("transcript") : setTranscriptEditing(true)}
                >
                  {transcriptEditing ? <Check size={14} /> : <Pencil size={14} />}
                  <span>{transcriptEditing ? t("common.done") : t("common.edit")}</span>
                </button>
              </div>
            </div>
            <textarea
              value={transcript}
              readOnly={!transcriptEditing}
              aria-label={t("main.rawTranscript")}
              onChange={(e) => { setTranscript(e.target.value); transcriptEditedByUser.current = true; }}
              placeholder=" "
            />
          </div>
          <div className={`text-pane result-pane ${copied ? "copied" : ""}`}>
            <div className="pane-head">
	              <span className="pane-title"><FileCheck2 size={14} />{t("main.compiled")}</span>
	              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
	                <button
	                  className={`merge-output-button ${state.current_session.merge_output ? "active" : ""}`}
	                  title={state.current_session.merge_output ? t("main.mergeOn") : t("main.mergeOff")}
	                  aria-pressed={state.current_session.merge_output}
	                  disabled={busy || state.runtime.recording || Boolean(activeJobId)}
	                  onClick={() => void toggleMergeOutput()}
	                >
	                  <GitMerge size={14} />
	                  <span>{t("main.mergeOutput")}</span>
	                </button>
	                <button
                  title={compiledEditing ? t("main.finishEdit") : t("main.editCompiled")}
                  disabled={busy}
                  onClick={() => compiledEditing ? void finishEditing("compiled") : setCompiledEditing(true)}
                >
                  {compiledEditing ? <Check size={14} /> : <Pencil size={14} />}
                  <span>{compiledEditing ? t("common.done") : t("common.edit")}</span>
                </button>
                <button className={copied ? "copy-button copied" : "copy-button"} title={copied ? t("common.copied") : t("common.copy")} onClick={copyCompiled}>
                  {copied ? <Check size={15} /> : <Clipboard size={15} />}
                  <span>{copied ? t("common.copied") : t("common.copy")}</span>
                </button>
              </div>
            </div>
            <textarea
              value={compiled}
              readOnly={!compiledEditing}
              aria-label={t("main.compiled")}
              onChange={(e) => setCompiled(e.target.value)}
              placeholder=" "
            />
          </div>
        </div>

      </section>
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
  warmupActive: boolean;
  warmupProgress: number;
  warmupFallback: boolean;
  onDraft: (settings: Settings) => void;
  onSave: (settings: Settings) => void;
  onWarmup: () => void;
  onTestMic: () => void;
  onTranscribeTest: () => void;
}) {
  const { t } = useTranslation();
  const { draft, devices, busy, onDraft } = props;
  return (
    <div className="settings-body">
      <label>
        <span>{t("speech.model")}</span>
        <select
          value={draft.stt_provider}
          onChange={(event) => {
            const next = { ...draft, stt_provider: event.target.value };
            onDraft(next);
            props.onSave(next);
          }}
        >
          <option value="sensevoice-small">{t("speech.sensevoice")}</option>
          <option value="whisper-large-v3">{t("speech.whisper")}</option>
        </select>
      </label>
      <div className="model-note">
        <strong>{draft.stt_provider === "whisper-large-v3" ? "Whisper Large V3" : "SenseVoice Small"}</strong>
        <span>
          {draft.stt_provider === "whisper-large-v3"
            ? t("speech.whisperNote")
            : t("speech.sensevoiceNote")}
        </span>
      </div>
      <label>
        <span>{t("speech.microphone")}</span>
        <select
          value={draft.input_device_index ?? ""}
          onChange={(event) => {
            const next = {
              ...draft,
              input_device_index: event.target.value === "" ? null : Number(event.target.value)
            };
            onDraft(next);
            props.onSave(next);
          }}
        >
          <option value="">{t("speech.defaultInput")}</option>
          {devices.map((device) => (
            <option key={device.index} value={device.index}>
              {device.index}: {device.name}
              {device.is_default_input ? t("speech.defaultSuffix") : ""}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("speech.cacheDir")}</span>
        <input
          value={draft.model_cache_dir || ""}
          onChange={(event) => onDraft({ ...draft, model_cache_dir: event.target.value })}
          onBlur={() => props.onSave(draft)}
        />
      </label>
      <div className="button-row">
        <button disabled={busy} onClick={props.onTestMic}>
          <Mic size={15} />
          <span>{t("speech.testMic")}</span>
        </button>
        <button disabled={busy} onClick={props.onTranscribeTest}>
          <Play size={15} />
          <span>{t("speech.testTranscription")}</span>
        </button>
      </div>
      <button onClick={props.onWarmup} disabled={props.warmupActive}>
        <Cpu size={15} />
        <span>{props.warmupActive ? t("speech.preloading") : t("speech.preload")}</span>
      </button>
      {props.warmupActive ? (
        <>
          <div className="boot-progress" role="progressbar" aria-label={t("speech.modelProgress")}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={props.warmupProgress}>
            <i style={{ width: `${Math.max(props.warmupProgress, 5)}%` }} />
          </div>
          {props.warmupFallback ? (
            <p className="warmup-fallback-hint">{t("runtime.whisperFallback")}</p>
          ) : null}
        </>
      ) : null}
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
          <strong>{t("speech.result")}</strong>
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
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState(modes[0]?.id || "");
  const selectedMode = modes.find((mode) => mode.id === selectedId) || modes[0];
  const officialModes = modes.filter((mode) => mode.source === "official");
  const customModes = modes.filter((mode) => mode.source === "custom");
  const canSave = modes.some((mode) => mode.enabled);

  useEffect(() => {
    if (!modes.length) return;
    if (!selectedId || !modes.some((mode) => mode.id === selectedId)) {
      setSelectedId(modes[0].id);
    }
  }, [modes, selectedId]);

  function nextId(base = "custom_mode") {
    let candidate = base;
    let index = 2;
    while (modes.some((mode) => mode.id === candidate)) {
      candidate = `${base}_${index}`;
      index += 1;
    }
    return candidate;
  }

  function addMode() {
    const id = nextId();
    const mode: Mode = {
      id,
      name: t("modes.newCustomName"),
      target: id,
      description: "",
      system_prompt: t("modes.defaultPrompt"),
      output_hint: "",
      source: "custom",
      enabled: true,
      icon: "sparkles",
      base_mode_id: ""
    };
    onModes([...modes, mode]);
    setSelectedId(id);
  }

  function updateMode(patch: Partial<Mode>) {
    if (!selectedMode) return;
    onModes(modes.map((mode) => (mode.id === selectedMode.id ? { ...mode, ...patch } : mode)));
  }

  function toggleMode(modeId: string, enabled: boolean) {
    onModes(modes.map((mode) => (mode.id === modeId ? { ...mode, enabled } : mode)));
  }

  function deleteMode(modeId: string) {
    const nextModes = modes.filter((mode) => mode.id !== modeId);
    onModes(nextModes);
    setSelectedId(nextModes[0]?.id || "");
  }

  function moveMode(modeId: string, delta: number) {
    const mode = modes.find((item) => item.id === modeId);
    if (!mode) return;
    const peerIndexes = modes
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.source === mode.source)
      .map(({ index }) => index);
    const currentPeerIndex = peerIndexes.indexOf(modes.findIndex((item) => item.id === modeId));
    const nextPeerIndex = currentPeerIndex + delta;
    if (nextPeerIndex < 0 || nextPeerIndex >= peerIndexes.length) return;
    const fromIndex = peerIndexes[currentPeerIndex];
    const toIndex = peerIndexes[nextPeerIndex];
    const nextModes = [...modes];
    [nextModes[fromIndex], nextModes[toIndex]] = [nextModes[toIndex], nextModes[fromIndex]];
    onModes(nextModes);
  }

  function renderGroup(source: Mode["source"], groupModes: Mode[]) {
    const official = source === "official";
    return (
      <section className={`mode-source-group ${source}`}>
        <header>
          <span>{official ? <ListChecks size={14} /> : <Sparkles size={14} />}</span>
          <strong>{official ? t("modes.official") : t("modes.custom")}</strong>
          <small>{groupModes.length}</small>
        </header>
        {groupModes.length === 0 ? <p>{t("modes.customEmpty")}</p> : null}
        {groupModes.map((mode, index) => (
          <div className={`mode-list-item ${mode.id === selectedMode?.id ? "active" : ""} ${mode.enabled ? "" : "disabled"}`} key={mode.id}>
            <button className="mode-list-select" onClick={() => setSelectedId(mode.id)}>
              <span className={`mode-list-icon ${mode.source}`}><ModeGlyph mode={mode} size={15} /></span>
              <span>
                <strong>{modeDisplayName(mode, t)}</strong>
                <small>{mode.base_mode_id ? t("modes.privateCopy") : mode.id}</small>
              </span>
            </button>
            <span className="mode-order-buttons">
              <button title={t("modes.moveUp")} disabled={index === 0} onClick={() => moveMode(mode.id, -1)}><ArrowUp size={13} /></button>
              <button title={t("modes.moveDown")} disabled={index === groupModes.length - 1} onClick={() => moveMode(mode.id, 1)}><ArrowDown size={13} /></button>
            </span>
            <label className="mode-enable-toggle" title={mode.enabled ? t("modes.enabled") : t("modes.disabled")}>
              <input type="checkbox" checked={mode.enabled} onChange={(event) => toggleMode(mode.id, event.target.checked)} />
              <span />
            </label>
          </div>
        ))}
      </section>
    );
  }

  if (!selectedMode) {
    return (
      <div className="settings-body">
        <button onClick={addMode}><Plus size={15} /><span>{t("modes.addMode")}</span></button>
      </div>
    );
  }

  return (
    <div className="mode-manager">
      <section className="mode-list">
        <div className="button-row">
          <button onClick={addMode}><Plus size={15} /><span>{t("common.add")}</span></button>
          <button disabled={!canSave} onClick={onSave}><Check size={15} /><span>{t("common.save")}</span></button>
        </div>
        {!canSave ? <p className="mode-validation">{t("modes.atLeastOne")}</p> : null}
        {renderGroup("official", officialModes)}
        {renderGroup("custom", customModes)}
      </section>

      <section className="mode-editor settings-body">
        <div className={`mode-source-banner ${selectedMode.source}`}>
          <ModeGlyph mode={selectedMode} size={17} />
          <span>
            <strong>{selectedMode.source === "official" ? t("modes.official") : t("modes.custom")}</strong>
            <small>{selectedMode.source === "official" ? t("modes.officialNote") : t("modes.customNote")}</small>
          </span>
        </div>
        <label>
          <span>{t("modes.name")}</span>
          <input value={selectedMode.name} onChange={(event) => updateMode({ name: event.target.value })} />
        </label>
        <label className="mode-description-field">
          <span>{t("modes.description")}</span>
          <textarea value={selectedMode.description} onChange={(event) => updateMode({ description: event.target.value })} />
        </label>
        <label className="mode-prompt-field">
          <span>Prompt</span>
          <textarea value={selectedMode.system_prompt} onChange={(event) => updateMode({ system_prompt: event.target.value })} />
        </label>
        <div className="button-row">
          <button disabled={!canSave} onClick={onSave}>
            <Check size={15} />
            <span>{selectedMode.source === "official" ? t("modes.savePrivate") : t("modes.saveMode")}</span>
          </button>
          {selectedMode.source === "custom" ? (
            <button onClick={() => deleteMode(selectedMode.id)}><Trash2 size={15} /><span>{t("common.delete")}</span></button>
          ) : null}
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
  onScan: (directory?: string) => void;
  onSave: () => void;
}) {
  const { t } = useTranslation();
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

  async function chooseSkillDirectory() {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: t("skills.chooseTitle")
      });
      if (typeof selected !== "string") return;
      onSkillScanDir(selected);
      onScan(selected);
    } catch (exc) {
      window.alert(`${t("skills.selectError")}: ${exc instanceof Error ? exc.message : String(exc)}`);
    }
  }

  return (
    <div className="skill-manager">
      <section className="skill-toolbar">
        <label>
          <span>{t("skills.directory")}</span>
          <div className="field-with-button">
            <input readOnly value={skillScanDir} />
            <button title={t("skills.chooseFolder")} onClick={() => void chooseSkillDirectory()}>
              <FolderOpen size={16} />
              <span>{t("skills.chooseFolder")}</span>
            </button>
          </div>
        </label>
        <p className="skill-match-hint">{t("skills.hint")}</p>
        <div className="button-row">
          <button onClick={() => onScan()}>
            <RefreshCcw size={15} />
            <span>{t("skills.extract")}</span>
          </button>
          <button onClick={addSkill}>
            <Plus size={15} />
            <span>{t("skills.addManual")}</span>
          </button>
        </div>
      </section>

      <section className="skill-list">
        {skills.length === 0 ? <p>{t("skills.empty")}</p> : null}
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
            <span>{t("skills.name")}</span>
            <input value={selectedSkill.name} onChange={(event) => updateSkill({ name: event.target.value })} />
          </label>
          <label>
            <span>{t("skills.category")}</span>
            <input value={selectedSkill.category} onChange={(event) => updateSkill({ category: event.target.value })} />
          </label>
          <label>
            <span>{t("skills.description")}</span>
            <textarea value={selectedSkill.description} onChange={(event) => updateSkill({ description: event.target.value })} />
          </label>
          <label>
            <span>{t("skills.example")}</span>
            <textarea
              value={selectedSkill.example}
              onChange={(event) => updateSkill({ example: event.target.value })}
              placeholder={t("skills.examplePlaceholder")}
            />
          </label>
          <div className="button-row">
            <button onClick={onSave}>
              <Check size={15} />
              <span>{t("skills.saveSkill")}</span>
            </button>
            <button onClick={() => deleteSkill(selectedSkill.id)}>
              <Trash2 size={15} />
              <span>{t("common.delete")}</span>
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
  const { t } = useTranslation();
  const [version, setVersion] = useState("0.1.0");
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateResult, setUpdateResult] = useState<UpdateCheckResult | null>(null);
  const [updateFailed, setUpdateFailed] = useState(false);

  useEffect(() => {
    void getVersion().then(setVersion).catch(() => undefined);
  }, []);

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

  async function setTheme(theme: ThemeId) {
    applyTheme(theme);
    onDraft({ ...draft, ui_theme: theme });
    const payload = await api.saveGeneral({ ui_theme: theme });
    onStateChange(payload.state);
  }

  async function setLanguage(language: UiLanguage) {
    const next = { ...draft, ui_language: language };
    onDraft(next);
    await setUiLanguage(language);
    await setTrayLanguage(language).catch(() => undefined);
    const payload = await api.saveGeneral({ ui_language: language });
    onStateChange(payload.state);
  }

  async function checkForUpdates() {
    setCheckingUpdate(true);
    setUpdateFailed(false);
    try {
      setUpdateResult(await checkGitHubUpdate(version));
    } catch {
      setUpdateResult(null);
      setUpdateFailed(true);
    } finally {
      setCheckingUpdate(false);
    }
  }

  return (
    <div className="settings-body">
      <div className="language-setting">
        <span>{t("general.language")}</span>
        <div className="language-switch" role="group" aria-label={t("general.language")}>
          {UI_LANGUAGES.map((language) => (
            <button
              className={draft.ui_language === language.value ? "active" : ""}
              aria-pressed={draft.ui_language === language.value}
              key={language.value}
              onClick={() => void setLanguage(language.value)}
            >
              {language.label}
            </button>
          ))}
        </div>
      </div>
      <div className="theme-setting">
        <span>{t("general.style")}</span>
        <div className="theme-switch" role="group" aria-label={t("general.style")}>
          <button
            className={draft.ui_theme === "morning" ? "active" : ""}
            aria-pressed={draft.ui_theme === "morning"}
            onClick={() => void setTheme("morning")}
          >
            <Sun size={16} />
            <span>{t("general.morning")}</span>
          </button>
          <button
            className={draft.ui_theme === "night" ? "active" : ""}
            aria-pressed={draft.ui_theme === "night"}
            onClick={() => void setTheme("night")}
          >
            <Moon size={16} />
            <span>{t("general.night")}</span>
          </button>
        </div>
      </div>
      <div className="checks">
        <label>
          <input type="checkbox" checked={draft.auto_copy} onChange={(event) => setAutoCopy(event.target.checked)} />
          <span>{t("general.autoCopy")}</span>
        </label>
        <label>
          <input type="checkbox" checked={draft.auto_launch} onChange={(event) => setAutoLaunch(event.target.checked)} />
          <span>{t("general.autoLaunch")}</span>
        </label>
        <label>
          <input type="checkbox" checked={draft.save_history} onChange={(event) => setSaveHistory(event.target.checked)} />
          <span>{t("general.saveHistory")}</span>
        </label>
      </div>
      <div className="about-setting">
        <span>{t("general.about")}</span>
        <div className="about-row">
          <div>
            <strong>Aura</strong>
            <small>{t("general.currentVersion")} {version}</small>
          </div>
          <div className="button-row">
            <button onClick={() => void openUrl(AURA_GITHUB_URL)}>
              <Github size={15} />
              <span>{t("general.github")}</span>
            </button>
            <button disabled={checkingUpdate} onClick={() => void checkForUpdates()}>
              <RefreshCcw size={15} />
              <span>{checkingUpdate ? t("general.checking") : t("general.checkUpdates")}</span>
            </button>
          </div>
        </div>
        {updateFailed ? <p className="setting-hint">{t("general.updateError")}</p> : null}
        {updateResult ? (
          <p className="setting-hint update-result">
            <span>{!updateResult.published
              ? t("general.noRelease")
              : updateResult.hasUpdate
                ? t("general.available", { version: updateResult.latestVersion })
                : t("general.latest")}</span>
            {updateResult.hasUpdate ? (
              <button onClick={() => void openUrl(updateResult.releaseUrl)}>{t("general.openRelease")}</button>
            ) : null}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function LlmSettings(props: {
  draft: Settings;
  onDraft: (settings: Settings) => void;
  onSaveLlm: () => void;
}) {
  const { draft, onDraft } = props;
  const { t } = useTranslation();
  const isDeepSeek = draft.llm_provider === "deepseek" || isDeepSeekEndpoint(draft.llm_base_url);
  const isCustom = !isDeepSeek;
  const deepseekModel = deepseekModels.includes(draft.llm_model)
    ? draft.llm_model
    : "deepseek-v4-flash";
  const apiKeyField = isCustom ? "custom_api_key" : "deepseek_api_key";
  const apiKeySource = isCustom
    ? draft.custom_api_key_source
    : draft.deepseek_api_key_source;

  function useDeepSeek() {
    onDraft({
      ...draft,
      llm_provider: "deepseek",
      llm_base_url: "https://api.deepseek.com",
      llm_model: "deepseek-v4-flash",
      llm_thinking_enabled: false
    });
  }

  function useCustom() {
    if (isCustom) return;
    onDraft({
      ...draft,
      llm_provider: "openai_compatible",
      llm_base_url: "",
      llm_model: "",
      llm_thinking_enabled: false
    });
  }

  return (
    <div className="settings-body llm-settings">
      <div className="llm-source-switch" role="group" aria-label={t("llm.source")}>
        <button className={!isCustom ? "active" : ""} onClick={useDeepSeek}>
          <img src={deepseekLogo} alt="DeepSeek" />
          <span><strong>DeepSeek</strong><small>{t("common.default")}</small></span>
        </button>
        <button className={isCustom ? "active" : ""} onClick={useCustom}>
          <SlidersHorizontal size={20} />
          <span><strong>{t("llm.custom")}</strong><small>OpenAI Compatible</small></span>
        </button>
      </div>

      <label>
        <span>{t("llm.endpoint")}</span>
        <input
          value={draft.llm_base_url}
          onChange={(event) => onDraft({ ...draft, llm_base_url: event.target.value })}
          placeholder={isCustom ? "http://127.0.0.1:11434/v1" : "https://api.deepseek.com"}
        />
      </label>
      <label>
        <span>{t("llm.modelName")}</span>
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
            placeholder={t("llm.modelPlaceholder")}
          />
        )}
      </label>
      <label>
        <span>{isCustom ? t("llm.customKey") : t("llm.deepseekKey")}</span>
        <input
          type="password"
          value={draft[apiKeyField] || ""}
          onFocus={(event) => {
            if (event.currentTarget.value === "********") {
              event.currentTarget.select();
            }
          }}
          onChange={(event) => onDraft({ ...draft, [apiKeyField]: event.target.value })}
          placeholder={isCustom ? t("llm.customKeyPlaceholder") : t("llm.deepseekKeyPlaceholder")}
        />
      </label>
      <p className="setting-hint">
        {apiKeySource === "config"
          ? t("llm.keySaved")
          : t("llm.keyUnsaved")}
      </p>
      {!isCustom ? (
        <label className="thinking-toggle">
          <input
            type="checkbox"
            checked={draft.llm_thinking_enabled}
            onChange={(event) => onDraft({ ...draft, llm_thinking_enabled: event.target.checked })}
          />
          <span><strong>{t("llm.thinking")}</strong><small>{t("llm.thinkingNote")}</small></span>
        </label>
      ) : (
        <p className="setting-hint">{t("llm.customNote")}</p>
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
        <span>{t("llm.save")}</span>
      </button>
    </div>
  );
}

function ShortcutsPanel() {
  const { t } = useTranslation();
  const shortcuts = [
    ["Ctrl+Shift+Space", t("shortcuts.focus")],
    ["Space", t("shortcuts.record")],
    ["Ctrl+N", t("shortcuts.newSession")],
    ["Esc", t("shortcuts.hide")]
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
  const { t } = useTranslation();
  return (
    <div className="settings-body log-list">
      <div className="button-row">
        <button onClick={() => void onRefresh()}>
          <RefreshCcw size={15} />
          <span>{t("common.refresh")}</span>
        </button>
        <button onClick={onClear}>
          <Trash2 size={15} />
          <span>{t("common.clear")}</span>
        </button>
      </div>
      {logs.length === 0 ? <p>{t("logs.empty")}</p> : null}
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
  const { t, i18n } = useTranslation();
  return (
    <div className="settings-body history-list">
      <button onClick={onClear}>
        <Trash2 size={15} />
        <span>{t("history.clear")}</span>
      </button>
      {state.history.length === 0 ? <p>{t("history.empty")}</p> : null}
      {state.history.map((item) => (
        <article key={item.id}>
          <div className="history-item-head">
            <strong>{item.title}</strong>
            <button title={t("history.deleteTitle")} onClick={() => onDelete(item.id)}>
              <Trash2 size={14} />
            </button>
          </div>
          <span>{item.mode_id} · {t("history.turns", { count: item.turn_count })}</span>
          <time>{shortTime(item.updated_at, i18n.language)}</time>
          <p>{compactText(item.last_transcript || item.last_compiled || t("common.noContent"), 90)}</p>
        </article>
      ))}
    </div>
  );
}
