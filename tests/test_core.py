from pathlib import Path

from aura.compiler import PromptCompiler
from aura.history import HistoryStore
from aura.models import CompileRequest, Session, Skill
from aura.modes import ModeRegistry
from aura.providers.llm import RuleBasedCompiler
from aura.providers.stt.model_cache import (
    resolve_modelscope_alias,
    resolve_modelscope_model,
)


def test_modes_load():
    modes = ModeRegistry(Path("modes")).load()
    ids = {mode.id for mode in modes.all()}
    names = {mode.name for mode in modes.all()}
    assert {"concise", "coding_agent", "professional"}.issubset(ids)
    assert {"简洁模式", "标准模式", "专业模式"}.issubset(names)
    assert modes.get("missing-mode").id in ids


def test_rule_based_compiler_adds_safety_boundary_for_risky_text():
    mode = ModeRegistry(Path("modes")).load().get("codex")
    compiler = PromptCompiler(RuleBasedCompiler())
    result = compiler.compile(
        CompileRequest(mode=mode, current_transcript="帮我删除旧文件并提交 git")
    )
    assert "安全边界" in result
    assert "不要删除文件" in result


def test_compile_request_includes_previous_context():
    mode = ModeRegistry(Path("modes")).load().get("codex")
    request = CompileRequest(
        mode=mode,
        current_transcript="补充一下，先不要改",
        previous_compiled_text="请优化登录页。",
        previous_transcripts=["帮我优化登录页"],
    )
    messages = request.as_messages()
    assert "上一版 AI 编译结果" in messages[-1]["content"]
    assert "整合后的完整 prompt" in messages[-1]["content"]


def test_compile_request_includes_enabled_skills():
    mode = ModeRegistry(Path("modes")).load().get("codex")
    request = CompileRequest(
        mode=mode,
        current_transcript="帮我整理成专利交底书",
        skills=[
            Skill(
                id="patent",
                name="patent-disclosure-writer",
                description="生成专利申请技术交底书",
                example="当用户描述创新点时调用该 Skill。",
                category="Writing",
                enabled=True,
            )
        ],
    )
    messages = request.as_messages()
    assert "可用 Skill 匹配规则" in messages[0]["content"]
    assert "patent-disclosure-writer" in messages[-1]["content"]
    assert "生成专利申请技术交底书" in messages[-1]["content"]
    assert "当用户描述创新点时调用该 Skill。" in messages[-1]["content"]


def test_rule_based_compiler_references_matching_skill_only():
    mode = ModeRegistry(Path("modes")).load().get("coding_agent")
    skill = Skill(
        id="patent",
        name="patent-disclosure-writer",
        description="生成中国专利申请技术交底书",
        example="当用户提出专利、创新方案或技术交底书需求时使用。",
        category="Writing",
        enabled=True,
    )
    compiler = PromptCompiler(RuleBasedCompiler())

    matched = compiler.compile(
        CompileRequest(mode=mode, current_transcript="把这个创新方案整理成专利技术交底书", skills=[skill])
    )
    unmatched = compiler.compile(
        CompileRequest(mode=mode, current_transcript="帮我写一封会议邀请邮件", skills=[skill])
    )

    assert "patent-disclosure-writer" in matched
    assert "patent-disclosure-writer" not in unmatched


def test_history_store_roundtrip(tmp_path):
    history = HistoryStore(tmp_path / "history.sqlite")
    session = Session(id="s1", mode_id="codex")
    session.add_turn(
        raw_transcript="帮我优化登录页",
        compiled_text="请优化登录页。",
        stt_provider="test",
        llm_provider="rule_based",
    )
    history.save_session(session)
    recent = history.recent_sessions()
    assert len(recent) == 1
    assert recent[0]["id"] == "s1"


def test_model_cache_prefers_local_snapshots(tmp_path):
    modelscope_snapshot = (
        tmp_path
        / "modelscope"
        / "models"
        / "iic--SenseVoiceSmall"
        / "snapshots"
        / "master"
    )
    modelscope_snapshot.mkdir(parents=True)
    (modelscope_snapshot / "configuration.json").write_text("{}", encoding="utf-8")

    vad_snapshot = (
        tmp_path
        / "modelscope"
        / "models"
        / "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch"
        / "snapshots"
        / "master"
    )
    vad_snapshot.mkdir(parents=True)
    (vad_snapshot / "configuration.json").write_text("{}", encoding="utf-8")

    assert resolve_modelscope_model(tmp_path, "iic/SenseVoiceSmall") == str(modelscope_snapshot)
    assert resolve_modelscope_alias(tmp_path, "fsmn-vad") == str(vad_snapshot)
