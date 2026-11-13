"""构建产物：README.md、dist/data.json、dist/ 静态站。

用法：
    python scripts/build.py            # 生成全部产物
    python scripts/build.py --check    # 只检查 README 是否与数据一致（CI 用）
    python scripts/build.py --stale    # 只输出过期条目报告（定时任务用）

零网络、零随机：同样输入必然得到同样输出，这样 CI 才能用 git diff 判定"忘了重新生成"。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows 控制台默认 GBK，输出中文和 ✓ 会炸；统一按 UTF-8 打印。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # 非文本流或被重定向
        pass

import lib  # noqa: E402

SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"
README = ROOT / "README.md"


def render_readme(resources, stats, generated_at: dt.date) -> str:
    today = generated_at

    def section(title, rows, intro=""):
        if not rows:
            return []
        out = [f"### {title}", ""]
        if intro:
            out += [intro, ""]
        out += [
            "| 服务 | 免费额度 | 代表模型 | OpenAI 兼容 | 国内可达 | 上次核验 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in rows:
            limits = "<br>".join(l.text for l in r.limits[:3]) or "见备注"
            models = "、".join(f"`{m}`" for m in r.models[:3]) or "—"
            compat = f"[✓]({r.base_url})" if r.openai_compatible else "—"
            if r.archived:
                checked = "已归档"
            elif r.verification.checked_at:
                days = (today - r.verification.checked_at).days
                checked = f"{r.verification.checked_at:%Y-%m-%d}（{days} 天前）"
            else:
                checked = "⏳ 待核验"
            name = f"[{r.name}]({r.url})<br><sub>{r.provider}</sub>"
            out.append(
                f"| {name} | {limits} | {models} | {compat} | {r.cn_icon} {r.cn_label} | {checked} |"
            )
        out.append("")
        return out

    active = [r for r in resources if not r.archived]
    archived = [r for r in resources if r.archived]

    body = []
    direct_rows = [r for r in active if r.cn_access == "direct"]
    if direct_rows:
        body += section(
            "🟢 国内可直连",
            direct_rows,
            "无需任何代理，中国大陆网络下可直接调用。",
        )
    else:
        body += [
            "### 🟢 国内可直连",
            "",
            "**暂时是空的**——严格按「长期免费 + 零门槛」筛下来，目前没有同时满足「国内可直连」的服务。",
            "这不是漏了，是筛选口径的结果：海外免费层大多要代理，国内厂商又基本都要实名或手机号。",
            "知道符合条件的，欢迎提 PR 补上。",
            "",
        ]
    body += section(
        "🟡 部分可用",
        [r for r in active if r.cn_access == "partial"],
        "国内多数网络可访问，但存在间歇性超时或需特殊 DNS，生产环境请自备重试。",
    )
    body += section(
        "🔴 需要代理",
        [r for r in active if r.cn_access == "blocked"],
        "中国大陆网络无法直接访问，需要自备网络出口。",
    )
    body += section(
        "⚪ 待实测",
        [r for r in active if r.cn_access == "unknown"],
        "还没有人在中国大陆网络下实测过可达性。这正是最容易上手的贡献点。",
    )
    if archived:
        body += ["### 🗄 已归档", "", "下列服务曾经可用，现在因下线、取消免费额度或收紧门槛而不再推荐。", ""]
        for r in archived:
            body.append(f"- **{r.name}**（{r.provider}）：{r.archived_reason}")
        body.append("")

    verified_note = (
        f"当前 **{len(active)}** 条在用资源，其中 **{stats['verified']}** 条在 "
        f"{lib.STALE_DAYS} 天内核验过，**{stats['unverified']}** 条待首次核验。"
    )

    readme = f"""# 免费午餐 · {lib.REPO_NAME}

> 只收**长期免费**、**零门槛**（不要信用卡、不要实名、不要手机验证）、**能直接用**的大模型 API。

{verified_note}

每个条目都带**核验日期**和**证据链接**。超过 {lib.STALE_DAYS} 天没核验的会自动降级为「待复核」，失效的转入归档——**我们不保留任何一行没人验证过的数据**。

[![站点预览](docs/preview.png)](https://your-name.github.io/{lib.REPO_NAME}/)

---

## 为什么会有这个项目

免费额度最大的问题不是少，而是**烂得快**：昨天还能用的免费层，今天已经要绑卡了；收藏夹里的清单，一半链接打不开。

所以这里不是又一张 Markdown 表格，而是一份**有证据、会过期、能自动维护**的数据：

| | 普通清单 | 本项目 |
| --- | --- | --- |
| 数据形态 | 手写 Markdown | YAML 单一数据源，自动生成 README 与网页 |
| 过期处理 | 无 | 超过 {lib.STALE_DAYS} 天自动降级，失效自动归档 |
| 证据 | 无 | 每条必须附官方文档链接，否则不予合并 |
| 门槛标注 | 常有遗漏 | 信用卡 / 实名 / 手机号，任一项为真即不收 |
| 国内可达性 | 基本没写 | 独立字段 + 实测，单独分组 |
| 机器可读 | 无 | `dist/data.json`，可自行二次开发 |

---

## 资源总表

{"\n".join(body)}

---

## 五分钟用起来

```bash
# 1. 挑一个标了 "国内直连" 且 "OpenAI 兼容" 的服务，去注册拿 key
# 2. 直接用官方 SDK，或者任意 OpenAI 兼容客户端
curl https://api.example.com/v1/chat/completions \\
  -H "Authorization: Bearer $FREE_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"model": "example-model", "messages": [{{"role": "user", "content": "你好"}}]}}'
```

表格里「OpenAI 兼容」一列点了可直接跳转到对应的 `base_url`，多数客户端只要填这两项就能用。

## 数据怎么用

构建产物是纯静态文件，可以直接当数据源：

```bash
curl -s https://your-name.github.io/{lib.REPO_NAME}/data.json | jq '.resources[] | select(.cn_access == "direct") | .name'
```

站点本身也是零后端：`dist/` 是纯 HTML/CSS/JS，`python -m http.server -d dist` 即可本地预览。

## 收录规则

进这张表要同时满足：

1. **长期免费**：不是注册赠送的试用额度，不是限时活动。
2. **零门槛**：不要信用卡、不要实名认证、不要手机验证。这一条由构建脚本强制校验，写进去也过不了 CI。
3. **有官方渠道**：必须是服务商自己的公开产品或免费层，不收中转、反代、逆向接口。
4. **有证据**：附官方文档链接和核验日期。

被排除的、以及为什么排除，记在 [docs/EXCLUDED.md](docs/EXCLUDED.md)——**知道什么不能用，和知道什么能用一样重要**。

完整规则见 [docs/POLICY.md](docs/POLICY.md)。

## 贡献

欢迎两种 PR，都不需要写代码：

- **补一条新资源**：复制 `data/llm-api/_template.yaml`，填好提交即可。
- **核验一条旧资源**：把 `verification` 里的日期和证据更新掉，哪怕结论是「它已经不免费了」——这一样是有效贡献。

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 文档

- [收录规则](docs/POLICY.md) — 什么叫"免费午餐"，以及为什么有些服务不收
- [被排除的服务](docs/EXCLUDED.md) — 看起来该收、实际不收的，逐条写了原因
- [核验手册](docs/VERIFY.md) — 怎么核验一条、国内可达性怎么测
- [本地开发](docs/DEVELOPMENT.md) — 构建、目录结构、设计取舍
- [路线图](docs/ROADMAP.md) — 下一步做什么，以及"要不要放宽门槛"的争论

## 免责声明

本项目与所列服务商无任何关联，不收受任何形式的推广费用。免费额度随时可能调整，**以官方文档为准**；因使用产生的任何后果由使用者自行承担。详见 [DISCLAIMER.md](DISCLAIMER.md)。

## 许可证

MIT。数据可自由取用、二次分发，无需署名。

---

<sub>本文件由 `scripts/build.py` 根据 `data/` 自动生成，请勿直接编辑。最后构建：{generated_at:%Y-%m-%d}</sub>
"""
    return readme


def build_payload(resources, stats, generated_at: dt.date) -> dict:
    return {
        "generated_at": generated_at.isoformat(),
        "repo": lib.REPO_URL,
        "stale_days": lib.STALE_DAYS,
        "stats": stats,
        "resources": [
            {
                **r.model_dump(mode="json", exclude={"verification"}),
                "freshness": r.freshness,
                "cn_label": r.cn_label,
                "verification": {
                    **r.verification.model_dump(mode="json"),
                    "method_label": lib.METHOD_LABEL[r.verification.method],
                },
                "limits_text": [l.text for l in r.limits],
            }
            for r in resources
        ],
    }


def check_stale(resources, today: dt.date) -> int:
    rows = [
        (r, r.freshness)
        for r in resources
        if not r.archived and r.freshness in ("unverified", "stale")
    ]
    if not rows:
        print("✓ 没有需要复核的条目")
        return 0
    for r, fresh in rows:
        if fresh == "unverified":
            print(f"· 待首次核验  {r.id:<28} {r.name}")
        else:
            days = (today - r.verification.checked_at).days
            print(f"· 超过 {days} 天  {r.id:<28} {r.name}")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验 README 是否最新")
    ap.add_argument("--stale", action="store_true", help="只报告过期条目")
    args = ap.parse_args()

    today = dt.date.today()
    resources, problems = lib.load_resources()
    if problems:
        print("✗ 数据校验未通过：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    counts = lib.stats(resources)

    if args.stale:
        n = check_stale(resources, today)
        print(f"\n共 {n} 条需要处理（总计 {counts['active']} 条在用资源）")
        return 0

    readme = render_readme(resources, counts, today)

    if args.check:
        current = README.read_text(encoding="utf-8") if README.exists() else ""
        # 忽略最后构建日期那一行，避免每天的日期变化导致 CI 误报
        strip = lambda s: s.rsplit("最后构建：", 1)[0]
        if strip(current) != strip(readme):
            print("✗ README.md 与数据不一致，请运行 python scripts/build.py", file=sys.stderr)
            return 1
        print("✓ README.md 与数据一致")
        return 0

    README.write_text(readme, encoding="utf-8")

    DIST_DIR.mkdir(exist_ok=True)
    for name in ("index.html", "app.js", "style.css"):
        shutil.copy2(SITE_DIR / name, DIST_DIR / name)
    payload = build_payload(resources, counts, today)
    (DIST_DIR / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"✓ README.md 已生成（{counts['active']} 条在用 + {counts['archived']} 条归档）")
    print(f"✓ dist/ 已生成：data.json、index.html、app.js、style.css")
    print(
        f"  国内直连 {counts['direct']} · 部分可用 {counts['partial']} · "
        f"需代理 {counts['blocked']} · 待实测 {counts['unknown']}"
    )
    print(
        f"  已核验 {counts['verified']} · 待复核 {counts['stale']} · 待核验 {counts['unverified']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
