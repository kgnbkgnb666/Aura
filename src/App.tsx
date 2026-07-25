import type { SVGProps } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { getVersion } from "@tauri-apps/api/app";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import {
  AlertTriangle,
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
  HelpCircle,
  History,
  Keyboard,
  Lightbulb,
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
import { setUiLanguage, storedLanguage, UI_LANGUAGES, UiLanguage } from "./i18n";
import { AURA_GITHUB_URL, checkGitHubUpdate, UpdateCheckResult } from "./update";

function DeepSeekLogo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="35" viewBox="0 0 63.1196 46.4033" fill="none" {...props}>
      <path d="M62.4575 3.89441C61.7888 3.56726 61.501 4.1908 61.1101 4.50769C60.9763 4.60999 60.863 4.7428 60.75 4.86548C59.7727 5.9082 58.6311 6.59302 57.1394 6.51123C54.9587 6.38855 53.0969 7.07349 51.4512 8.73975C51.1013 6.68506 49.939 5.45837 48.1699 4.67126C47.2441 4.26233 46.3081 3.85352 45.6599 2.96411C45.2073 2.33032 45.084 1.625 44.8577 0.929932C44.7136 0.510864 44.5696 0.081543 44.0862 0.0098877C43.5615 -0.0718994 43.3557 0.367676 43.1501 0.735718C42.3271 2.2384 42.0083 3.89441 42.0391 5.5708C42.1111 9.34277 43.7056 12.3481 46.8738 14.4846C47.2336 14.73 47.3264 14.9753 47.2131 15.333C46.9971 16.0691 46.74 16.7847 46.5137 17.5206C46.3696 17.9908 46.1538 18.093 45.6497 17.8887C43.9114 17.1628 42.4094 16.0895 41.0825 14.7913C38.8298 12.6139 36.7932 10.2117 34.2524 8.33081C33.6558 7.89124 33.0593 7.48242 32.4421 7.09399C29.8499 4.57922 32.7815 2.5144 33.4604 2.26904C34.1702 2.01343 33.7073 1.1344 31.4133 1.14465C29.1196 1.15479 27.0212 1.92151 24.3467 2.94373C23.9558 3.09705 23.5444 3.20947 23.1226 3.30151C20.6951 2.84143 18.1748 2.73926 15.5415 3.03577C10.5835 3.58777 6.62329 5.92859 3.7124 9.92554C0.215088 14.73 -0.60791 20.1886 0.400146 25.8824C1.45972 31.8828 4.5249 36.8508 9.23608 40.7354C14.1221 44.7629 19.7488 46.7357 26.1675 46.3575C30.0659 46.1327 34.4067 45.6113 39.303 41.4713C40.5374 42.0847 41.8335 42.33 43.9834 42.514C45.6394 42.6674 47.2336 42.4323 48.468 42.1766C50.4019 41.7678 50.2683 39.9789 49.5688 39.6517C43.9009 37.0144 45.1455 38.0878 44.0142 37.2189C46.8943 33.8148 51.2351 30.278 52.9324 18.8188C53.0662 17.9091 52.9529 17.3367 52.9324 16.6006C52.9221 16.1509 53.0249 15.9771 53.5393 15.9259C54.9587 15.7625 56.3372 15.3739 57.6023 14.6788C61.2747 12.6753 62.7559 9.38367 63.1055 5.43799C63.157 4.83484 63.0952 4.2113 62.4575 3.89441ZM30.4568 39.4065C24.9639 35.0927 22.2998 33.6718 21.199 33.7332C20.1704 33.7944 20.3557 34.97 20.5818 35.7367C20.8186 36.493 21.1272 37.0144 21.5591 37.6788C21.8574 38.1184 22.0632 38.7727 21.2607 39.2633C19.4915 40.3571 16.416 38.8953 16.272 38.8237C12.6924 36.718 9.69897 33.9375 7.59033 30.1349C5.55347 26.4753 4.37061 22.5499 4.17529 18.3589C4.12378 17.3468 4.42212 16.989 5.43018 16.8051C6.75708 16.5597 8.12524 16.5087 9.45215 16.7029C15.0581 17.5206 19.8311 20.025 23.8323 23.9913C26.116 26.2504 27.844 28.9491 29.6235 31.5864C31.5164 34.3873 33.553 37.0553 36.145 39.2429C37.0605 40.0095 37.791 40.5922 38.4905 41.0215C36.3816 41.2567 32.8638 41.3077 30.4568 39.4065ZM33.0901 22.4886C33.0901 22.0388 33.4502 21.681 33.9026 21.681C34.0056 21.681 34.0981 21.7015 34.1804 21.7322C34.2935 21.7731 34.3965 21.8344 34.4788 21.9264C34.6228 22.0695 34.7051 22.2739 34.7051 22.4886C34.7051 22.9384 34.345 23.2961 33.8923 23.2961C33.4397 23.2961 33.0901 22.9384 33.0901 22.4886ZM41.2676 26.6798C40.7432 26.8944 40.2185 27.0784 39.7144 27.0989C38.9326 27.1398 38.0789 26.8229 37.616 26.4344C36.896 25.8313 36.3816 25.494 36.1658 24.441C36.073 23.9913 36.1245 23.2961 36.2068 22.8975C36.3921 22.0388 36.1863 21.4868 35.5793 20.986C35.0857 20.577 34.4583 20.4646 33.769 20.4646C33.5117 20.4646 33.2751 20.3522 33.1003 20.2601C32.8123 20.1171 32.5757 19.7593 32.802 19.3197C32.874 19.1766 33.2239 18.8291 33.3062 18.7677C34.2422 18.2362 35.3223 18.4099 36.3201 18.8086C37.2458 19.1869 37.9453 19.882 38.9534 20.8633C39.9819 22.0491 40.167 22.3762 40.7534 23.2655C41.2163 23.9607 41.6379 24.6761 41.926 25.494C42.1008 26.0051 41.8745 26.4242 41.2676 26.6798Z" fill="#4D6BFE" />
    </svg>
  );
}

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

function ClarityDonut({ score, level, label }: {
  score: number;
  level: string;
  label: string;
}) {
  const color = level === "high" ? "#28a765" : level === "medium" ? "#d4a017" : "#d14343";
  const r = 15;
  const circumference = 2 * Math.PI * r;
  const dashOffset = circumference * (1 - score / 100);

  return (
    <div className="clarity-donut" title={`${label}: ${score}%`}>
      <svg width="34" height="34" viewBox="0 0 40 40">
        <circle cx="20" cy="20" r={r} fill="none" stroke="var(--clarity-track)" strokeWidth="5" />
        <circle
          cx="20" cy="20" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={circumference} strokeDashoffset={dashOffset}
          strokeLinecap="round" transform="rotate(-90 20 20)"
          style={{ transition: "stroke-dashoffset 0.5s ease, stroke 0.3s ease" }}
        />
        <text x="20" y="25" textAnchor="middle" fontSize="15" fontWeight="700" fill="currentColor">
          {score}
        </text>
      </svg>
    </div>
  );
}

export default function App() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<AppState | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("main");
  const [transcript, setTranscript] = useState("");
  const [compiled, setCompiled] = useState("");
  const [copied, setCopied] = useState(false);
  const [copiedFading, setCopiedFading] = useState(false);
  const copiedTimeoutRef = useRef<number | null>(null);
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
  const [clarity, setClarity] = useState<{ score: number; level: string; label: string } | null>(null);
  const [clarityLoading, setClarityLoading] = useState(false);
  const [questions, setQuestions] = useState<Array<{ id: string; question: string; options: string[]; multi_select: boolean; selectedAnswers: string[] }>>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [showQuestionsModal, setShowQuestionsModal] = useState(false);
  const questionsCacheRef = useRef<{ transcript: string; questions: Array<{ id: string; question: string; options: string[]; multi_select: boolean; selectedAnswers: string[] }> } | null>(null);
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
          if (restored?.clarity) {
            setClarity(restored.clarity);
          } else if (restored?.transcript?.trim()) {
            assessClarity(restored.transcript);
          }
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
        // Translate known error codes to user-friendly messages.
        const errorCode = payload.job.error;
        if (errorCode === "transcriber.recordingTooQuiet") {
          setError(t("main.recordingTooQuiet"));
        } else if (errorCode === "llm.notConfigured") {
          setError(t("llm.notConfigured"));
        } else if (errorCode === "llm.invalidKey") {
          setError(t("llm.invalidKey"));
        } else if (errorCode === "llm.timeout") {
          setError(t("llm.timeoutError"));
        } else if (errorCode === "llm.connectionError") {
          setError(t("llm.connectionError"));
        } else {
          setError(errorCode);
        }
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
          if (!payload.job.error && payload.job.transcript) {
            assessClarity(payload.job.transcript);
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
    setCopiedFading(false);
    // Clear any existing timeout
    if (copiedTimeoutRef.current !== null) window.clearTimeout(copiedTimeoutRef.current);
    // Show "Copied" for 900ms, then start fading
    copiedTimeoutRef.current = window.setTimeout(() => {
      setCopiedFading(true);
    }, 900) as unknown as number;
    // Fully remove after fade completes
    const fadeId = window.setTimeout(() => {
      setCopied(false);
      setCopiedFading(false);
      copiedTimeoutRef.current = null;
      setState((current) => {
        if (!current || current.runtime.status !== t("common.copied")) return current;
        return { ...current, runtime: { ...current.runtime, status: t("main.organized") } };
      });
    }, 1600);
    return () => {
      window.clearTimeout(fadeId);
      if (copiedTimeoutRef.current !== null) {
        window.clearTimeout(copiedTimeoutRef.current);
        copiedTimeoutRef.current = null;
      }
    };
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
    textEditing: transcriptEditing || compiledEditing || showQuestionsModal,
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
    setQuestions([]);
    questionsCacheRef.current = null;
    // Use persisted clarity if available; only re-assess if missing and transcript exists
    if (payload.clarity) {
      setClarity(payload.clarity);
    } else if (payload.transcript.trim()) {
      assessClarity(payload.transcript);
    } else {
      setClarity(null);
    }
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
    setClarity(null);
    setQuestions([]);
    questionsCacheRef.current = null;
  }

  async function copyCompiled() {
    if (!compiled.trim()) return;
    await navigator.clipboard.writeText(compiled);
    // Force refresh even if already "copied" state (e.g. after auto-copy)
    setCopied(false);
    requestAnimationFrame(() => setCopied(true));
  }

  async function assessClarity(text: string) {
    if (!text.trim()) { setClarity(null); return; }
    setClarityLoading(true);
    try {
      const result = await api.assessClarity(text);
      if (result.clarity) setClarity(result.clarity);
      else setClarity(null);
    } catch {
      setClarity(null);
    } finally {
      setClarityLoading(false);
    }
  }

  async function loadQuestions(forceRefresh = false) {
    if (!transcript.trim()) return;
    const cacheKey = transcript.trim();
    // Reuse cached questions for same transcript unless forced refresh
    if (!forceRefresh && questionsCacheRef.current?.transcript === cacheKey) {
      setQuestions(structuredClone(questionsCacheRef.current.questions));
      return;
    }
    setQuestionsLoading(true);
    try {
      const result = await api.generateQuestions(transcript);
      const fresh = result.questions.map(q => ({ ...q, selectedAnswers: [] }));
      questionsCacheRef.current = { transcript: cacheKey, questions: structuredClone(fresh) };
      setQuestions(fresh);
    } catch {
      setQuestions([]);
    } finally {
      setQuestionsLoading(false);
    }
  }

  async function refreshQuestions() {
    await loadQuestions(true);
  }

  async function handleConfirmQuestions() {
    const answeredQuestions = questions.filter(q => q.selectedAnswers.length > 0);
    if (answeredQuestions.length === 0) {
      setShowQuestionsModal(false);
      return;
    }

    const supplementText = answeredQuestions
      .map(q => `${q.question}\n答：${q.selectedAnswers.join("；")}`)
      .join("\n\n");

    const enhancedTranscript = transcript + "\n\n[补充信息]\n" + supplementText;
    setTranscript(enhancedTranscript);
    transcriptEditedByUser.current = true;
    setShowQuestionsModal(false);
    setQuestions([]);

    setBusy(true);
    setError("");
    try {
      await api.updateTurn(enhancedTranscript, compiled);
      const payload = await api.compile(enhancedTranscript);
      setCompiled(payload.compiled);
      setState(payload.state);
      setTranscriptEditing(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }

    await assessClarity(enhancedTranscript);
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
    assessClarity(transcript);
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

  async function saveLlm(settings?: Settings) {
    const payload = await api.saveLlm(settings || draft);
    setState(payload.state);
    // Only update draft with server response if no newer save is pending
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
                {clarity ? (
                  <>
                    <span className="clarity-label">{t("clarity.label")}</span>
                    <ClarityDonut score={clarity.score} level={clarity.level} label={clarity.label} />
                  </>
                ) : null}
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
	                  title={t("clarity.supplementaryTitle")}
	                  disabled={busy || !transcript.trim()}
	                  onClick={() => {
	                    void loadQuestions();
	                    setShowQuestionsModal(true);
	                  }}
	                >
	                  <Lightbulb size={14} />
	                  <span>{t("clarity.supplementary")}</span>
	                </button>
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
                <button className={`copy-button ${copied ? `copied${copiedFading ? " copied-fading" : ""}` : ""}`} title={copied ? t("common.copied") : t("common.copy")} onClick={copyCompiled}>
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

        {showQuestionsModal ? (
          <div className="modal-overlay" onClick={() => setShowQuestionsModal(false)}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
              <header className="modal-header">
                <h3>{t("clarity.supplementaryTitle")}</h3>
                <button className="modal-close" onClick={() => setShowQuestionsModal(false)}>✕</button>
              </header>
              <div className="questions-list">
                {questions.length === 0 ? (
                  <p className="questions-empty">{questionsLoading ? "..." : t("clarity.noQuestions")}</p>
                ) : (
                  questions.map((q, i) => (
                    <div key={q.id} className="question-item">
                      <p className="question-text">
                        {i + 1}. {q.question}
                        {q.multi_select ? <span className="multi-select-badge">{t("clarity.multiSelect")}</span> : null}
                      </p>
                      <div className="question-options">
                        {q.options.map((opt, j) => {
                          const isSelected = q.selectedAnswers.includes(opt);
                          return (
                            <button
                              key={j}
                              className={`option-chip ${isSelected ? "active" : ""}`}
                              onClick={() => {
                                setQuestions(prev => prev.map(item => {
                                  if (item.id !== q.id) return item;
                                  if (item.multi_select) {
                                    // Toggle: add/remove from selectedAnswers
                                    const next = isSelected
                                      ? item.selectedAnswers.filter(a => a !== opt)
                                      : [...item.selectedAnswers, opt];
                                    return { ...item, selectedAnswers: next };
                                  }
                                  // Single select: replace
                                  return { ...item, selectedAnswers: isSelected ? [] : [opt] };
                                }));
                              }}
                            >
                              {isSelected && q.multi_select ? <Check size={11} /> : null}
                              {opt}
                            </button>
                          );
                        })}
                        <input
                          className="option-input"
                          placeholder={t("clarity.customAnswer")}
                          value={(() => {
                            const custom = q.selectedAnswers.filter(a => !q.options.includes(a));
                            return custom.length > 0 ? custom.join("；") : "";
                          })()}
                          onChange={e => {
                            setQuestions(prev => prev.map(item => {
                              if (item.id !== q.id) return item;
                              const optionAnswers = item.selectedAnswers.filter(a => item.options.includes(a));
                              const newCustom = e.target.value ? [e.target.value] : [];
                              return { ...item, selectedAnswers: [...optionAnswers, ...newCustom] };
                            }));
                          }}
                          onKeyDown={e => {
                            if (e.code === "Space") e.stopPropagation();
                          }}
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>
              <footer className="modal-footer">
                <button
                  className="modal-refresh"
                  title={t("clarity.refreshQuestions")}
                  disabled={questionsLoading}
                  onClick={refreshQuestions}
                >
                  {questionsLoading ? <RefreshCcw size={14} className="spinning" /> : <RefreshCcw size={14} />}
                  <span>{questionsLoading ? t("clarity.refreshing") : t("clarity.refreshQuestions")}</span>
                </button>
                <button className="modal-confirm" onClick={handleConfirmQuestions}>
                  <Check size={14} />
                  <span>{t("common.done")}</span>
                </button>
              </footer>
            </div>
          </div>
        ) : null}

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
    } catch (exc) {
      setUpdateResult(null);
      setUpdateFailed(true);
      const message = exc instanceof Error ? exc.message : String(exc);
      if (message.includes("abort") || message.includes("AbortError") || message.includes("Timeout")) {
        console.warn("Update check timed out:", message);
      } else {
        console.warn("Update check failed:", message);
      }
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
  onSaveLlm: (settings: Settings) => void;
}) {
  const { draft, onDraft, onSaveLlm } = props;
  const { t } = useTranslation();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);
  const testVersionRef = useRef(0);
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
    const next = {
      ...draft,
      llm_provider: "deepseek",
      llm_base_url: "https://api.deepseek.com",
      llm_model: "deepseek-v4-flash",
      llm_thinking_enabled: false
    };
    onDraft(next);
    onSaveLlm(next);
  }

  function useCustom() {
    if (isCustom) return;
    const next = {
      ...draft,
      llm_provider: "openai_compatible",
      llm_base_url: "",
      llm_model: "",
      llm_thinking_enabled: false
    };
    onDraft(next);
    onSaveLlm(next);
  }

  async function runLlmTest() {
    testVersionRef.current += 1;
    const version = testVersionRef.current;
    setTesting(true);
    setTestResult(null);
    try {
      // Save current settings first so the sidecar has the latest config
      await api.saveLlm(draft);
      const result = await api.testLlm();
      if (version !== testVersionRef.current) return;
      if (result.ok) {
        setTestResult({ ok: true, text: t("llm.testSuccess", { model: result.model || draft.llm_model }) });
      } else {
        const code = result.error || "";
        if (code === "llm.notConfigured") setTestResult({ ok: false, text: t("llm.notConfigured") });
        else if (code === "llm.invalidKey") setTestResult({ ok: false, text: t("llm.invalidKey") });
        else if (code === "llm.timeout") setTestResult({ ok: false, text: t("llm.timeoutError") });
        else if (code === "llm.connectionError") setTestResult({ ok: false, text: t("llm.connectionError") });
        else { setTestResult({ ok: false, text: code || t("llm.testFailed") }); }
      }
    } catch (exc) {
      if (version !== testVersionRef.current) return;
      setTestResult({ ok: false, text: exc instanceof Error ? exc.message : t("llm.testFailed") });
    } finally {
      if (version === testVersionRef.current) setTesting(false);
    }
  }

  return (
    <div className="settings-body llm-settings">
      <div className="llm-source-switch" role="group" aria-label={t("llm.source")}>
        <button className={!isCustom ? "active" : ""} onClick={useDeepSeek}>
          <DeepSeekLogo width={48} height={35} aria-hidden="true" />
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
          onBlur={() => onSaveLlm(draft)}
          placeholder={isCustom ? "http://127.0.0.1:11434/v1" : "https://api.deepseek.com"}
        />
      </label>
      <label>
        <span>{t("llm.modelName")}</span>
        {!isCustom ? (
          <select
            value={deepseekModel}
            onChange={(event) => {
              const next = {
                ...draft,
                llm_provider: "deepseek",
                llm_model: event.target.value
              };
              onDraft(next);
              onSaveLlm(next);
            }}
          >
            <option value="deepseek-v4-flash">deepseek-v4-flash</option>
            <option value="deepseek-v4-pro">deepseek-v4-pro</option>
          </select>
        ) : (
          <input
            value={draft.llm_model}
            onChange={(event) => onDraft({ ...draft, llm_model: event.target.value })}
            onBlur={() => onSaveLlm(draft)}
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
          onBlur={() => onSaveLlm(draft)}
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
            onChange={(event) => {
              const next = { ...draft, llm_thinking_enabled: event.target.checked };
              onDraft(next);
              onSaveLlm(next);
            }}
          />
          <span><strong>{t("llm.thinking")}</strong><small>{t("llm.thinkingNote")}</small></span>
        </label>
      ) : (
        <p className="setting-hint">{t("llm.customNote")}</p>
      )}
      <div className="llm-test-row">
        <button className="llm-test-button" disabled={testing} onClick={() => void runLlmTest()}>
          {testing ? (
            <RefreshCcw size={15} className="spinning" />
          ) : (
            <Play size={15} />
          )}
          <span>{testing ? t("llm.testing") : t("llm.testConnection")}</span>
        </button>
        {testResult ? (
          <span className={`llm-test-result ${testResult.ok ? "ok" : "fail"}`}>
            {testResult.ok ? <Check size={14} /> : <AlertTriangle size={14} />}
            <span>{testResult.text}</span>
          </span>
        ) : null}
      </div>
      <div className="split-fields">
        <label>
          <span>Temperature</span>
          <input type="number" min="0" max="2" step="0.1" value={draft.llm_temperature} onChange={(event) => onDraft({ ...draft, llm_temperature: Number(event.target.value) })} onBlur={() => onSaveLlm(draft)} />
        </label>
        <label>
          <span>Timeout</span>
          <input type="number" min="5" max="600" value={draft.llm_timeout_seconds} onChange={(event) => onDraft({ ...draft, llm_timeout_seconds: Number(event.target.value) })} onBlur={() => onSaveLlm(draft)} />
        </label>
      </div>
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
