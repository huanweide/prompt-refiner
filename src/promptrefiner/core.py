"""主流程：串联 分析 → 规则 → 渲染 → 报告。

对外只暴露两个函数：

    refine(text)              -> str     只要结果
    optimize_with_report(text)  -> dict    结果 + 诊断报告

流程本身没有副作用：纯字符串进出，同样的输入永远得到同样的输出。
这带来两个好处——可单测、可 diff，也方便嵌进任何 pipeline。
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .analyzer import analyze
from .renderer import render
from .rules import active_rules, RULES
from .tokens import compare


def refine(
    text: str,
    *,
    disable: list[str] | None = None,
    include_raw: bool = True,
) -> str:
    """把任意文字优化为结构化提示词。

    Args:
        text: 原始输入，任意自然语言
        disable: 要禁用的规则 id 列表，例如 ["ambiguity"]
        include_raw: 是否在结尾附上原始诉求节

    Returns:
        结构化提示词字符串

    Raises:
        TypeError: text 不是字符串
        ValueError: text 为空或全空白
    """
    intent = analyze(text)
    rules = active_rules(set(disable or []))
    return render(intent, rules, include_raw=include_raw)


def refine_with_report(
    text: str,
    *,
    disable: list[str] | None = None,
    include_raw: bool = True,
) -> dict[str, Any]:
    """同 refine，但额外返回诊断信息，便于调试与展示。

    Returns:
        {
          "output": 优化后的提示词,
          "intent": 分析结果,
          "token_report": token 变化,
          "applied_rules": 实际生效的规则,
          "disabled_rules": 被禁用的规则,
        }
    """
    intent = analyze(text)
    disabled = set(disable or [])
    rules = active_rules(disabled)

    fired: list[dict[str, str]] = []
    for rule in rules:
        try:
            produced = rule(intent)
        except Exception:
            produced = []
        if produced:
            fired.append(
                {
                    "id": rule.id,
                    "kind": rule.kind,
                    "description": rule.description,
                    "lines": produced,
                }
            )

    output = render(intent, rules, include_raw=include_raw)

    return {
        "output": output,
        "intent": asdict(intent),
        "token_report": compare(text, output),
        "applied_rules": fired,
        "disabled_rules": sorted(disabled),
        "available_rules": [
            {"id": r.id, "kind": r.kind, "description": r.description} for r in RULES
        ],
    }
