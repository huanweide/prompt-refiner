"""规则层：定义所有可插拔的提示词优化规则。

每条规则是一个纯函数：接收 Intent，返回对最终提示词的贡献。
规则分三类：
  - expand   : 补全缺失的上下文（角色、背景、边界）
  - compress : 压缩冗余表达，省 token
  - clarify  : 消歧，把模糊说法变成明确指令

之所以做成规则而不是硬编码在渲染器里，是为了让用户能自由增删、
也能清楚看到"这句话是谁加的"，便于审查原意是否被悄悄改变。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .analyzer import Intent


RuleKind = Literal["expand", "compress", "clarify"]


@dataclass(frozen=True)
class Rule:
    """一条优化规则。"""

    id: str
    kind: RuleKind
    description: str
    apply: Callable[[Intent], list[str]]

    def __call__(self, intent: Intent) -> list[str]:
        return self.apply(intent)


# ---------------------------------------------------------------------------
# expand —— 补全上下文与边界
# ---------------------------------------------------------------------------

def _role_hint(intent: Intent) -> list[str]:
    """按任务类型补一个合适的角色，让模型更快进入状态。"""
    roles = {
        "code": "资深软件工程师",
        "write": "专业内容创作者",
        "translate": "专业译者（母语级双语）",
        "summarize": "信息提炼专家",
        "explain": "擅长类比讲解的老师",
        "analyze": "严谨的分析顾问",
        "transform": "文字编辑",
    }
    role = roles.get(intent.task_type)
    return [f"角色：{role}"] if role else []


def _deliverable_hint(intent: Intent) -> list[str]:
    """明确产物形态，减少模型自由发挥带来的返工。"""
    if intent.deliverable:
        return [f"交付物：{intent.deliverable}"]
    return []


def _audience_hint(intent: Intent) -> list[str]:
    if intent.audience:
        return [f"目标读者：{intent.audience}"]
    return []


def _boundary_hint(intent: Intent) -> list[str]:
    """补边界：提示模型什么不该做。这是最省 token 的"提效"手段。"""
    common = ["不要复述我的问题", "直接给结果，不要寒暄"]
    if intent.task_type == "code":
        common.append("给出可直接运行的完整代码，并标注关键行注释")
    elif intent.task_type == "write":
        common.append("不要出现明显的 AI 套话")
    elif intent.task_type == "analyze":
        common.append("区分事实与推测，推测需标注依据")
    return common


def _intent_guard(intent: Intent) -> list[str]:
    """原意保护：显式声明不得改变原始诉求。"""
    return ["保留我原始诉求的核心意思，不要自行加需求或删减重点"]


# ---------------------------------------------------------------------------
# compress —— 省 token
# ---------------------------------------------------------------------------

def _filler_removed(intent: Intent) -> list[str]:
    """填充词剥离后，若确实变短了，标记已压缩。"""
    if len(intent.core) < len(intent.raw):
        saved = len(intent.raw) - len(intent.core)
        return [f"（已剥离 {saved} 字客套 / 冗余表达）"]
    return []


def _no_redundant_context(intent: Intent) -> list[str]:
    return ["只提供完成任务必需的信息，不扩写背景"]


# ---------------------------------------------------------------------------
# clarify —— 消歧
# ---------------------------------------------------------------------------

def _format_hint(intent: Intent) -> list[str]:
    """定义输出结构，避免模型给一大坨散文。"""
    if intent.is_question:
        return ["输出：先给一句话结论，再给不超过 5 条的支撑理由"]
    if intent.task_type == "code":
        return ["输出：代码块 + 关键实现说明（不超过 3 句）"]
    if intent.task_type in {"write", "transform"}:
        return ["输出：正文 + 一句话说明你做了哪些取舍"]
    if intent.task_type == "summarize":
        return ["输出：要点列表，每条不超过 25 字"]
    return ["输出：结构清晰的分点陈述"]


def _keyword_emphasis(intent: Intent) -> list[str]:
    """把抽取到的关键词显式列出，防止模型忽略主体。"""
    if intent.keywords:
        return [f"必须围绕这些要素展开：{'、'.join(intent.keywords)}"]
    return []


def _ambiguity_flag(intent: Intent) -> list[str]:
    """输入过短时，提示模型先确认再执行。"""
    if len(intent.core) <= 6:
        return ["输入信息偏少：如关键信息缺失，先提一个最关键的澄清问题再作答"]
    return []


# ---------------------------------------------------------------------------
# 规则注册表
# ---------------------------------------------------------------------------
RULES: list[Rule] = [
    Rule("role", "expand", "按任务类型补角色", _role_hint),
    Rule("deliverable", "expand", "明确交付物形态", _deliverable_hint),
    Rule("audience", "expand", "明确目标读者", _audience_hint),
    Rule("boundary", "expand", "补充不做清单，减少废话", _boundary_hint),
    Rule("intent_guard", "expand", "声明原意保护", _intent_guard),
    Rule("compress_filler", "compress", "标记已剥离的冗余", _filler_removed),
    Rule("no_extra_context", "compress", "禁止无关扩写", _no_redundant_context),
    Rule("format", "clarify", "定义输出结构", _format_hint),
    Rule("keyword", "clarify", "强调核心要素", _keyword_emphasis),
    Rule("ambiguity", "clarify", "输入过短时先澄清", _ambiguity_flag),
]


def rules_by_kind(kind: RuleKind) -> list[Rule]:
    return [r for r in RULES if r.kind == kind]


def active_rules(disabled: set[str] | None = None) -> list[Rule]:
    """返回启用中的规则。disabled 集合里的规则会被跳过。"""
    disabled = disabled or set()
    return [r for r in RULES if r.id not in disabled]
