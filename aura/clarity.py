from __future__ import annotations

import json

LANGUAGE_LABELS = {
    "zh-CN": {"high": "清晰", "medium": "一般", "low": "模糊"},
    "zh-TW": {"high": "清晰", "medium": "一般", "low": "模糊"},
    "en": {"high": "Clear", "medium": "Fair", "low": "Vague"},
    "ja": {"high": "明確", "medium": "普通", "low": "曖昧"},
}

CLARITY_SYSTEM_PROMPT = """\
You are a problem-clarity evaluator. Analyze the user's problem description for completeness, specificity, and actionability.

Scoring guidelines:
- 80–100 (high): Clear goal, specific context, actionable scope, minimal ambiguity. Ready to execute.
- 50–79 (medium): Basic goal is present but missing important details, context, constraints, or success criteria.
- 0–49 (low): Vague intent, missing key information, hard to determine what to do.

Return ONLY a JSON object (no markdown, no explanation) with exactly these keys:
- "score": integer 0–100
- "level": one of "high", "medium", "low"
- "label": a short label in the user's language describing the clarity level\
"""


def build_clarity_messages(transcript: str, language: str = "zh-CN") -> list[dict[str, str]]:
    labels = LANGUAGE_LABELS.get(language, LANGUAGE_LABELS["zh-CN"])
    user_prompt = (
        f"User's language: {language}\n"
        f"Label mapping: high={labels['high']}, medium={labels['medium']}, low={labels['low']}\n\n"
        f"Problem description to evaluate:\n{transcript}"
    )
    return [
        {"role": "system", "content": CLARITY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


SUPPLEMENT_SYSTEM_PROMPT = """\
You are an assistant that helps users clarify their problem descriptions. Based on the user's current description and conversation history, identify 2–4 specific gaps and generate clarifying questions.

Rules:
- Each question should target one missing piece: goal, context, constraints, expected output, scope, environment, or priority.
- Each question MUST have 2–4 concrete, distinct answer options the user can select from. Make options realistic and helpful.
- Consider previous conversation context so you don't ask about already-covered topics.
- Questions should be in the user's language.

Return ONLY a JSON array (no markdown, no explanation) of objects with exactly these keys:
- "id": a short kebab-case identifier (e.g. "target-env")
- "question": the question text
- "options": array of 2–4 answer choice strings\
"""


def build_supplement_messages(
    transcript: str,
    history: list[str],
    language: str = "zh-CN",
) -> list[dict[str, str]]:
    history_block = ""
    if history:
        recent = history[-5:]  # Last 5 turns at most
        history_block = "Previous conversation turns (for context, newest last):\n" + "\n---\n".join(recent) + "\n\n"

    user_prompt = (
        f"User's language: {language}\n\n"
        f"{history_block}"
        f"Current problem description:\n{transcript}\n\n"
        "Generate 2–4 clarifying questions based on gaps in this description."
    )
    return [
        {"role": "system", "content": SUPPLEMENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def parse_clarity_response(raw: str, language: str = "zh-CN") -> dict[str, object]:
    """Parse the LLM JSON response for clarity assessment. Returns a dict with score, level, label."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3].strip()
    parsed = json.loads(text)
    score = max(0, min(100, int(parsed.get("score", 50))))
    level = str(parsed.get("level", "medium"))
    if level not in ("high", "medium", "low"):
        level = "medium"
    labels = LANGUAGE_LABELS.get(language, LANGUAGE_LABELS["zh-CN"])
    label = str(parsed.get("label") or labels.get(level, level))
    return {"score": score, "level": level, "label": label}


def parse_supplement_response(raw: str) -> list[dict[str, object]]:
    """Parse the LLM JSON response for supplementary questions. Returns a list of question dicts."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3].strip()
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        return []
    result: list[dict[str, object]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or f"q{len(result) + 1}")
        question = str(item.get("question") or "").strip()
        options = item.get("options")
        if not question or not isinstance(options, list) or len(options) < 2:
            continue
        result.append({
            "id": qid,
            "question": question,
            "options": [str(o) for o in options],
        })
    return result
