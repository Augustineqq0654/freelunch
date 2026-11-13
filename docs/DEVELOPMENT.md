# 本地开发

## 准备环境

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e .
```

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `python scripts/build.py` | 校验数据、生成 README.md 和 dist/ |
| `python scripts/build.py --check` | 只校验，用于 CI（README 与数据不一致就失败） |
| `python scripts/build.py --stale` | 列出超过 60 天没核验、以及从未核验的条目 |
| `python -m http.server -d dist` | 本地预览站点（必须走 HTTP，`file://` 下 fetch 会被拦） |

## 目录结构

```
data/llm-api/      每条资源一个 YAML，是唯一数据源
scripts/lib.py     数据模型与校验规则
scripts/build.py   生成 README / data.json / 静态站
site/              纯前端单页（原生 HTML/CSS/JS）
dist/              构建产物，已 gitignore，由 CI 生成并部署
docs/              收录规则、排除清单、核验手册
```

## 设计取舍

几个刻意的选择，改动前请先想清楚：

- **一条资源一个文件**。多人同时提 PR 不会在同一处冲突，review 也只需要看一个文件。
- **README 是生成物**。手改 README 会被 CI 打回。"数据改了但忘了重新生成"是这类仓库最常见的腐烂方式。
- **不落盘的状态字段**。`freshness`（已核验/待复核/待核验）由 `checked_at` 实时算出来，不存成字段，避免两处真相。
- **零前端依赖**。没有框架、没有打包器、没有 node_modules。一个静态页面的维护成本应该与之匹配。
- **构建零网络**。`build.py` 不请求任何外部资源，同样的数据必然得到同样的输出，CI 才能用 diff 判定产物是否最新。

## 发布前要改的地方

仓库刚建出来时用的是占位地址，正式发布前替换这三处：

| 位置 | 改什么 |
| --- | --- |
| `scripts/lib.py` 的 `REPO_URL` | 改成真实仓库地址，站点的"GitHub 仓库"链接用它 |
| `.github/ISSUE_TEMPLATE/config.yml` | 讨论区链接 |
| `scripts/build.py` 的 README 模板 | 「数据怎么用」里的 `your-name.github.io` 示例 |

另外需要在仓库设置里做两件事：

1. **Settings → Pages → Source** 选 `GitHub Actions`（不是分支），否则 `pages.yml` 部署不生效
2. **Actions → General → Workflow permissions** 允许读写，`stale.yml` 才能自动开 issue

## 依赖

运行时只有 `pydantic`（校验）和 `PyYAML`（读数据）。模板用 f-string 拼，没有引入模板引擎——两个模板而已，多一层抽象反而难改。
