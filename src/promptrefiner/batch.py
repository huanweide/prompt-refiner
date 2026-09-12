"""批量处理：对手全都没有的能力。

现有提示词优化工具都是"单条交互式"——打开网页、粘贴一条、等 LLM 返回。
这在两个场景下直接失效：

1. 存量提示词治理：项目里积累了 200 条提示词模板，想统一规范
2. CI 流水线：提交代码时自动检查提示词质量

因为我们是确定性纯函数引擎，批量处理天然可行：
不消耗 token、不需要并发控制、结果可复现。
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .analyzer import analyze
from .core import refine_with_report
from .quality import evaluate


@dataclass
class BatchItem:
    index: int
    source: str
    output: str = ""
    ok: bool = True
    error: str = ""
    score: int = 0
    grade: str = ""
    task_type: str = ""
    token_delta: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "source": self.source,
            "output": self.output,
            "ok": self.ok,
            "error": self.error,
            "score": self.score,
            "grade": self.grade,
            "task_type": self.task_type,
            "token_delta": self.token_delta,
        }


@dataclass
class BatchResult:
    items: list[BatchItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def succeeded(self) -> int:
        return sum(1 for i in self.items if i.ok)

    @property
    def failed(self) -> int:
        return self.total - self.succeeded

    @property
    def avg_score(self) -> float:
        ok = [i for i in self.items if i.ok]
        return round(sum(i.score for i in ok) / len(ok), 1) if ok else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "avg_score": self.avg_score,
            "items": [i.to_dict() for i in self.items],
        }


def process_lines(
    lines: Iterable[str],
    *,
    disable: list[str] | None = None,
    include_raw: bool = True,
) -> BatchResult:
    """批量处理多行输入。

    单条失败不影响整批——错误被记录在 item.error 里继续跑，
    这是批处理工具必须有的韧性。
    """
    result = BatchResult()

    for idx, raw in enumerate(lines):
        text = raw.strip()
        if not text:
            continue

        try:
            report = refine_with_report(
                text, disable=disable, include_raw=include_raw
            )
            intent = analyze(text)
            quality = evaluate(intent, report["output"])

            result.items.append(
                BatchItem(
                    index=idx,
                    source=text,
                    output=report["output"],
                    ok=True,
                    score=quality.total,
                    grade=quality.grade,
                    task_type=intent.task_type,
                    token_delta=report["token_report"]["token_delta"],
                )
            )
        except Exception as exc:  # 逐条容错
            result.items.append(
                BatchItem(index=idx, source=text, ok=False, error=f"{type(exc).__name__}: {exc}")
            )

    return result


def read_input_file(path: str | Path) -> list[str]:
    """读取输入文件。支持 .txt（一行一条）与 .json（字符串数组）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")

    text = p.read_text(encoding="utf-8")

    if p.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, list):
            return [str(x) for x in data]
        if isinstance(data, dict) and isinstance(data.get("prompts"), list):
            return [str(x) for x in data["prompts"]]
        raise ValueError("JSON 输入需为字符串数组，或含 prompts 数组的对象")

    return [l for l in text.splitlines() if l.strip()]


def to_markdown(result: BatchResult) -> str:
    """导出为 Markdown，便于贴进 Issue / PR 做评审。"""
    lines = [
        "# PromptRefiner 批量精炼报告",
        "",
        f"- 总条数：{result.total}",
        f"- 成功：{result.succeeded}",
        f"- 失败：{result.failed}",
        f"- 平均质量分：{result.avg_score}",
        "",
        "| # | 质量分 | 等级 | 任务类型 | token 变化 | 原文摘要 |",
        "|---|---|---|---|---|---|",
    ]
    for item in result.items:
        summary = item.source[:28].replace("|", "\\|")
        if item.ok:
            lines.append(
                f"| {item.index} | {item.score} | {item.grade} | "
                f"{item.task_type} | {item.token_delta:+d} | {summary} |"
            )
        else:
            lines.append(f"| {item.index} | - | 失败 | - | - | {summary} |")

    lines.append("")
    lines.append("## 精炼结果")
    for item in result.items:
        if not item.ok:
            continue
        lines.append("")
        lines.append(f"### {item.index}. （质量分 {item.score} / {item.grade}）")
        lines.append("")
        lines.append("```text")
        lines.append(item.output)
        lines.append("```")

    return "\n".join(lines)


def to_csv(result: BatchResult) -> str:
    """导出 CSV，便于进 Excel 做统计。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["index", "ok", "score", "grade", "task_type", "token_delta", "error", "source", "output"]
    )
    for item in result.items:
        writer.writerow(
            [
                item.index,
                item.ok,
                item.score,
                item.grade,
                item.task_type,
                item.token_delta,
                item.error,
                item.source,
                item.output,
            ]
        )
    return buf.getvalue()
