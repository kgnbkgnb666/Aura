import { describe, expect, it } from "vitest";
import { delay, LatestOperation, OperationTimeoutError, retryWithBackoff, withTimeout } from "./async";

describe("async workflow helpers", () => {
  it("returns a completed operation before its deadline", async () => {
    await expect(withTimeout(async () => "ok", 50, "test operation")).resolves.toBe("ok");
  });

  it("rejects an operation that exceeds its deadline", async () => {
    await expect(
      withTimeout((signal) => delay(100, signal), 5, "test operation"),
    ).rejects.toBeInstanceOf(OperationTimeoutError);
  });

  it("forwards caller cancellation", async () => {
    const controller = new AbortController();
    const pending = withTimeout((signal) => delay(100, signal), 500, "test operation", controller.signal);
    controller.abort(new Error("cancelled by caller"));
    await expect(pending).rejects.toThrow("cancelled by caller");
  });

  it("retries transient failures with exponential backoff", async () => {
    let attempts = 0;
    const result = await retryWithBackoff(async () => {
      attempts += 1;
      if (attempts < 3) throw new TypeError("offline");
      return "ready";
    }, { maxAttempts: 3, baseDelayMs: 0 });
    expect(result).toBe("ready");
    expect(attempts).toBe(3);
  });

  it("keeps only the latest debounced operation", async () => {
    const runner = new LatestOperation();
    const first = runner.run(async () => "first", 20);
    const second = runner.run(async () => "second", 0);
    await expect(first).resolves.toEqual({ status: "superseded" });
    await expect(second).resolves.toEqual({ status: "completed", value: "second" });
  });
});
