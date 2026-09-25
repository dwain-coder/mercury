"""Content model: config, sources, properties, areas, pages, backlog.

Everything is read from content/ — TOML for structured data, HTML with TOML front matter for
pages. No database: the whole publication is a directory a human can review in a diff.
"""

from __future__ import annotations

import datetime as dt
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

PAGE_TYPES = {"property", "comparison", "article", "hub", "index", "about", "contact"}
STATUSES = {"published", "review", "draft"}
INTENTS = {"transactional", "commercial", "informational", "navigational"}


# --------------------------------------------------------------------------- config

@dataclass
class Config:
    raw: dict

    def get(self, dotted: str, default: str = "") -> str:
        """site.toml value, overridden by HM_<DOTTED_UPPER> in the environment."""
        env = "HM_" + dotted.replace(".", "_").upper()
        # booking.url -> HM_BOOKING_URL, analytics.website_id -> HM_ANALYTICS_WEBSITE_ID
        if env in os.environ and os.environ[env].strip():
            return os.environ[env].strip()
        node = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return str(node).strip() if node is not None else default

    # Values a release cannot ship without. Each maps to one line in site.toml.
    REQUIRED = {
        "publisher": "運営者名（About と Organization schema）",
    }
    # Operator decisions 2026-09-25: booking.url unset = CTAs fall back to the on-page search
    # widget (same marker); no analytics (re-add the /about/ measurement paragraph if a
    # website_id is ever set); contact page unpublished, so contact_endpoint is unused.
    RECOMMENDED = {"booking.url": "Travelpayouts の予約リンク（未設定なら検索ウィジェットへ）"}

    def missing(self, which: dict) -> list[str]:
        return [k for k in which if not self.get(k)]


def load_config() -> Config:
    return Config(tomllib.loads((CONTENT / "site.toml").read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- sources

@dataclass
class Source:
    id: str
    title: str
    publisher: str
    url: str
    retrieved: dt.date
    kind: str
    note: str = ""


def load_sources() -> dict[str, Source]:
    data = tomllib.loads((CONTENT / "sources.toml").read_text(encoding="utf-8"))
    return {k: Source(id=k, **v) for k, v in data.items()}


# --------------------------------------------------------------------------- entities

@dataclass
class Fact:
    key: str
    value: str
    source: str
    note: str = ""


@dataclass
class Entity:
    """A property or an area — anything that owns sourced facts."""
    id: str
    kind: str                     # "property" | "area"
    data: dict
    facts: dict[str, Fact]

    def __getattr__(self, name):  # entity.name, entity.page, ...
        try:
            return self.__dict__["data"][name]
        except KeyError as e:
            raise AttributeError(name) from e


def _load_entities(folder: str, kind: str) -> dict[str, Entity]:
    out = {}
    for f in sorted((CONTENT / folder).glob("*.toml")):
        data = tomllib.loads(f.read_text(encoding="utf-8"))
        facts = {k: Fact(key=k, **v) for k, v in data.pop("facts", {}).items()}
        out[data["id"]] = Entity(id=data["id"], kind=kind, data=data, facts=facts)
    return out


def load_entities() -> dict[str, Entity]:
    ents = _load_entities("properties", "property")
    ents.update(_load_entities("areas", "area"))
    return ents


# --------------------------------------------------------------------------- pages

@dataclass
class Page:
    path: Path
    meta: dict
    body: str
    # filled during render
    html: str = ""
    cited: list[str] = field(default_factory=list)
    links: set[str] = field(default_factory=set)      # internal hrefs found in the body

    @property
    def id(self) -> str: return self.meta["id"]
    @property
    def url(self) -> str: return self.meta["url"]
    @property
    def type(self) -> str: return self.meta["type"]
    @property
    def lang(self) -> str: return self.meta.get("lang", "ja")
    @property
    def status(self) -> str: return self.meta.get("status", "draft")
    @property
    def title(self) -> str: return self.meta["title"]
    @property
    def h1(self) -> str: return self.meta.get("h1", self.meta["title"])
    @property
    def nav_title(self) -> str: return self.meta.get("nav_title", self.h1)
    @property
    def updated(self) -> dt.date: return self.meta["updated"]


FRONT = "+++"


def parse_page(path: Path) -> Page:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(FRONT):
        raise ValueError(f"{path}: missing +++ front matter")
    _, fm, body = text.split(FRONT, 2)
    meta = tomllib.loads(fm)
    return Page(path=path, meta=meta, body=body.strip())


def load_pages() -> list[Page]:
    return [parse_page(p) for p in sorted((CONTENT / "pages").rglob("*.html"))]


# --------------------------------------------------------------------------- backlog

def load_backlog() -> list[dict]:
    f = CONTENT / "backlog.toml"
    if not f.exists():
        return []
    return tomllib.loads(f.read_text(encoding="utf-8")).get("item", [])
