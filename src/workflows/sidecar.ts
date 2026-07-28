import type { AppState, ProcessingJob, RuntimeState } from "../api";
import { delay, OperationTimeoutError, throwIfAborted } from "./async";

export const STT_BOOT_TIMEOUT_MS = 10 * 60 * 1000;
export const PROCESSING_JOB_TIMEOUT_MS = 5 * 60 * 1000;

type JobPayload = { job: ProcessingJob; state: AppState };

export class SidecarConnectionError extends Error {
  readonly cause: unknown;

  constructor(cause: unknown) {
    super("Aura sidecar stopped responding after 3 consecutive attempts");
    this.name = "SidecarConnectionError";
    this.cause = cause;
  }
}

export async function waitForTranscriber(options: {
  initialState: AppState;
  warmup: (signal: AbortSignal) => Promise<unknown>;
  getState: (signal: AbortSignal) => Promise<AppState>;
  onState: (state: AppState) => void;
  signal: AbortSignal;
  timeoutMs?: number;
  pollIntervalMs?: number;
}): Promise<AppState> {
  const {
    warmup,
    getState,
    onState,
    signal,
    timeoutMs = STT_BOOT_TIMEOUT_MS,
    pollIntervalMs = 200,
  } = options;
  let state = options.initialState;
  if (state.service.transcriber_ready) return state;

  await warmup(signal);
  const deadline = Date.now() + timeoutMs;
  while (true) {
    throwIfAborted(signal);
    if (Date.now() >= deadline) {
      throw new OperationTimeoutError("STT startup", timeoutMs);
    }
    state = await getState(signal);
    onState(state);
    if (state.service.transcriber_ready) return state;
    if (state.service.transcriber_status === "error") {
      throw new Error(state.service.transcriber_error || state.runtime.status || "STT startup failed");
    }
    await delay(pollIntervalMs, signal);
  }
}

export async function pollProcessingJob(options: {
  jobId: string;
  getJob: (jobId: string, signal: AbortSignal) => Promise<JobPayload>;
  onUpdate: (payload: JobPayload) => void | Promise<void>;
  signal: AbortSignal;
  timeoutMs?: number;
  pollIntervalMs?: number;
  maxConsecutiveFailures?: number;
  onTransientError?: (error: unknown, failureCount: number) => void;
}): Promise<JobPayload> {
  const {
    jobId,
    getJob,
    onUpdate,
    signal,
    timeoutMs = PROCESSING_JOB_TIMEOUT_MS,
    pollIntervalMs = 180,
    maxConsecutiveFailures = 3,
    onTransientError,
  } = options;
  const deadline = Date.now() + timeoutMs;
  let consecutiveFailures = 0;

  while (true) {
    throwIfAborted(signal);
    if (Date.now() >= deadline) {
      throw new OperationTimeoutError("processing job", timeoutMs);
    }
    let payload: JobPayload;
    try {
      payload = await getJob(jobId, signal);
      consecutiveFailures = 0;
    } catch (error) {
      throwIfAborted(signal);
      consecutiveFailures += 1;
      if (consecutiveFailures >= maxConsecutiveFailures) {
        throw new SidecarConnectionError(error);
      }
      onTransientError?.(error, consecutiveFailures);
      await delay(200 * 2 ** (consecutiveFailures - 1), signal);
      continue;
    }
    throwIfAborted(signal);
    await onUpdate(payload);
    if (payload.job.done) return payload;
    await delay(pollIntervalMs, signal);
  }
}

export async function monitorRuntimeStatus(options: {
  getStatus: (signal: AbortSignal) => Promise<RuntimeState>;
  onUpdate: (status: RuntimeState) => void;
  signal: AbortSignal;
  pollIntervalMs?: number;
  maxConsecutiveFailures?: number;
}): Promise<void> {
  const {
    getStatus,
    onUpdate,
    signal,
    pollIntervalMs = 220,
    maxConsecutiveFailures = 3,
  } = options;
  let consecutiveFailures = 0;

  while (true) {
    throwIfAborted(signal);
    try {
      const status = await getStatus(signal);
      consecutiveFailures = 0;
      onUpdate(status);
    } catch (error) {
      throwIfAborted(signal);
      consecutiveFailures += 1;
      if (consecutiveFailures >= maxConsecutiveFailures) {
        throw new SidecarConnectionError(error);
      }
    }
    await delay(pollIntervalMs, signal);
  }
}
