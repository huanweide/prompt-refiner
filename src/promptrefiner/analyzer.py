"""意图分析层：把一段口语化的输入拆成可结构化的零件。

这是整个工具的"理解"部分。它不做语义推理（那需要大模型），
而是用规则把输入里可识别的成分抽出来：

- 任务动词（写/改/翻译/解释/总结…）→ 决定输出模板
- 约束条件（字数、格式、语言、受众…）→ 归入 Constraints
- 目标产物（邮件、代码、文章…）→ 归入 Deliverable
- 疑问 / 指令语气 → 决定 Output Format

设计原则：宁可漏抽，不可错抽。抽不出来的部分原样保留在 Context 里，
交给后续的"忠实回填"步骤，保证原意零丢失。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


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
         "爬虫", "脚本", "正则", "组件", "命令行", "cli", "sql", "程序"],
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
    r"^(?:帮我|帮忙|请帮我|请你|你能|你能不能|可以帮我|能不能帮我)\s*",
    r"(?:谢谢|thanks|thank you|辛苦了)[。.!！\s]*$",
    r"(?:一下吧|一下|的话|然后呢|那个|就是|其实|反正|大概|可能吧)",
    r"(?:尽量|最好能|如果能的话|可以的话)",
]


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


def _strip_fillers(text: str) -> str:
    """剥离客套与冗余，保留任务本体。"""
    out = text.strip()
    for pat in FILLER_PATTERNS:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip(" ，,。.、")


def _detect_task(text: str) -> tuple[str, str]:
    """按优先级匹配任务类型。返回 (type, label)。"""
    lowered = text.lower()
    for task_type, label, keywords in TASK_PATTERNS:
        for kw in keywords:
            if kw.lower() in lowered:
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
