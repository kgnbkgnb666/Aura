import { invoke } from "@tauri-apps/api/core";
import { useEffect, useRef, useState } from "react";
import { BookOpen, Download, Pencil, Plus, Upload, X } from "lucide-react";
import { api, type Settings, type RewriteSkill } from "./api";

export const targets = {
  en: "英语",
  zh: "中文",
  ja: "日语",
  ko: "韩语",
  fr: "法语",
  de: "德语",
  es: "西班牙语",
};
export const defaultKeys = {
  dictate: "RightAlt",
  translate: "RightAlt+RightShift",
};
type Action = keyof typeof defaultKeys;
type Save = (value: Partial<Settings>) => void;
const keyLabel = (k: string) =>
  k.replace(/Right/g, "Right ").replace(/\+/g, " + ");

const capturedKey = (event: KeyboardEvent) => {
  const code = event.code;
  if (code === "AltRight") return "RightAlt";
  if (code === "ControlRight") return "RightCtrl";
  if (code === "ShiftRight") return "RightShift";
  if (code === "Space") return "Space";
  if (/^F(?:[1-9]|1[0-2])$/.test(code)) return code;
  return "";
};

function ShortcutCapture({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [armed, setArmed] = useState(false);
  const [draft, setDraft] = useState(value);
  const held = useRef(new Set<string>());
  const timer = useRef<number>();
  const mouseCommitted = useRef(false);
  useEffect(() => () => {
    window.clearTimeout(timer.current);
    void invoke("set_shortcut_capture", { active: false });
  }, []);
  useEffect(() => setDraft(value), [value]);
  const stop = () => {
    window.clearTimeout(timer.current);
    held.current.clear();
    setArmed(false);
    void invoke("set_shortcut_capture", { active: false });
  };
  const commit = (next: string) => {
    if (!next) return;
    setDraft(next);
    onChange(next);
    stop();
  };
  const arm = () => {
    setArmed(true);
    setDraft("");
    void invoke("set_shortcut_capture", { active: true });
  };
  return (
    <button
      type="button"
      className={`shortcut-capture${armed ? " armed" : ""}`}
      aria-label="语音快捷键"
      onClick={() => {
        if (mouseCommitted.current) {
          mouseCommitted.current = false;
          return;
        }
        armed ? stop() : arm();
      }}
      onBlur={() => armed && stop()}
      onMouseDown={(event) => {
        if (!armed || event.button > 2) return;
        event.preventDefault();
        event.stopPropagation();
        mouseCommitted.current = true;
        commit(event.button === 0 ? "MouseLeft" : event.button === 1 ? "MouseMiddle" : "MouseRight");
      }}
      onKeyDown={(event) => {
        if (!armed) return;
        event.preventDefault();
        event.stopPropagation();
        const key = capturedKey(event.nativeEvent);
        if (!key) return;
        held.current.add(key);
        const order = ["RightAlt", "RightCtrl", "RightShift", "Space"];
        const keys = [...held.current].sort((a, b) => order.indexOf(a) - order.indexOf(b));
        const next = keys.join("+");
        setDraft(next);
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => commit(next), 180);
      }}
    >
      {armed ? (draft ? keyLabel(draft) : "按下键盘快捷或鼠标按钮") : keyLabel(value)}
    </button>
  );
}

export function VoicePreferences({
  settings,
  save,
}: {
  settings: Settings;
  save: Save;
}) {
  const configured = settings.voice_shortcuts ?? defaultKeys;
  const keys = {
    dictate: configured.dictate ?? defaultKeys.dictate,
    translate: configured.translate ?? defaultKeys.translate,
  };
  return (
    <>
      {(Object.keys(keys) as Action[]).map((action) => (
        <div className="pref-row" key={action}>
          <div>
            <strong>
              {({ dictate: "语音输入", translate: "语音翻译" }[action])}
            </strong>
            <small>
              {({ dictate: "轻按开始，再按一次完成。", translate: "说完后将译文输入到光标处。" }[action])}
            </small>
          </div>
          <ShortcutCapture
            value={keys[action]}
            onChange={(value) => save({ voice_shortcuts: { ...keys, [action]: value } })}
          />
        </div>
      ))}
      <div className="pref-row">
        <strong>翻译目标语言</strong>
        <select
          aria-label="翻译目标语言"
          value={settings.translation_language ?? "en"}
          onChange={(e) => save({ translation_language: e.target.value })}
        >
          {Object.entries(targets).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>
      <h3 className="preview-label">语音文字预览</h3>
      <div
        className="preview-choices"
        role="radiogroup"
        aria-label="语音文字预览"
      >
        {(["bar", "input"] as const).map((mode) => (
          <button
            type="button"
            role="radio"
            aria-checked={(settings.preview_mode ?? "bar") === mode}
            key={mode}
            onClick={() => save({ preview_mode: mode })}
          >
            <div className="preview-example" aria-hidden="true">
              <span>{mode === "input" ? "明天下午开会" : "▏"}</span>
              <b>{mode === "bar" ? "明天下午开会  〽" : "〽"}</b>
            </div>
            <strong>{mode === "bar" ? "在语音条中" : "在输入框内"}</strong>
            <small>
              {mode === "bar"
                ? "录音时看字幕，完成后写入"
                : "在光标处预览，完成后写入"}
            </small>
          </button>
        ))}
      </div>
      <p className="preview-footnote">
        预览按短段更新，结束后使用完整录音校正。云端识别会额外转写预览片段。
      </p>
    </>
  );
}

const blank: RewriteSkill = {
  name: "",
  intent: "",
  instructions: "",
  enabled: true,
};
export function RewriteSkills({
  settings,
  save,
}: {
  settings: Settings;
  save: (skills: RewriteSkill[]) => Promise<void>;
}) {
  const skills = settings.rewrite_skills ?? [];
  const [draft, setDraft] = useState<RewriteSkill | null>(null);
  const [index, setIndex] = useState(-1);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const persist = async (items: RewriteSkill[]) => {
    await save(items);
    setError("");
  };
  const fail = (e: unknown) =>
    setError(String(e instanceof Error ? e.message : e));
  const editor = draft && (
    <form
      key={index < 0 ? "skill-new" : `skill-edit-${index}`}
      className="skill-editor"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          const next = [...skills];
          next[index < 0 ? next.length : index] = draft;
          await persist(next);
          setDraft(null);
        } catch (e) {
          fail(e);
        }
      }}
    >
      <h3>{index >= 0 ? "编辑 Skill" : "新建 Skill"}</h3>
      {(["name", "intent", "instructions"] as const).map((k) => (
        <label key={k}>
          {
            { name: "名称", intent: "何时使用", instructions: "改写指令" }[
              k
            ]
          }
          <textarea
            required
            rows={k === "instructions" ? 4 : 1}
            maxLength={{ name: 64, intent: 500, instructions: 20000 }[k]}
            value={draft[k]}
            onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
          />
        </label>
      ))}
      <div>
        <button type="button" onClick={() => setDraft(null)}>
          取消
        </button>{" "}
        <button className="primary">保存</button>
      </div>
    </form>
  );
  return (
    <>
      <div className="skill-tools">
        <button
          className="primary"
          onClick={() => {
            setIndex(-1);
            setDraft({ ...blank });
            setError("");
          }}
        >
          <Plus size={14} />
          新建
        </button>
        <button onClick={() => file.current?.click()}>
          <Upload size={14} />
          导入
        </button>
        <button
          onClick={() => {
            void invoke("export_rewrite_skills", { skills }).catch(fail);
          }}
        >
          <Download size={14} />
          导出 JSON
        </button>
      </div>
      <input
        ref={file}
        type="file"
        hidden
        accept=".json,.md"
        onChange={async (e) => {
          const f = e.currentTarget.files?.[0];
          e.currentTarget.value = "";
          if (!f) return;
          try {
            if (f.size > 512 * 1024) throw new Error("导入文件不能超过 512 KB");
            const { skills: add } = await api.importRewriteSkills(
              f.name,
              await f.text(),
            );
            const merged = [...skills];
            for (const s of add) {
              const existing = merged.find(
                (v) => v.name.toLowerCase() === s.name.toLowerCase(),
              );
              if (!existing) merged.push(s);
              else if (JSON.stringify(existing) !== JSON.stringify(s))
                throw new Error("同名 Skill 已存在：" + s.name);
            }
            await persist(merged);
          } catch (e) {
            fail(e);
          }
        }}
      />
      {error && (
        <p role="alert" className="pref-alert">
          {error}
        </p>
      )}
      {index < 0 && editor}
      {skills.map((s, i) => (
        <section className="skill-item" key={s.name}>
          <div>
            <BookOpen size={16} />
            <strong>{s.name}</strong>
          </div>
          <p>{s.intent}</p>
          <footer>
            <label>
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={() =>
                  void persist(
                    skills.map((v, n) =>
                      n === i ? { ...v, enabled: !v.enabled } : v,
                    ),
                  ).catch(fail)
                }
              />
              启用
            </label>
            <button
              aria-label={"编辑 " + s.name}
              aria-expanded={index === i && draft !== null}
              onClick={() => {
                setError("");
                if (index === i && draft) {
                  setDraft(null);
                  return;
                }
                setIndex(i);
                setDraft({ ...s });
              }}
            >
              <Pencil size={14} />
            </button>
            <button
              aria-label={"删除 " + s.name}
              onClick={() => {
                if (window.confirm("删除 " + s.name + "？"))
                  void persist(skills.filter((_, n) => n !== i))
                    .then(() => setDraft(null))
                    .catch(fail);
              }}
            >
              <X size={14} />
            </button>
          </footer>
          {index === i && editor}
        </section>
      ))}
    </>
  );
}
