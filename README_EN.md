**中文** · [README.md](./README.md)

<p align="center">
  <img src="assets/banner.svg" alt="PromptRefiner">
</p>

<p align="center">
  <a href="#what-problem-it-solves">Overview</a> · <a href="#three-core-promises">Features</a> · <a href="#quick-start">Quick start</a> · <a href="#how-it-works">How it works</a> · <a href="#pluggable-rules">Extending</a>
</p>

<div align="center">

# PromptRefiner

**Turn casual speech into prompts. Runs locally, zero dependencies, costs nothing.**

*For everyone too lazy to learn "prompt engineering" but wants the AI to get it right the first time*

[![CI](https://github.com/huanweide/prompt-refiner/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/prompt-refiner/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/badge/pypi-coming%20soon-blue)](https://pypi.org/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](pyproject.toml)

[中文](#中文) · [Online demo](#quick-start) · [**▶ Try the demo page**](https://htmlpreview.github.io/?https://github.com/huanweide/prompt-refiner/blob/main/docs/assets/demo.html)

</div>

---

## What problem it solves

You send the AI one sentence, and the AI replies with three questions — or just answers off-target. **That's not the AI being dumb; your prompt needs a translation.**

Existing tools' approach: **hire another AI to rewrite your prompt for you.** You register, pay, fill in an API key, and your prompt gets uploaded to someone else's server.

PromptRefiner's approach: **ship an unplugged ruler.** A pure local rule engine — works the moment `pip install` finishes. No network, no token burn, no changing your original intent.

### Before / after

| What you said | PromptRefiner's output |
|---|---|
| `帮我弄个爬虫抓下B站视频 标题和播放量 谢谢` | `# 任务 / Task` → write a Python scraper for Bilibili video titles and play counts<br>`# 上下文 / Context` → role: senior engineer; deliverable: code<br>`# 约束 / Constraints` → don't echo my question; give result directly; output runnable complete code; keep my core intent<br>`# 输出格式 / Output` → code block + key implementation notes<br>`# 原始诉求 / Original ask` → (your exact words, for verification) |

The AI returns code in one round instead of going back and forth.

---

## Three core promises

| Promise | How it's guaranteed |
|---|---|
| **Doesn't change your intent** | The output always appends an "original ask (must not change)" section you can verify char-by-char. Keywords are extracted and listed explicitly; compression only cuts pleasantries, never semantics |
| **Saves tokens** | Strips zero-information filler like "hello / excuse me / can you help / thanks"; output uses key-value pairs, not long paragraphs |
| **Supplements necessary context** | Auto-adds role, deliverable shape, target reader, and most importantly a **"do-not" list** (no small talk, no echoing the question) — the single biggest round-trip saver |

---

## Who should use it

- You want the AI to **get it right the first time** without learning prompt engineering.
- You need **CI pipelines, batch prompt governance, privacy-sensitive environments, or offline machines** — places where another-AI rewriters can't go.
- You write **Chinese colloquial prompts** and want them structured deterministically.

## Who should NOT use it

- You want **semantic LLM rewriting** — this is a deterministic rule engine, not a model; same input always yields same output.
- You expect it to **call an LLM** — it doesn't; it's pure local computation.
- You only write English and want English-tuned heuristics — it's specifically designed for Chinese colloquial input (English works, but Chinese is the priority).

---

## Quick start

### Method 1: zero-install, single file ⭐ recommended

Copy just [`standalone/prompt_refiner.py`](standalone/prompt_refiner.py) into your project. Done.

> This file is auto-generated from `src/promptrefiner/` by `scripts/build_standalone.py` and behaves **identically** to the pip package (a consistency test guards it in CI). Don't hand-edit it — edits get overwritten on next build and CI fails on "not regenerated". Change `src/` source, then run `python scripts/build_standalone.py`.

```bash
python prompt_refiner.py "帮我写个爬虫抓B站数据 谢谢"
echo "写篇500字的推广文案，给新手看" | python prompt_refiner.py
```

```python
from prompt_refiner import refine

better = refine("帮我写个爬虫抓B站数据 谢谢")
print(better)
```

No pip, no API key, no third-party library.

### Method 2: pip install the full version

```bash
pip install prompt-refiner   # available after release
```

```bash
# CLI
prompt-refiner "帮我写个爬虫"
cat draft.txt | prompt-refiner
prompt-refiner --report "总结这篇文章"        # with diagnostic report
prompt-refiner --json "写个函数"             # JSON output, easy to pipe
prompt-refiner --list-rules                  # view all rules
prompt-refiner --batch prompts.txt --out-md  # batch → Markdown report
```

```python
from promptrefiner import refine, refine_with_report, score_text

# three lines to integrate into any project
refine("帮我写个爬虫")

# with diagnostics
r = refine_with_report("总结这篇文章")
print(r["output"])
print(r["token_report"])   # {'tokens_before': 9, 'tokens_after': 118, ...}

# use as a quality gate in CI
assert score_text(open("prompt.txt").read()).total >= 75
```

---

## Why not use the existing tools? (vs. those 10k+ star tools)

| | Mainstream prompt optimizers | **PromptRefiner** |
|---|---|---|
| Prerequisite | API key, network, paid | **Zero key, zero network, zero cost** |
| Data privacy | Prompt uploaded to third party | **All local, never leaves the machine** |
| Token cost | Every optimization burns tokens | **0, pure function computation** |
| Result determinism | Different every time | **Same input → same output, diffable and unit-testable** |
| Batch | Manual paste one by one | **`--batch` supported, CI-ready** |
| Quantified eval | Human feel | **Built-in 3-dimension quality score** |
| Chinese colloquial fit | English-leaning | **Designed for Chinese colloquial input** |

> Not a replacement — a fill for the scenarios they don't cover: **CI pipelines, batch governance, privacy-sensitive environments, offline machines.**

---

## How it works

```
Input (any natural language)
        │
        ▼
┌───────────────────┐
│ 1. Intent analysis │  detect task type / extract constraints / audience / keywords
│   analyzer.py     │  strip filler, keep task core
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ 2. Rule engine    │  expand : add role, deliverable, boundary
│    rules.py       │  compress: cut pleasantries
│                   │  clarify : set format, emphasize keywords, clarify if too short
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ 3. Structure render│  output Task / Context / Constraints / Output format
│   renderer.py     │  append original ask at the end for verification
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ 4. Quality score  │  structure 45% + intent-kept 40% + conciseness 15%
│    quality.py     │  losing original intent is heavily penalized
└─────────┬─────────┘
          ▼
Output (structured prompt + quality score)
```

### Output format definition

| Section | Content | Purpose |
|---|---|---|
| `# 任务 / Task` | task core after stripping pleasantries | let the AI grab the point in one line |
| `# 上下文 / Context` | role / deliverable / target reader | supply background the AI doesn't know |
| `# 约束 / Constraints` | user constraints + do-not list + intent protection | cut fluff and drift |
| `# 输出格式 / Output` | expected artifact shape + must-cover elements | one-shot, no rework |
| `# 原始诉求 / Original ask` | user's verbatim words | human verification that intent wasn't changed |

---

## Pluggable rules

```bash
prompt-refiner --list-rules
```

```
[expand] complete context
  role               add role by task type
  deliverable        specify deliverable shape
  audience           specify target reader
  boundary           add do-not list, cut fluff
  intent_guard       declare intent protection

[compress] compress redundancy
  compress_filler    mark stripped redundancy
  no_extra_context   forbid irrelevant expansion

[clarify] disambiguate
  format             define output structure
  keyword            emphasize core elements
  ambiguity          clarify first if input too short
```

Don't like one? Turn it off:

```bash
prompt-refiner --disable ambiguity "嗯"
```

```python
refine("你的文字", disable=["ambiguity", "boundary"])
```

---

## Batch mode

Got 200 prompts in a project you want to standardize? One command:

```bash
prompt-refiner --batch prompts.txt --out-md report.md
```

`prompts.txt` (one per line):
```text
帮我写个爬虫
总结一下这篇文章的要点
写封给客户的道歉邮件，语气正式
```

The produced `report.md` has an overview table + each prompt's refined result, ready to paste into a PR for review. CSV export (`--out-csv`) and JSON input (`prompts.json`) are also supported.

---

## Project structure

```
prompt-refiner/
├── standalone/
│   └── prompt_refiner.py      # single-file zero-install version (recommended entry, generated by scripts/, don't hand-edit)
├── scripts/
│   ├── build_standalone.py    # generate single-file from src; --check validates freshness in CI
│   └── check_metadata.py      # verify pyproject links don't point to other repos
├── src/promptrefiner/
│   ├── analyzer.py            # intent analysis
│   ├── rules.py               # pluggable rules
│   ├── renderer.py            # structure render
│   ├── quality.py             # quality score
│   ├── batch.py               # batch processing
│   ├── tokens.py              # token estimate
│   └── cli.py                 # command line
├── tests/                     # 100+ tests
├── examples/                  # real use cases
└── .github/workflows/ci.yml   # multi-platform multi-version CI
```

---

## Development

```bash
git clone https://github.com/huanweide/prompt-refiner.git
cd prompt-refiner
pip install -e ".[dev]"
pytest -q
```

---

## Contributing

A use case that doesn't run? A new rule you want? Issues and PRs welcome.

A new rule is just three steps: add a function in `rules.py` → register it in `RULES` → add a test.

**Current status**: source is open and usable; PyPI release pending authorization (see [publishing guide](docs/publishing.md)). Until PyPI is up, use the single-file version or `git clone` + `pip install -e .`.

---

## Documentation

- [Online demo](https://htmlpreview.github.io/?https://github.com/huanweide/prompt-refiner/blob/main/docs/assets/demo.html) — try it in the browser
- [Promo copy pack](docs/promo.md) — copy templates for sharing across platforms
- [Publishing guide](docs/publishing.md) — how to publish to PyPI

---

## CI gate usage

Ready to drop into CI out of the box: run the tool in your pipeline; it outputs a health score and severity. If any required item is unmet it exits non-zero, blocking the problematic commit (see parameters in Quick start above).

---

## License

MIT © [huanweide](https://github.com/huanweide)

<div align="center">

**If this tool saved you one round-trip conversation, a Star ⭐ is the best thanks**

</div>
