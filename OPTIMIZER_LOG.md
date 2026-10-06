# OPTIMIZER_LOG · prompt-refiner（第 1 轮 · 2026-10-06）

> 改这个项目之前先看这个文件，避免推翻上一轮已经想清楚的决定。

## 一、轮转状态

| 项 | 值 |
|---|---|
| 仓库 | huanweide/prompt-refiner |
| star | 0 |
| 主语言 | Python（零依赖） |
| 本轮判定 | **保留 + 单点深度特化** |
| 基线 commit | fb72577（即当时的 GitHub main） |
| 状态文件 | `GH_OPTIMIZER_STATE.json` |

## 二、先摸清事实（动手前）

- 2356 行源码，8 个模块：analyzer（意图）/ rules（可插拔规则）/ renderer（渲染）/ quality（评分）/ batch（批量）/ tokens（估算）/ cli / core。
- 对外有两个入口：**pip 装的包**（`prompt-refiner` 命令）和 **`standalone/prompt_refiner.py`**（号称「复制即用」的单文件版）。
- 已经有 CI：3 个 Python 版本 × 3 个 OS 矩阵 + 一个 lint job，还有 release workflow。
- 已有 93 个测试全通过。**「测试全绿」这件事本身骗了我一次，见第六节。**

## 三、存活评估（规范一：先查同类，别闭门造车）

| 对比对象 | 情况 | 结论 |
|---|---|---|
| fabric 等成熟 prompt 工具 | 功能强，但要调 LLM API | 不同赛道 |
| 各类 prompt-optimizer | 绝大多数依赖在线大模型改写，要 key、要联网、要花钱 | 不同赛道 |

**结论：保留，不转向。**

分水岭在于：本项目的主张不是「我优化得更好」，而是「**不需要 key 的那一种**」。纯本地规则引擎意味着确定性（同样输入必得同样输出）、可 diff、可离线、零成本。这跟「调 API 让大模型帮你改写」是两件事，不存在碾压级替代。

真正的风险不在外部竞争，而在**内部正确性** —— 见下一节。

## 四、方向选择（规范二：二选一）

选 **单点深度特化：意图识别的正确性**。

理由（第一性原理）：这个工具的全部价值押在一件事上 —— 把口语变成结构化提示词。而 `task_type` 一判错，**角色、约束、输出格式三节全部走错分支**，且不会报任何错，只会安静地给你一份措辞漂亮的错误结果。这是最伤的一种 bug，因为它没有症状。

具体到本轮，抓到的核心问题是两类：

1. **英文短关键词的子串误伤**（见下）
2. **两个入口的行为漂移**（见下）

## 五、本轮改了什么

### 5.1 P0 — 英文短关键词子串误伤，导致任务类型判错

`_detect_task` 原来是这样的：

```python
lowered = text.lower()
for task_type, label, keywords in TASK_PATTERNS:
    for kw in keywords:
        if kw.lower() in lowered:      # <-- 朴素子串匹配
            return task_type, label
```

`code` 类的关键词里有 `api` / `cli` / `code` / `sql` / `bug`。于是：

| 关键词 | 误伤的英文词 |
|---|---|
| `api` | **r-api-d**、therap-ist、capit-al |
| `cli` | **cli-mate**、cli-ent |
| `code` | de-code、co-dependent |

实测后果（不是报错，是悄悄给错东西）：

| 输入 | 改前判定 | 改后判定 |
|---|---|---|
| 写一篇关于首都 **rapid** 发展的文章 | code（代码任务） | write ✓ |
| 介绍一下 **climate** 变化的成因 | code（代码任务） | explain ✓ |

「rapid」那例改前的输出是「角色：资深软件工程师 / 输出：代码块 + 关键实现说明」——给一篇普通文章配上代码任务的模板。

**修法**：英文关键词要求左右两侧都不是 ASCII 字母/数字/下划线；中文关键词仍用子串（中文没有词分隔，「帮我写写代码」里的「写代码」就该命中）。

**为什么不用正则的 `\b`**：输入是中英夹杂的，「调用API」两侧都是中文，`\b` 在这儿的语义不可靠。必须显式写边界条件。

**连带修正**：加了词边界后，`decode` 不再能被 `code` 子串蒙中，所以把它显式收进关键词表。同时**刻意没有**收 `json` / `parse` —— 它们常出现在「把这段 json 翻译一下」这种非代码诉求里，而 code 的优先级高于 translate，收了就会把翻译抢成代码任务。**给高优先级类别扩关键词不是免费收益。**

### 5.2 P0 — 两个入口行为漂移

`standalone/prompt_refiner.py` 曾是一份**独立手写**的实现。抽取 15 条常见输入对比，**4 条输出不一致**：

| 输入 | 差异 |
|---|---|
| 做个 CLI 工具管理 dotfiles | 包版判为代码任务，单文件版判为通用任务（它的动词表里漏了 `cli`） |
| 介绍一下 climate 变化的成因 | 包版判成代码任务，单文件版判对（包版被子串 bug 坑了） |
| 翻译这段话成英文 | 包版多一条「语言：英文」约束，单文件版没有 |
| 给小白讲清楚什么是神经网络 | 包版多一条角色设定，单文件版没有 |

两版各修各的、互不知情，**谁也不比谁完整**。而 README 同时推荐两种用法，用户随机拿到其中一种。

**治标 vs 治本**：加个 CI 比diff 只是事后抓。治本是让它们本来就是同一份源码 ——

新增 `scripts/build_standalone.py`，把 `analyzer.py` + `rules.py` + `renderer.py` 拼接成单文件（这三个模块除了顶部相对 import 外没有其他项目内依赖）。现在 `standalone` 是**生成产物**，漂移在结构上不可能发生。

### 5.3 P1 — 原有的一致性测试从未真正生效

仓库里其实**已经有** `TestStandaloneParity`。为什么三分之一的输入不一致它还全绿？

```python
def _load_standalone(self):
    spec = importlib.util.spec_from_file_location("standalone_refiner", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)      # <-- 没把 mod 注册进 sys.modules
    return mod
```

文件里有 `@dataclass`，而 dataclass 在解析字段注解时会查 `sys.modules[cls.__module__]`，模块没登记就得到 `None`，于是：

```
AttributeError: 'NoneType' object has no attribute '__dict__'
```

而且即便它能跑，也**只测了 1 条输入** —— 恰好是两版一致的那条。

**这是本轮最值得记住的一课：假测试比没测试更危险，因为它提供了「已经测过了」的安全感。** 已修复加载方式（先 `sys.modules[...] = mod` 再 `exec_module`）。

### 5.4 P1 — pyproject 三个 URL 指向不存在的仓库

`Homepage` / `Repository` / `Issues` 全部写成 `huanweide/prompt-forge`，实测 API 返回 404。本地开发、跑测试、打包全都正常，**只有发布到 PyPI 之后项目页那三个链接才是死链** —— 问题只在对外可见的那一刻暴露。已修正，并新增 `scripts/check_metadata.py` 把「所有 GitHub 链接必须与本仓库同名」钉进 CI。

### 5.5 P2 — 测试可能测到了别处的同名包

本机环境里有一个 editable 安装指向 `Desktop/Projects/prompt-refiner`（另一份副本），pytest 会**静默 import 到那份源码** —— 测试全绿，但绿的是别人家的代码。新增 `conftest.py` 把仓库内 `src` 顶到 `sys.path` 最前，顺带让 clone 下来不装包也能跑测试。

> ⚠️ **关于那份本地副本**：它落后 origin/main 2 个 commit，且有未提交改动（README.md / CONTRIBUTING.md）。用户的日常工作副本一律只读，**本次刻意没有触碰**。合并 PR 后 pull 即可获得本轮修复。

### 5.6 改动清单

| 类型 | 文件 |
|---|---|
| 新增 | `scripts/build_standalone.py`、`scripts/check_metadata.py`、`conftest.py`、`tests/test_task_boundary.py`、`tests/test_standalone_parity.py` |
| 修改 | `src/promptrefiner/analyzer.py`（词边界 + 收录 decode）、`standalone/prompt_refiner.py`（改为生成产物，324→707 行）、`pyproject.toml`（死链）、`tests/test_quality_and_batch.py`（修加载方式）、`.github/workflows/ci.yml`（两条真门禁）、`README.md` |
| 没动 | `quality.py`、`batch.py`、`tokens.py`、`cli.py`、`core.py`、`renderer.py`、`rules.py` |

## 六、自检证据

| 检查 | 结果 |
|---|---|
| 全量 pytest | **151 passed**（原 93 + 新增 58） |
| Python 3.9 语法兼容 | 17 个文件全部可解析（CI 矩阵含 3.9） |
| CI YAML 解析 | OK（jobs: test / lint） |
| CLI 冒烟 | 参数模式 + stdin 模式均通过 |
| **变异测试** | **5/5 被拦截，基线全绿** |

变异测试明细（往副本里注入我知道是错的改法，验证门禁真的会响）：

| 注入的错误 | 应该被谁拦 | 结果 |
|---|---|---|
| 手工改 standalone 却不重新生成 | `build_standalone --check` | 拦截 ✓ |
| 改了 src 源码但忘记重新生成 | `build_standalone --check` | 拦截 ✓ |
| 元数据链接改回 prompt-forge | `check_metadata` | 拦截 ✓ |
| 词边界匹配被关掉 | `tests/test_task_boundary.py` | 拦截 ✓ |
| 两版重新漂移（包版多一条约束） | `tests/test_standalone_parity.py` | 拦截 ✓ |
| 基线（干净副本） | —— | 全绿 ✓ |

## 七、我自己犯的错

1. **变异测试的注入没验证，制造了一次假警报。** 第一版变异脚本里，检查用的正则经过 Python 字符串 + heredoc 多层转义后，`github\.com` 变成了匹配字面反斜杠的错正则，结果「元数据检查没拦住」——实际是**变异压根没生效**。
   > 这是第二次踩同一个坑（上一轮 live-subtitle 里，变异瞄准的 `return $out` 在源码中根本不存在）。形式上不同，本质是同一个：**变异前必须先 assert 锚点命中**，否则会把自己的 bug 当成门禁失灵。既然靠记性不管用，就得把它变成流程 —— 本轮因此把元数据检查抽成可被独立调用的 `scripts/check_metadata.py`，从根上消除 heredoc 转义这个变量。

2. **编辑测试文件时误删了一行赋值**，导致 `NameError`。改完立刻重跑才暴露。教训：改测试和修改源码一样，改完必须马上验证，不能假设结构没动。

3. **差点顺手加错关键词。** 一开始想给 code 类补 `json` / `parse`，走了一步推理才发现 code 优先级高于 translate，会把「把这段 json 翻译一下」抢成代码任务。已放弃并把原因写进代码注释。

## 八、回滚与兼容

- squash 单 commit，一条 `git revert <commit>` 即可整体撤销。
- `standalone` 的公开 API 保持不变（`refine` / `analyze_intent`），且 `refine` 新增了可选的 `disable` 参数，是旧签名的超集，不会破坏现有调用。
- 生成的单文件版与包版本行为 100% 一致，有 15 条输入的一致性矩阵守着。

## 九、下一轮建议（按性价比）

1. **把 `--check` 接进 release workflow**，避免打包时带上一份过期的 standalone（现在只有 CI 拦，发布路径没拦）。
2. 给 `scripts/` 自己补测试 —— `build_standalone` 的 strip / dedup 逻辑目前只被变异测试间接覆盖。
3. `HARD_CONSTRAINT_PATTERNS` 里「点 / 条」过于宽泛，可能误伤普通量词，可用同一套词边界思路收敛。
4. 中文数字（「三年」「五个要点」）目前识别不到，只有阿拉伯数字能命中。
