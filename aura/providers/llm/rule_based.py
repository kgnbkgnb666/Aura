from __future__ import annotations

import re
from typing import Iterable


RISK_WORDS = [
    "删除",
    "删掉",
    "drop",
    "迁移",
    "数据库",
    "支付",
    "权限",
    "认证",
    "登录",
    "git commit",
    "提交",
    "push",
    "安装依赖",
]

SKILL_STOP_WORDS = {
    "skill",
    "使用",
    "用户",
    "任务",
    "需求",
    "处理",
    "生成",
    "调用",
    "用于",
    "进行",
    "相关",
    "when",
    "user",
    "uses",
    "use",
    "with",
    "from",
    "this",
}


def _match_tokens(value: str) -> set[str]:
    tokens = {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", value)
        if token.lower() not in SKILL_STOP_WORDS
    }
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        for size in (2, 3, 4):
            tokens.update(
                chunk[index : index + size]
                for index in range(max(0, len(chunk) - size + 1))
                if chunk[index : index + size] not in SKILL_STOP_WORDS
            )
    return tokens


def _matching_skills(user_text: str, transcript: str) -> list[str]:
    marker = "当前可使用 Skill（名称、描述、使用示例）："
    if marker not in user_text:
        return []
    section = user_text.split(marker, 1)[1].split("请参考 Skill 的使用示例", 1)[0]
    transcript_lower = transcript.lower()
    transcript_tokens = _match_tokens(transcript)
    matches: list[str] = []
    for block in re.split(r"\n\s*\n(?=\d+\. )", section.strip()):
        first_line, _, details = block.partition("\n")
        name = re.sub(r"^\d+\.\s*", "", first_line).strip()
        if not name:
            continue
        name_tokens = [token for token in re.split(r"[-_\s]+", name.lower()) if len(token) >= 3]
        exact_name_match = name.lower() in transcript_lower or any(
            token in transcript_lower for token in name_tokens
        )
        shared_tokens = transcript_tokens & _match_tokens(details)
        if exact_name_match or len(shared_tokens) >= 2 or any(len(token) >= 4 for token in shared_tokens):
            matches.append(name)
    return matches


class RuleBasedCompiler:
    """Development fallback used when no LLM key is configured."""

    name = "rule_based"

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterable[str]:
        text = self.chat(messages)
        for chunk in re.findall(r".{1,24}", text, flags=re.S):
            yield chunk

    def chat(self, messages: list[dict[str, str]]) -> str:
        user_text = messages[-1]["content"]
        transcript = user_text.split("本次原始语音转录：")[-1].strip()
        previous = ""
        if "上一版 AI 编译结果：" in user_text:
            previous = user_text.split("上一版 AI 编译结果：", 1)[1].split(
                "这次输入是对上一版", 1
            )[0].strip()

        risky = any(word.lower() in transcript.lower() for word in RISK_WORDS)
        matched_skills = _matching_skills(user_text, transcript)
        lines = [
            "请完成以下任务：",
            "",
            "目标：",
            f"- {transcript}",
        ]
        if previous:
            lines.extend(["", "已有上下文：", previous])
        if matched_skills:
            lines.extend(["", "可用能力："])
            lines.extend(
                f"- 使用 Skill `{name}`，并将上述目标与原始需求作为调用上下文。"
                for name in matched_skills
            )
        lines.extend(
            [
                "",
                "约束：",
                "- 保留用户真实意图，不要自行扩展未提到的需求。",
                "- 遵循现有项目风格，保持最小必要修改。",
                "",
                "执行要求：",
                "- 先阅读相关代码和配置，再给出修改方案。",
                "- 如果信息不足，先提出需要确认的问题。",
                "",
                "验收标准：",
                "- 输出结果清晰说明改动范围、风险和验证方式。",
            ]
        )
        if risky:
            lines.extend(
                [
                    "",
                    "安全边界：",
                    "- 在我确认前，不要删除文件、不要修改数据库、不要提交或推送 git。",
                    "- 涉及认证、权限、支付、迁移等高风险逻辑时，请先分析并等待确认。",
                ]
            )
        return "\n".join(lines)
