"""Preferences shared by dictation, translation and selection editing."""

import json

import yaml


LANGUAGES = {"en": "英语", "zh": "中文", "ja": "日语", "ko": "韩语", "fr": "法语", "de": "德语", "es": "西班牙语"}
# ``edit`` remains readable for older config files, but is no longer an
# exposed action. Right Alt automatically selects rewrite when text is selected.
DEFAULT_KEYS = {"dictate": "RightAlt", "edit": "RightAlt+Space", "translate": "RightAlt+RightShift"}
KEYS = {"RightAlt", "RightCtrl", "RightShift", "Space", "MouseLeft", "MouseRight", "MouseMiddle", *(f"F{i}" for i in range(1, 13))}
MODIFIERS = {"RightAlt", "RightCtrl", "RightShift"}


def _legacy_skills():
    return [
        {"name": "去 AI 味", "intent": "用户想消除套话、改得更自然、像本人写的。",
         "instructions": "保留事实和说话人的立场，用具体、自然的日常表达替换空话和重复修饰。", "enabled": True},
        {"name": "Prompt 工程", "intent": "用户要把想法写成给 Agent 的任务、优化提示词或整理验收条件。",
         "instructions": "将已有信息整理为直接可交给 Agent 的任务。说明目标、已有上下文、约束、交付物与可验证的完成条件；缺失的必要信息明确标为待确认，不编造。", "enabled": True},
    ]


def default_skills():
    skills = _legacy_skills()
    skills[0]["instructions"] = """目标
让文字符合作者和场景，例如工作群消息、邮件、报告或口语。保持原文语言、立场、事实、数字、专业术语和必要限定。

编辑方法
1. 找出可以直接删除的套话、重复总结、空泛表扬和夸大程度。把已有的具体信息提到前面。
2. 优先使用明确的主语和动词。句子太长时按意思拆开，保留作者有辨识度的措辞和行业惯用表达。
3. 根据场景保留必要的礼貌、标题和格式。原文已经自然的句子尽量少改，避免强行口语化。
4. 检查人名、数字、因果、时间、否定和不确定性。缺少证据时保留原有范围，不补人物、数据或承诺。

示例
「为进一步提升协同效率，我们将于周五前完成事项汇总。」→「我们会在周五前汇总这些事项。」
「这次调整可能影响 2 月的数据。」→「这次调整可能影响 2 月的数据。」

输出
只交付可直接替换选区的正文。"""
    skills[1]["instructions"] = """目标
把原文和口述要求整理成能直接交给 Agent 的任务说明。根据任务大小决定篇幅，一句话能交代清楚的任务可用一段写完。

组织任务
1. 用动词写清目标和最终交付物。保留文件路径、产品术语、版本、环境和已有决定。
2. 把硬性约束和可由执行者决定的细节区分开。原文提供范围时明确边界，避免替用户选技术方案。把已观察到的问题和新需求分开写。「重试应保留编辑」是需求，原文明确报告内容丢失时才写入现状。
3. 按依赖关系排列必要步骤。只有步骤能减少歧义时才添加，避免通用流程套话。
4. 把完成条件写成可观察的行为、输出或检查。若缺失的信息会影响执行，列为待确认项，绝不虚构路径、指标或权限。
5. 自检是否覆盖了用户的修改要求，交付物是否能够逐项验收。

示例
「导出失败用户看不到」→「修复导出失败反馈。失败时显示原因和重试入口，保留当前编辑内容。验收：模拟导出失败后，用户能看到提示并重试，成功导出路径正常工作。」

输出
只交付可粘贴给 Agent 的任务正文。复杂任务可用目标、上下文、约束和验收条件分段。"""
    return skills


def upgrade_default_skills(skills):
    for old, new in zip(_legacy_skills(), default_skills()):
        for skill in skills:
            if isinstance(skill, dict) and all(skill.get(field) == old[field] for field in ("name", "intent", "instructions")):
                skill["instructions"] = new["instructions"]
    return skills


def validate_skills(items):
    if not isinstance(items, list) or len(items) > 40:
        raise ValueError("最多可保存 40 个 Skill")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Skill 格式无效")
        skill = {}
        for key, limit in (("name", 64), ("intent", 500), ("instructions", 20000)):
            value = item.get(key)
            if not isinstance(value, str) or not 0 < len(value.strip()) <= limit:
                raise ValueError(f"Skill 字段 {key} 为空或过长")
            skill[key] = value.strip()
        if any(s["name"].casefold() == skill["name"].casefold() for s in result):
            raise ValueError("Skill 名称不能重复")
        if not isinstance(item.get("enabled", True), bool):
            raise ValueError("Skill 启用状态无效")
        result.append({**skill, "enabled": item.get("enabled", True)})
    if sum(len(s["instructions"]) for s in result) > 100_000:
        raise ValueError("Skill 指令总长度不能超过 100000 字符")
    return result


def import_skills(payload):
    content = payload.get("content")
    if not isinstance(content, str) or len(content.encode("utf8")) > 512 * 1024:
        raise ValueError("请选择 512 KB 以内的 Skill 文件")
    content = content.lstrip("\ufeff").replace("\r\n", "\n")
    if str(payload.get("filename", "")).lower().endswith(".md"):
        lines = content.strip().splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            raise ValueError("SKILL.md 需要 YAML 元数据")
        end = lines.index("---", 1)
        try:
            meta = yaml.safe_load("\n".join(lines[1:end]))
        except yaml.YAMLError as exc:
            raise ValueError("SKILL.md 元数据格式错误") from exc
        if not isinstance(meta, dict):
            raise ValueError("SKILL.md 缺少名称和说明")
        items = [{"name": meta.get("name"), "intent": meta.get("description"),
                  "instructions": "\n".join(lines[end+1:]), "enabled": True}]
    else:
        data = json.loads(content)
        items = data.get("skills") if isinstance(data, dict) else data
    return {"skills": validate_skills(items)}


def validate_keys(keys):
    if not isinstance(keys, dict) or not {"dictate", "translate"}.issubset(keys):
        raise ValueError("需要分别设置听写和翻译快捷键")
    names = ["dictate", "translate"] + (["edit"] if "edit" in keys else [])
    seen = set()
    for name in names:
        value = keys[name]
        if not isinstance(value, str):
            raise ValueError("快捷键格式无效")
        parts = value.split("+")
        if len(parts) > 2 or any(k not in KEYS for k in parts) or len(set(parts)) != len(parts):
            raise ValueError("不支持该快捷键")
        if (len(parts) == 2 and parts[0] not in MODIFIERS) or parts == ["Space"]:
            raise ValueError("空格需搭配修饰键")
        chord = frozenset(parts)
        if chord in seen:
            raise ValueError("快捷键不能重复")
        seen.add(chord)
    return {name: keys[name] for name in ("dictate", "translate")}
