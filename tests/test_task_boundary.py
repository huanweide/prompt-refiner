"""英文关键词词边界回归测试。

背景：_detect_task 原来用朴素子串匹配 `kw in text`，于是短英文关键词
会命中大量无关英文单词：

    "api"  -> rapid / capital / therapist
    "cli"  -> climate / client
    "code" -> decode / codependent

后果不是报错，而是悄悄把任务类型判错 —— 整套模板（角色 / 约束 / 输出格式）
全部走错分支。比如「写一篇关于首都 rapid 发展的文章」会被当成代码任务，
输出「角色：资深软件工程师 / 输出：代码块 + 关键实现说明」。

修法：英文关键词要求左右都不是 ASCII 字母/数字/下划线；中文关键词仍用子串
（中文没有词分隔，「帮我写写代码」里的「写代码」就该命中）。

注意不能用正则的 \\b：本工具输入是中英夹杂（"调用API" 两侧都是中文），
\\b 的语义在这里不可靠，必须显式写边界条件。
"""

from __future__ import annotations

import pytest

from promptrefiner.analyzer import _keyword_hits, analyze


# (输入, 期望任务类型)
EXPECTED = [
    # --- 曾经被误伤的真实场景 ---
    ("写一篇关于首都 rapid 发展的文章", "write"),
    ("介绍一下 climate 变化的成因", "explain"),
    ("capital 是哪个国家的首都", "general"),
    ("这份 therapist 报告帮我总结一下", "summarize"),
    # --- 词边界修好后，真正的代码信号不能丢 ---
    ("做个 CLI 工具管理 dotfiles", "code"),
    ("调用 API 拉取天气数据", "code"),
    ("把这段 SQL 优化一下", "code"),
    ("帮我写个爬虫抓B站数据 谢谢", "code"),
    ("decode 这段 base64", "code"),
    ("用 CLIENT_ID 登录失败，报错了", "code"),
    # --- 中文原有的子串匹配行为不能被破坏 ---
    ("帮我写写代码", "code"),
    ("翻译这段话成英文", "translate"),
    ("给小白讲清楚什么是神经网络", "explain"),
]


@pytest.mark.parametrize("text,expected", EXPECTED)
def test_task_type(text, expected):
    assert analyze(text).task_type == expected, (
        f"{text!r} 判成了 {analyze(text).task_type}，期望 {expected}"
    )


@pytest.mark.parametrize(
    "keyword,text,should_hit",
    [
        ("api", "调用 API 接口", True),
        ("api", "rapid development", False),
        ("api", "the therapist said", False),
        ("cli", "写个 CLI 工具", True),
        ("cli", "climate change", False),
        ("cli", "a client request", False),
        ("code", "写段 code", True),
        ("code", "decode this", False),
        # 中文关键词本来就该是子串匹配
        ("写代码", "帮我写写代码", True),
        ("翻译", "帮我翻译", True),
        # 大小写不敏感
        ("api", "RESTful API", True),
        ("api", "RAPID", False),
    ],
)
def test_keyword_hits(keyword, text, should_hit):
    assert _keyword_hits(text.lower(), keyword) is should_hit, (
        f"关键词 {keyword!r} 对 {text!r} 的判定不对"
    )


def test_no_english_word_leaks_into_unrelated_task():
    """兜底检查：一批常见英文单词不应该把任务带偏到 code。"""
    for word in ["rapid", "climate", "capital", "therapist", "client",
                 "article", "particle", "vocabulary", "magic", "logic"]:
        got = analyze(f"帮我写一篇关于 {word} 的文章").task_type
        assert got == "write", f"{word} 把任务带偏成了 {got}"
