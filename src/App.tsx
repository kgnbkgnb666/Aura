import {
  VoicePreferences,
  RewriteSkills,
  defaultKeys,
} from "./VoicePreferences";
import { invoke } from "@tauri-apps/api/core";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getVersion } from "@tauri-apps/api/app";
import { listen } from "@tauri-apps/api/event";
import { openUrl } from "@tauri-apps/plugin-opener";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { useTranslation } from "react-i18next";
import {
  AudioLines,
  BookOpen,
  Check,
  ChevronRight,
  Copy,
  History,
  Github,
  RefreshCw,
  Keyboard,
  Mic,
  Monitor,
  Pencil,
  Plus,
  Search,
  Settings2,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import {
  api,
  autostart,
  copyText,
  ensureSidecar,
  hideMainWindow,
  setTrayLanguage,
  type AppState,
  type DeviceInfo,
  type HistoryEntry,
  type Settings,
} from "./api";
import { setUiLanguage, UI_LANGUAGES, type UiLanguage } from "./i18n";
import "./preferences.css";

const labels = {
  installUpdate: ["更新并重启", "更新並重新啟動", "Update and restart", "更新して再起動"],
  downloadingUpdate: ["正在下载更新…", "正在下載更新…", "Downloading update…", "更新をダウンロード中…"],
  installingUpdate: ["正在安装更新…", "正在安裝更新…", "Installing update…", "更新をインストール中…"],
  updateInstallError: ["安装更新失败，请重试。", "安裝更新失敗，請重試。", "Could not install the update. Try again.", "更新をインストールできませんでした。再試行してください。"],
  inputLevel: ["输入检测", "輸入檢測", "Input check", "入力の確認"],
  skills: ["改写 Skill", "改寫 Skill", "Rewrite skills", "書き換えスキル"],
  skillsHint: [
    "在选区改写时，根据口述要求匹配已启用的 Skill。",
    "依口述要求選用改寫技能。",
    "Match enabled skills to spoken editing requests.",
    "編集の指示に応じてスキルを選択します。",
  ],
  general: ["通用设置", "一般設定", "Preferences", "一般設定"],
  history: ["听写历史", "聽寫記錄", "History", "履歴"],
  dictionary: ["个人词典", "個人詞典", "Dictionary", "ユーザー辞書"],
  service: ["模型服务", "模型服務", "Models", "モデル"],
  generalHint: [
    "调整听写、麦克风和桌面偏好。",
    "調整聽寫、麥克風和桌面偏好。",
    "Set up dictation, your microphone and desktop preferences.",
    "音声入力、マイク、表示を設定します。",
  ],
  dictate: ["语音输入", "語音輸入", "Dictate", "音声入力"],
  dictateHint: [
    "按一次开始，再按一次写入光标处。",
    "按一下開始，再按一下輸入。",
    "Press once to record and again to insert.",
    "一度押して録音、もう一度押して入力。",
  ],
  edit: ["选区改写", "選取改寫", "Edit selection", "選択範囲の編集"],
  editHint: [
    "选中文字，说出你想怎么改。",
    "選取文字，說出修改要求。",
    "Select text and say what to change.",
    "テキストを選び、変更を伝えます。",
  ],
  audio: ["音频输入", "音訊輸入", "Audio input", "音声入力デバイス"],
  preferences: ["桌面偏好", "桌面偏好", "Desktop", "デスクトップ"],
  saved: ["已保存", "已儲存", "Saved", "保存しました"],
  testing: ["正在测试…", "正在測試…", "Testing…", "テスト中…"],
  micOk: [
    "已收到麦克风声音",
    "已收到麥克風聲音",
    "Microphone signal detected",
    "音声を検出しました",
  ],
  micLow: [
    "音量偏低，请检查输入设备",
    "音量偏低，請檢查輸入裝置",
    "Low signal. Check the input device.",
    "入力音量が低いです",
  ],
  dictionaryHint: [
    "添加人名、项目名和常用术语，帮助文字模型在整理听写时写对它们。",
    "新增人名、專案名稱和術語，協助模型正確書寫。",
    "Add names and terms to guide spelling when your text model edits a transcript.",
    "名前や専門用語を登録し、文章を整える際の表記に使用します。",
  ],
  word: [
    "输入一个词，例如 WebView2",
    "輸入詞語，例如 WebView2",
    "Add a term, e.g. WebView2",
    "用語を入力（例 WebView2）",
  ],
  emptyWords: [
    "词典里还没有词条",
    "詞典尚無詞條",
    "Your dictionary is empty",
    "辞書に単語がありません",
  ],
  search: [
    "搜索原话或整理结果",
    "搜尋原話或整理結果",
    "Search transcripts and results",
    "発話や結果を検索",
  ],
  emptyHistory: [
    "没有找到听写记录",
    "沒有找到聽寫記錄",
    "No matching entries",
    "該当する履歴はありません",
  ],
  more: ["加载更多", "載入更多", "Load more", "さらに表示"],
  original: ["查看原话", "查看原話", "Show original", "元の発話を見る"],
  historyHint: [
    "找回、搜索和复制你说过的话。",
    "找回、搜尋和複製說過的話。",
    "Find and copy something you dictated.",
    "過去の音声入力を検索・コピーできます。",
  ],
  clear: [
    "清空所有历史？",
    "清空所有記錄？",
    "Clear all history?",
    "履歴をすべて消去しますか？",
  ],
  delete: [
    "删除这条记录？",
    "刪除這筆記錄？",
    "Delete this entry?",
    "この履歴を削除しますか？",
  ],
  cancel: ["取消", "取消", "Cancel", "キャンセル"],
  recognition: ["语音识别", "語音辨識", "Speech recognition", "音声認識"],
  text: [
    "文字整理与改写",
    "文字整理與改寫",
    "Text cleanup and editing",
    "文章の整形と編集",
  ],
  serviceHint: [
    "选择将录音转成文字、再整理成稿的服务。",
    "選擇轉錄與文字整理服務。",
    "Choose how to transcribe recordings and edit the resulting text.",
    "音声の文字起こしと文章の編集に使うサービスを選びます。",
  ],
  backend: ["设置", "設定", "Settings", "設定"],
  provider: ["服务提供方", "服務提供者", "Provider", "プロバイダー"],
  ready: ["已连接", "已連線", "Connected", "接続済み"],
} as const;
type Page = "skills" | "general" | "history" | "dictionary" | "service";
type Label = keyof typeof labels;
type Words = (key: Label) => string;
const pages = {
  general: Settings2,
  history: History,
  dictionary: BookOpen,
  skills: Pencil,
  service: SlidersHorizontal,
};
const message = (error: unknown) =>
  error instanceof Error ? error.message : String(error);

function Row({
  title,
  detail,
  children,
}: {
  title: string;
  detail?: string;
  children: ReactNode;
}) {
  return (
    <div className="pref-row">
      <div>
        <strong>{title}</strong>
        {detail && <small>{detail}</small>}
      </div>
      <div className="pref-control">{children}</div>
    </div>
  );
}
function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="pref-section">
      <h2>
        {icon}
        {title}
      </h2>
      {children}
    </section>
  );
}
function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      className="pref-switch"
      role="switch"
      aria-label={label}
      aria-checked={checked}
      onClick={onChange}
    >
      <i />
    </button>
  );
}

export default function App() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState<Page>("general");
  const [state, setState] = useState<AppState>();
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [version, setVersion] = useState("");
  const [updateCheck, setUpdateCheck] = useState<{
    message: string; update?: Update; pending?: boolean; progress?: number;
  }>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mic, setMic] = useState("");
  const [micTesting, setMicTesting] = useState(false);
  const [micBusy, setMicBusy] = useState(false);
  const [micSamples, setMicSamples] = useState<number[]>([]);
  useEffect(() => {
    if (!micTesting) return;
    const controller = new AbortController();
    let timer: number | undefined;
    async function sample() {
      try {
        const { mic_test_volume = 0 } = await api.status(controller.signal, 1);
        if (!controller.signal.aborted) {
          setMicSamples((values) => [...values.slice(-19), mic_test_volume]);
        }
      } catch {
        // The recording request reports microphone errors.
      }
      if (!controller.signal.aborted) timer = window.setTimeout(sample, 65);
    }
    timer = window.setTimeout(sample, 100);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [micTesting]);
  async function toggleMicTest() {
    setMicBusy(true);
    setMic(micTesting ? "正在结束测试…" : "正在打开麦克风…");
    try {
      if (micTesting) {
        await api.stopMicrophoneTest();
        setMicTesting(false);
        setMicSamples([]);
        setMic("测试已结束");
      } else {
        setMicSamples([]);
        await api.startMicrophoneTest();
        setMicTesting(true);
        setMic("请说话，观察波形是否随声音变化");
      }
    } catch (e) {
      setMic(`麦克风测试失败：${message(e)}`);
    } finally {
      setMicBusy(false);
    }
  }
  const [word, setWord] = useState("");
  const [refreshId, setRefreshId] = useState(0);
  const generation = useRef(0);
  const saving = useRef(false);
  const s = state?.settings;
  const lang =
    ({ "zh-CN": 0, "zh-TW": 1, en: 2, ja: 3 } as Record<string, number>)[
      s?.ui_language || i18n.language
    ] ?? 0;
  const w: Words = (key) => labels[key][lang];
  async function checkUpdates() {
    setUpdateCheck({ message: t("general.checking"), pending: true });
    try {
      await updateCheck?.update?.close();
      const update = await check({ timeout: 15_000 });
      setUpdateCheck(update
        ? { message: t("general.available", { version: update.version }), update }
        : { message: t("general.latest") });
    } catch {
      setUpdateCheck({ message: t("general.updateError") });
    }
  }
  async function installUpdate(update: Update) {
    let received = 0;
    let total: number | undefined;
    const downloading = w("downloadingUpdate");
    setUpdateCheck({ message: downloading, pending: true });
    try {
      await update.downloadAndInstall((event) => {
        if (event.event === "Started") total = event.data.contentLength;
        if (event.event === "Progress") {
          received += event.data.chunkLength;
          if (total) {
            setUpdateCheck({
              message: downloading, pending: true,
              progress: Math.min(100, Math.floor(received * 100 / total)),
            });
          }
        }
        if (event.event === "Finished") {
          setUpdateCheck({ message: w("installingUpdate"), pending: true });
        }
      });
    } catch {
      setUpdateCheck({ message: w("updateInstallError"), update });
    }
  }
  const refresh = useCallback(async () => {
    const id = ++generation.current;
    try {
      await ensureSidecar();
      const [next, inputs] = await Promise.all([
        api.state(),
        api.devices().catch(() => ({ devices: [] })),
      ]);
      if (id !== generation.current || saving.current) return;
      setState(next);
      setDevices(inputs.devices);
      setError("");
      setRefreshId((n) => n + 1);
    } catch (e) {
      if (id === generation.current) setError(message(e));
    }
  }, []);
  useEffect(() => {
    void refresh();
    void getVersion()
      .then(setVersion)
      .catch(() => undefined);
    const listener = listen("aura://shown", () => {
      void refresh();
    });
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") void hideMainWindow();
    };
    window.addEventListener("keydown", esc);
    return () => {
      generation.current++;
      void listener.then((stop) => stop()).catch(() => undefined);
      window.removeEventListener("keydown", esc);
    };
  }, [refresh]);
  useEffect(() => {
    if (!s) return;
    void setUiLanguage(s.ui_language);
    void setTrayLanguage(s.ui_language).catch(() => undefined);
    document.documentElement.style.colorScheme =
      s.ui_theme === "night" ? "dark" : "light";
  }, [s?.ui_language, s?.ui_theme]);

  const bindings = JSON.stringify(s?.voice_shortcuts ?? defaultKeys);
  useEffect(() => {
    if (s)
      void invoke("configure_shortcuts", {
        shortcuts: JSON.parse(bindings),
      }).catch((e) => setError(message(e)));
  }, [bindings, !!s]);

  async function run(action: () => Promise<void>) {
    if (saving.current) return;
    saving.current = true;
    generation.current++;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(message(e));
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  const general = async (values: Partial<Settings>) =>
    setState((await api.saveGeneral(values)).state);
  const speech = async (values: Partial<Settings>) =>
    setState((await api.saveSpeech(values)).state);
  const words = s?.vocabulary || [];
  const description = {
    general: "generalHint",
    history: "historyHint",
    dictionary: "dictionaryHint",
    skills: "skillsHint",
    service: "serviceHint",
  } as const;
  return (
    <main className="preferences" data-dark={s?.ui_theme === "night"}>
      <aside className="pref-sidebar">
        <div className="pref-brand">
          <span>
            <AudioLines size={21} />
          </span>
          Aura
        </div>
        <nav aria-label={w("backend")}>
          {(Object.keys(pages) as Page[]).map((id) => {
            const Icon = pages[id];
            return (
              <button
                key={id}
                aria-current={page === id ? "page" : undefined}
                onClick={() => {
                  setPage(id);
                  setError("");
                }}
              >
                <Icon size={17} />
                {w(id)}
              </button>
            );
          })}
        </nav>
        <footer>
          <span className="pref-version-dot" />
          Aura{version && " · v" + version}
          <button
            className="pref-github"
            aria-label="Aura GitHub"
            title="Aura GitHub"
            onClick={() => void openUrl("https://github.com/kgnbkgnb666/Aura").catch((e) => setError(message(e)))}
          >
            <Github size={14} />
          </button>
          <button
            className="pref-update"
            aria-label={t("general.checkUpdates")}
            title={t("general.checkUpdates")}
            disabled={!version || updateCheck?.pending}
            onClick={() => void checkUpdates()}
          >
            <RefreshCw size={14} />
          </button>
        </footer>
        {updateCheck && (
          <div className="pref-update-result" aria-live="polite">
            <span>{updateCheck.message}</span>
            {updateCheck.progress !== undefined && (
              <progress max={100} value={updateCheck.progress} aria-label={w("downloadingUpdate")} />
            )}
            {updateCheck.update && (
              <button onClick={() => {
                if (updateCheck.update) void installUpdate(updateCheck.update);
              }}>{w("installUpdate")}</button>
            )}
          </div>
        )}
      </aside>
      <article className="pref-content" key={page}>
        <header>
          <h1>{w(page)}</h1>
          <p>{w(description[page])}</p>
        </header>
        {error && (
          <div role="alert" className="pref-alert">
            {error}
            {!s && (
              <button onClick={() => void refresh()}>
                {t("common.refresh")}
              </button>
            )}
          </div>
        )}
        {!s ? (
          <p role="status">…</p>
        ) : (
          <fieldset disabled={busy} className="pref-fields">
            {page === "general" && (
              <>
                <Section
                  title={t("tabs.shortcuts")}
                  icon={<Keyboard size={16} />}
                >
                  <VoicePreferences
                    settings={s}
                    save={(v) => void run(() => general(v))}
                  />
                </Section>
                <Section title={w("audio")} icon={<Mic size={16} />}>
                  <Row title={t("speech.microphone")}>
                    <select
                      aria-label={t("speech.microphone")}
                      value={s.input_device_index ?? ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        void run(async () => {
                          await speech({
                            input_device_index: v === "" ? null : Number(v),
                          });
                          setMic("");
                        });
                      }}
                    >
                      <option value="">{t("speech.defaultInput")}</option>
                      {devices.map((d) => (
                        <option key={d.index} value={d.index}>
                          {d.name}
                        </option>
                      ))}
                    </select>
                  </Row>
                  <Row title={w("inputLevel")} detail={mic || undefined}>
                    <div className="mic-wave" role="img" aria-label="麦克风实时音量">
                      {Array.from({ length: 20 }, (_, index) => {
                        const level = micSamples[index - 20 + micSamples.length] || 0;
                        return <i key={index} style={{ height: 2 + Math.min(1, Math.sqrt(level / 1800)) * 22 }} />;
                      })}
                    </div>
                    <button
                      disabled={micBusy}
                      onClick={() => void toggleMicTest()}
                    >
                      <AudioLines size={14} />
                      {micTesting ? "结束测试" : t("speech.testMic")}
                    </button>
                  </Row>
                </Section>
                <Section title={w("preferences")} icon={<Monitor size={16} />}>
                  <Row title={t("general.style")}>
                    <select
                      aria-label={t("general.style")}
                      value={s.ui_theme}
                      onChange={(e) =>
                        void run(() =>
                          general({
                            ui_theme: e.target.value as Settings["ui_theme"],
                          }),
                        )
                      }
                    >
                      <option value="morning">{t("general.morning")}</option>
                      <option value="night">{t("general.night")}</option>
                    </select>
                  </Row>
                  <Row title={t("general.language")}>
                    <select
                      aria-label={t("general.language")}
                      value={s.ui_language}
                      onChange={(e) =>
                        void run(() =>
                          general({
                            ui_language: e.target.value as UiLanguage,
                          }),
                        )
                      }
                    >
                      {UI_LANGUAGES.map((l) => (
                        <option key={l.value} value={l.value}>
                          {l.label}
                        </option>
                      ))}
                    </select>
                  </Row>
                  <Row title={t("general.autoLaunch")}>
                    <Toggle
                      label={t("general.autoLaunch")}
                      checked={s.auto_launch}
                      onChange={() =>
                        void run(async () => {
                          const next = !s.auto_launch;
                          await (next
                            ? autostart.enable()
                            : autostart.disable());
                          try {
                            await general({ auto_launch: next });
                          } catch (e) {
                            await (next
                              ? autostart.disable()
                              : autostart.enable());
                            throw e;
                          }
                        })
                      }
                    />
                  </Row>
                </Section>
              </>
            )}
            {page === "skills" && (
              <RewriteSkills
                settings={s}
                save={async (skills) => {
                  setBusy(true);
                  try {
                    await general({ rewrite_skills: skills });
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            )}
            {page === "dictionary" && (
              <>
                <form
                  className="pref-add"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const v = word.trim();
                    if (!v || words.includes(v)) return;
                    void run(async () => {
                      await general({ vocabulary: [...words, v] });
                      setWord("");
                    });
                  }}
                >
                  <input
                    aria-label={w("word")}
                    placeholder={w("word")}
                    value={word}
                    maxLength={80}
                    onChange={(e) => setWord(e.target.value)}
                  />
                  <button
                    className="primary"
                    disabled={
                      !word.trim() ||
                      words.includes(word.trim()) ||
                      words.length >= 200
                    }
                  >
                    <Plus size={15} />
                    {t("common.add")}
                  </button>
                </form>
                <div className="pref-list">
                  {words.length === 0 ? (
                    <div className="pref-empty">
                      <BookOpen />
                      {w("emptyWords")}
                    </div>
                  ) : (
                    words.map((v) => (
                      <Row key={v} title={v}>
                        <button
                          aria-label={t("common.delete") + " " + v}
                          onClick={() =>
                            void run(() =>
                              general({
                                vocabulary: words.filter((x) => x !== v),
                              }),
                            )
                          }
                        >
                          <X size={14} />
                        </button>
                      </Row>
                    ))
                  )}
                </div>
              </>
            )}
            {page === "history" && (
              <HistoryPage
                w={w}
                state={state!}
                refreshId={refreshId}
                run={run}
                update={setState}
                toggle={() =>
                  void run(() => general({ save_history: !s.save_history }))
                }
              />
            )}
            {page === "service" && (
              <Services
                w={w}
                s={s}
                run={run}
                update={setState}
              />
            )}
          </fieldset>
        )}
      </article>
    </main>
  );
}

type Run = (action: () => Promise<void>) => Promise<void>;
function Services({
  w,
  s,
  run,
  update,
}: {
  w: Words;
  s: Settings;
  run: Run;
  update: (v: AppState) => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(s);
  const [status, setStatus] = useState("");
  const [asrKey, setAsrKey] = useState(s.asr_api_key || "");
  const keyField = "ark_api_key" as const;
  const keyLabel = "火山方舟 API Key";
  const field = (key: keyof Settings, value: string) => {
    setStatus("");
    setDraft((v) => ({ ...v, [key]: value }));
  };
  async function save(test: boolean) {
    const next = await api.saveLlm({
      ark_api_key: draft.ark_api_key || "",
      asr_api_key: asrKey.trim(),
      stt_provider: "doubao-asr",
      llm_provider: "doubao",
      llm_base_url: "https://ark.cn-beijing.volces.com/api/v3",
      llm_model: "doubao-seed-2-0-mini-260428",
    });
    update(next.state);
    setDraft(next.state.settings);
    setAsrKey(next.state.settings.asr_api_key || "");
    if (test) {
      const result = await api.testLlm();
      const asr = result.asr.ok ? w("ready") : t(result.asr.error || "llm.testFailed");
      const llm = result.llm.ok ? w("ready") : t(result.llm.error || "llm.testFailed");
      setStatus(`${w("recognition")}：${asr} · ${w("text")}：${llm}`);
    } else setStatus(w("saved"));
  }
  return (
    <>
      <Section title={w("recognition")} icon={<Mic size={16} />}>
        <Row
          title={t("speech.model")}
          detail="速度快 延迟低 适合实时语音输入"
        >
          <span className="model-fixed">豆包流式 ASR 2.0</span>
        </Row>
          <Row title="豆包 ASR API Key">
            <input
              type="password"
              autoComplete="off"
              aria-label="豆包 ASR API Key"
              value={asrKey}
              onChange={(e) => {
                setStatus("");
                setAsrKey(e.target.value);
              }}
            />
          </Row>
      </Section>
      <Section title={w("text")} icon={<SlidersHorizontal size={16} />}>
        <Row title={w("provider")}>
          <span className="model-fixed">豆包 Seed 2.0 Mini</span>
        </Row>
        <Row title={t("llm.modelName")}>
          <span className="model-fixed">doubao-seed-2-0-mini-260428</span>
        </Row>
          <Row key={keyField} title={keyLabel}
            detail={!s.ark_api_key ? "尚未配置。请填写方舟密钥后保存并测试连接。" : undefined}>
            <input
              type="password"
              aria-label={keyLabel}
              autoComplete="off"
              value={draft[keyField] || ""}
              onFocus={(e) => e.target.select()}
              onChange={(e) => field(keyField, e.target.value)}
            />
          </Row>
        <div className="pref-actions">
          <span role="status">{status}</span>
          <button onClick={() => void run(() => save(true))}>
            测试连接
          </button>
          <button
            className="primary"
            onClick={() => void run(() => save(false))}
          >
            {t("common.save")}
          </button>
        </div>
      </Section>
    </>
  );
}

function HistoryPage({
  w,
  state,
  refreshId,
  run,
  update,
  toggle,
}: {
  w: Words;
  state: AppState;
  refreshId: number;
  run: Run;
  update: (s: AppState) => void;
  toggle: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [more, setMore] = useState(false);
  const [pending, setPending] = useState("");
  const [copied, setCopied] = useState("");
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  useEffect(() => {
    const n = ++seq.current;
    setLoading(true);
    setMore(false);
    const timer = window.setTimeout(() => {
      void api
        .entries(query, 0)
        .then((r) => {
          if (seq.current === n) {
            setEntries(r.entries);
            setMore(r.more);
            setError("");
          }
        })
        .catch((e) => {
          if (seq.current === n) setError(message(e));
        })
        .finally(() => {
          if (seq.current === n) setLoading(false);
        });
    }, 100);
    return () => {
      seq.current++;
      window.clearTimeout(timer);
    };
  }, [query, revision, refreshId]);
  const copy = (id: string, text: string) =>
    void run(async () => {
      await copyText(text);
      setCopied(id);
    });
  return (
    <>
      <Row title={t("general.saveHistory")}>
        <Toggle
          label={t("general.saveHistory")}
          checked={state.settings.save_history}
          onChange={toggle}
        />
      </Row>
      <div className="pref-search">
        <Search size={16} />
        <input
          aria-label={w("search")}
          placeholder={w("search")}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPending("");
          }}
        />
        <button
          disabled={!entries.length && !query}
          onClick={() => setPending("all")}
        >
          {t("common.clear")}
        </button>
      </div>
      {pending && (
        <div className="pref-confirm" role="alert">
          {w(pending === "all" ? "clear" : "delete")}
          <button onClick={() => setPending("")}>{w("cancel")}</button>
          <button
            onClick={() =>
              void run(async () => {
                update(
                  (pending === "all"
                    ? await api.clearHistory()
                    : await api.deleteEntry(pending)
                  ).state,
                );
                setPending("");
                setRevision((v) => v + 1);
              })
            }
          >
            {t("common.delete")}
          </button>
        </div>
      )}
      {error && <div role="alert">{error}</div>}
      {loading ? (
        <p>…</p>
      ) : entries.length === 0 ? (
        <div className="pref-empty">
          <History />
          {w("emptyHistory")}
        </div>
      ) : (
        entries.map((e) => (
          <section key={e.id} className="pref-entry">
            <header>
              <time>
                {new Date(e.created_at).toLocaleString(i18n.language)}
              </time>
              <div>
                <button
                  aria-label={t("common.copy")}
                  onClick={() =>
                    copy(e.id, e.compiled_text || e.raw_transcript)
                  }
                >
                  {copied === e.id ? <Check size={15} /> : <Copy size={15} />}
                </button>
                <button
                  aria-label={t("common.delete")}
                  onClick={() => setPending(e.id)}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </header>
            <p>{e.compiled_text || e.raw_transcript}</p>
            {e.raw_transcript &&
              e.compiled_text &&
              e.compiled_text !== e.raw_transcript && (
                <details>
                  <summary>{w("original")}</summary>
                  <p>{e.raw_transcript}</p>
                </details>
              )}
          </section>
        ))
      )}
      {more && (
        <button
          onClick={() =>
            void run(async () => {
              const n = seq.current;
              const r = await api.entries(query, entries.length);
              if (n === seq.current) {
                setEntries((v) => [...v, ...r.entries]);
                setMore(r.more);
              }
            })
          }
        >
          {w("more")}
          <ChevronRight size={14} />
        </button>
      )}
    </>
  );
}
