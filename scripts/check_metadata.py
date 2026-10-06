"""校验项目元数据：不允许出现指向别的仓库的链接。

为什么要这个检查
----------------
这个仓库曾经把 `pyproject.toml` 里的 Homepage / Repository / Issues 三个链接
全部写成 `https://github.com/huanweide/prompt-forge` —— 而那个仓库并不存在
（实测 API 返回 404）。

后果很隐蔽：本地开发、跑测试、甚至打包全都正常，只有发布到 PyPI 之后，
项目页上那三个链接点进去才是 404。也就是说问题只在对外可见的那一刻暴露，
而那时已经有人顺着链接点过去了。

这类「别的项目 / 旧名字残留」不可能靠人记着检查，只能钉进 CI。

为什么不用在线校验（真的去请求那个 URL）
--------------------------------------
1. CI 里做网络请求会让构建不稳定，还可能被限流误判；
2. 更重要的是，哪怕是**存在但不对**的仓库（比如指向别人家的项目），
   在线校验也发现不了 —— 它只看 200 不看语义。
所以这里做的是**一致性校验**：所有提到的 GitHub 仓库都必须与当前仓库同名。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    print(
        "需要 Python 3.11+ 才内置 tomllib。\n"
        "本脚本只在 CI 的 lint 任务里跑（那里是 3.13），\n"
        "如果你在本地老版本 Python 上想跑它，请先 pip install tomli。"
    )
    raise SystemExit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# 仓库名。改这个值等于改门禁标准，所以写死而不是自动推断：
# 自动推断（比如取目录名）会让「仓库被改名」这种情况悄悄失去保护。
EXPECTED_REPO = "prompt-refiner"

_GITHUB_URL = re.compile(r"github\.com/([^/]+)/([^/#?\s]+)")


def extract_repo_slugs(text: str) -> list[tuple[str, str, str]]:
    """抽出文本里所有 GitHub 仓库引用，返回 (原始 URL, owner, repo)。"""
    out = []
    for match in _GITHUB_URL.finditer(text):
        url = match.group(0)
        out.append(("https://" + url, match.group(1), match.group(2)))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验项目元数据链接")
    parser.add_argument(
        "--expect-repo", default=EXPECTED_REPO,
        help=f"期望的仓库名（默认 {EXPECTED_REPO}）",
    )
    args = parser.parse_args(argv)

    if not PYPROJECT.exists():
        print(f"找不到 {PYPROJECT}")
        return 1

    try:
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(f"pyproject.toml 解析失败：{exc}")
        return 1

    urls = data.get("project", {}).get("urls", {})
    if not urls:
        print("pyproject.toml 里没有 [project.urls]，无从校验")
        return 1

    bad: list[str] = []
    for name, url in urls.items():
        for full, owner, repo in extract_repo_slugs(str(url)):
            if repo != args.expect_repo:
                bad.append(f"  [{name}] {url}  -> 指向了 {owner}/{repo}")

    if bad:
        print(f"以下元数据链接没有指向 {args.expect_repo}（会是死链或连错仓库）：")
        print("\n".join(bad))
        return 1

    print(f"元数据链接全部指向 {args.expect_repo}（共 {len(urls)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
