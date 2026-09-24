"""Quality gate. Runs on every build; errors stop the build.

What it enforces, and why each is a hard rule rather than a guideline:

IDENTITY     The domain's history is the whole risk. The old operator's booking engine,
             phone, fax and mail can never reappear, and the site never speaks as the hotel.
FACTS        A figure with a unit (分, 円, ㎡, 室, km/m) typed straight into prose has no
             source by definition. Figures come from {{fact}} only.
FILLER       The stock phrases of generated copy are banned outright.
INTENT       One target query per page; titles and descriptions unique.
LINKS        No dead internal links, no orphans, every article reaches its parent and at least
             two related pages.
COMMERCIAL   Every CTA is labelled 広告 and rel="sponsored"; CTA density is capped per page type.
SCHEMA       Every JSON-LD block parses; FAQPage only with a visible FAQ; no rating markup.
RELEASE      No placeholders, no preview markers, nothing unpublished linked.
"""

from __future__ import annotations

import json
import re
from collections import Counter, deque

IDENTITY_BANNED = [
    "489.jp", "e-concierge", "03-3866-1211", "03-3866-1216", "reserve@hotelmercury",
    "当ホテル", "当館", "私たちのホテル", "弊社ホテル", "our hotel",
]
FILLER_BANNED = [
    "この記事では", "について詳しく解説します", "詳しく解説していきます", "ぜひ参考にしてください",
    "いかがでしたか", "いかがでしたでしょうか", "紹介していきます", "見ていきましょう",
    "結論から言うと", "Discover Japan", "hidden gem", "隠れた名所",
]
# A number followed by a unit, typed directly in prose.
UNSOURCED_FIGURE = re.compile(
    r"\d[\d,，.〜~\-–]*\s*(分|円|㎡|平米|室|km|ｍ|min|minutes|yen|m²|m(?![a-z²]))")
CTA_LIMIT = {"property": 10, "comparison": 4, "article": 2, "hub": 2, "index": 2,
             "about": 0, "contact": 0}
RELEASE_BANNED = ["#book-unset", "写真枠：", "photo--demo", 'class="preview', "preview-only", "TODO", "lorem",
                  "PENDING"]
# The publication must never be identified by a property's name or mark. 「ホテルマーキュリー」
# is a registered trademark (登録3130305, lodging); on this domain that matters doubly.
BRAND_BANNED = ["マーキュリー", "mercury"]
REQUIRED_META = ["id", "url", "type", "title", "description", "status", "updated", "cluster",
                 "intent"]


def _text_only(body: str) -> str:
    """Prose as a reader sees it, minus shortcodes, tags and attribute values."""
    body = re.sub(r"\{\{.*?\}\}", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return body


def check_brand(cfg) -> list[str]:
    errs = []
    for k in ("name", "name_en", "tagline", "publisher"):
        v = cfg.get(k).lower()
        errs += [f"config {k}: brand must not use '{b}'" for b in BRAND_BANNED if b in v]
    return errs


def check_backlog(pages, backlog) -> list[str]:
    """A planned article may not target a live page's query or claim its URL — that is how
    a site ends up with two pages competing for one search."""
    from .score import priority
    errs = []
    live_q = {p.meta.get("target_query") for p in pages if p.meta.get("target_query")}
    live_u = {p.url for p in pages}
    for b in backlog:
        if b["target_query"] in live_q:
            errs.append(f"backlog '{b['title']}': target_query already owned by a live page")
        if b.get("url") and b["url"] in live_u:
            errs.append(f"backlog '{b['title']}': url already used by a live page")
        try:
            priority(b["score"])
        except ValueError as e:
            errs.append(f"backlog '{b['title']}': {e}")
    return errs


def check_sources(sources) -> list[str]:
    errs = []
    for s in sources.values():
        if not s.url.startswith("https://"):
            errs.append(f"source {s.id}: url must be https")
        if not s.retrieved:
            errs.append(f"source {s.id}: no retrieval date")
    return errs


def check_pages(pages, entities, published_only: bool) -> list[str]:
    errs = []
    live = [p for p in pages if p.status == "published" or not published_only]

    for p in pages:
        for k in REQUIRED_META:
            if k not in p.meta:
                errs.append(f"{p.id if 'id' in p.meta else p.path.name}: missing '{k}'")
        if p.meta.get("type") not in CTA_LIMIT:
            errs.append(f"{p.meta.get('id')}: unknown type {p.meta.get('type')}")
        if p.type == "article" and not p.meta.get("related"):
            errs.append(f"{p.id}: articles need related pages")
        if p.type in ("article", "comparison") and len(p.meta.get("related", [])) < 2:
            errs.append(f"{p.id}: needs at least two related pages")
        if p.type in ("article", "comparison", "property") and not p.meta.get("target_query"):
            errs.append(f"{p.id}: no target_query")

    for field in ("title", "description", "target_query", "url"):
        c = Counter(p.meta.get(field) for p in live if p.meta.get(field))
        errs += [f"duplicate {field}: {v}" for v, n in c.items() if n > 1]

    for p in live:
        prose = _text_only(p.body) + " " + p.meta.get("dek", "") + " " + p.title
        for b in IDENTITY_BANNED:
            if b.lower() in (p.body + p.title + p.meta.get("dek", "")).lower():
                errs.append(f"{p.id}: identity string '{b}'")
        for b in FILLER_BANNED:
            if b in prose:
                errs.append(f"{p.id}: filler phrase '{b}'")
        for part in (p.title, p.h1, p.meta.get("og_title", "")):
            if "公式" in part:
                errs.append(f"{p.id}: 公式 in title/h1")
        faq_text = " ".join(_text_only(i.get("a", "")) for i in p.meta.get("faq", []))
        for m in UNSOURCED_FIGURE.finditer(prose + " " + faq_text):
            errs.append(f"{p.id}: unsourced figure '{m.group(0)}' — use {{{{fact}}}}")
    return errs


def check_rendered(pages, all_urls: set[str], release: bool) -> list[str]:
    """Checks on the final HTML: links, CTAs, schema, placeholders."""
    errs = []
    urls = {p.url for p in pages}
    for p in pages:
        h = p.html
        for href in p.links:
            if href not in urls and not href.startswith("/assets/"):
                state = "unpublished" if href in all_urls else "missing"
                errs.append(f"{p.id}: link to {state} page {href}")
        # Commercial links: every one sponsored + labelled.
        for m in re.finditer(r'<a [^>]*data-hm-cta="[^"]+"[^>]*>.*?</a>', h, re.S):
            tag = m.group(0)
            if 'rel="sponsored noopener"' not in tag:
                errs.append(f"{p.id}: CTA without rel=sponsored")
            if "広告" not in tag and ">Ad<" not in tag:
                errs.append(f"{p.id}: CTA without 広告 label")
        main = h.split("<main", 1)[-1].split("</main>", 1)[0]
        n = len(re.findall(r'data-hm-cta="(?!sticky|rail)', main))
        if n > CTA_LIMIT.get(p.type, 0):
            errs.append(f"{p.id}: {n} booking CTAs (limit {CTA_LIMIT[p.type]} for {p.type})")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try:
                doc = json.loads(block)
            except ValueError as e:
                errs.append(f"{p.id}: JSON-LD does not parse: {e}")
                continue
            types = {g.get("@type") for g in doc.get("@graph", [])}
            if types & {"Review", "AggregateRating", "Rating"}:
                errs.append(f"{p.id}: rating/review schema is not allowed")
            if "FAQPage" in types and 'class="faq"' not in h:
                errs.append(f"{p.id}: FAQPage schema without a visible FAQ")
        ident = "".join(re.findall(r'<header class="mast">.*?</header>', h, re.S))
        ident += "".join(re.findall(r'og:site_name" content="([^"]*)"', h))
        for b in BRAND_BANNED:
            if b in ident.lower():
                errs.append(f"{p.id}: property name '{b}' on a site-identity surface")
        if release:
            for b in RELEASE_BANNED:
                if b in h:
                    errs.append(f"{p.id}: release output contains '{b}'")
    return errs


def check_graph(pages) -> list[str]:
    """Orphans and reachability. Nav and footer links are excluded on purpose — a page only
    linked from the global menu has no place in the editorial graph."""
    errs = []
    by_url = {p.url: p for p in pages}
    inbound = Counter()
    for p in pages:
        for u in p.links:
            if u != p.url:
                inbound[u] += 1
    for p in pages:
        if p.url != "/" and inbound[p.url] == 0 and p.type not in ("about", "contact"):
            errs.append(f"{p.id}: orphan — no in-content link points here")
    seen, q = {"/"}, deque(["/"])
    while q:
        for u in by_url[q.popleft()].links:
            if u in by_url and u not in seen:
                seen.add(u)
                q.append(u)
    for p in pages:
        if p.url not in seen and p.type not in ("about", "contact"):
            errs.append(f"{p.id}: not reachable from / through content links")
    return errs
