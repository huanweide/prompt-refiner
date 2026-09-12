# 发布到 PyPI 指南

> 目标：让 `pip install prompt-refiner` 真的能用。
> 全程只需你操作 **3 步**，其余自动化。

---

## 为什么必须你本人操作

PyPI 账号和 token 属于个人凭据，**任何工具都不该代持**。
这是安全红线，不做例外。

---

## 前置检查（已确认）

| 项目 | 状态 |
|---|---|
| 包名 `prompt-refiner` 在 PyPI | ✅ 未占用（查询返回 404） |
| GitHub 仓库 | ✅ https://github.com/huanweide/prompt-refiner |
| 构建产物 | ✅ sdist + wheel 均已通过 `twine check` |
| 干净环境实测 | ✅ 全新 venv 装 whl 后 CLI/API 正常 |
| 发布流水线 | ✅ `.github/workflows/release.yml` 已就位 |
| 测试套件 | ✅ 93 项全绿 |

**结论：万事俱备，只差一个 PyPI 账号授权。**

---

## 方案 A：Trusted Publishing（推荐，免 token）

这是官方推荐的现代做法，**不需要生成或保存任何 API token**，
靠 GitHub 与 PyPI 之间的 OIDC 信任关系授权，安全性最高。

### 第 1 步：注册 PyPI 账号

访问 https://pypi.org/account/register/ 注册并验证邮箱。

### 第 2 步：配置 Trusted Publisher

1. 登录后访问 https://pypi.org/manage/account/publishing/
2. 在「Add a new pending publisher」表单填：

| 字段 | 填写内容 |
|---|---|
| PyPI Project Name | `prompt-refiner` |
| Owner | `huanweide` |
| Repository name | `prompt-refiner` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

3. 点「Add」

### 第 3 步：创建 GitHub Environment

1. 打开 https://github.com/huanweide/prompt-refiner/settings/environments
2. 点「New environment」，名字填 `pypi`
3. 保存

### 第 4 步：打 tag 触发发布

```bash
cd C:\Users\Administrator\Desktop\Projects\prompt-refiner
git tag v0.1.0
git push origin v0.1.0
```

推完 tag 后，GitHub Actions 会自动：
跑测试 → 打包 → twine check → 装 whl 冒烟 → 发布到 PyPI

**完成。** 之后 `pip install prompt-refiner` 就能用了。

---

## 方案 B：API Token（备选）

不想配 Trusted Publisher 的话，用 token 也行，但**token 是敏感凭据，
绝不能提交进仓库**（本项目 `.gitignore` 已屏蔽 `.pypirc` 与 `.env*`）。

### 第 1 步：生成 token

访问 https://pypi.org/manage/account/token/

- Token name：`prompt-refiner-upload`
- Scope：选「Project: prompt-refiner」（首次发布选「Entire account」）
- 生成后**立刻复制**（只显示一次）

### 第 2 步：本地配置（不要把 token 写进任何文件）

```bash
# 仅当前终端会话有效，用完即弃，不落盘
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-你的token
```

### 第 3 步：构建并上传

```bash
cd C:\Users\Administrator\Desktop\Projects\prompt-refiner
python -m pip install --upgrade build twine
python -m build
twine check dist/*
twine upload dist/*
```

### 安全提醒

- **绝不**把 token 写进 `.env` 并提交
- **绝不**把 token 写进代码或文档
- 上传完执行 `unset TWINE_PASSWORD` 清掉环境变量
- 如果怀疑泄露，立刻去 PyPI 页面吊销重建

---

## 验证发布成功

```bash
# 1. 查 PyPI 页面
curl -s https://pypi.org/pypi/prompt-refiner/json | head -c 200

# 2. 全新环境实测（最可靠）
python -m venv /tmp/test-pypi
/tmp/test-pypi/bin/pip install prompt-refiner   # Windows: Scripts\pip
/tmp/test-pypi/bin/prompt-refiner "帮我写个爬虫"
```

---

## 后续版本发布流程

改完代码后：

1. 更新三处版本号（保持一致）：
   - `pyproject.toml` 的 `version`
   - `src/promptrefiner/__init__.py` 的 `__version__`
2. 跑门禁：`pytest -q` 必须全绿
3. 提交推送
4. 打新 tag 并推送：`git tag v0.1.1 && git push origin v0.1.1`
5. 流水线自动发布

> 版本号必须严格递增。PyPI **不允许**覆盖已发布的版本，传重复版本号会直接报错。
