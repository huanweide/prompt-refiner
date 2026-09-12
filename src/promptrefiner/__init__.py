"""PromptRefiner — 本地零依赖的提示词精炼引擎。

与市面上"调用大模型来改写提示词"的工具不同，本引擎全部优化
在本地规则层完成：不联网、不花钱、不泄露内容、结果可复现。

对外主入口：

    from promptrefiner import refine, refine_with_report, evaluate

    refine("帮我写个爬虫")             # 只要结果
    refine_with_report("帮我写个爬虫")  # 结果 + 诊断
    evaluate("帮我写个爬虫")            # 只要质量分
"""

from .analyzer import analyze, Intent
from .core import refine, refine_with_report
from .quality import evaluate, QualityScore
from .renderer import render
from .rules import RULES, Rule
from .tokens import estimate_tokens, compare

# 兼容别名（旧命名 optimize 保留，不破坏已写好的脚本）
optimize = refine
optimize_with_report = refine_with_report

__version__ = "0.1.0"
__all__ = [
    "refine",
    "refine_with_report",
    "optimize",
    "optimize_with_report",
    "evaluate",
    "QualityScore",
    "analyze",
    "Intent",
    "render",
    "RULES",
    "Rule",
    "estimate_tokens",
    "compare",
    "__version__",
]
