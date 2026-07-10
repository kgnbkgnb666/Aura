import { invoke } from "@tauri-apps/api/core";

export type Mode = {
  id: string;
  name: string;
  target: string;
  description: string;
  system_prompt: string;
  output_hint: string;
};

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
  model_cache_dir: string | null;
  llm_provider: string;
  llm_base_url: string;
  llm_api_key: string;
  llm_model: string;
  llm_temperature: number;
  llm_timeout_seconds: number;
  history_path: string | null;
  skills: Skill[];
  skill_scan_dir: string;
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
  };
  history: Array<{
    id: string;
    title: string;
    mode_id: string;
    created_at: string;
    updated_at: string;
    last_transcript: string;
    last_compiled: string;
    turn_count: number;
  }>;
  skills: Skill[];
  service: {
    stt_provider: string;
    llm_provider: string;
    transcriber: string;
    transcriber_ready: boolean;
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

export async function ensureSidecar(): Promise<void> {
  try {
    const info = await invoke<{ port: number; base_url: string }>("ensure_sidecar");
    baseUrl = info.base_url || `http://127.0.0.1:${info.port}`;
  } catch {
    baseUrl = "http://127.0.0.1:8765";
  }
  const health = await request<{ ok: boolean; app?: string; api_version?: number }>("/api/health");
  if (!health.ok || health.app !== "Aura" || health.api_version !== 2) {
    throw new Error("Aura sidecar protocol mismatch. Stop old sidecar processes and restart Aura.");
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload as T;
}

export const api = {
  state: () => request<AppState>("/api/state"),
  devices: () => request<{ devices: DeviceInfo[] }>("/api/devices"),
  status: () => request<RuntimeState>("/api/status"),
  startRecording: () =>
    request<{ state: AppState }>("/api/record/start", { method: "POST", body: "{}" }),
  stopRecording: () =>
    request<RecordStopResponse>("/api/record/stop", { method: "POST", body: "{}" }),
  job: (jobId: string) => request<{ job: ProcessingJob; state: AppState }>(`/api/jobs/${jobId}`),
  newSession: (modeId: string) =>
    request<{ state: AppState }>("/api/session/new", {
      method: "POST",
      body: JSON.stringify({ mode_id: modeId })
    }),
  loadSession: (sessionId: string) =>
    request<{ session: AppState["current_session"]; transcript: string; compiled: string; state: AppState }>(
      "/api/session/load",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId })
      }
    ),
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
  warmupStt: () =>
    request<{ state: AppState }>("/api/stt/warmup", { method: "POST", body: "{}" }),
  testMicrophone: () =>
    request<{ recording: RecordingResult; state: AppState }>("/api/microphone/test", {
      method: "POST",
      body: JSON.stringify({ duration_seconds: 3 })
    }),
  transcribeTest: () =>
    request<{ transcript: string; state: AppState }>("/api/transcribe/test", {
      method: "POST",
      body: "{}"
    }),
  clearHistory: () =>
    request<{ state: AppState }>("/api/history/clear", { method: "POST", body: "{}" }),
  logs: () => request<{ logs: LogEntry[]; state: AppState }>("/api/logs"),
  clearLogs: () =>
    request<{ logs: LogEntry[]; state: AppState }>("/api/logs/clear", {
      method: "POST",
      body: "{}"
    })
};
