# 推广文案包 · PromptRefiner

> 用途：发 B站评论 / 小红书 / 知乎 / V2EX / Reddit 时直接取用。
> 统一文末水印：`ReTri` + GitHub 链接。

---

## 一、一句话卖点（选一个用）

1. **"别人让你配 API Key 才能改提示词，我这个 `pip install` 完就能用。"**
2. **"提示词优化不该花钱。我做了一把不插电的尺子。"**
3. **"你说人话，它给你一段 AI 一次就能听懂的结构化提示词。全程本地，零成本。"**

---

## 二、GitHub 仓库简介（225 字符内）

### 当前已用
```
把口语变提示词。本地跑，零依赖，零 API Key，不花一分钱。Turn casual speech into structured prompts — 100% local, zero dependencies.
```

### 备选（更适合英文流量）
```
Most prompt optimizers rent you another AI. This one is a local rule engine: zero API key, zero cost, deterministic output. Turn casual speech into structured prompts.
```

---

## 三、B站评论（3 版，去 AI 味）

### 版本 A · 痛点切入
```
之前试过几个提示词优化工具，上来第一步全是让你填 API Key，有的还要充钱
其实就是想把话说清楚一点，搞得跟要部署一套系统似的

后来自己写了个本地的，纯 Python 规则引擎，pip install 完就能用
说的原话它会给你拆成 任务/上下文/约束/输出格式 四块
关键是有个「原始诉求」节会把你的原话贴回去，能对照着看有没有被改意思

最爽的是不联网不花钱，扔 CI 里跑批量也没压力
github.com/huanweide/prompt-refiner

ReTri
```

### 版本 B · 对比切入
```
提示词优化这块有个怪现象：工具本身要靠调大模型来工作
等于你再雇一个 AI 帮你改给 AI 的话，还得先交钱

思路换一下——这东西完全可以用规则做，不需要模型
我写了个 PromptRefiner，本地跑，零依赖，零 API Key
同输入同输出，能 diff 能单测，还带质量评分和批量模式

github.com/huanweide/prompt-refiner
觉得有用给个 star

ReTri
```

### 版本 C · 短平快
```
分享个自己写的工具：把口语变结构化提示词，纯本地零依赖零 API Key
不联网不花钱，pip install 就能用，还支持批量

github.com/huanweide/prompt-refiner

ReTri
```

---

## 四、小红书（图文文案）

### 标题（选一）
- `提示词优化工具居然都要收钱？我自己写了个免费的`
- `不会写提示词？让工具帮你把话说清楚 ✨`
- `零成本把口语变成 AI 秒懂的结构化提示词`

### 正文
```
每次问 AI 都要来回好几轮才说清楚
不是 AI 笨，是你那句话它得先猜一遍

试过几个优化工具，第一步全是填 API Key + 掏钱
我就想不明白，把话说清楚这么基础的事为啥要收费

于是自己写了一个 👇
✅ 纯本地运行，不联网
✅ 零依赖，pip install 就用
✅ 不花一分钱，不烧 token
✅ 你说的话→自动拆成 任务/上下文/约束/输出格式
✅ 还会把原话贴回来，能对照检查有没有改你意思

比如你发「帮我写个爬虫抓B站数据 谢谢」
它会给你整理成带角色、约束、输出格式的完整提示词
AI 一轮就出结果，不用来回问

GitHub: huanweide/prompt-refiner

#提示词 #AI工具 #效率工具 #程序员 #开源 #Python

ReTri
```

---

## 五、知乎回答模板

```
先说结论：提示词优化这件事，被过度复杂化了。

现在市面上的工具基本都是一个思路——调用一个大模型来帮你改写提示词。
这个方案没错，但它有三个绕不过去的成本：
1. 你得先有 API Key，还得充钱
2. 每次优化都在烧 token
3. 你得把内容传给第三方服务器

但仔细想想，"把口语整理成结构清晰的指令"这件事，
本质上是文本规整，不是语义创造。规则引擎完全能做。

我按这个思路写了 PromptRefiner：
- 意图分析：识别你在干什么（写代码/写文章/翻译/总结…），抽取约束和关键词
- 规则引擎：补角色、补边界、删冗余、定输出格式，规则可插拔
- 结构渲染：输出 任务/上下文/约束/输出格式 四节 + 原始诉求核对节
- 质量评分：结构分 + 原意保留分 + 精简分，能接 CI 当质量门禁

最大的差别是它不需要任何配置：pip install 完就能用，或者直接复制一个
单文件放进项目。同输入必然同输出，所以可以写单测、可以 diff。

适合的场景是批量和自动化——比如项目里攒了几百条提示词想统一规范，
或者想在 CI 里检查提交的提示词质量。这些场景下，需要 API Key 的方案
成本会高到不可接受。

github.com/huanweide/prompt-refiner （MIT，欢迎 star 和提 issue）

ReTri
```

---

## 六、Reddit / Hacker News（英文）

```
Show HN: PromptRefiner – Turn casual speech into structured prompts, locally

Most prompt optimizers work by renting you another AI: you need an API key,
you pay per call, and your text goes to a third-party server.

But turning casual speech into a structured instruction is largely text
normalization, not semantic creation. That can be done with rules.

PromptRefiner is a pure-Python rule engine:
- Zero dependencies, zero API key, zero cost
- 100% local — nothing leaves your machine
- Deterministic: same input, same output (diffable, unit-testable)
- Batch mode + quality scoring for CI gates
- Also ships as a single file you can copy into any project

pip install prompt-refiner  (or just copy standalone/prompt_refiner.py)

Would love feedback on the rule set and the output format.

https://github.com/huanweide/prompt-refiner
```

---

## 七、发帖节奏建议

| 平台 | 频次 | 注意 |
|---|---|---|
| B站评论 | 随每日推广流程走 | 只在播放量 ≥ 1 万的 AI 相关视频下评论 |
| 小红书 | 每周 1-2 篇 | 配图用工具前后对比截图 |
| 知乎 | 找"提示词工程"相关问题回答 | 不要硬广，先给干货 |
| V2EX / Reddit | 发一次即可 | 英文区用版本六 |

**核心原则**：先讲痛点再给方案，别一上来贴链接。评论区只发一次，不要刷屏。
