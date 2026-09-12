"""PromptRefiner 测试套件。

测试分四组，对应四条对外承诺：
  1. 意图识别正确 —— 输入什么样的任务，认得出
  2. 原意零丢失   —— 优化后核心诉求仍在（这条最重要）
  3. 结构可解析   —— 输出能被程序稳定解析
  4. 规则可插拔   —— disable 生效，边界输入不崩
"""

from __future__ import annotations

import re

import pytest

from promptrefiner import __version__, analyze, optimize, optimize_with_report
from promptrefiner.renderer import render
from promptrefiner.rules import RULES, active_rules
from promptrefiner.tokens import compare, estimate_tokens


# ---------------------------------------------------------------------------
# 1. 意图识别
# ---------------------------------------------------------------------------
class TestAnalyzer:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("帮我写个 Python 爬虫抓取网页", "code"),
            ("写一篇关于春天的散文", "write"),
            ("把这段英文翻译成中文", "translate"),
            ("总结一下这篇文章的要点", "summarize"),
            ("解释一下什么是量子纠缠", "explain"),
            ("对比一下 React 和 Vue 的优缺点", "analyze"),
            ("把这段话润色一下", "transform"),
        ],
    )
    def test_task_detection(self, text, expected):
        assert analyze(text).task_type == expected

    def test_unknown_task_falls_back_to_general(self):
        """不认识的任务不应该报错，应降级为通用任务。"""
        assert analyze("嗯").task_type == "general"

    def test_constraints_extracted(self):
        intent = analyze("写一篇 500 字的文章，要点 3 条，语气正式")
        joined = " ".join(intent.constraints)
        assert "500" in joined
        assert "3" in joined
        assert "正式" in joined

    def test_audience_extracted(self):
        assert analyze("给零基础新手解释一下链表").audience == "零基础新手"

    def test_language_detected(self):
        assert analyze("用英文写一封邮件").language == "英文"

    def test_question_detected(self):
        assert analyze("什么是闭包？").is_question is True
        assert analyze("写一段代码").is_question is False

    def test_keywords_picked_up(self):
        intent = analyze('写一篇关于「机器学习」的科普，用到 Python')
        assert "机器学习" in intent.keywords
        assert any("Python" in k for k in intent.keywords)

    def test_filler_stripped(self):
        intent = analyze("你好，请问能不能帮我写一个函数？谢谢")
        assert "你好" not in intent.core
        assert "谢谢" not in intent.core
        assert "函数" in intent.core

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            analyze("   ")

    def test_non_string_input_raises(self):
        with pytest.raises(TypeError):
            analyze(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. 原意保护 —— 这是本工具最核心的承诺
# ---------------------------------------------------------------------------
class TestIntentPreservation:
    def test_raw_preserved_in_output_by_default(self):
        raw = "帮我写个爬虫抓 B 站视频"
        out = optimize(raw)
        assert raw in out

    def test_raw_can_be_omitted(self):
        raw = "帮我写个爬虫抓 B 站视频"
        out = optimize(raw, include_raw=False)
        assert raw not in out
        assert "爬虫" in out

    def test_core_content_survives(self):
        """关键词必须出现在优化结果里，不能被压缩掉。"""
        raw = "写一篇关于「碳交易」的分析，面向投资人"
        out = optimize(raw)
        assert "碳交易" in out
        assert "投资人" in out

    def test_no_requirement_invented(self):
        """工具不得凭空增加用户没提的需求。

        这里检查输出里不出现"用户没提但常被 AI 硬塞"的典型词。
        """
        raw = "把这句话翻译成英文"
        out = optimize(raw)
        forbidden = ["必须加参考文献", "附上免责声明", "输出盈利预测"]
        for word in forbidden:
            assert word not in out

    def test_guard_line_present(self):
        out = optimize("分析一下这份数据")
        assert "保留我原始诉求" in out


# ---------------------------------------------------------------------------
# 3. 输出结构
# ---------------------------------------------------------------------------
class TestRenderer:
    def test_has_required_sections(self):
        out = optimize("写一封给客户的道歉邮件，语气正式")
        assert "# 任务" in out
        assert "# 约束" in out
        assert "# 输出格式" in out

    def test_sections_are_markdown_headings(self):
        out = optimize("总结这篇文章")
        for line in out.splitlines():
            if line.startswith("#"):
                assert re.match(r"^# .+", line)

    def test_no_duplicate_bullets(self):
        out = optimize("写篇文章")
        bullets = [l for l in out.splitlines() if l.startswith("- ")]
        assert len(bullets) == len(set(bullets))

    def test_user_constraints_come_first(self):
        out = optimize("写篇 800 字的散文，语气正式")
        constraints_block = out.split("# 约束")[1].split("#")[0]
        lines = [l for l in constraints_block.splitlines() if l.startswith("- ")]
        assert "800" in lines[0]

    def test_output_is_stable(self):
        """纯函数：同样输入必须同样输出。"""
        raw = "帮我写个函数计算斐波那契"
        assert optimize(raw) == optimize(raw)

    def test_render_handles_broken_rule(self):
        """单条规则抛异常不应让整体崩掉。"""

        class Boom:
            id = "boom"
            kind = "expand"
            description = "always fails"

            def __call__(self, intent):
                raise RuntimeError("intentional")

        intent = analyze("测试一下")
        out = render(intent, [Boom()])  # type: ignore[list-item]
        assert "# 任务" in out


# ---------------------------------------------------------------------------
# 4. 规则可插拔 + 边界
# ---------------------------------------------------------------------------
class TestRules:
    def test_rule_ids_unique(self):
        ids = [r.id for r in RULES]
        assert len(ids) == len(set(ids))

    def test_disable_removes_rule_effect(self):
        raw = "嗯"
        with_rule = optimize(raw)
        without = optimize(raw, disable=["ambiguity"])
        assert "澄清问题" in with_rule
        assert "澄清问题" not in without

    def test_all_rules_are_callable(self):
        intent = analyze("随便写点什么")
        for rule in RULES:
            assert isinstance(rule(intent), list)

    def test_active_rules_filters(self):
        assert len(active_rules({"ambiguity"})) == len(RULES) - 1
        assert len(active_rules(set())) == len(RULES)

    def test_every_rule_has_kind(self):
        for rule in RULES:
            assert rule.kind in {"expand", "compress", "clarify"}
            assert rule.description


# ---------------------------------------------------------------------------
# 5. 报告与 token
# ---------------------------------------------------------------------------
class TestReport:
    def test_report_shape(self):
        result = optimize_with_report("写个爬虫")
        for key in ("output", "intent", "token_report", "applied_rules", "available_rules"):
            assert key in result

    def test_report_intent_serializable(self):
        import json

        result = optimize_with_report("写个爬虫")
        json.dumps(result, ensure_ascii=False)  # 不该抛异常

    def test_filler_compression_detected(self):
        result = optimize_with_report("你好，请问能不能帮我写个函数，谢谢")
        assert result["token_report"]["token_delta"] < 0 or "compress_filler" in [
            r["id"] for r in result["applied_rules"]
        ]

    def test_token_estimate_chinese(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens("你好世界") > 0

    def test_token_estimate_scales(self):
        short = estimate_tokens("你好")
        long = estimate_tokens("你好" * 50)
        assert long > short

    def test_compare_verdict(self):
        result = compare("你好世界", "你好世界")
        assert result["token_delta"] == 0
        assert result["verdict"] == "基本持平"


class TestEdgeCases:
    def test_very_long_input(self):
        raw = "写一篇关于人工智能的文章，" * 200
        out = optimize(raw)
        assert "# 任务" in out

    def test_only_punctuation(self):
        out = optimize("。。。")
        assert out  # 不该崩，也不该返回空

    def test_emoji_input(self):
        out = optimize("帮我写个文案 🎉🎉")
        assert out

    def test_newlines_in_input(self):
        out = optimize("请帮我：\n1. 写个函数\n2. 加上注释")
        assert "# 任务" in out

    def test_special_chars_no_crash(self):
        out = optimize("写个正则匹配 <a href=\"x\"> & * + ? [] {}")
        assert out

    def test_version_string(self):
        assert re.match(r"^\d+\.\d+\.\d+$", __version__)
