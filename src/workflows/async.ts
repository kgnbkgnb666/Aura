export class OperationTimeoutError extends Error {
  constructor(operation: string, timeoutMs: number) {
    super(`${operation} timed out after ${timeoutMs}ms`);
    this.name = "OperationTimeoutError";
  }
}

function abortReason(signal: AbortSignal): Error {
  return signal.reason instanceof Error
    ? signal.reason
    : new DOMException("The operation was aborted", "AbortError");
}

export function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw abortReason(signal);
}

export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  throwIfAborted(signal);
  return new Promise((resolve, reject) => {
    const timer = globalThis.setTimeout(done, ms);

    function done() {
      cleanup();
      resolve();
    }

    function cancel() {
      cleanup();
      reject(abortReason(signal as AbortSignal));
    }

    function cleanup() {
      globalThis.clearTimeout(timer);
      signal?.removeEventListener("abort", cancel);
    }

    signal?.addEventListener("abort", cancel, { once: true });
  });
}

export async function withTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  operationName: string,
  parentSignal?: AbortSignal,
): Promise<T> {
  throwIfAborted(parentSignal);
  const controller = new AbortController();
  let timedOut = false;
  const forwardAbort = () => controller.abort(parentSignal?.reason);
  parentSignal?.addEventListener("abort", forwardAbort, { once: true });
  const timer = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    return await operation(controller.signal);
  } catch (error) {
    if (timedOut) throw new OperationTimeoutError(operationName, timeoutMs);
    if (parentSignal?.aborted) throw abortReason(parentSignal);
    throw error;
  } finally {
    globalThis.clearTimeout(timer);
    parentSignal?.removeEventListener("abort", forwardAbort);
  }
}

export async function retryWithBackoff<T>(
  operation: (attempt: number) => Promise<T>,
  options: {
    maxAttempts: number;
    baseDelayMs?: number;
    signal?: AbortSignal;
    shouldRetry?: (error: unknown) => boolean;
  },
): Promise<T> {
  const {
    maxAttempts,
    baseDelayMs = 150,
    signal,
    shouldRetry = () => true,
  } = options;
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    throwIfAborted(signal);
    try {
      return await operation(attempt);
    } catch (error) {
      lastError = error;
      if (attempt >= maxAttempts || !shouldRetry(error)) throw error;
      await delay(baseDelayMs * 2 ** (attempt - 1), signal);
    }
  }
  throw lastError;
}

export type LatestOperationResult<T> =
  | { status: "completed"; value: T }
  | { status: "superseded" };

export class LatestOperation {
  private controller: AbortController | null = null;

  cancel(): void {
    this.controller?.abort();
    this.controller = null;
  }

  async run<T>(
    operation: (signal: AbortSignal) => Promise<T>,
    debounceMs = 0,
  ): Promise<LatestOperationResult<T>> {
    this.cancel();
    const controller = new AbortController();
    this.controller = controller;
    try {
      if (debounceMs > 0) await delay(debounceMs, controller.signal);
      const value = await operation(controller.signal);
      if (this.controller !== controller || controller.signal.aborted) {
        return { status: "superseded" };
      }
      return { status: "completed", value };
    } catch (error) {
      if (controller.signal.aborted) return { status: "superseded" };
      throw error;
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }
}
