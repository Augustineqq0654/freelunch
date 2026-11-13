"""freelunch 核心模型与数据装载。

设计约定：
- 一条资源一个 YAML 文件，放在 data/<category>/ 下，文件名即 id。
- 所有校验规则都在这里，构建脚本和 CI 共用同一份。
- 这里出现的字段都必须能同时适用于"大模型 API"和未来的"免费服务器/容器"，
  分类专属字段放 details 之外的同级字段，靠 category 区分语义。
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------- 全局策略

REPO_NAME = "freelunch"
REPO_TAGLINE = "长期免费、零门槛、能直接用的大模型 API"
REPO_URL = "https://github.com/your-name/freelunch"  # 发布前替换

# 超过这个天数没有核验，就进入"待复核"
STALE_DAYS = 60

CATEGORIES = ("llm-api",)
CATEGORY_LABEL = {"llm-api": "大模型 API"}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------- 枚举与中文标签

CnAccess = Literal["direct", "partial", "blocked", "unknown"]
CN_ACCESS_LABEL = {
    "direct": "国内直连",
    "partial": "部分可用",
    "blocked": "需代理",
    "unknown": "待实测",
}
CN_ACCESS_ICON = {"direct": "🟢", "partial": "🟡", "blocked": "🔴", "unknown": "⚪"}
CN_ACCESS_ORDER = {"direct": 0, "partial": 1, "blocked": 2, "unknown": 3}

Unit = Literal[
    "rpm", "rph", "rpd", "tpm", "tph", "tpd", "tokens_month", "requests_month", "neurons_day"
]
UNIT_LABEL = {
    "rpm": "次/分",
    "rph": "次/时",
    "rpd": "次/日",
    "tpm": "token/分",
    "tph": "token/时",
    "tpd": "token/日",
    "tokens_month": "token/月",
    "requests_month": "次/月",
    "neurons_day": "Neurons/日",
}

VerifyMethod = Literal["manual", "api-probe", "http-probe", "unverified"]
METHOD_LABEL = {
    "manual": "人工核验",
    "api-probe": "接口实测",
    "http-probe": "页面探测",
    "unverified": "未核验",
}

Freshness = Literal["verified", "stale", "unverified", "archived"]
FRESHNESS_LABEL = {
    "verified": "已核验",
    "stale": "待复核",
    "unverified": "待核验",
    "archived": "已归档",
}

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# ---------------------------------------------------------------- 模型


class Limit(BaseModel):
    """一条额度限制。刻意做成通用结构，将来"免费服务器"可以复用来描述 vCPU/流量。"""

    model_config = ConfigDict(extra="forbid")

    unit: Unit
    value: int = Field(gt=0)
    model: str | None = None
    note: str | None = None

    @property
    def text(self) -> str:
        label = UNIT_LABEL[self.unit]
        body = f"{self.value:,} {label}"
        if self.model:
            body = f"{self.model}：{body}"
        return body


class Requirements(BaseModel):
    """准入门槛。本项目只收全 false 的资源，这条规则由校验器强制。

    字段存在的意义不是"支持收费门槛"，而是让提交者在填了 true 的时候
    得到一句明确的拒绝理由，而不是稿子被默默关掉。
    """

    model_config = ConfigDict(extra="forbid")

    credit_card: bool = False
    kyc: bool = False
    phone: bool = False
    invite_only: bool = False

    @model_validator(mode="after")
    def _zero_threshold(self) -> "Requirements":
        blocked = [name for name, value in self.model_dump().items() if value]
        if blocked:
            raise ValueError(
                "本项目只收录零门槛资源，以下门槛必须为 false："
                + "、".join(blocked)
                + "。若该服务值得推荐但需要门槛，请改提 PR 到 docs/EXCLUDED.md，说明原因。"
            )
        return self


class Verification(BaseModel):
    """证据链。没有证据的条目只能停在"未核验"。"""

    model_config = ConfigDict(extra="forbid")

    method: VerifyMethod = "unverified"
    checked_at: dt.date | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Verification":
        if self.method == "unverified":
            if self.checked_at is not None:
                raise ValueError("method 为 unverified 时不应填写 checked_at")
            return self
        if self.checked_at is None:
            raise ValueError(f"method={self.method} 必须填写 checked_at（核验日期）")
        if not self.evidence:
            raise ValueError(f"method={self.method} 必须填写 evidence（官方文档或实测记录链接）")
        return self

    def freshness(self, today: dt.date | None = None) -> Freshness:
        if self.checked_at is None:
            return "unverified"
        today = today or dt.date.today()
        return "verified" if (today - self.checked_at).days <= STALE_DAYS else "stale"


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    provider: str
    category: Literal["llm-api"] = "llm-api"

    url: str
    docs: str | None = None
    signup: str | None = None

    # 这两个是本项目最核心的两个筛选维度
    cn_access: CnAccess = "unknown"
    openai_compatible: bool = False
    base_url: str | None = None

    models: list[str] = Field(default_factory=list)
    context_window: int | None = None
    limits: list[Limit] = Field(default_factory=list)
    requirements: Requirements = Field(default_factory=Requirements)

    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    verification: Verification
    archived: bool = False
    archived_reason: str | None = None

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(f"id 必须是小写短横线格式（如 my-provider），当前为 {v!r}")
        return v

    @field_validator("url", "docs", "signup", "base_url")
    @classmethod
    def _https(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError(f"链接必须是 https://开头：{v!r}")
        return v

    @model_validator(mode="after")
    def _coherent(self) -> "Resource":
        if self.openai_compatible and not self.base_url:
            raise ValueError("openai_compatible 为 true 时必须给出 base_url，否则读者没法直接用")
        if self.archived and not self.archived_reason:
            raise ValueError("归档条目必须填写 archived_reason，说明为什么不再推荐")
        if not self.limits and not self.notes:
            raise ValueError("至少要有 limits 或 notes 之一，否则读者不知道免费在哪")
        return self

    # ---- 派生属性（不落盘，构建时计算）

    @property
    def freshness(self) -> Freshness:
        if self.archived:
            return "archived"
        return self.verification.freshness()

    @property
    def cn_label(self) -> str:
        return CN_ACCESS_LABEL[self.cn_access]

    @property
    def cn_icon(self) -> str:
        return CN_ACCESS_ICON[self.cn_access]

    @property
    def sort_key(self) -> tuple:
        return (
            1 if self.archived else 0,
            CN_ACCESS_ORDER[self.cn_access],
            0 if self.openai_compatible else 1,
            self.provider.lower(),
            self.id,
        )


# ---------------------------------------------------------------- 装载


class LoadError(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} 处数据问题")


def load_resources(data_dir: Path = DATA_DIR) -> tuple[list[Resource], list[str]]:
    """读全部 YAML，返回 (资源列表, 问题列表)。不抛异常，方便 CI 一次列全。"""
    resources: list[Resource] = []
    problems: list[str] = []
    seen: dict[str, Path] = {}

    for path in sorted(data_dir.glob("*/*.yaml")):
        if path.name.startswith("_"):  # _template.yaml 之类的脚手架文件
            continue
        rel = path.relative_to(data_dir.parent).as_posix()
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problems.append(f"{rel}: YAML 解析失败 — {exc}")
            continue

        if not isinstance(raw, dict):
            problems.append(f"{rel}: 顶层必须是一个映射（key: value）")
            continue

        try:
            res = Resource(**raw)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"]) or "(文件顶层)"
                msg = err["msg"]
                if msg.startswith("Value error, "):
                    msg = msg[len("Value error, ") :]
                problems.append(f"{rel}: {loc} — {msg}")
            continue

        if res.id in seen:
            problems.append(f"{rel}: id {res.id!r} 与 {seen[res.id]!s} 重复")
            continue
        if path.stem != res.id:
            problems.append(f"{rel}: 文件名应与 id 一致（期望 {res.id}.yaml）")
            continue
        if res.category not in path.parent.name:
            problems.append(f"{rel}: category={res.category} 与所在目录 {path.parent.name} 不符")
            continue

        seen[res.id] = path
        resources.append(res)

    if not resources and not problems:
        problems.append(f"{data_dir} 下没有找到任何 data/<category>/*.yaml")

    resources.sort(key=lambda r: r.sort_key)
    return resources, problems


def stats(resources: list[Resource]) -> dict:
    active = [r for r in resources if not r.archived]
    return {
        "total": len(resources),
        "active": len(active),
        "direct": sum(1 for r in active if r.cn_access == "direct"),
        "partial": sum(1 for r in active if r.cn_access == "partial"),
        "blocked": sum(1 for r in active if r.cn_access == "blocked"),
        "unknown": sum(1 for r in active if r.cn_access == "unknown"),
        "openai": sum(1 for r in active if r.openai_compatible),
        "verified": sum(1 for r in active if r.freshness == "verified"),
        "stale": sum(1 for r in active if r.freshness == "stale"),
        "unverified": sum(1 for r in active if r.freshness == "unverified"),
        "archived": sum(1 for r in resources if r.archived),
    }
