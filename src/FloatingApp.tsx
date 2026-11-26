import { invoke } from "@tauri-apps/api/core";
import { useCallback, useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { Check, Copy, Undo2, LoaderCircle, Mic, X } from "lucide-react";
import { api, AppState, ensureSidecar, insertText, copyText } from "./api";

import { targets } from "./VoicePreferences";
import { pollProcessingJob } from "./workflows/sidecar";

function Waveform({ volume, active }: { volume: number; active: boolean }) {
  const level = Math.max(0.08, Math.min(1, volume / 1500));
  return (
    <div
      className={`float-wave ${active ? "active" : ""}`}
      aria-label={active ? "正在录音" : "音量"}
    >
      {Array.from({ length: 10 }, (_, index) => {
        const shape = 0.35 + Math.abs(Math.sin(index * 1.7)) * 0.65;
        return (
          <i
            key={index}
            style={{
              height: `${2 + (active ? level * shape * 18 : 0)}px`,
              animationDelay: `${-index * 55}ms`,
            }}
          />
        );
      })}
    </div>
  );
}

function DraftText({
  text,
  inline = false,
}: {
  text: string;
  inline?: boolean;
}) {
  const node = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (node.current) node.current.scrollLeft = node.current.scrollWidth;
  }, [text]);
  return (
    <span
      ref={node}
      className={inline ? "inline-draft" : "draft-line"}
      title={text}
    >
      {text}
    </span>
  );
}

export function InlinePreview() {
  const [text, setText] = useState("");
  useEffect(() => {
    const p = listen<string>("aura://draft", (e) => setText(e.payload));
    return () => {
      void p.then((stop) => stop());
    };
  }, []);
  return <DraftText text={text} inline />;
}

export function RecordingBar() {
  const [state, setState] = useState<AppState | null>(null);
  const settingsRef = useRef<AppState["settings"] | null>(null);
  const [phase, setPhase] = useState<
    "idle" | "starting" | "recording" | "processing" | "recover" | "done" | "error"
  >("idle");
  const busy = useRef(false);
  const dismissed = useRef(false);
  const [message, setMessage] = useState("右 Alt 开始");
  const recording = useRef(false);
  const queuedFinish = useRef(false);
  const starting = useRef(false);
  const [mode, setMode] = useState<"dictate" | "edit" | "translate">("dictate");
  const [language, setLanguage] = useState("en");
  const [recordId, setRecordId] = useState("");
  const [preview, setPreview] = useState("");
  const [inline, setInline] = useState(false);
  const [placement, setPlacement] = useState<"input" | "bar">("bar");
  const session = useRef(0);
  const captionQueue = useRef(Promise.resolve(false));
  const caption = useCallback((text: string) => {
    const next = captionQueue.current
      .then(() => invoke<boolean>("inline_preview", { text }))
      .catch(() => false);
    captionQueue.current = next;
    return next;
  }, []);
  const selection = useRef("");
  const pending = useRef("");
  const hideTimer = useRef<number | undefined>(undefined);
  const clearHideTimer = () => window.clearTimeout(hideTimer.current);
  useEffect(() => clearHideTimer, []);

  const complete = useCallback((label: string) => {
    setMessage(label);
    setPhase("done");
    clearHideTimer();
    hideTimer.current = window.setTimeout(
      () => {
        void invoke("set_bar_visible", { visible: false });
        setPhase("idle");
      },
      label === "撤销改写" ? 3000 : 650,
    );
  }, []);

  const refresh = useCallback(async () => {
    const next = await api.state();
    settingsRef.current = next.settings;
    setState(next);
    return next;
  }, []);

  useEffect(() => {
    void ensureSidecar()
      .then(refresh)
      .catch((error) => {
        setPhase("error");
        setMessage(String(error));
      });
  }, [refresh]);

  useEffect(() => {
    if (phase !== "recording") return;
    const id = window.setInterval(
      () =>
        void api
          .status(undefined, 1)
          .then((runtime) => {
            setState((current) =>
              current ? { ...current, runtime } : current,
            );
          })
          .catch(() => undefined),
      90,
    );
    return () => window.clearInterval(id);
  }, [phase]);

  useEffect(() => {
    if (phase !== "recording" || !recordId) return;
    const controller = new AbortController();
    const current = session.current;
    let timer = 0;
    let accumulated = "";
    const streaming = state?.settings.stt_provider === "doubao-asr";
    async function fetchChunk() {
      try {
        const { text, snapshot } = await api.previewRecording(
          recordId,
          controller.signal,
        );
        if (
          controller.signal.aborted ||
          session.current !== current ||
          !recording.current
        )
          return;
        if (snapshot) {
          setPreview(text);
        } else if (text.trim()) {
          accumulated = (accumulated + " " + text.trim()).trim();
          setPreview(accumulated);
        }
      } catch {
        /* Final recognition uses the entire recording even if a partial request fails. */
      }
      if (!controller.signal.aborted)
        timer = window.setTimeout(() => void fetchChunk(), streaming ? 120 : 550);
    }
    timer = window.setTimeout(() => void fetchChunk(), streaming ? 120 : 1500);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [phase, recordId, state?.settings.stt_provider]);

  useEffect(() => {
    if (
      !preview ||
      phase !== "recording" ||
      placement !== "input" ||
      mode === "edit"
    )
      return;
    let stopped = false;
    let timer = 0;
    async function position() {
      if (stopped || !recording.current) return;
      const shown = await caption(preview);
      if (!stopped) {
        setInline(shown);
        timer = window.setTimeout(() => void position(), 420);
      }
    }
    void position();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [preview, phase, placement, mode, caption]);

  const start = useCallback(
    async (action: "dictate" | "translate" = "dictate") => {
      if (recording.current || busy.current) return;
      busy.current = true;
      try {
        // Capture a possible selection for the default Right Alt action too.
        // With a selection it becomes rewrite, without one it remains dictation.
        const captureSelection = action !== "translate";
        starting.current = true;
        queuedFinish.current = false;
        session.current++;
        dismissed.current = false;
        clearHideTimer();
        const settings = settingsRef.current;
        setMode(action);
        setPlacement(settings?.preview_mode ?? "bar");
        setPreview("");
        setInline(false);
        setRecordId("");
        clearHideTimer();
        pending.current = "";
        selection.current = "";
        setPhase("starting");
        setMessage("正在启动录音");
        const [target, started] = await Promise.allSettled([
          invoke<string | null>("set_bar_visible", {
            visible: true,
            editing: captureSelection,
            wide: settings?.preview_mode !== "input",
            translating: action === "translate",
          }),
          settings ? api.startRecording() : ensureSidecar().then(api.startRecording),
        ]);
        if (dismissed.current) {
          if (started.status === "fulfilled") await api.cancelRecording();
          await invoke("set_bar_visible", { visible: false });
          return;
        }
        if (started.status === "rejected") throw started.reason;
        const payload = started.value;
        selection.current = target.status === "fulfilled" ? target.value || "" : "";
        settingsRef.current = payload.state.settings;
        setLanguage(payload.state.settings.translation_language ?? "en");
        setPlacement(payload.state.settings.preview_mode ?? "bar");
        const effectiveMode =
          action === "translate"
            ? "translate"
            : selection.current
              ? "edit"
              : "dictate";
        setMode(effectiveMode);
        setMessage(effectiveMode === "edit" ? "说出修改要求" : "正在聆听");
        recording.current = true;
        setState(payload.state);
        setRecordId(payload.recording_id);
        setPhase("recording");
      } catch (error) {
        recording.current = false;
        setPhase("error");
        setMessage(error instanceof Error ? error.message : String(error));
      } finally {
        starting.current = false;
        busy.current = false;
      }
    },
    [],
  );

  const finish = useCallback(async () => {
    if (!recording.current || busy.current) return;
    busy.current = true;
    recording.current = false;
    setPhase("processing");
    setMessage("正在转写…");
    try {
      void caption("");
      const stopped = await api.stopRecording(
        true,
        selection.current,
        mode === "translate" ? language : "",
      );
      setState(stopped.state);
      const payload = await pollProcessingJob({
        jobId: stopped.job.id,
        getJob: api.job,
        onUpdate: (result) => setState(result.state),
        signal: new AbortController().signal,
        pollIntervalMs: 45,
      });
      if (dismissed.current) return;
      if (payload.job.error) throw new Error(payload.job.error);
      const output = payload.job.compiled;
      if (!output.trim()) throw new Error("没有可输入的文字");
      pending.current = output;
      const copied = await copyText(output).then(() => true, () => false);
      if (dismissed.current) return;
      if (await insertText(output).catch(() => false)) {
        if (!dismissed.current)
          complete(selection.current ? "撤销改写" : "已输入");
      } else if (copied && !dismissed.current) {
        complete("已复制");
      } else if (!dismissed.current) {
        setPhase("recover");
        setMessage("复制失败，点击重试");
      }
    } catch (error) {
      setPhase("error");
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      busy.current = false;
    }
  }, [complete, mode, language, caption]);

  useEffect(() => {
    if (phase === "recording" && queuedFinish.current) {
      queuedFinish.current = false;
      void finish();
    }
  }, [phase, finish]);

  const cancel = useCallback(async () => {
    clearHideTimer();
    dismissed.current = true;
    session.current++;
    queuedFinish.current = false;
    void caption("");
    await invoke("set_bar_visible", { visible: false });
    selection.current = "";
    if (!busy.current && recording.current) {
      busy.current = true;
      try {
        await api.cancelRecording();
      } finally {
        recording.current = false;
        busy.current = false;
      }
    }
    setPhase("idle");
    setMessage("右 Alt 开始");
  }, []);

  const toggle = useCallback(
    (action: "dictate" | "translate" = "dictate") => {
      if (starting.current) {
        queuedFinish.current = true;
        return;
      }
      return recording.current ? finish() : start(action);
    },
    [finish, start],
  );

  useEffect(() => {
    let disposed = false;
    const disposers: Array<() => void> = [];
    const keep = (fn: () => void) => (disposed ? fn() : disposers.push(fn));
    void listen("aura://record-toggle", () => void toggle()).then(keep);
    void listen("aura://record-translate", () => void toggle("translate")).then(
      keep,
    );
    return () => {
      disposed = true;
      disposers.forEach((fn) => fn());
    };
  }, [finish, start, toggle]);

  const copyPending = async () => {
    try {
      await copyText(pending.current);
      complete("已复制");
    } catch {
      setMessage("复制失败，点击重试");
    }
  };

  const undo = async () => {
    if (busy.current) return;
    busy.current = true;
    clearHideTimer();
    const restored = await invoke<boolean>("undo_edit").catch(() => false);
    busy.current = false;
    if (!dismissed.current) complete(restored ? "已撤销" : "选区已变");
  };
  const canUndo = phase === "done" && message === "撤销改写";
  const active = phase === "recording";
  let action = toggle;
  let actionLabel = active
    ? "完成听写"
    : `开始听写（${state?.settings.voice_shortcuts?.dictate ?? "RightAlt"}）`;
  if (phase === "recover") {
    action = copyPending;
    actionLabel = "复制结果";
  } else if (canUndo) {
    action = undo;
    actionLabel = "撤销改写";
  }
  return (
    <div className="voice-shell">
      {mode === "translate" && (
        <div className="translation-strip">
          <span>文 A</span>翻译为{" "}
          <select
            aria-label="本次目标语言"
            disabled={phase !== "recording"}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            {Object.entries(targets).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </div>
      )}
      <main className={`recording-float ${phase}`}>
        <button
          className="float-action cancel"
          title="取消并隐藏"
          aria-label="取消并隐藏"
          onClick={() => void cancel()}
        >
          <X size={15} />
        </button>
        <button
          className="float-wave-button"
          title={message}
          aria-label={message}
          disabled={phase === "processing"}
          onClick={() => void action()}
        >
          {phase === "processing" ? (
            <span className="float-status"><LoaderCircle size={13} className="float-spinner" />处理中</span>
          ) : phase === "starting" ? (
            <span className="float-status"><LoaderCircle size={13} className="float-spinner" />启动中</span>
          ) : phase === "recover" ? (
            <small>点此复制</small>
          ) : phase === "error" ? (
            <small>
              {/volume is too low|recordingTooQuiet|No audio/i.test(message)
                ? "未听清"
                : /too short/i.test(message)
                  ? "录音太短"
                  : message.includes("选中")
                    ? "先选文字"
                    : selection.current
                      ? "改写失败"
                      : "转写失败"}
            </small>
          ) : phase === "done" ? (
            <small>{message}</small>
          ) : active && preview && !inline ? (
            <DraftText text={preview} />
          ) : (
            <Waveform volume={state?.runtime.volume || 0} active={active} />
          )}
        </button>
        <button
          className="float-action confirm"
          disabled={phase === "processing"}
          title={actionLabel}
          aria-label={actionLabel}
          onClick={() => void action()}
        >
          {canUndo ? (
            <Undo2 size={14} />
          ) : phase === "recover" ? (
            <Copy size={14} />
          ) : active ? (
            <Check size={16} />
          ) : (
            <Mic size={14} />
          )}
        </button>
      </main>
    </div>
  );
}
