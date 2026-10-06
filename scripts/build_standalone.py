"""从 src 包生成 standalone 单文件版。

为什么要有这个脚本
------------------
仓库里曾经并存两份实现：`src/promptrefiner/`（PyPI 包）和
`standalone/prompt_refiner.py`（可直接拷走的零依赖单文件）。它们是各写各的，
于是必然漂移。实测抽取 12 条常见输入，有 4 条两版输出不一致：

- 「做个 CLI 工具」—— 包版本判为代码任务，单文件版判为通用任务
  （单文件版的动词表里漏了 "cli"）
- 「介绍一下 climate 变化的成因」—— 包版本判成代码任务，单文件版判对
  （包版本的 "cli" 子串命中了 climate）
- 「翻译这段话成英文」—— 包版本多一条「语言：英文」约束，单文件版没有
- 「给小白讲清楚什么是神经网络」—— 包版本多一条角色设定，单文件版没有

也就是说两版各修各的、互不知情，谁也不比谁完整。README 同时推荐两种用法，
用户随机拿到其中一种，得到不同结果 —— 而这类差异不会报错，只是悄悄给你一份
措辞漂亮但行为不同的工具。

**治标的办法**是加个 CI 检查，每次比对两版输出。但那只是在事后抓。

**治本的办法**是让它们本来就是同一份源码：单文件版不再手写，而是由本脚本
从 src 拼接生成。这样漂移在结构上就不可能发生。

生成策略
--------
单文件版只需要「分析 + 规则 + 渲染」三块，不需要 token 估算 / 批量处理 / CLI。
这三个模块除了顶部的相对 import（`from .analyzer import Intent`）之外没有别的
项目内依赖，所以拼接是可行的：

1. 用 `ast` 精确定位并剔除：相对 import、模块 docstring。
2. 把各模块顶部的标准库 import 汇总去重，统一放在生成文件的头部。
3. 按 analyzer → rules → renderer 顺序拼接（依赖顺序）。
4. 追加精简入口 `refine()` / `analyze_intent()` 和一个最小 CLI。

用法
----
    python scripts/build_standalone.py            # 生成到 standalone/
    python scripts/build_standalone.py --check    # 只检查是否过期，CI 用
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import sys
from typing import Iterable

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src", "promptrefiner")
TARGET = os.path.join(REPO_ROOT, "standalone", "prompt_refiner.py")

# 拼接顺序即依赖顺序：rules 依赖 analyzer，renderer 依赖 rules 与 analyzer
MODULES = ["analyzer", "rules", "renderer"]

HEADER = '''"""PromptRefiner 单文件版 —— 零安装，复制即用。

用法（把这个文件整个复制进你的项目）：

    from prompt_refiner import refine

    better = refine("帮我写个爬虫抓B站数据 谢谢")
    print(better)

或者直接命令行：

    python prompt_refiner.py "帮我写个爬虫抓B站数据 谢谢"
    echo "帮我写个爬虫" | python prompt_refiner.py

不依赖任何第三方库，Python 3.9+ 均可运行。

------------------------------------------------------------------------------
注意：本文件由 `scripts/build_standalone.py` 从 `src/promptrefiner/` 自动生成，
请勿手工编辑 —— 改了会在下次 CI 被判为「已过期」而失败。
要改行为请改 src 下的源文件，然后运行生成器重新产出本文件。
------------------------------------------------------------------------------
"""

from __future__ import annotations

__all__ = ["refine", "analyze_intent", "analyze", "active_rules", "RULES"]

'''

FOOTER = '''

# ---------------------------------------------------------------------------
# 四、精简入口（单文件版不打包 analyze_with_report / batch / quality 模块）
# ---------------------------------------------------------------------------
def refine(text: str, *, disable: list[str] | None = None,
           include_raw: bool = True) -> str:
    """把任意文字精炼为结构化提示词。

    Args:
        text: 原始输入，口语、书面、中英夹杂均可
        disable: 要禁用的规则 id 列表，例如 ["ambiguity"]
        include_raw: 是否在结尾附上"原始诉求"节，便于核对原意

    Returns:
        结构化提示词字符串

    Raises:
        TypeError: text 不是字符串
        ValueError: text 为空
    """
    intent = analyze(text)
    rules = active_rules(set(disable or []))
    return render(intent, rules, include_raw=include_raw)


def analyze_intent(text: str) -> dict:
    """分析与 analyze() 相同，但返回 dict，便于单文件场景直接使用。"""
    return analyze(text).to_dict()


# ---------------------------------------------------------------------------
# 五、CLI
# ---------------------------------------------------------------------------
def _main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--no-raw"]
    include_raw = "--no-raw" not in argv

    if not args:
        if sys.stdin is None or sys.stdin.isatty():
            print('用法：python prompt_refiner.py "你的文字"', file=sys.stderr)
            print('      echo "你的文字" | python prompt_refiner.py', file=sys.stderr)
            return 2
        text = sys.stdin.read()
    else:
        text = " ".join(args)

    try:
        print(refine(text, include_raw=include_raw))
        return 0
    except (TypeError, ValueError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
'''


def _read_lines(path: str) -> list[str]:
    with io.open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def strip_module(source_path: str) -> tuple[list[str], list[str]]:
    """剥掉相对 import 与模块 docstring，返回 (剩余源码行, 标准库 import 行)。

    用 ast 而不是正则：行号精确，不会因为注释里恰好写了 import 就误删。
    """
    lines = _read_lines(source_path)
    source = "\n".join(lines)
    tree = ast.parse(source)

    drop_ranges: list[tuple[int, int]] = []   # (起, 止) 1-based 含两端
    stdlib_imports: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
                # 相对导入（from .analyzer import Intent）—— 拼接后同名已在同文件，删掉
                drop_ranges.append((node.lineno, node.end_lineno or node.lineno))
            else:
                # 标准库导入 —— 同样要删，统一汇总到生成文件头部，避免重复 import
                # 以及 "from __future__ imports must occur at the beginning" 报错
                drop_ranges.append((node.lineno, node.end_lineno or node.lineno))
                stdlib_imports.append(
                    "\n".join(lines[node.lineno - 1: (node.end_lineno or node.lineno)])
                )
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and node.lineno == tree.body[0].lineno
        ):
            # 模块级 docstring —— 拼接后多个 docstring 只会互相覆盖，删掉
            drop_ranges.append((node.lineno, node.end_lineno or node.lineno))

    keep: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if any(start <= idx <= end for start, end in drop_ranges):
            continue
        keep.append(line)

    return keep, stdlib_imports


def dedup_imports(import_blocks: Iterable[str]) -> list[str]:
    """按 module 聚合去重，import xxx 与 from xxx import a, b 合并成一块。"""
    seen: dict[str, set[str]] = {}
    order: list[str] = []

    for block in import_blocks:
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("import "):
                for name in line[len("import "):].split(","):
                    mod = name.strip().split(" as ")[0].strip()
                    if not mod:
                        continue
                    if mod not in seen:
                        seen[mod] = set()
                        order.append(mod)
            elif line.startswith("from "):
                body, _, tail = line[len("from "):].partition(" import ")
                mod = body.strip()
                if mod not in seen:
                    seen[mod] = set()
                    order.append(mod)
                for name in tail.split(","):
                    nm = name.strip().split(" as ")[0].strip()
                    if nm:
                        seen[mod].add(nm)

    out: list[str] = []
    for mod in order:
        if mod == "__future__":
            continue
        names = sorted(seen[mod])
        if names:
            out.append(f"from {mod} import " + ", ".join(names))
        else:
            out.append(f"import {mod}")
    return out


def generate() -> str:
    bodies: list[str] = []
    all_imports: list[str] = []

    for name in MODULES:
        path = os.path.join(SRC_DIR, f"{name}.py")
        body, imports = strip_module(path)
        all_imports.extend(imports)
        title = {"analyzer": "一、意图识别", "rules": "二、规则补全",
                 "renderer": "三、渲染"}[name]
        bodies.append(
            "# " + "-" * 73
            + f"\n# {title}\n# 源码来源：src/promptrefiner/{name}.py\n"
            + "# " + "-" * 73
            + "\n" + "\n".join(body).strip() + "\n"
        )

    parts = [HEADER, "\n".join(dedup_imports(all_imports + ["import sys"])), "\n\n"]
    parts.extend(bodies)
    parts.append(FOOTER)
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 standalone 单文件版")
    parser.add_argument("--check", action="store_true",
                        help="不写文件，只检查现有 standalone 是否已过期")
    args = parser.parse_args()

    produced = generate()

    if args.check:
        if not os.path.exists(TARGET):
            print(f"缺失：{TARGET}（运行 python scripts/build_standalone.py 生成）")
            return 1
        current = io.open(TARGET, encoding="utf-8").read()
        if current != produced:
            print("standalone/prompt_refiner.py 已过期。")
            print("它是 src/promptrefiner/ 的生成产物，不要再手工编辑。")
            print("请运行：python scripts/build_standalone.py")
            return 1
        print("standalone 与 src 完全一致")
        return 0

    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(produced)
    print(f"已生成 {os.path.relpath(TARGET, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
