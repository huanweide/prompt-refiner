<div align="center">

# 🔨 PromptRefiner

**把口语变提示词。本地跑，零依赖，不花一分钱。**

*写给所有懒得学"提示词工程"、但想让 AI 一次听懂的人*

[![CI](https://github.com/huanweide/prompt-refiner/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/prompt-refiner/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/badge/pypi-coming%20soon-blue)](https://pypi.org/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](pyproject.toml)

[English](#english) · [中文](#中文) · [在线体验](#快速开始)

</div>

---

## 它解决什么问题

你发给 AI 一句话，AI 却反问你三个问题，或者干脆答偏——**这不是 AI 笨，是你的提示词需要一次翻译。**

现有工具的做法是：**再雇一个 AI 来帮你改提示词**。要注册、要充钱、要填 API Key，你的提示词还得先上传到别人的服务器。

PromptRefiner 的做法是：**装一把不插电的尺子。** 纯本地规则引擎，`pip install` 完就能用，不联网、不烧 token、不改你的原意。

### 前后对比

<table>
<tr><th width="50%">你说的话</th><th width="50%">PromptRefiner 的输出</th></tr>
<tr><td>

```
帮我弄个爬虫抓下B站视频
标题和播放量 谢谢
```

↓ 对方 AI 内心活动：

要抓多少条？存哪？
什么语言？要处理反爬吗？

**→ 反问你，或者自己乱猜**

</td><td>

```markdown
# 任务
写个 Python 爬虫抓 B 站视频的标题和播放量

# 上下文
- 角色：资深软件工程师
- 交付物：代码

# 约束
- 不要复述我的问题
- 直接给结果，不要寒暄
- 给出可直接运行的完整代码
- 保留我原始诉求的核心意思

# 输出格式
- 输出：代码块 + 关键实现说明
```

**→ AI 一轮出代码，不再来回**

</td></tr>
</table>

---

## 三个核心承诺

| 承诺 | 怎么保证的 |
|---|---|
| **不改变原意** | 输出末尾永远附「原始诉求（不得改变）」节，你可以逐字核对。关键词抽出来显式列出，压缩只删客套不删语义 |
| **尽量省 token** | 剥离"你好/请问/能不能帮我/谢谢"这类零信息量的填充词；输出用键值对而非长段落 |
| **补充必要上下文** | 按任务类型自动补角色、交付物形态、目标读者、以及最关键的——**"不做清单"**（不要寒暄、不要复述问题），这是最省往返的一招 |

---

## 快速开始

### 方式一：零安装，单文件直接用 ⭐ 推荐

把 [`standalone/prompt_refiner.py`](standalone/prompt_refiner.py) 这一个文件复制进你的项目，完事。

```bash
python prompt_refiner.py "帮我写个爬虫抓B站数据 谢谢"
echo "写篇500字的推广文案，给新手看" | python prompt_refiner.py
```

```python
from prompt_refiner import refine

better = refine("帮我写个爬虫抓B站数据 谢谢")
print(better)
```

不需要 pip、不需要 API Key、不依赖任何第三方库。

### 方式二：pip 安装完整版

```bash
pip install prompt-refiner   # 发布后可用
```

```bash
# 命令行
prompt-refiner "帮我写个爬虫"
cat draft.txt | prompt-refiner
prompt-refiner --report "总结这篇文章"        # 带诊断报告
prompt-refiner --json "写个函数"             # JSON 输出，便于接管道
prompt-refiner --list-rules                  # 查看所有规则
prompt-refiner --batch prompts.txt --out-md  # 批量处理 → Markdown 报告
```

```python
from promptrefiner import refine, refine_with_report, score_text

# 三行接入任何项目
refine("帮我写个爬虫")

# 要诊断信息
r = refine_with_report("总结这篇文章")
print(r["output"])
print(r["token_report"])   # {'tokens_before': 9, 'tokens_after': 118, ...}

# 接进 CI 当质量门禁
assert score_text(open("prompt.txt").read()).total >= 75
```

---

## 为什么不用现成的？（vs. 那些上万 star 的工具）

|  | 主流提示词优化器 | **PromptRefiner** |
|---|---|---|
| 运行前提 | 必须填 API Key、联网、付费 | **零 Key、零联网、零成本** |
| 数据隐私 | 提示词要上传第三方 | **全部本地，内容不出机器** |
| 词元消耗 | 每次优化都烧 token | **0，纯函数计算** |
| 结果确定性 | 每次输出都不一样 | **同输入同输出，可 diff 可单测** |
| 批量处理 | 只能一条条手工粘贴 | **`--batch` 支持，可进 CI** |
| 可量化评估 | 靠人肉感觉 | **自带三维质量分** |
| 中文口语适配 | 偏向英文场景 | **专门为中文口语设计** |

> 不是替代它们，是补上它们覆盖不到的场景：**CI 流水线、批量治理、隐私敏感环境、离线机器。**

---

## 自动精炼流程

```
输入（任意自然语言）
        │
        ▼
┌───────────────────┐
│ 1. 意图分析        │  识别任务类型 / 抽取约束 / 受众 / 关键词
│   analyzer.py     │  剥离填充词，保留任务主干
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ 2. 规则引擎        │  expand : 补角色、交付物、边界
│    rules.py       │  compress: 删客套
│                   │  clarify : 定格式、强调关键词、过短则先澄清
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ 3. 结构渲染        │  输出 任务 / 上下文 / 约束 / 输出格式
│   renderer.py     │  末尾附原始诉求供核对
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ 4. 质量评分        │  结构分 45% + 原意保留分 40% + 精简分 15%
│    quality.py     │  丢原意会被重罚
└─────────┬─────────┘
          ▼
输出（结构化提示词 + 质量分）
```

### 输出格式定义

| 节 | 内容 | 作用 |
|---|---|---|
| `# 任务` | 剥离客套后的任务主干 | 让 AI 一句话抓住重点 |
| `# 上下文` | 角色 / 交付物 / 目标读者 | 补 AI 不知道的背景 |
| `# 约束` | 用户约束 + 不做清单 + 原意保护 | 减少废话与跑偏 |
| `# 输出格式` | 期望的产物形态 + 必须覆盖的要素 | 一次成型，不用返工 |
| `# 原始诉求` | 用户原话 | 人工核对原意是否被改 |

---

## 可插拔规则

```bash
prompt-refiner --list-rules
```

```
[expand] 补全上下文
  role               按任务类型补角色
  deliverable        明确交付物形态
  audience           明确目标读者
  boundary           补充不做清单，减少废话
  intent_guard       声明原意保护

[compress] 压缩冗余
  compress_filler    标记已剥离的冗余
  no_extra_context   禁止无关扩写

[clarify] 消歧澄清
  format             定义输出结构
  keyword            强调核心要素
  ambiguity          输入过短时先澄清
```

不满意哪条？关掉：

```bash
prompt-refiner --disable ambiguity "嗯"
```

```python
refine("你的文字", disable=["ambiguity", "boundary"])
```

---

## 批量模式

项目里攒了 200 条提示词想统一规范？一条命令：

```bash
prompt-refiner --batch prompts.txt --out-md report.md
```

`prompts.txt`（一行一条）:
```text
帮我写个爬虫
总结一下这篇文章的要点
写封给客户的道歉邮件，语气正式
```

产出的 `report.md` 含总览表 + 每条的精炼结果，可直接贴进 PR 做评审。
也支持 CSV 导出（`--out-csv`）和 JSON 输入（`prompts.json`）。

---

## English

**PromptRefiner turns casual speech into structured prompts — locally, with zero dependencies.**

Most prompt-optimizer tools work by *hiring another AI* to rewrite your prompt: you need an API key, you pay per call, and your text goes to a third-party server.

PromptRefiner is a **local rule engine**. No API key. No network. No cost. Deterministic output you can diff and unit-test.

```bash
python prompt_refiner.py "write me a scraper for bilibili"
```

```python
from promptrefiner import refine
print(refine("help me write a web scraper, thanks"))
```

Output:
```markdown
# 任务 / Task
write me a scraper for bilibili

# 上下文 / Context
- Role: Senior software engineer
- Deliverable: code
...
```

Best for: **CI pipelines, batch prompt governance, privacy-sensitive environments, offline machines.**

---

## 项目结构

```
prompt-refiner/
├── standalone/
│   └── prompt_refiner.py      # 单文件零安装版（推荐入口）
├── src/promptrefiner/
│   ├── analyzer.py            # 意图分析
│   ├── rules.py               # 可插拔规则
│   ├── renderer.py            # 结构渲染
│   ├── quality.py             # 质量评分
│   ├── batch.py               # 批量处理
│   ├── tokens.py              # token 估算
│   └── cli.py                 # 命令行
├── tests/                     # 100+ 项测试
├── examples/                  # 真实用例
└── .github/workflows/ci.yml   # 多平台多版本 CI
```

---

## 开发

```bash
git clone https://github.com/huanweide/prompt-refiner.git
cd prompt-refiner
pip install -e ".[dev]"
pytest -q
```

---

## 参与贡献

有用例跑不通？有想要的新规则？欢迎提 Issue 和 PR。

新规则只需要三步：在 `rules.py` 加一个函数 → 注册进 `RULES` → 补一条测试。

---

## License

MIT © [ReTri](https://github.com/huanweide)

<div align="center">

**如果这个工具帮你省下了一次来回对话，点个 Star ⭐ 就是最好的回报**

</div>
