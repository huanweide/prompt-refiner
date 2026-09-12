"""PromptRefiner 单文件版 —— 零安装，复制即用。

用法（把这个文件整个复制进你的项目）：

    from prompt_refiner import refine

    better = refine("帮我写个爬虫抓B站数据 谢谢")
    print(better)

或者直接命令行：

    python prompt_refiner.py "帮我写个爬虫抓B站数据 谢谢"
    echo "帮我写个爬虫" | python prompt_refiner.py

不依赖任何第三方库，Python 3.8+ 均可运行。
"""

from __future__ import annotations

import re
import sys

__all__ = ["refine", "analyze_intent"]

# ---------------------------------------------------------------------------
# 一、意图识别
# ---------------------------------------------------------------------------
TASK_PATTERNS = [
    ("code", "代码任务", ["写代码", "写个函数", "实现", "重构", "debug", "调试", "bug",
                        "写脚本", "写个脚本", "写程序", "编程", "函数", "接口", "api",
                        "算法", "爬虫", "脚本", "正则", "组件", "命令行", "sql", "程序"]),
    ("write", "写作任务", ["写一篇", "写文章", "写文案", "写邮件", "写报告", "写方案",
                         "写总结", "写小说", "写故事", "写演讲稿", "起草", "帮我写",
                         "写封", "写封信", "写份", "写一段", "文案", "推广语", "公众号", "推文"]),
    ("translate", "翻译任务", ["翻译", "译成", "中译英", "英译中", "translate"]),
    ("summarize", "总结任务", ["总结", "归纳", "提炼", "摘要", "概括", "提取要点", "划重点"]),
    ("explain", "解释任务", ["解释", "讲解", "科普", "是什么意思", "怎么理解", "原理", "介绍一下"]),
    ("analyze", "分析任务", ["分析", "评估", "对比", "优缺点", "调研", "诊断", "排查", "找出问题"]),
    ("transform", "改写任务", ["改写", "润色", "重写", "扩写", "缩写", "改一下", "调整语气", "换个说法"]),
]

HARD_CONSTRAINTS = [
    (r"(\d+)\s*字(?:以内|以下|左右|之内|以上)?", "字数限制：{0} 字"),
    (r"(?:要点|点|建议|步骤|例子|条|项|个理由|个方面)\s*(\d+)\s*(?:个|条|点|项)?", "要点数量：{0} 条"),
    (r"(\d+)\s*(?:个|条)(?:要点|点|建议|步骤|例子|理由|方面)", "要点数量：{0} 条"),
    (r"(?:不超过|最多|最多不超过|不超)\s*(\d+)", "上限：{0}"),
    (r"(?:至少|不少于|不低于)\s*(\d+)", "下限：{0}"),
]

SOFT_CONSTRAINTS = [
    (r"(正式|严谨|专业)", "语气：正式专业"),
    (r"(口语|大白话|通俗|易懂|接地气)", "语气：口语化通俗"),
    (r"(简短|简洁|精简|别啰嗦|不要废话)", "风格：简洁不啰嗦"),
    (r"(详细|详尽|细致|深入)", "风格：详尽深入"),
    (r"(幽默|有趣|生动|活泼)", "风格：轻松生动"),
]

AUDIENCE_PATTERNS = [
    (r"(新手|小白|零基础|初学者|入门)", "零基础新手"),
    (r"(专业|专家|同行|开发者|程序员|工程师)", "专业人士"),
    (r"(孩子|儿童|小学生|中学生)", "学生"),
    (r"(老板|领导|客户|甲方|面试官)", "决策者 / 上级"),
    (r"(投资人|用户|消费者|读者)", "目标用户"),
]

DELIVERABLE_PATTERNS = [
    (r"(邮件|e-?mail)", "邮件"),
    (r"(周报|日报|月报|工作总结)", "工作报告"),
    (r"(报告|方案|策划|计划书|白皮书)", "书面报告"),
    (r"(推广文案|宣传文案|营销文案|广告文案|slogan|宣传语)", "文案"),
    (r"(小说|故事|剧情|章节|剧本)", "叙事文本"),
    (r"(爬虫|脚本|函数|程序|组件|接口|代码)", "代码"),
    (r"(PPT|演示文稿|幻灯片|演讲稿)", "演示材料"),
    (r"(表格|列表|清单|对照表|思维导图)", "结构化表格"),
    (r"(论文|综述|文献|学术)", "学术文本"),
    (r"(散文|诗歌|文章|随笔|推文|博客)", "文章"),
]

QUESTION_WORDS = [
    "是什么", "什么是", "什么叫", "为什么", "为何",
    "怎么理解", "如何理解", "什么意思", "是什么意思",
    "怎么用", "怎么弄", "如何实现", "怎么做", "如何做",
    "哪个", "哪些", "是否", "能不能解释",
]
POLITE_REQUEST_MARKERS = ["帮我", "写", "生成", "做个", "做一个", "实现", "翻译",
                          "总结", "改一下", "优化", "润色", "分析", "设计", "给我",
                          "整理", "列出"]

FILLERS = [
    r"^(?:你好|您好|hi|hello|hey)[，,。!！\s]*",
    r"^(?:请问|想问一下|想问下|我想问|麻烦你|麻烦|劳驾)[，,。\s]*",
    r"^(?:一下|的话|那个|其实|反正)[，,。\s]*",
    r"^(?:帮我|帮忙|请帮我|请你|你能|你能不能|可以帮我|能不能帮我)\s*",
    r"\s*(?:谢谢|多谢|感谢|thanks|thank you|辛苦了)[。.!！~～\s]*$",
    r"[，,]\s*(?:然后呢|那个|其实|反正|大概|可能吧)\s*[，,]",
    r"[，,]\s*(?:一下|的话)\s*[，,]",
    r"(?:然后呢|那个|其实|反正|大概|可能吧|的话|一下吧)[。.!！\s]*$",
    r"(?:尽量|最好能|如果能的话|可以的话)",
]


def _strip_fillers(text: str) -> str:
    """剥离客套与冗余，保留任务本体；并清理残留/重复标点。"""
    out = text.strip()
    for pat in FILLERS:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    out = re.sub(r"^[\s，,。.、；;：:!！?？~～\-]+", "", out)
    out = re.sub(r"[\s，,。.、；;：:!！~～\-]+$", "", out)
    out = re.sub(r"([，,。.、；;：:])\1+", r"\1", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def _detect_task(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for t, label, kws in TASK_PATTERNS:
        if any(k.lower() in lowered for k in kws):
            return t, label
    return "general", "通用任务"


def _collect(text: str):
    found, audience, deliverable, language = [], None, None, None

    for pat, tpl in HARD_CONSTRAINTS + SOFT_CONSTRAINTS:
        if isinstance(tpl, str):
            m = re.search(pat, text)
            if m:
                try:
                    item = tpl.format(*m.groups())
                except Exception:
                    item = tpl
                if item not in found:
                    found.append(item)

    for pat, name in AUDIENCE_PATTERNS:
        if re.search(pat, text) and not audience:
            audience = name
    for pat, name in DELIVERABLE_PATTERNS:
        if re.search(pat, text) and not deliverable:
            deliverable = name

    if re.search(r"(英文|英语|English)", text):
        language = "英文"
    elif re.search(r"(中文|汉语)", text):
        language = "中文"

    if audience:
        found = [c for c in found if not c.startswith("受众：")]

    return found, audience, deliverable, language


def _keywords(text: str) -> list[str]:
    kws = [m.group(1).strip()
           for m in re.finditer(r"[「『\"'“”《]([^」』\"'“”》]{2,30})[」』\"'“”》]", text)]
    stop = {"the", "and", "for", "with", "that", "this", "you", "are", "can"}
    kws += [m.group(0) for m in re.finditer(r"\b[A-Za-z][A-Za-z0-9\.\-\+]{1,20}\b", text)
            if m.group(0).lower() not in stop]
    seen, out = set(), []
    for k in kws:
        if k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out[:8]


def analyze_intent(text: str) -> dict:
    """把输入拆成结构化零件，返回 dict。"""
    if not isinstance(text, str):
        raise TypeError("输入必须是字符串")
    raw = text.strip()
    if not raw:
        raise ValueError("输入不能为空")

    core = _strip_fillers(raw)
    task_type, task_label = _detect_task(raw)
    constraints, audience, deliverable, language = _collect(raw)

    # 疑问判定：疑问词 + 句末问号。双条件能区分
    # "什么是闭包？"（真提问）与"帮我写个爬虫？"（其实是请求）。
    has_qword = any(w in raw for w in QUESTION_WORDS)
    ends_with_qmark = raw.rstrip().endswith(("?", "？"))
    is_q = has_qword and ends_with_qmark
    if is_q and any(m in raw for m in POLITE_REQUEST_MARKERS):
        is_q = False

    return {
        "raw": raw, "core": core or raw, "task_type": task_type,
        "task_label": task_label, "constraints": constraints,
        "audience": audience, "deliverable": deliverable,
        "language": language, "is_question": is_q, "keywords": _keywords(raw),
    }


# ---------------------------------------------------------------------------
# 二、规则补全
# ---------------------------------------------------------------------------
ROLES = {
    "code": "资深软件工程师",
    "write": "专业内容创作者",
    "translate": "专业译者（母语级双语）",
    "summarize": "信息提炼专家",
    "explain": "擅长类比讲解的老师",
    "analyze": "严谨的分析顾问",
    "transform": "文字编辑",
}


def _boundaries(task_type: str) -> list[str]:
    common = ["不要复述我的问题", "直接给结果，不要寒暄"]
    if task_type == "code":
        common.append("给出可直接运行的完整代码，并标注关键行注释")
    elif task_type == "write":
        common.append("不要出现明显的 AI 套话")
    elif task_type == "analyze":
        common.append("区分事实与推测，推测需标注依据")
    return common


def _output_format(intent: dict) -> list[str]:
    if intent["is_question"]:
        return ["输出：先给一句话结论，再给不超过 5 条的支撑理由"]
    t = intent["task_type"]
    if t == "code":
        return ["输出：代码块 + 关键实现说明（不超过 3 句）"]
    if t in ("write", "transform"):
        return ["输出：正文 + 一句话说明你做了哪些取舍"]
    if t == "summarize":
        return ["输出：要点列表，每条不超过 25 字"]
    return ["输出：结构清晰的分点陈述"]


def _dedup(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        k = i.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


# ---------------------------------------------------------------------------
# 三、渲染
# ---------------------------------------------------------------------------
def refine(text: str, *, include_raw: bool = True) -> str:
    """把任意文字精炼为结构化提示词。

    Args:
        text: 原始输入，口语、书面、中英夹杂均可
        include_raw: 是否在结尾附上"原始诉求"节，便于核对原意

    Returns:
        结构化提示词字符串

    Raises:
        TypeError: text 不是字符串
        ValueError: text 为空
    """
    intent = analyze_intent(text)

    context = []
    if intent["task_type"] in ROLES:
        context.append(f"角色：{ROLES[intent['task_type']]}")
    if intent["deliverable"]:
        context.append(f"交付物：{intent['deliverable']}")
    if intent["audience"]:
        context.append(f"目标读者：{intent['audience']}")

    constraints = list(intent["constraints"])
    constraints += _boundaries(intent["task_type"])
    constraints.append("保留我原始诉求的核心意思，不要自行加需求或删减重点")
    constraints.append("只提供完成任务必需的信息，不扩写背景")
    if len(intent["core"]) <= 6:
        constraints.append("输入信息偏少：如关键信息缺失，先提一个最关键的澄清问题再作答")

    fmt = list(_output_format(intent))
    if intent["keywords"]:
        fmt.append(f"必须围绕这些要素展开：{'、'.join(intent['keywords'])}")

    parts = ["# 任务", intent["core"]]

    if context:
        parts += ["", "# 上下文"] + [f"- {c}" for c in _dedup(context)]
    if constraints:
        parts += ["", "# 约束"] + [f"- {c}" for c in _dedup(constraints)]
    if fmt:
        parts += ["", "# 输出格式"] + [f"- {c}" for c in _dedup(fmt)]

    if len(intent["core"]) < len(intent["raw"]):
        parts += ["", f"（已剥离 {len(intent['raw']) - len(intent['core'])} 字客套 / 冗余表达）"]

    if include_raw and intent["raw"] != intent["core"]:
        parts += ["", "# 原始诉求（不得改变）", intent["raw"]]

    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# 四、CLI
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
