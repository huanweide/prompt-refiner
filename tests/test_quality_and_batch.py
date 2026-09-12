"""质量评分与批量处理的测试。

这两块是本项目区别于"调 LLM 改提示词"类工具的核心能力，
必须有测试兜底——尤其原意保留分，它是安全阀。
"""

from __future__ import annotations

import json

import pytest

from promptrefiner import evaluate, analyze, refine
from promptrefiner.batch import (
    BatchResult,
    process_lines,
    read_input_file,
    to_csv,
    to_markdown,
)
from promptrefiner.quality import (
    evaluate as eval_direct,
    score_compaction,
    score_preservation,
    score_structure,
    score_text,
)


# ---------------------------------------------------------------------------
# 质量评分
# ---------------------------------------------------------------------------
class TestQuality:
    def test_score_text_returns_score(self):
        q = score_text("帮我写个爬虫")
        assert 0 <= q.total <= 100
        assert q.grade in {"优秀", "良好", "及格", "待改进"}

    def test_structure_full_marks_on_complete_output(self):
        out = refine("帮我写个爬虫")
        score, detail = score_structure(out)
        assert score >= 80
        assert detail["sections_missing"] == []

    def test_structure_penalizes_missing_sections(self):
        score, detail = score_structure("# 任务\n随便写点")
        assert score < 60
        assert len(detail["sections_missing"]) > 0

    def test_preservation_high_when_keywords_kept(self):
        raw = '写一篇关于「碳交易」的分析'
        intent = analyze(raw)
        out = refine(raw)
        score, detail = score_preservation(intent, out)
        assert score >= 80
        assert "碳交易" in detail["keywords_hit"]

    def test_preservation_penalizes_lost_keywords(self):
        intent = analyze('写一篇关于「碳交易」的分析')
        score, detail = score_preservation(intent, "完全无关的输出")
        assert score < 60
        assert detail["keywords_missed"]

    def test_raw_traceable_bonus(self):
        raw = "帮我写个爬虫抓数据"
        intent = analyze(raw)
        out = refine(raw)  # 默认含原始诉求节
        _, detail = score_preservation(intent, out)
        assert detail["raw_traceable"] is True

    def test_compaction_full_when_no_filler(self):
        intent = analyze("写个爬虫")
        score, detail = score_compaction(intent, "输出")
        assert detail["stripped_chars"] == 0
        assert score >= 0

    def test_compaction_detects_stripping(self):
        intent = analyze("你好，请问能不能帮我写个爬虫，谢谢谢谢谢谢")
        score, detail = score_compaction(intent, "输出")
        assert detail["stripped_chars"] > 0

    def test_evaluate_returns_all_dimensions(self):
        raw = "帮我写个爬虫"
        q = eval_direct(analyze(raw), refine(raw))
        assert q.structure >= 0
        assert q.preservation >= 0
        assert q.compaction >= 0
        assert set(q.details.keys()) == {"structure", "preservation", "compaction"}

    def test_quality_serializable(self):
        q = score_text("写个函数")
        json.dumps(q.to_dict(), ensure_ascii=False)

    def test_preservation_weighted_heavily(self):
        """丢原意的输出，总分必须明显低于正常输出。"""
        raw = '写一篇关于「区块链」的分析'
        good = score_text(raw)
        intent = analyze(raw)
        bad = eval_direct(intent, "# 任务\n完全无关内容\n# 约束\n- x\n# 输出格式\n- y")
        assert good.total > bad.total


# ---------------------------------------------------------------------------
# 批量处理
# ---------------------------------------------------------------------------
class TestBatch:
    def test_process_lines_basic(self):
        result = process_lines(["帮我写个爬虫", "总结这篇文章"])
        assert result.total == 2
        assert result.succeeded == 2
        assert result.avg_score > 0

    def test_skips_blank_lines(self):
        result = process_lines(["写个函数", "   ", "", "总结一下"])
        assert result.total == 2

    def test_continues_after_bad_line(self):
        """单条异常不应中断整批，这是批处理的韧性要求。"""
        result = process_lines(["写个爬虫", "\x00\x01坏数据", "总结一下"])
        assert result.total == 3
        # 正常条目仍然成功
        assert result.succeeded >= 2

    def test_each_item_has_score(self):
        result = process_lines(["写个爬虫", "总结文章"])
        for item in result.items:
            assert item.ok
            assert 0 <= item.score <= 100
            assert item.grade

    def test_item_serializable(self):
        result = process_lines(["写个爬虫"])
        json.dumps(result.to_dict(), ensure_ascii=False)

    def test_disable_propagates(self):
        result = process_lines(["嗯"], disable=["ambiguity"])
        assert "澄清问题" not in result.items[0].output

    def test_no_raw_propagates(self):
        result = process_lines(["帮我写个爬虫"], include_raw=False)
        assert "# 原始诉求" not in result.items[0].output

    def test_empty_input_returns_empty(self):
        result = process_lines([])
        assert result.total == 0
        assert result.avg_score == 0.0

    def test_to_markdown_has_table(self):
        md = to_markdown(process_lines(["写个爬虫"]))
        assert "# PromptRefiner 批量精炼报告" in md
        assert "| # |" in md

    def test_to_markdown_escapes_pipe(self):
        md = to_markdown(process_lines(["写个 a|b 函数"]))
        assert "\\|" in md

    def test_to_csv_has_header(self):
        csv_text = to_csv(process_lines(["写个爬虫"]))
        assert csv_text.splitlines()[0].startswith("index,ok,score")

    def test_read_txt_file(self, tmp_path):
        f = tmp_path / "p.txt"
        f.write_text("帮我写个爬虫\n总结一下\n", encoding="utf-8")
        lines = read_input_file(f)
        assert len(lines) == 2

    def test_read_json_array(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps(["写个爬虫", "总结一下"], ensure_ascii=False), encoding="utf-8")
        assert len(read_input_file(f)) == 2

    def test_read_json_object_with_prompts(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({"prompts": ["a", "b"]}), encoding="utf-8")
        assert len(read_input_file(f)) == 2

    def test_read_json_invalid_shape(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({"wrong": 1}), encoding="utf-8")
        with pytest.raises(ValueError):
            read_input_file(f)

    def test_read_missing_file(self):
        with pytest.raises(FileNotFoundError):
            read_input_file("不存在的文件.txt")

    def test_batch_result_counts(self):
        r = BatchResult()
        assert r.total == 0
        assert r.avg_score == 0.0


# ---------------------------------------------------------------------------
# 单文件版与包版一致性
# ---------------------------------------------------------------------------
class TestStandaloneParity:
    """单文件版必须和包版行为一致，否则用户会踩坑。"""

    def _load_standalone(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).parent.parent / "standalone" / "prompt_refiner.py"
        spec = importlib.util.spec_from_file_location("standalone_refiner", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_standalone_importable(self):
        mod = self._load_standalone()
        assert hasattr(mod, "refine")

    def test_standalone_zero_third_party(self):
        """单文件版不得引入第三方库，这是它"零安装"的根基。"""
        from pathlib import Path

        src = (Path(__file__).parent.parent / "standalone" / "prompt_refiner.py").read_text(
            encoding="utf-8"
        )
        forbidden = ["import requests", "import openai", "import numpy", "import pandas"]
        for f in forbidden:
            assert f not in src

    def test_standalone_output_matches_package(self):
        mod = self._load_standalone()
        raw = "帮我写个爬虫抓B站数据 谢谢"
        assert mod.refine(raw) == refine(raw)

    def test_standalone_question_detection(self):
        mod = self._load_standalone()
        assert mod.analyze_intent("什么是闭包？")["is_question"] is True
        assert mod.analyze_intent("帮我写个爬虫？")["is_question"] is False

    def test_standalone_empty_raises(self):
        mod = self._load_standalone()
        with pytest.raises(ValueError):
            mod.refine("  ")
