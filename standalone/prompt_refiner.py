"""PromptRefiner 单文件版 —— 零安装，复制即用。

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


import re
from dataclasses import dataclass, field
from typing import Callable, Literal
import sys



# -------------------------------------------------------------------------
# 一、意图识别
# 源码来源：src/promptrefiner/analyzer.py
# -------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 动词表：按优先级从高到低匹配。越靠前的意图越具体。
# ---------------------------------------------------------------------------
TASK_PATTERNS: list[tuple[str, str, list[str]]] = [
    (
        "code",
        "代码任务",
        ["写代码", "写个函数", "写一个函数", "实现", "重构", "debug", "调试",
         "报错", "bug", "写脚本", "写个脚本", "写程序", "编程", "code", "函数",
         "接口", "api", "算法", "性能优化", "单元测试", "写测试",
         "爬虫", "脚本", "正则", "组件", "命令行", "cli", "sql", "程序",
         # 加了词边界后，"decode" 不再能被 "code" 子串蒙中，必须显式收录。
         # 这里刻意不收 json / parse 之类：它们常出现在「把这段 json 翻译一下」
         # 这种非代码诉求里，而 code 的优先级高于 translate，收了就会抢走。
         "decode"],
    ),
    (
        "write",
        "写作任务",
        ["写一篇", "写一篇文章", "写文案", "写邮件", "写报告", "写方案",
         "写总结", "写小说", "写故事", "写演讲稿", "写推广", "写介绍",
         "起草", "拟一份", "拟一个", "帮我写", "帮忙写", "生成文案",
         "写封", "写个邮件", "写封信", "写份", "写一段", "写一节",
         "文案", "推广语", "宣传语", "公众号", "推文", "演讲稿"],
    ),
    (
        "translate",
        "翻译任务",
        ["翻译", "译成", "中译英", "英译中", "translate", "转译"],
    ),
    (
        "summarize",
        "总结任务",
        ["总结", "归纳", "提炼", "摘要", "概括", "summarize", "总结一下",
         "提取要点", "划重点"],
    ),
    (
        "explain",
        "解释任务",
        ["解释", "讲解", "说明一下", "科普", "是什么意思", "怎么理解",
         "为什么", "原理", "explain", "讲清楚", "介绍一下"],
    ),
    (
        "analyze",
        "分析任务",
        ["分析", "评估", "对比", "比较一下", "优缺点", "调研", "研究一下",
         "诊断", "排查", "找出问题", "analyze"],
    ),
    (
        "transform",
        "改写任务",
        ["改写", "润色", "优化一下", "重写", "扩写", "缩写", "改一下",
         "调整语气", "换个说法", "polish", "rewrite"],
    ),
]

# ---------------------------------------------------------------------------
# 约束识别：分"硬约束"（有明确数值/枚举）与"软约束"（风格倾向）
# ---------------------------------------------------------------------------
HARD_CONSTRAINT_PATTERNS: list[tuple[str, str]] = [
    (r"(\d+)\s*字(?:以内|以下|左右|之内|以上)?", "字数限制：{0} 字"),
    (r"(?:要点|点|建议|步骤|例子|条|项|个理由|个方面)\s*(\d+)\s*(?:个|条|点|项)?", "要点数量：{0} 条"),
    (r"(\d+)\s*(?:个|条)(?:要点|点|建议|步骤|例子|理由|方面)", "要点数量：{0} 条"),
    (r"(?:不超过|最多|最多不超过|不超)\s*(\d+)", "上限：{0}"),
    (r"(?:至少|不少于|不低于)\s*(\d+)", "下限：{0}"),
    (r"(周报|日报|月报|表格|列表|清单|分点|markdown|Markdown|JSON|json|表格形式)", "输出形式：{0}"),
]

SOFT_CONSTRAINT_PATTERNS: list[tuple[str, str]] = [
    (r"(正式|严谨|专业)", "语气：正式专业"),
    (r"(口语|大白话|通俗|易懂|接地气)", "语气：口语化通俗"),
    (r"(简短|简洁|精简|别啰嗦|不要废话)", "风格：简洁不啰嗦"),
    (r"(详细|详尽|细致|深入)", "风格：详尽深入"),
    (r"(幽默|有趣|生动|活泼)", "风格：轻松生动"),
    (r"(面向|给|针对)\s*(新手|小白|零基础|初学者)", "受众：零基础新手"),
    (r"(面向|给|针对)\s*(专业|专家|同行|开发者|程序员)", "受众：专业人士"),
    (r"(孩子|儿童|小学生)", "受众：儿童"),
    (r"(英文|英语|English)", "语言：英文"),
    (r"(中文|汉语)", "语言：中文"),
]

# 受众 / 语言 / 场景 的补充抽取（单列出来便于组合）
AUDIENCE_PATTERNS: list[tuple[str, str]] = [
    (r"(新手|小白|零基础|初学者|入门)", "零基础新手"),
    (r"(专业|专家|同行|开发者|程序员|工程师)", "专业人士"),
    (r"(孩子|儿童|小学生|中学生)", "学生"),
    (r"(老板|领导|客户|甲方|面试官)", "决策者 / 上级"),
    (r"(投资人|用户|消费者|读者)", "目标用户"),
]

DELIVERABLE_PATTERNS: list[tuple[str, str]] = [
    (r"(邮件|e-?mail|邮件正文)", "邮件"),
    (r"(周报|日报|月报|工作总结)", "工作报告"),
    (r"(报告|方案|策划|计划书|白皮书)", "书面报告"),
    (r"(推广文案|宣传文案|营销文案|广告文案|slogan|宣传语)", "文案"),
    (r"(小说|故事|剧情|章节|剧本)", "叙事文本"),
    (r"(爬虫|脚本|函数|程序|组件|接口|代码)", "代码"),
    (r"(PPT|演示文稿|幻灯片|演讲稿|演示材料)", "演示材料"),
    (r"(表格|列表|清单|对照表|思维导图)", "结构化表格"),
    (r"(论文|综述|文献|学术)", "学术文本"),
    (r"(散文|诗歌|文章|随笔|推文|博客)", "文章"),
]

# 疑问句特征 → 更适合"对话式回答"而非"指令式提示词"
#
# 注意：中文疑问词的语序多变（"是什么" / "什么是" / "什么叫"），
# 用完整短语匹配会漏。改为"疑问词 + 问号"的组合判定：
# 只要出现疑问词且句末有问号，才算真提问。这样
# "帮我写个爬虫？" 不会因为带问号被误判（它没有疑问词）。
QUESTION_WORDS = [
    "是什么", "什么是", "什么叫", "为什么", "为何",
    "怎么理解", "如何理解", "什么意思", "是什么意思",
    "怎么用", "怎么弄", "如何实现", "怎么做", "如何做",
    "哪个", "哪些", "是否", "能不能解释",
]

# 礼貌性疑问（"能不能帮我写…"）本质是指令，不是提问。
# 若输入同时命中这两类，判定为指令，避免误用对话式模板。
POLITE_REQUEST_MARKERS = [
    "帮我", "写", "生成", "做个", "做一个", "实现", "翻译", "总结",
    "改一下", "优化", "润色", "分析", "设计", "给我", "整理", "列出",
]

# 填充词 / 冗余表达：优化时删除，不损失语义
FILLER_PATTERNS = [
    r"^(?:你好|您好|hi|hello|hey)[，,。!！\s]*",
    r"^(?:请问|想问一下|想问下|我想问|麻烦你|麻烦|劳驾)[，,。\s]*",
    # 上面匹配完 "请问" 后可能残留 "一下"，需再扫一遍开头的语气词
    r"^(?:一下|的话|那个|其实|反正)[，,。\s]*",
    r"^(?:帮我|帮忙|请帮我|请你|你能|你能不能|可以帮我|能不能帮我)\s*",
    # 尾部的感谢与语气词：允许前面有空格，并吃掉尾部标点
    r"\s*(?:谢谢|多谢|感谢|thanks|thank you|辛苦了)[。.!！~～\s]*$",
    # 逗号分隔的语气词（"，然后呢，"）——连同前后标点一起吃掉，
    # 否则删词后会留下孤立的"，，"双标点
    r"[，,]\s*(?:然后呢|那个|其实|反正|大概|可能吧)\s*[，,]",
    r"[，,]\s*(?:一下|的话)\s*[，,]",
    # 句尾语气词
    r"(?:然后呢|那个|其实|反正|大概|可能吧|的话|一下吧)[。.!！\s]*$",
    r"(?:尽量|最好能|如果能的话|可以的话)",
]


def _strip_fillers(text: str) -> str:
    """剥离客套与冗余，保留任务本体。

    顺序很关键：先删填充词（含周边标点），再统一清理残留的
    孤立标点与重复标点。否则会出现「写个爬虫，，加注释」这种脏输出。
    """
    out = text.strip()
    for pat in FILLER_PATTERNS:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)

    # 清理首尾标点与空白
    out = re.sub(r"^[\s，,。.、；;：:!！?？~～\-]+", "", out)
    out = re.sub(r"[\s，,。.、；;：:!！~～\-]+$", "", out)
    # 折叠重复标点（，， → ，）
    out = re.sub(r"([，,。.、；;：:])\1+", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


@dataclass
class Intent:
    """分析结果：把原始输入拆解成结构化零件。"""

    raw: str
    task_type: str = "general"
    task_label: str = "通用任务"
    core: str = ""                      # 去掉填充词后的任务主干
    constraints: list[str] = field(default_factory=list)
    audience: str | None = None
    deliverable: str | None = None
    language: str | None = None
    is_question: bool = False
    keywords: list[str] = field(default_factory=list)
    unparsed: str = ""                  # 没能归类、必须原样保留的部分

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "task_label": self.task_label,
            "core": self.core,
            "constraints": self.constraints,
            "audience": self.audience,
            "deliverable": self.deliverable,
            "language": self.language,
            "is_question": self.is_question,
            "keywords": self.keywords,
            "unparsed": self.unparsed,
        }


_ASCII_WORD = re.compile(r"^[A-Za-z0-9_]+$")

# 英文关键词的两侧边界缓存：同一个关键词会被反复匹配，编译一次复用。
_BOUNDARY_CACHE: dict[str, "re.Pattern[str]"] = {}


def _keyword_boundary_regex(keyword: str) -> "re.Pattern[str]":
    """为纯 ASCII 关键词构造带词边界的正则。

    为什么需要这个：直接子串匹配会让短英文词误伤大量无关单词。
    实测踩到的三个：

        "api" 命中 "r-api-d" / "therap-ist" / "capit-al"
        "cli" 命中 "cli-mate" / "cli-ent"
        "code" 命中 "de-code" / "co-dependent"

    后果是「写一篇关于首都 rapid 发展的文章」被判成代码任务，
    整套模板（角色 / 约束 / 输出格式）全部走错 —— 这是最伤的一种错，
    因为它不报错，只是悄悄给你一份措辞漂亮的错提示词。

    注意不能用 \\b：\\b 依赖 ASCII 与中文的边界定义，
    而这里输入是中英夹杂（"调用API" 里 API 两侧都是中文），
    必须显式规定「左右都不能是 ASCII 字母/数字/下划线」。
    """
    cached = _BOUNDARY_CACHE.get(keyword)
    if cached is None:
        cached = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(keyword.lower()) + r"(?![A-Za-z0-9_])"
        )
        _BOUNDARY_CACHE[keyword] = cached
    return cached


def _keyword_hits(text_lowered: str, keyword: str) -> bool:
    """判断关键词是否命中：英文按词边界，中文按子串。

    中文关键词保持子串匹配，因为中文没有词分隔，
    「写代码」在「帮我写写代码」里就该算命中。
    """
    lowered = keyword.lower()
    if _ASCII_WORD.match(lowered):
        return _keyword_boundary_regex(lowered).search(text_lowered) is not None
    return lowered in text_lowered


def _detect_task(text: str) -> tuple[str, str]:
    """按优先级匹配任务类型。返回 (type, label)。"""
    lowered = text.lower()
    for task_type, label, keywords in TASK_PATTERNS:
        for kw in keywords:
            if _keyword_hits(lowered, kw):
                return task_type, label
    return "general", "通用任务"


def _collect_constraints(text: str) -> tuple[list[str], str | None, str | None, str | None]:
    """抽取约束、受众、产物、语言。"""
    found: list[str] = []
    audience: str | None = None
    deliverable: str | None = None
    language: str | None = None

    for pat, tpl in HARD_CONSTRAINT_PATTERNS:
        m = re.search(pat, text)
        if m:
            found.append(tpl.format(*m.groups()))

    for pat, tpl in SOFT_CONSTRAINT_PATTERNS:
        if re.search(pat, text):
            if tpl not in found:
                found.append(tpl)

    for pat, name in AUDIENCE_PATTERNS:
        if re.search(pat, text) and not audience:
            audience = name

    for pat, name in DELIVERABLE_PATTERNS:
        if re.search(pat, text) and not deliverable:
            deliverable = name

    # 受众若已单列到"上下文"，就不再在"约束"里重复一遍——省 token
    if audience:
        found = [c for c in found if not c.startswith("受众：")]

    if re.search(r"(英文|英语|English)", text):
        language = "英文"
    elif re.search(r"(中文|汉语)", text):
        language = "中文"

    return found, audience, deliverable, language


def _extract_keywords(text: str) -> list[str]:
    """轻量关键词抽取：保留专有名词、英文词、引号内容。

    不引入分词库，只做对提示词最有价值的抽取——这些往往是用户
    真正想强调的主体（产品名、技术名、主题词）。
    """
    keywords: list[str] = []

    # 引号/书名号里的内容，通常是最核心的主题
    for m in re.finditer(r"[「『\"'“”《]([^」』\"'“”》]{2,30})[」』\"'“”》]", text):
        keywords.append(m.group(1).strip())

    # 英文词 / 技术术语
    for m in re.finditer(r"\b[A-Za-z][A-Za-z0-9\.\-\+]{1,20}\b", text):
        word = m.group(0)
        if word.lower() not in {"the", "and", "for", "with", "that", "this", "you", "are", "can"}:
            keywords.append(word)

    # 去重且保序
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        key = kw.lower()
        if key not in seen:
            seen.add(key)
            result.append(kw)
    return result[:8]


def analyze(text: str) -> Intent:
    """主入口：把一段原始输入变成 Intent 对象。"""
    if not isinstance(text, str):
        raise TypeError("输入必须是字符串")

    raw = text.strip()
    if not raw:
        raise ValueError("输入不能为空")

    core = _strip_fillers(raw)
    task_type, task_label = _detect_task(raw)
    constraints, audience, deliverable, language = _collect_constraints(raw)
    keywords = _extract_keywords(raw)

    # 疑问判定：必须有疑问词，且句末是问号（或中英问号）。
    # 双条件能有效区分"什么是闭包？"（真提问）
    # 与"帮我写个爬虫？"（其实是请求）。
    has_qword = any(w in raw for w in QUESTION_WORDS)
    ends_with_qmark = raw.rstrip().endswith(("?", "？"))
    is_question = has_qword and ends_with_qmark

    # 礼貌性请求（"能不能帮我写…"）是指令而非提问，需排除误判
    if is_question and any(m in raw for m in POLITE_REQUEST_MARKERS):
        is_question = False

    # unparsed = 原句去掉已识别的关键词，剩下的部分仍需保留语义。
    # 这里不做破坏性删除，仅记录原始文本供渲染层回填。
    unparsed = core if core else raw

    return Intent(
        raw=raw,
        task_type=task_type,
        task_label=task_label,
        core=unparsed,
        constraints=constraints,
        audience=audience,
        deliverable=deliverable,
        language=language,
        is_question=is_question,
        keywords=keywords,
        unparsed=unparsed,
    )

# -------------------------------------------------------------------------
# 二、规则补全
# 源码来源：src/promptrefiner/rules.py
# -------------------------------------------------------------------------
RuleKind = Literal["expand", "compress", "clarify"]


@dataclass(frozen=True)
class Rule:
    """一条优化规则。"""

    id: str
    kind: RuleKind
    description: str
    apply: Callable[[Intent], list[str]]

    def __call__(self, intent: Intent) -> list[str]:
        return self.apply(intent)


# ---------------------------------------------------------------------------
# expand —— 补全上下文与边界
# ---------------------------------------------------------------------------

def _role_hint(intent: Intent) -> list[str]:
    """按任务类型补一个合适的角色，让模型更快进入状态。"""
    roles = {
        "code": "资深软件工程师",
        "write": "专业内容创作者",
        "translate": "专业译者（母语级双语）",
        "summarize": "信息提炼专家",
        "explain": "擅长类比讲解的老师",
        "analyze": "严谨的分析顾问",
        "transform": "文字编辑",
    }
    role = roles.get(intent.task_type)
    return [f"角色：{role}"] if role else []


def _deliverable_hint(intent: Intent) -> list[str]:
    """明确产物形态，减少模型自由发挥带来的返工。"""
    if intent.deliverable:
        return [f"交付物：{intent.deliverable}"]
    return []


def _audience_hint(intent: Intent) -> list[str]:
    if intent.audience:
        return [f"目标读者：{intent.audience}"]
    return []


def _boundary_hint(intent: Intent) -> list[str]:
    """补边界：提示模型什么不该做。这是最省 token 的"提效"手段。"""
    common = ["不要复述我的问题", "直接给结果，不要寒暄"]
    if intent.task_type == "code":
        common.append("给出可直接运行的完整代码，并标注关键行注释")
    elif intent.task_type == "write":
        common.append("不要出现明显的 AI 套话")
    elif intent.task_type == "analyze":
        common.append("区分事实与推测，推测需标注依据")
    return common


def _intent_guard(intent: Intent) -> list[str]:
    """原意保护：显式声明不得改变原始诉求。"""
    return ["保留我原始诉求的核心意思，不要自行加需求或删减重点"]


# ---------------------------------------------------------------------------
# compress —— 省 token
# ---------------------------------------------------------------------------

def _filler_removed(intent: Intent) -> list[str]:
    """填充词剥离后，若确实变短了，标记已压缩。"""
    if len(intent.core) < len(intent.raw):
        saved = len(intent.raw) - len(intent.core)
        return [f"（已剥离 {saved} 字客套 / 冗余表达）"]
    return []


def _no_redundant_context(intent: Intent) -> list[str]:
    return ["只提供完成任务必需的信息，不扩写背景"]


# ---------------------------------------------------------------------------
# clarify —— 消歧
# ---------------------------------------------------------------------------

def _format_hint(intent: Intent) -> list[str]:
    """定义输出结构，避免模型给一大坨散文。"""
    if intent.is_question:
        return ["输出：先给一句话结论，再给不超过 5 条的支撑理由"]
    if intent.task_type == "code":
        return ["输出：代码块 + 关键实现说明（不超过 3 句）"]
    if intent.task_type in {"write", "transform"}:
        return ["输出：正文 + 一句话说明你做了哪些取舍"]
    if intent.task_type == "summarize":
        return ["输出：要点列表，每条不超过 25 字"]
    return ["输出：结构清晰的分点陈述"]


def _keyword_emphasis(intent: Intent) -> list[str]:
    """把抽取到的关键词显式列出，防止模型忽略主体。"""
    if intent.keywords:
        return [f"必须围绕这些要素展开：{'、'.join(intent.keywords)}"]
    return []


def _ambiguity_flag(intent: Intent) -> list[str]:
    """输入过短时，提示模型先确认再执行。"""
    if len(intent.core) <= 6:
        return ["输入信息偏少：如关键信息缺失，先提一个最关键的澄清问题再作答"]
    return []


# ---------------------------------------------------------------------------
# 规则注册表
# ---------------------------------------------------------------------------
RULES: list[Rule] = [
    Rule("role", "expand", "按任务类型补角色", _role_hint),
    Rule("deliverable", "expand", "明确交付物形态", _deliverable_hint),
    Rule("audience", "expand", "明确目标读者", _audience_hint),
    Rule("boundary", "expand", "补充不做清单，减少废话", _boundary_hint),
    Rule("intent_guard", "expand", "声明原意保护", _intent_guard),
    Rule("compress_filler", "compress", "标记已剥离的冗余", _filler_removed),
    Rule("no_extra_context", "compress", "禁止无关扩写", _no_redundant_context),
    Rule("format", "clarify", "定义输出结构", _format_hint),
    Rule("keyword", "clarify", "强调核心要素", _keyword_emphasis),
    Rule("ambiguity", "clarify", "输入过短时先澄清", _ambiguity_flag),
]


def rules_by_kind(kind: RuleKind) -> list[Rule]:
    return [r for r in RULES if r.kind == kind]


def active_rules(disabled: set[str] | None = None) -> list[Rule]:
    """返回启用中的规则。disabled 集合里的规则会被跳过。"""
    disabled = disabled or set()
    return [r for r in RULES if r.id not in disabled]

# -------------------------------------------------------------------------
# 三、渲染
# 源码来源：src/promptrefiner/renderer.py
# -------------------------------------------------------------------------
SECTION_TASK = "# 任务"
SECTION_CONTEXT = "# 上下文"
SECTION_CONSTRAINTS = "# 约束"
SECTION_FORMAT = "# 输出格式"
SECTION_RAW = "# 原始诉求（不得改变）"

# 哪些规则 id 归入哪一节
CONTEXT_RULES = {"role", "deliverable", "audience"}
CONSTRAINT_RULES = {"boundary", "intent_guard", "no_extra_context", "ambiguity"}
FORMAT_RULES = {"format", "keyword"}
COMPRESS_RULES = {"compress_filler"}


def render(
    intent: Intent,
    rules: list[Rule],
    include_raw: bool = True,
) -> str:
    """把分析结果渲染成结构化提示词。

    Args:
        intent: 分析层输出
        rules: 本次启用的规则
        include_raw: 是否附上"原始诉求"节，用于人工核对原意
    """
    context: list[str] = []
    constraints: list[str] = []
    fmt: list[str] = []
    notes: list[str] = []

    for rule in rules:
        try:
            lines = rule(intent)
        except Exception:  # 单条规则失败不应让整体崩掉
            continue
        if not lines:
            continue

        if rule.id in CONTEXT_RULES:
            context.extend(lines)
        elif rule.id in CONSTRAINT_RULES:
            constraints.extend(lines)
        elif rule.id in FORMAT_RULES:
            fmt.extend(lines)
        elif rule.id in COMPRESS_RULES:
            notes.extend(lines)

    # 用户自带的约束排在最前，工具补的在后 —— 优先级一目了然
    ordered_constraints = list(intent.constraints) + constraints

    parts: list[str] = []

    parts.append(SECTION_TASK)
    parts.append(intent.core or intent.raw)

    if context:
        parts.append("")
        parts.append(SECTION_CONTEXT)
        parts.extend(f"- {c}" for c in _dedup(context))

    if ordered_constraints:
        parts.append("")
        parts.append(SECTION_CONSTRAINTS)
        parts.extend(f"- {c}" for c in _dedup(ordered_constraints))

    if fmt:
        parts.append("")
        parts.append(SECTION_FORMAT)
        parts.extend(f"- {c}" for c in _dedup(fmt))

    if notes:
        parts.append("")
        parts.append(" ".join(notes))

    if include_raw and intent.raw != intent.core:
        parts.append("")
        parts.append(SECTION_RAW)
        parts.append(intent.raw)

    return "\n".join(parts).strip()


def _dedup(items: list[str]) -> list[str]:
    """保序去重，避免规则之间互相叠加产生重复行。"""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out



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
