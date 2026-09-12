"""质量评分：把"优化得好不好"从主观感受变成可量化的数字。

这是本工具与"调 LLM 改提示词"类产品的核心分野：
- 对手给不出分数，只能靠人肉对比；
- 我们因为是确定性规则引擎，可以精确计算每一维度。

三个指标：

1. structure_score（结构分）
   输出是否具备 任务/上下文/约束/输出格式 四要素。
   缺项扣分——这正是"提示词能不能被 AI 稳定执行"的关键。

2. preservation_score（原意保留分）
   原始输入里的关键词有多少进了输出。
   这是安全阀：任何优化都不许以"改写"为名丢掉用户诉求。

3. compaction_score（精简分）
   客套与冗余被剥掉了多少。注意这是"信噪比"指标，
   不是"越短越好"——补全上下文会让总分上涨是合理的。

综合分 = 结构 0.45 + 保留 0.40 + 精简 0.15
保留权重给得很高，因为丢原意是不可接受的硬伤。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .analyzer import Intent, analyze


REQUIRED_SECTIONS = ("# 任务", "# 约束", "# 输出格式")


@dataclass
class QualityScore:
    structure: int
    preservation: int
    compaction: int
    total: int
    grade: str
    details: dict

    def to_dict(self) -> dict:
        return {
            "structure": self.structure,
            "preservation": self.preservation,
            "compaction": self.compaction,
            "total": self.total,
            "grade": self.grade,
            "details": self.details,
        }


def _grade(total: int) -> str:
    if total >= 90:
        return "优秀"
    if total >= 75:
        return "良好"
    if total >= 60:
        return "及格"
    return "待改进"


def score_structure(output: str) -> tuple[int, dict]:
    """结构分：四要素齐全度 + 分节是否规范。"""
    hit = [s for s in REQUIRED_SECTIONS if s in output]
    base = len(hit) / len(REQUIRED_SECTIONS) * 80

    # 加分项：有分点符号（说明真的是结构化而非堆段落）
    bullets = len([l for l in output.splitlines() if l.startswith("- ")])
    bonus = min(20, bullets * 3)

    return round(base + bonus), {
        "sections_found": hit,
        "sections_missing": [s for s in REQUIRED_SECTIONS if s not in hit],
        "bullet_count": bullets,
    }


def score_preservation(intent: Intent, output: str) -> tuple[int, dict]:
    """原意保留分：关键词命中率 + 原句是否可追溯。"""
    kws = intent.keywords
    if kws:
        hit = [k for k in kws if k in output]
        ratio = len(hit) / len(kws)
        detail_hit, detail_miss = hit, [k for k in kws if k not in hit]
    else:
        # 没有可抽取的关键词时，退化为"任务主干是否保留"
        core_ok = intent.core[:8] in output if intent.core else True
        ratio = 1.0 if core_ok else 0.5
        detail_hit, detail_miss = (["(任务主干)"] if core_ok else []), (
            [] if core_ok else ["(任务主干丢失)"]
        )

    base = ratio * 85
    # 原句可追溯额外加分（用户能核对没被改）
    traceable = 15 if intent.raw in output else 0

    return round(base + traceable), {
        "keywords_hit": detail_hit,
        "keywords_missed": detail_miss,
        "raw_traceable": bool(traceable),
    }


def score_compaction(intent: Intent, output: str) -> tuple[int, dict]:
    """精简分：冗余剥离情况。

    没有冗余可剥时给满分——说明用户输入本来就很干净，
    不该因此扣分。
    """
    raw_len = len(intent.raw)
    core_len = len(intent.core)
    if raw_len == 0:
        return 100, {"stripped_chars": 0, "note": "无输入"}

    stripped = max(0, raw_len - core_len)
    ratio = stripped / raw_len

    # 剥离 10% 左右即算不错；超过 30% 给满分
    points = min(100, round(ratio / 0.30 * 100))

    # 但若工具往输出里注入了大量解释性文字导致膨胀，扣分
    noise = output.count("（已剥离")
    if noise > 1:
        points = max(0, points - 10)

    return points, {
        "stripped_chars": stripped,
        "stripped_ratio": round(ratio, 3),
        "note": "无冗余可剥，输入本就精炼" if stripped == 0 else "已剥离客套与冗余",
    }


def evaluate(intent: Intent, output: str) -> QualityScore:
    """对一次优化结果打综合分。"""
    s, s_detail = score_structure(output)
    p, p_detail = score_preservation(intent, output)
    c, c_detail = score_compaction(intent, output)

    total = round(s * 0.45 + p * 0.40 + c * 0.15)

    return QualityScore(
        structure=s,
        preservation=p,
        compaction=c,
        total=total,
        grade=_grade(total),
        details={"structure": s_detail, "preservation": p_detail, "compaction": c_detail},
    )


def score_text(text: str) -> QualityScore:
    """便捷入口：直接对一段原始文字做"精炼+打分"。

    适合在 CI 里当质量门禁使用：

        from promptrefiner import score_text
        assert score_text(open("prompt.txt").read()).total >= 75
    """
    # 延迟导入，避免 quality 与 core 之间形成循环依赖
    from .core import refine

    intent = analyze(text)
    output = refine(text)
    return evaluate(intent, output)

