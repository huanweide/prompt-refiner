"""渲染层：把 Intent + 规则产出拼装成最终提示词。

输出格式刻意保持极简的键值 + 分节结构，理由有三：

1. 省 token —— 键值对没有解释性文字，模型对它的解析成本最低；
2. 结构稳 —— 固定分节让模型形成可靠的定位习惯，比长段落更少误读；
3. 人可读 —— 用户一眼能看出"哪些是我说的、哪些是工具补的"，
   便于审查原意有没有被篡改。

模板长这样：

    # 任务
    <一句话说清要干什么>

    # 上下文
    - 角色：...
    - 目标读者：...

    # 约束
    - 字数限制：...
    - 不要复述我的问题

    # 输出格式
    - 输出：...

    # 原始诉求（不得改变）
    <用户原话>
"""

from __future__ import annotations

from .analyzer import Intent
from .rules import Rule


SECTION_TASK = "# 任务"
SECTION_CONTEXT = "# 上下文"
SECTION_CONSTRAINTS = "# 约束"
SECTION_FORMAT = "# 输出格式"
SECTION_RAW = "# 原始诉求（不得改变）"

# 哪些规则 id 归入哪一节
CONTEXT_RULES = {"role", "deliverable", "audience"}
CONSTRAINT_RULES = {"boundary", "intent_guard", "no_extra_context", "ambiguity"}
FORMAT_RULES = {"format", "keyword"}
COMPRESS_RULES = {"compress_filler"}


def render(
    intent: Intent,
    rules: list[Rule],
    include_raw: bool = True,
) -> str:
    """把分析结果渲染成结构化提示词。

    Args:
        intent: 分析层输出
        rules: 本次启用的规则
        include_raw: 是否附上"原始诉求"节，用于人工核对原意
    """
    context: list[str] = []
    constraints: list[str] = []
    fmt: list[str] = []
    notes: list[str] = []

    for rule in rules:
        try:
            lines = rule(intent)
        except Exception:  # 单条规则失败不应让整体崩掉
            continue
        if not lines:
            continue

        if rule.id in CONTEXT_RULES:
            context.extend(lines)
        elif rule.id in CONSTRAINT_RULES:
            constraints.extend(lines)
        elif rule.id in FORMAT_RULES:
            fmt.extend(lines)
        elif rule.id in COMPRESS_RULES:
            notes.extend(lines)

    # 用户自带的约束排在最前，工具补的在后 —— 优先级一目了然
    ordered_constraints = list(intent.constraints) + constraints

    parts: list[str] = []

    parts.append(SECTION_TASK)
    parts.append(intent.core or intent.raw)

    if context:
        parts.append("")
        parts.append(SECTION_CONTEXT)
        parts.extend(f"- {c}" for c in _dedup(context))

    if ordered_constraints:
        parts.append("")
        parts.append(SECTION_CONSTRAINTS)
        parts.extend(f"- {c}" for c in _dedup(ordered_constraints))

    if fmt:
        parts.append("")
        parts.append(SECTION_FORMAT)
        parts.extend(f"- {c}" for c in _dedup(fmt))

    if notes:
        parts.append("")
        parts.append(" ".join(notes))

    if include_raw and intent.raw != intent.core:
        parts.append("")
        parts.append(SECTION_RAW)
        parts.append(intent.raw)

    return "\n".join(parts).strip()


def _dedup(items: list[str]) -> list[str]:
    """保序去重，避免规则之间互相叠加产生重复行。"""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
