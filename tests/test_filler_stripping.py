"""填充词剥离的回归测试。

这一组测试来自真实踩坑：填充词剥离看似简单，但删词会留下
孤立标点、重复标点、或残留语气词，输出会很脏。

每条断言对应一次真实发现的问题：
- "，，" 双逗号：删掉「然后呢」后前后标点撞在一起
- "一下 写个函数"：删掉「请问」后残留语气词
- "测试" 而非 "测试一下"：过度剥离改变了语义
"""

from __future__ import annotations

import pytest

from promptrefiner.analyzer import analyze
from promptrefiner.analyzer import _strip_fillers


class TestFillerStripping:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            # 开头客套
            ("你好，帮我写个爬虫", "写个爬虫"),
            ("请问 帮我 总结一下这篇文章 谢谢", "总结一下这篇文章"),
            ("请问一下 写个函数", "写个函数"),
            # 尾部感谢
            ("写个爬虫抓B站数据 谢谢", "写个爬虫抓B站数据"),
            ("写个函数 多谢！", "写个函数"),
            ("总结这篇文章 谢谢", "总结这篇文章"),
            # 句中语气词
            ("帮我写个爬虫，然后呢，加注释", "写个爬虫加注释"),
            # 保留动作意味（不能过度剥离）
            ("测试一下", "测试一下"),
            # 保留句中副词（它承载语义）
            ("帮我写个函数 其实 要递归的", "写个函数 其实 要递归的"),
        ],
    )
    def test_strip_cases(self, raw, expected):
        assert _strip_fillers(raw) == expected

    def test_no_double_punctuation(self):
        """删词后不得留下「，，」这类重复标点。"""
        for raw in [
            "帮我写个爬虫，然后呢，加注释",
            "写个爬虫，一下，加注释",
            "写个函数，，要递归的",
        ]:
            out = _strip_fillers(raw)
            assert "，，" not in out
            assert ",," not in out

    def test_no_leading_trailing_punctuation(self):
        """输出首尾不得有孤立标点或空白。"""
        for raw in ["，写个爬虫", "写个爬虫，", "  写个爬虫  ", "！写个爬虫！"]:
            out = _strip_fillers(raw)
            assert out == out.strip()
            assert out[0] not in "，,。.、；;：:!！"
            assert out[-1] not in "，,。.、；;：:!！~～"

    def test_semantic_content_preserved(self):
        """剥离只能删客套，不能删任务本体。"""
        raw = "你好，请问能不能帮我写个 Python 爬虫抓 B 站数据？谢谢"
        out = _strip_fillers(raw)
        for must_keep in ["Python", "爬虫", "B 站"]:
            assert must_keep in out

    def test_idempotent(self):
        """剥离应当幂等：再剥一次结果不变，说明没有残留脏东西。"""
        for raw in [
            "你好，帮我写个爬虫 谢谢",
            "请问一下 写个函数",
            "帮我写个爬虫，然后呢，加注释",
        ]:
            once = _strip_fillers(raw)
            twice = _strip_fillers(once)
            assert once == twice

    def test_stripped_shorter_or_equal(self):
        """剥离结果不应比原文更长。"""
        for raw in ["你好，帮我写个爬虫 谢谢", "请问一下 写个函数", "写个爬虫"]:
            assert len(_strip_fillers(raw)) <= len(raw)

    def test_empty_after_full_strip_is_safe(self):
        """全是客套的输入，剥离后为空也不应崩——由上层抛 ValueError。"""
        out = _strip_fillers("你好，谢谢")
        assert isinstance(out, str)

    def test_analyze_uses_stripped_core(self):
        intent = analyze("你好，请问能不能帮我写个爬虫？谢谢")
        assert "你好" not in intent.core
        assert "请问" not in intent.core
        assert "谢谢" not in intent.core
        assert "爬虫" in intent.core
