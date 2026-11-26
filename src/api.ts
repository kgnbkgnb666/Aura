import { invoke } from "@tauri-apps/api/core";
import { enable, disable, isEnabled } from "@tauri-apps/plugin-autostart";
import { OperationTimeoutError, retryWithBackoff, withTimeout } from "./workflows/async";

export type Mode = {
  id: string;
  name: string;
  target: string;
  description: string;
  system_prompt: string;
  output_hint: string;
  source: "official" | "custom";
  enabled: boolean;
  icon: string;
  base_mode_id: string;
};

export type RewriteSkill = {name: string; intent: string; instructions: string; enabled: boolean};

export type Settings = {
  app_name: string;
  mode_id: string;
  auto_copy: boolean;
  save_history: boolean;
  keep_window_on_top: boolean;
  hotkey: string;
  push_to_talk_key: string;
  input_device_index: number | null;
  stt_provider: string;
  asr_api_key: string;
  asr_ws_url: string;
  asr_resource_id: string;
  model_cache_dir: string | null;
  ui_theme: "morning" | "night";
  ui_language: "zh-CN" | "zh-TW" | "en" | "ja";
  llm_provider: string;
  llm_base_url: string;
  deepseek_api_key: string;
  custom_api_key: string;
  ark_api_key: string;
  deepseek_api_key_source?: "config" | "unset";
  custom_api_key_source?: "config" | "unset";
  llm_model: string;
  llm_thinking_enabled: boolean;
  llm_temperature: number;
  llm_timeout_seconds: number;
  auto_launch: boolean;
  history_path: string | null;
  skills: Skill[];
  skill_scan_dir: string;
  preview_mode?: "bar" | "input";
  translation_language?: string;
  voice_shortcuts?: Record<"dictate" | "translate", string>;
  rewrite_skills?: RewriteSkill[];
  vocabulary?: string[];
};

export const autostart = {
  isEnabled: () => isEnabled(),
  enable: () => enable(),
  disable: () => disable(),
};

export type Skill = {
  id: string;
  name: string;
  description: string;
  example: string;
  category: string;
  enabled: boolean;
  source_path: string;
};

export type DeviceInfo = {
  index: number;
  name: string;
  max_input_channels: number;
  default_sample_rate: number;
  is_default_input: boolean;
};

export type RuntimeState = {
  status: string;
  volume: number;
  mic_test_volume?: number;
  recording: boolean;
  latest_job_id: string;
  log_count: number;
};

export type AppState = {
  settings: Settings;
  modes: Mode[];
  current_mode: Mode;
  current_session: {
    id: string;
    mode_id: string;
    title: string;
    created_at: string;
    updated_at: string;
    turn_count: number;
    merge_output: boolean;
  };
  current_clarity: { score: number; level: string; label: string } | null;
  history: Array<{
    id: string;
    title: string;
    mode_id: string;
    created_at: string;
    updated_at: string;
    last_transcript: string;
    last_compiled: string;
    turn_count: number;
    merge_output: boolean;
  }>;
  skills: Skill[];
  service: {
    stt_provider: string;
    llm_provider: string;
    transcriber: string;
    transcriber_ready: boolean;
    transcriber_status: "not_loaded" | "loading" | "ready" | "error";
    transcriber_progress: number;
    transcriber_error: string;
  };
  runtime: RuntimeState;
};

export type RecordingResult = {
  wav_path: string;
  duration_seconds: number;
  average_volume: number;
  max_volume: number;
};

export type RecordStopResponse = {
  job: ProcessingJob;
  state: AppState;
};

export type ProcessingJob = {
  id: string;
  phase: "transcribing" | "compiling" | "done" | "error";
  done: boolean;
  error: string;
  transcript: string;
  compiled: string;
  recording: RecordingResult;
};

export type LogEntry = {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "error";
  source: string;
  message: string;
  details: string;
};

let baseUrl = "http://127.0.0.1:8765";
let authToken = "";
const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
const LONG_REQUEST_TIMEOUT_MS = 120_000;
const SIDECAR_API_VERSION = 9;

type RequestOptions = RequestInit & { timeoutMs?: number; retryAttempts?: number };

class RetryableHttpError extends Error {}

export async function ensureSidecar(): Promise<void> {
  try {
    const info = await withTimeout(
      () => invoke<{ port: number; base_url: string; token: string }>("ensure_sidecar"),
      30_000,
      "sidecar startup",
    );
    baseUrl = info.base_url || `http://127.0.0.1:${info.port}`;
    authToken = info.token;
  } catch {
    baseUrl = "http://127.0.0.1:8765";
    authToken = "";
  }
  const health = await request<{ ok: boolean; app?: string; api_version?: number }>("/api/health");
  if (!health.ok || health.app !== "Aura" || health.api_version !== SIDECAR_API_VERSION) {
    throw new Error("Aura sidecar protocol mismatch. Stop old sidecar processes and restart Aura.");
  }
}

export function hideMainWindow(): Promise<void> {
  return invoke<void>("hide_window");
}

export function setTrayLanguage(language: Settings["ui_language"]): Promise<void> {
  return invoke<void>("set_tray_language", { language });
}

export function showMainWindow(tab = "general"): Promise<void> {
  return invoke<void>("show_main", { tab });
}

export function copyText(text: string): Promise<void> {
  return invoke<void>("copy_text", { text });
}

export function insertText(text: string): Promise<boolean> {
  return invoke<boolean>("insert_text", { text });
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    retryAttempts,
    signal: parentSignal,
    ...init
  } = options;
  const method = (init.method || "GET").toUpperCase();
  const maxAttempts = retryAttempts ?? (method === "GET" ? 3 : 1);
  const { response, responseText } = await retryWithBackoff(
    () => withTimeout(
      async (signal) => {
        const response = await fetch(`${baseUrl}${path}`, {
          ...init,
          signal,
          headers: {
            "Content-Type": "application/json",
            "X-Aura-Token": authToken,
            ...(init.headers || {})
          }
        });
        const responseText = await response.text();
        if ([502, 503, 504].includes(response.status)) {
          throw new RetryableHttpError(`Sidecar temporarily unavailable: ${response.status}`);
        }
        return { response, responseText };
      },
      timeoutMs,
      `${method} ${path}`,
      parentSignal || undefined,
    ),
    {
      maxAttempts,
      signal: parentSignal || undefined,
      shouldRetry: (error) =>
        error instanceof RetryableHttpError ||
        error instanceof OperationTimeoutError ||
        error instanceof TypeError,
    },
  );
  let payload: Record<string, unknown> = {};
  if (responseText) {
    try {
      payload = JSON.parse(responseText) as Record<string, unknown>;
    } catch {
      throw new Error(`Invalid JSON response from ${path} (${response.status})`);
    }
  }
  if (!response.ok) {
    throw new Error(String(payload.error || `Request failed: ${response.status}`));
  }
  return payload as T;
}

export type HistoryEntry = { id: string; created_at: string; raw_transcript: string; compiled_text: string; llm_provider: string };

export const api = {
  latestRelease: () => request<{ tag: string | null }>("/api/releases/latest", {
    retryAttempts: 1,
  }),
  importRewriteSkills: (filename:string,content:string) => request<{skills:RewriteSkill[]}>("/api/settings/skills/import", {
    method:"POST",body:JSON.stringify({filename,content})
  }),
  entries: (query: string, offset: number) => request<{entries: HistoryEntry[]; more: boolean}>("/api/history/entries", {
    method: "POST", body: JSON.stringify({ query, offset })
  }),
  deleteEntry: (id: string) => request<{state: AppState}>("/api/history/delete-entry", {
    method: "POST", body: JSON.stringify({ id })
  }),
  state: (signal?: AbortSignal) => request<AppState>("/api/state", { signal }),
  devices: (signal?: AbortSignal) => request<{ devices: DeviceInfo[] }>("/api/devices", { signal }),
  status: (signal?: AbortSignal, retryAttempts = 3) =>
    request<RuntimeState>("/api/status", { signal, retryAttempts }),
  startRecording: () =>
    request<{ state: AppState; recording_id: string }>("/api/record/start", { method: "POST", body: "{}" }),
  previewRecording: (id:string, signal:AbortSignal) => request<{text:string; snapshot?:boolean}>("/api/record/preview", {method:"POST",body:JSON.stringify({recording_id:id}),signal,timeoutMs:30000}),
  stopRecording: (dictation = false, selected = "", language = "") =>
    request<RecordStopResponse>("/api/record/stop", { method: "POST", body: JSON.stringify({ dictation, selected, language }) }),
  cancelRecording: () =>
    request<{ state: AppState }>("/api/record/cancel", { method: "POST", body: "{}" }),
  job: (jobId: string, signal?: AbortSignal) => request<{ job: ProcessingJob; state: AppState }>(`/api/jobs/${jobId}`, { signal, retryAttempts: 1 }),
  newSession: (modeId: string, signal?: AbortSignal) =>
    request<{ state: AppState }>("/api/session/new", {
      method: "POST",
      body: JSON.stringify({ mode_id: modeId }),
      signal,
    }),
  loadSession: (sessionId: string, signal?: AbortSignal) =>
    request<{ session: AppState["current_session"]; transcript: string; compiled: string; clarity: { score: number; level: string; label: string } | null; state: AppState }>(
      "/api/session/load",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
        signal,
      }
    ),
  setMergeOutput: (mergeOutput: boolean) =>
    request<{ state: AppState }>("/api/session/merge-output", {
      method: "POST",
      body: JSON.stringify({ merge_output: mergeOutput })
    }),
  setMode: (modeId: string) =>
    request<{ state: AppState }>("/api/mode", {
      method: "POST",
      body: JSON.stringify({ mode_id: modeId })
    }),
  saveModes: (modes: Mode[]) =>
    request<{ state: AppState }>("/api/modes", {
      method: "POST",
      body: JSON.stringify({ modes })
    }),
  scanSkills: (directory: string) =>
    request<{ skills: Skill[]; state: AppState }>("/api/skills/scan", {
      method: "POST",
      body: JSON.stringify({ directory })
    }),
  saveSkills: (skills: Skill[], skillScanDir: string) =>
    request<{ state: AppState }>("/api/skills/save", {
      method: "POST",
      body: JSON.stringify({ skills, skill_scan_dir: skillScanDir })
    }),
  saveGeneral: (payload: Partial<Settings>) =>
    request<{ state: AppState }>("/api/settings/general", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  saveSpeech: (payload: Partial<Settings>) =>
    request<{ state: AppState }>("/api/settings/speech", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  saveLlm: (payload: Partial<Settings>) =>
    request<{ state: AppState }>("/api/settings/llm", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  warmupStt: (signal?: AbortSignal) =>
    request<{ state: AppState }>("/api/stt/warmup", { method: "POST", body: "{}", signal }),
  testLlm: () =>
    request<{ ok: boolean; asr: { ok: boolean; error?: string }; llm: { ok: boolean; error?: string } }>("/api/llm/test", {
      method: "POST",
      body: "{}",
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    }),
  compile: (transcript: string, signal?: AbortSignal) =>
    request<{ transcript: string; compiled: string; state: AppState }>("/api/compile", {
      method: "POST",
      body: JSON.stringify({ transcript }),
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      signal,
    }),
  updateTurn: (transcript: string, compiled: string, signal?: AbortSignal) =>
    request<{ state: AppState }>("/api/turn/update", {
      method: "POST",
      body: JSON.stringify({ transcript, compiled }),
      signal,
    }),
  assessClarity: (transcript: string, signal?: AbortSignal) =>
    request<{ clarity: { score: number; level: string; label: string } | null }>("/api/clarity/assess", {
      method: "POST",
      body: JSON.stringify({ transcript }),
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      signal,
    }),
  generateQuestions: (transcript: string, signal?: AbortSignal) =>
    request<{ questions: Array<{ id: string; question: string; options: string[]; multi_select: boolean }> }>("/api/clarity/questions", {
      method: "POST",
      body: JSON.stringify({ transcript }),
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      signal,
    }),
  testMicrophone: (transcribe = false) =>
    request<{ recording: RecordingResult; state: AppState; transcript: string | null }>("/api/microphone/test", {
      method: "POST",
      body: JSON.stringify({ duration_seconds: 3, keep_audio: false, transcribe }),
      timeoutMs: transcribe ? LONG_REQUEST_TIMEOUT_MS : DEFAULT_REQUEST_TIMEOUT_MS,
    }),
  startMicrophoneTest: () =>
    request<{ testing: boolean }>("/api/microphone/start", { method: "POST", body: "{}" }),
  stopMicrophoneTest: () =>
    request<{ testing: boolean }>("/api/microphone/stop", { method: "POST", body: "{}" }),
  transcribeTest: () =>
    request<{ transcript: string; state: AppState }>("/api/transcribe/test", {
      method: "POST",
      body: "{}"
    }),
  clearHistory: () =>
    request<{ state: AppState }>("/api/history/clear", { method: "POST", body: "{}" }),
  deleteHistory: (sessionId: string) =>
    request<{ deleted: boolean; deleted_current: boolean; state: AppState }>("/api/history/delete", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId })
    }),
  logs: (signal?: AbortSignal) => request<{ logs: LogEntry[]; state: AppState }>("/api/logs", { signal }),
  clearLogs: () =>
    request<{ logs: LogEntry[]; state: AppState }>("/api/logs/clear", {
      method: "POST",
      body: "{}"
    })
};
