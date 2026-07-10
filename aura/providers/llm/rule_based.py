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
        lines = [
            "请完成以下任务：",
            "",
            "目标：",
            f"- {transcript}",
        ]
        if previous:
            lines.extend(["", "已有上下文：", previous])
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

