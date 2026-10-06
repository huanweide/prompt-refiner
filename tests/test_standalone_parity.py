"""单文件版与包版本的一致性测试。

这两个入口曾经各自独立实现并漂移：抽取 12 条常见输入有 4 条输出不一致。
现在 standalone 由 scripts/build_standalone.py 从 src 生成，本测试负责
把「两版行为必须完全一致」这件事钉死，也顺便兜住生成器出问题没人发现的情况。

加载方式有个坑：模块里有 @dataclass，dataclass 在解析注解时会去查
sys.modules[cls.__module__]，所以手动 importlib 加载前必须先把模块
注册进 sys.modules，否则报
    AttributeError: 'NoneType' object has no attribute '__dict__'
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from promptrefiner.core import refine as pkg_refine  # noqa: E402

STANDALONE = ROOT / "standalone" / "prompt_refiner.py"


@pytest.fixture(scope="module")
def standalone():
    spec = importlib.util.spec_from_file_location("pr_standalone", STANDALONE)
    module = importlib.util.module_from_spec(spec)
    # 关键：先注册再执行，否则 dataclass 解析注解时会找不到自己的模块对象
    sys.modules["pr_standalone"] = module
    spec.loader.exec_module(module)
    return module


# 覆盖各任务类型 + 曾出过误判的输入
CASES = [
    "帮我写个爬虫抓B站数据 谢谢",
    "解释一下什么是闭包？",
    # 下面两条是词边界 bug 的回归用例：
    # "rapid" 含 "api"、"climate" 含 "cli"，子串匹配会把它们误判成代码任务
    "写一篇关于首都 rapid 发展的文章",
    "介绍一下 climate 变化的成因",
    # standalone 版缺 "cli" 关键词，这条曾判成通用任务
    "做个 CLI 工具管理 dotfiles",
    "调用 API 拉取天气数据",
    "把这段 SQL 优化一下",
    # 下面两条是 standalone 少了语言约束 / 角色设定的回归用例
    "翻译这段话成英文",
    "给小白讲清楚什么是神经网络",
    "帮我总结一下这三年的工作",
    "写封邮件给领导说明项目延期",
    "帮我写个脚本备份文件",
    "用不超过 200 字介绍一下量子计算",
    "这段文案不够口语化，帮我润色一下",
    "分析一下电动汽车的优缺点",
]


@pytest.mark.parametrize("text", CASES)
def test_refine_output_identical(standalone, text):
    """两版对同一输入必须产出完全相同的提示词。"""
    assert standalone.refine(text) == pkg_refine(text), f"输出不一致：{text}"


@pytest.mark.parametrize("text", CASES)
def test_task_type_identical(standalone, text):
    """任务类型判定必须一致，否则会走到完全不同的模板。"""
    from promptrefiner.analyzer import analyze  # noqa: PLC0415

    assert standalone.analyze_intent(text)["task_type"] == analyze(text).task_type, (
        f"任务类型不一致：{text}"
    )


def test_common_keywords_extracted_identically(standalone):
    """关键词抽取也要一致，它会被渲染成「必须围绕这些要素展开」。"""
    from promptrefiner.analyzer import analyze  # noqa: PLC0415

    for text in ["做个 CLI 工具管理 dotfiles", "介绍一下 climate 变化的成因"]:
        assert standalone.analyze_intent(text)["keywords"] == analyze(text).keywords


def test_bad_input_raises_same_as_package(standalone):
    """错误输入的行为也要一致，保持一致的错误契约。"""
    from promptrefiner.core import refine as pk  # noqa: PLC0415

    for bad in ["", "   "]:
        with pytest.raises(ValueError):
            pk(bad)
        with pytest.raises(ValueError):
            standalone.refine(bad)

    with pytest.raises(TypeError):
        standalone.refine(None)
    with pytest.raises(TypeError):
        pk(None)
