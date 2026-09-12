"""PromptRefiner 命令行入口。

用法：

    prompt-refiner "你的文字"                    # 直接传参
    cat draft.txt | prompt-refiner               # 从管道读
    prompt-refiner --report "总结这篇文章"        # 带诊断报告
    prompt-refiner --score "写个函数"             # 只要质量分
    prompt-refiner --batch prompts.txt --out-md r.md   # 批量
    prompt-refiner --list-rules                  # 查看规则

设计取舍：默认输出干净的结果文本，方便直接 pipe 给别的命令；
只有显式加 --report / --json 时才输出额外信息，避免污染 stdout。
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import refine, refine_with_report
from .quality import score_text
from .rules import rules_by_kind


def _read_input(text_arg: str | None) -> str:
    """从参数或 stdin 取输入。"""
    if text_arg:
        return text_arg

    if sys.stdin is None or sys.stdin.isatty():
        print(
            "未收到输入。用法：\n"
            '  prompt-refiner "你的文字"\n'
            '  echo "你的文字" | prompt-refiner',
            file=sys.stderr,
        )
        raise SystemExit(2)

    data = sys.stdin.read()
    if not data.strip():
        print("stdin 为空。", file=sys.stderr)
        raise SystemExit(2)
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prompt-refiner",
        description="把任何文字精炼成结构清晰、省 token、不丢原意的提示词。本地运行，无需 API Key。",
        epilog='示例：prompt-refiner "帮我写一封给客户的道歉邮件"',
    )
    parser.add_argument("text", nargs="?", help="要精炼的文字；留空则从 stdin 读取")
    parser.add_argument("--report", action="store_true", help="输出人类可读的诊断报告")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整结果")
    parser.add_argument("--score", action="store_true", help="只输出质量分")
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="批量处理文件（.txt 一行一条，或 .json 字符串数组）",
    )
    parser.add_argument("--out-md", metavar="FILE", help="把批量结果写成 Markdown 报告")
    parser.add_argument("--out-csv", metavar="FILE", help="把批量结果写成 CSV")
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="RULE_ID",
        help="禁用某条规则，可重复。用 --list-rules 查看 id",
    )
    parser.add_argument("--no-raw", action="store_true", help="不在结果末尾附上原始诉求节")
    parser.add_argument("--list-rules", action="store_true", help="列出全部可用规则后退出")
    parser.add_argument("--version", action="version", version=f"prompt-refiner {__version__}")
    return parser


def _print_rule_list() -> None:
    labels = {"expand": "补全上下文", "compress": "压缩冗余", "clarify": "消歧澄清"}
    print("可用规则：\n")
    for kind in ("expand", "compress", "clarify"):
        print(f"[{kind}] {labels[kind]}")
        for rule in rules_by_kind(kind):
            print(f"  {rule.id:<18} {rule.description}")
        print()
    print('用法：prompt-refiner --disable ambiguity "你的文字"')


def _print_report(result: dict) -> None:
    from .analyzer import analyze
    from .quality import evaluate

    intent_data = result["intent"]
    report = result["token_report"]
    quality = evaluate(analyze(intent_data["raw"]), result["output"])

    print("=" * 64)
    print("PromptRefiner 诊断报告")
    print("=" * 64)
    print(f"任务类型   : {intent_data['task_label']}")
    print(f"是否疑问句 : {'是' if intent_data['is_question'] else '否'}")
    print(f"目标读者   : {intent_data['audience'] or '（未识别）'}")
    print(f"交付物     : {intent_data['deliverable'] or '（未识别）'}")
    print(f"关键词     : {'、'.join(intent_data['keywords']) or '（无）'}")
    print(f"识别到约束 : {'；'.join(intent_data['constraints']) or '（无）'}")
    print()
    print(
        f"token 估算 : {report['tokens_before']} → {report['tokens_after']} "
        f"({report['token_delta']:+d}, {report['token_delta_pct']:+.1f}%)"
    )
    print(f"体积评价   : {report['verdict']}")
    print(f"成本权衡   : {report.get('tradeoff_note', '')}")
    print(f"预计省往返 : 约 {report.get('clarification_rounds_saved', 0)} 轮澄清对话")
    print()
    print(f"质量评分   : {quality.total} / 100 （{quality.grade}）")
    print(f"  ├ 结构分   : {quality.structure}  （四要素齐全度 + 分点密度）")
    print(f"  ├ 原意保留 : {quality.preservation}  （关键词命中 + 原句可追溯）")
    print(f"  └ 精简分   : {quality.compaction}  （冗余剥离比例）")
    print()
    print("生效规则：")
    for rule in result["applied_rules"]:
        print(f"  [{rule['kind']:<8}] {rule['id']:<18} {rule['description']}")
    if result["disabled_rules"]:
        print(f"\n已禁用：{'、'.join(result['disabled_rules'])}")
    print("=" * 64)


def _run_batch(args) -> int:
    from .batch import process_lines, read_input_file, to_csv, to_markdown

    try:
        lines = read_input_file(args.batch)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2

    result = process_lines(
        lines, disable=args.disable, include_raw=not args.no_raw
    )

    print(f"总条数：{result.total}  成功：{result.succeeded}  失败：{result.failed}")
    print(f"平均质量分：{result.avg_score}")

    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(result))
        print(f"Markdown 报告已写入：{args.out_md}")

    if args.out_csv:
        with open(args.out_csv, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(to_csv(result))
        print(f"CSV 已写入：{args.out_csv}")

    if not args.out_md and not args.out_csv:
        for item in result.items:
            print(f"\n--- [{item.index}] {item.score} 分 / {item.grade} ---")
            print(item.output if item.ok else f"失败：{item.error}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_rules:
        _print_rule_list()
        return 0

    if args.batch:
        return _run_batch(args)

    try:
        text = _read_input(args.text)
    except SystemExit as exc:
        return int(exc.code)

    try:
        if args.json:
            result = refine_with_report(
                text, disable=args.disable, include_raw=not args.no_raw
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.score:
            quality = score_text(text)
            print(f"{quality.total} / 100 （{quality.grade}）")
            print(
                f"结构 {quality.structure} · 原意保留 {quality.preservation} "
                f"· 精简 {quality.compaction}"
            )
            return 0

        if args.report:
            result = refine_with_report(
                text, disable=args.disable, include_raw=not args.no_raw
            )
            print(result["output"])
            print()
            _print_report(result)
            return 0

        print(refine(text, disable=args.disable, include_raw=not args.no_raw))
        return 0

    except (TypeError, ValueError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
