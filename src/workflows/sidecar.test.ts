import { describe, expect, it, vi } from "vitest";
import type { AppState, ProcessingJob } from "../api";
import { OperationTimeoutError } from "./async";
import { monitorRuntimeStatus, pollProcessingJob, SidecarConnectionError, waitForTranscriber } from "./sidecar";

function state(status: AppState["service"]["transcriber_status"]): AppState {
  return {
    service: {
      transcriber_ready: status === "ready",
      transcriber_status: status,
      transcriber_progress: status === "ready" ? 100 : 20,
      transcriber_error: status === "error" ? "model failed" : "",
    },
    runtime: { status: status === "error" ? "model failed" : status },
  } as AppState;
}

function job(done: boolean): ProcessingJob {
  return {
    id: "job-1",
    phase: done ? "done" : "transcribing",
    done,
    error: "",
    transcript: done ? "hello" : "",
    compiled: done ? "result" : "",
    recording: { wav_path: "", duration_seconds: 1, average_volume: 1, max_volume: 1 },
  };
}

describe("sidecar workflows", () => {
  it("warms up and waits until the transcriber is ready", async () => {
    const warmup = vi.fn(async () => undefined);
    const updates = vi.fn();
    const result = await waitForTranscriber({
      initialState: state("not_loaded"),
      warmup,
      getState: async () => state("ready"),
      onState: updates,
      signal: new AbortController().signal,
      pollIntervalMs: 0,
    });

    expect(result.service.transcriber_ready).toBe(true);
    expect(warmup).toHaveBeenCalledOnce();
    expect(updates).toHaveBeenCalledOnce();
  });

  it("surfaces a transcriber error", async () => {
    await expect(waitForTranscriber({
      initialState: state("loading"),
      warmup: async () => undefined,
      getState: async () => state("error"),
      onState: () => undefined,
      signal: new AbortController().signal,
      pollIntervalMs: 0,
    })).rejects.toThrow("model failed");
  });

  it("times out a stalled transcriber startup", async () => {
    await expect(waitForTranscriber({
      initialState: state("loading"),
      warmup: async () => undefined,
      getState: async () => state("loading"),
      onState: () => undefined,
      signal: new AbortController().signal,
      timeoutMs: 0,
    })).rejects.toBeInstanceOf(OperationTimeoutError);
  });

  it("polls a processing job to completion", async () => {
    const getJob = vi.fn()
      .mockResolvedValueOnce({ job: job(false), state: state("ready") })
      .mockResolvedValueOnce({ job: job(true), state: state("ready") });
    const onUpdate = vi.fn();

    const result = await pollProcessingJob({
      jobId: "job-1",
      getJob,
      onUpdate,
      signal: new AbortController().signal,
      pollIntervalMs: 0,
    });

    expect(result.job.done).toBe(true);
    expect(getJob).toHaveBeenCalledTimes(2);
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it("recovers from two transient job polling failures", async () => {
    const getJob = vi.fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce({ job: job(true), state: state("ready") });
    const result = await pollProcessingJob({
      jobId: "job-1",
      getJob,
      onUpdate: () => undefined,
      signal: new AbortController().signal,
      pollIntervalMs: 0,
    });
    expect(result.job.done).toBe(true);
    expect(getJob).toHaveBeenCalledTimes(3);
  });

  it("reports a dead sidecar after three consecutive polling failures", async () => {
    await expect(pollProcessingJob({
      jobId: "job-1",
      getJob: async () => { throw new TypeError("offline"); },
      onUpdate: () => undefined,
      signal: new AbortController().signal,
      pollIntervalMs: 0,
    })).rejects.toBeInstanceOf(SidecarConnectionError);
  });

  it("reports a dead sidecar after three recording-status failures", async () => {
    await expect(monitorRuntimeStatus({
      getStatus: async () => { throw new TypeError("offline"); },
      onUpdate: () => undefined,
      signal: new AbortController().signal,
      pollIntervalMs: 0,
    })).rejects.toBeInstanceOf(SidecarConnectionError);
  });
});
