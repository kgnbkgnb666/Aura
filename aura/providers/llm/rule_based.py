from __future__ import annotations

import json
import re
from typing import Iterable

from ...prompt_loader import load_prompt_config


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

TEMPLATES = {
    "zh-CN": {
        "intro": "请完成以下任务：", "existing": "已有需求（继续保留）：", "new": "新增或修订需求：", "goal": "目标：", "abilities": "可用能力：", "skill": "- 使用 Skill `{name}`，并将上述目标与原始需求作为调用上下文。", "constraints": "约束：", "constraint_items": ["- 保留用户真实意图，不要自行扩展未提到的需求。", "- 遵循现有项目风格，保持最小必要修改。"], "execution": "执行要求：", "execution_items": ["- 先阅读相关代码和配置，再给出修改方案。", "- 如果信息不足，先提出需要确认的问题。"], "acceptance": "验收标准：", "acceptance_item": "- 输出结果清晰说明改动范围、风险和验证方式。", "safety": "安全边界：", "safety_items": ["- 在我确认前，不要删除文件、不要修改数据库、不要提交或推送 git。", "- 涉及认证、权限、支付、迁移等高风险逻辑时，请先分析并等待确认。"],
    },
    "zh-TW": {
        "intro": "請完成以下任務：", "existing": "既有需求（繼續保留）：", "new": "新增或修訂需求：", "goal": "目標：", "abilities": "可用能力：", "skill": "- 使用 Skill `{name}`，並將上述目標與原始需求作為呼叫內容。", "constraints": "限制：", "constraint_items": ["- 保留使用者的真實意圖，不要自行擴充未提及的需求。", "- 遵循現有專案風格，維持最小必要修改。"], "execution": "執行要求：", "execution_items": ["- 先閱讀相關程式碼與設定，再提出修改方案。", "- 如果資訊不足，先提出需要確認的問題。"], "acceptance": "驗收標準：", "acceptance_item": "- 清楚說明修改範圍、風險與驗證方式。", "safety": "安全界線：", "safety_items": ["- 在我確認前，不要刪除檔案、修改資料庫、提交或推送 git。", "- 涉及驗證、權限、付款或遷移等高風險邏輯時，請先分析並等待確認。"],
    },
    "en": {
        "intro": "Complete the following task:", "existing": "Existing requirements to preserve:", "new": "New or revised requirements:", "goal": "Goal:", "abilities": "Available capabilities:", "skill": "- Use Skill `{name}` and provide the goal and original requirements as context.", "constraints": "Constraints:", "constraint_items": ["- Preserve the user's actual intent and do not invent unrequested requirements.", "- Follow the existing project style and make only the necessary changes."], "execution": "Execution requirements:", "execution_items": ["- Read the relevant code and configuration before proposing changes.", "- Ask focused questions first when essential information is missing."], "acceptance": "Acceptance criteria:", "acceptance_item": "- Clearly describe the change scope, risks, and verification performed.", "safety": "Safety boundaries:", "safety_items": ["- Do not delete files, modify databases, commit, or push git until I confirm.", "- Analyze and wait for confirmation before changing authentication, permissions, payments, migrations, or other high-risk logic."],
    },
    "ja": {
        "intro": "以下のタスクを完了してください：", "existing": "維持する既存要件：", "new": "新規または修正要件：", "goal": "目標：", "abilities": "利用可能な機能：", "skill": "- Skill `{name}` を使用し、上記の目標と元の要件をコンテキストとして渡してください。", "constraints": "制約：", "constraint_items": ["- ユーザーの本来の意図を維持し、依頼されていない要件を追加しないでください。", "- 既存のプロジェクトスタイルに従い、必要最小限の変更にしてください。"], "execution": "実行要件：", "execution_items": ["- 関連するコードと設定を確認してから変更案を提示してください。", "- 必要な情報が不足している場合は、先に確認事項を質問してください。"], "acceptance": "受け入れ基準：", "acceptance_item": "- 変更範囲、リスク、検証方法を明確に説明してください。", "safety": "安全上の制約：", "safety_items": ["- 確認するまで、ファイル削除、データベース変更、git の commit や push を行わないでください。", "- 認証、権限、決済、移行などの高リスクな変更は、先に分析して確認を待ってください。"],
    },
}

MODE_GUIDANCE = {
    "decision_partner": {
        "zh-CN": {
            "intro": "请完成以下决策分析：",
            "goal": "待决策事项：",
            "sections": [
                (
                    "分析要求：",
                    [
                        "- 从目标、资源和硬约束出发，用第一性原理拆解问题，区分事实、假设和未知。",
                        "- 比较彼此真正不同的选项，必要时包含维持现状，并说明收益、成本、风险、可逆性和机会成本。",
                        "- 主动寻找反方观点、失败情景，以及最可能推翻当前判断的证据。",
                    ],
                ),
                (
                    "交付要求：",
                    [
                        "- 明确推荐一个方向，给出关键理由、置信度和会触发改判的新信息。",
                        "- 给出成本最低的下一步验证动作；只做分析，不执行外部或高风险操作。",
                    ],
                ),
            ],
        },
        "zh-TW": {
            "intro": "請完成以下決策分析：",
            "goal": "待決策事項：",
            "sections": [
                ("分析要求：", ["- 從目標、資源與硬性限制出發，以第一性原理拆解問題，區分事實、假設與未知。", "- 比較真正不同的選項，必要時包含維持現狀，並說明收益、成本、風險、可逆性與機會成本。", "- 主動尋找反方觀點、失敗情境，以及最可能推翻目前判斷的證據。"]),
                ("交付要求：", ["- 明確推薦一個方向，提供關鍵理由、信心程度與會觸發改判的新資訊。", "- 提出成本最低的下一步驗證動作；只做分析，不執行外部或高風險操作。"]),
            ],
        },
        "en": {
            "intro": "Analyze the following decision:",
            "goal": "Decision to make:",
            "sections": [
                ("Analysis requirements:", ["- Start from the objective, resources, and hard constraints. Use first principles and separate facts, assumptions, and unknowns.", "- Compare genuinely different options, including the status quo when useful, across benefits, costs, risks, reversibility, and opportunity cost.", "- Seek counterarguments, failure scenarios, and evidence that would overturn the current view."]),
                ("Deliverable:", ["- Recommend one direction with the decisive reasons, confidence level, and signals that should trigger a change of course.", "- Propose the lowest-cost next validation step. Analyze only; do not perform external or high-risk actions."]),
            ],
        },
        "ja": {
            "intro": "次の意思決定を分析してください：",
            "goal": "決定事項：",
            "sections": [
                ("分析要件：", ["- 目的、資源、必須制約から第一原理で分解し、事実・仮定・未知を区別してください。", "- 必要に応じて現状維持を含む、本質的に異なる選択肢を便益、費用、リスク、可逆性、機会費用で比較してください。", "- 反対意見、失敗シナリオ、現在の判断を覆す証拠を積極的に探してください。"]),
                ("成果物：", ["- 一つの方向を明確に推奨し、決め手、確信度、判断を変更すべき新情報を示してください。", "- 最小コストの次の検証を提案してください。分析のみを行い、外部操作や高リスク操作は実行しないでください。"]),
            ],
        },
    },
    "creative_studio": {
        "zh-CN": {
            "intro": "请完成以下创作任务：",
            "goal": "创作简报：",
            "sections": [
                (
                    "创作要求：",
                    [
                        "- 明确目标受众、使用场景、核心信息和希望产生的感受，保留用户已有声音与素材。",
                        "- 分开不可改变的约束与可探索的创作空间，避免陈词滥调、空泛形容词和模板化表达。",
                        "- 开放任务先提出少量彼此明显不同的方向；目标清楚时直接深化最合适的方向。",
                    ],
                ),
                (
                    "交付要求：",
                    [
                        "- 交付可直接使用的成稿、脚本、命名、概念或其他指定作品，而不只是创作建议。",
                        "- 参考风格只提炼可描述的特征和机制，不复制具体个人的独特表达。",
                    ],
                ),
            ],
        },
        "zh-TW": {
            "intro": "請完成以下創作任務：",
            "goal": "創作簡報：",
            "sections": [
                ("創作要求：", ["- 明確目標受眾、使用情境、核心訊息與希望產生的感受，保留使用者原有的聲音與素材。", "- 分開不可改變的限制與可探索的創作空間，避免陳腔濫調、空泛形容詞與模板化表達。", "- 開放任務先提出少量明顯不同的方向；目標清楚時直接深化最適合的方向。"]),
                ("交付要求：", ["- 交付可直接使用的成稿、腳本、命名、概念或其他指定作品，而不只是創作建議。", "- 風格參考只提煉可描述的特徵與機制，不複製特定個人的獨特表達。"]),
            ],
        },
        "en": {
            "intro": "Complete the following creative task:",
            "goal": "Creative brief:",
            "sections": [
                ("Creative requirements:", ["- Define the audience, context, core message, and intended feeling while preserving the user's existing voice and material.", "- Separate fixed constraints from creative freedom. Avoid cliches, empty adjectives, and template-like phrasing.", "- For open briefs, propose a few clearly distinct directions; when the goal is clear, deepen the strongest direction directly."]),
                ("Deliverable:", ["- Produce ready-to-use copy, scripts, names, concepts, or the requested artifact rather than creative advice alone.", "- Extract describable qualities from style references without copying a specific person's distinctive expression."]),
            ],
        },
        "ja": {
            "intro": "次のクリエイティブタスクを完了してください：",
            "goal": "クリエイティブブリーフ：",
            "sections": [
                ("制作要件：", ["- 対象者、利用場面、核となるメッセージ、与えたい感情を明確にし、ユーザー固有の声と素材を維持してください。", "- 固定制約と創作の自由を分け、常套句、空疎な形容詞、テンプレート的な表現を避けてください。", "- 開かれた依頼では明確に異なる少数の方向を示し、目的が明確なら最適な方向を直接深めてください。"]),
                ("成果物：", ["- 助言だけでなく、そのまま使える文章、脚本、名称、コンセプト、または指定された作品を提出してください。", "- スタイル参照から説明可能な特徴と仕組みを抽出し、特定個人の独自表現は複製しないでください。"]),
            ],
        },
    },
}

_PROMPT_CONFIG = load_prompt_config("rule_based.json")
_EXTERNAL_TEMPLATES = _PROMPT_CONFIG.get("templates")
_EXTERNAL_MODE_GUIDANCE = _PROMPT_CONFIG.get("mode_guidance")
if isinstance(_EXTERNAL_TEMPLATES, dict) and "zh-CN" in _EXTERNAL_TEMPLATES:
    TEMPLATES = _EXTERNAL_TEMPLATES
if isinstance(_EXTERNAL_MODE_GUIDANCE, dict):
    MODE_GUIDANCE = _EXTERNAL_MODE_GUIDANCE


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


def _matching_skills(skills: list[dict[str, str]], transcript: str) -> list[str]:
    transcript_lower = transcript.lower()
    transcript_tokens = _match_tokens(transcript)
    matches: list[str] = []
    for skill in skills:
        name = str(skill.get("name") or "").strip()
        if not name:
            continue
        details = " ".join(
            str(skill.get(key) or "") for key in ("category", "description", "example")
        )
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
    is_configured = False
    supports_structured_output = False

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterable[str]:
        text = self.chat(messages)
        for chunk in re.findall(r".{1,24}", text, flags=re.S):
            yield chunk

    def chat(self, messages: list[dict[str, str]]) -> str:
        user_text = messages[-1]["content"]
        evidence_text = user_text.split("输入证据（JSON）：", 1)[-1].strip()
        try:
            evidence = json.loads(evidence_text)
        except json.JSONDecodeError:
            evidence = {"current_transcript": user_text, "available_skills": []}
        transcript = str(evidence.get("current_transcript") or "").strip()
        previous = str(evidence.get("previous_compiled_prompt") or "").strip()
        output_language = str(evidence.get("output_language") or "zh-CN")
        template = TEMPLATES.get(output_language, TEMPLATES["zh-CN"])
        mode = evidence.get("mode") or {}
        mode_id = str(mode.get("id") or "") if isinstance(mode, dict) else ""
        mode_guidance = MODE_GUIDANCE.get(mode_id, {}).get(output_language)
        if mode_guidance is None and mode_id in MODE_GUIDANCE:
            mode_guidance = MODE_GUIDANCE[mode_id]["zh-CN"]
        merge_output = bool(evidence.get("merge_output", True))
        available_skills = evidence.get("available_skills") or []
        if not isinstance(available_skills, list):
            available_skills = []

        risky = any(word.lower() in transcript.lower() for word in RISK_WORDS)
        matched_skills = _matching_skills(
            [skill for skill in available_skills if isinstance(skill, dict)], transcript
        )
        lines = [mode_guidance["intro"] if mode_guidance else template["intro"]]
        if previous and merge_output:
            lines.extend(
                [
                    "",
                    template["existing"],
                    previous,
                    "",
                    template["new"],
                    f"- {transcript}",
                ]
            )
        else:
            goal_label = mode_guidance["goal"] if mode_guidance else template["goal"]
            lines.extend(["", goal_label, f"- {transcript}"])
        if matched_skills:
            lines.extend(["", template["abilities"]])
            lines.extend(
                template["skill"].format(name=name)
                for name in matched_skills
            )
        if mode_guidance:
            for title, items in mode_guidance["sections"]:
                lines.extend(["", title, *items])
        else:
            lines.extend(
                [
                    "",
                    template["constraints"],
                    *template["constraint_items"],
                    "",
                    template["execution"],
                    *template["execution_items"],
                    "",
                    template["acceptance"],
                    template["acceptance_item"],
                ]
            )
        if risky:
            lines.extend(
                [
                    "",
                    template["safety"],
                    *template["safety_items"],
                ]
            )
        return "\n".join(lines)
