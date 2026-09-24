#!/usr/bin/env python3
"""Growth loop — "what should we improve next?"

Joins three exports that already exist, and turns them into an ordered action list:

    Search Console   pages CSV (Performance > Pages > Export). Optionally the previous period
                     too, for momentum.
    Umami            booking-click events, one row per attribution key
                     (event property `key` = hm-<page-id>-<placement>).
    Travelpayouts    conversions by SubID (the same key, when the booking URL carries {subid}).

    python monitor.py --gsc pages.csv [--gsc-prev prev.csv] [--clicks clicks.csv]
                      [--bookings bookings.csv] [--out reports/growth-actions.md]

Column names are matched loosely (GSC exports in Japanese or English both work). Nothing here
calls an API or needs a credential — exports in, Markdown out.

The rules are the editorial playbook, in the order they are usually worth doing:
  1  earns bookings               -> build adjacent content in the same cluster
  2  clicks but no bookings       -> property relevance / booking UX / destination intent
  3  ranks 5–15                   -> depth, internal links, tables, differentiation
  4  impressions, poor CTR        -> title / meta / intent alignment
  5  traffic, no booking clicks   -> commercial intent and CTA placement
  6  losing momentum              -> refresh facts, check SERP change
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
KEY = re.compile(r"^hm-(?P<page>.+)-(?P<placement>hero|hotel-main|room-single|room-double|room-twin|"
                 r"rail|sticky|widget|article-intro|article-mid|article-end|comparison|"
                 r"related-hotel|faq|area-page)$")

ALIASES = {
    "page": ["page", "top pages", "上位のページ", "ページ", "url", "landing page"],
    "clicks": ["clicks", "クリック数"],
    "impressions": ["impressions", "表示回数"],
    "ctr": ["ctr"],
    "position": ["position", "掲載順位", "average position"],
    "key": ["key", "event_key", "sub_id", "subid", "sub id"],
    "count": ["count", "clicks", "events", "total", "件数"],
    "bookings": ["bookings", "actions", "conversions", "予約数"],
    "commission": ["commission", "revenue", "報酬"],
}


def _num(v: str) -> float:
    v = (v or "").replace(",", "").replace("%", "").strip()
    try:
        return float(v)
    except ValueError:
        return 0.0


def read(path: str | None) -> list[dict]:
    if not path:
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        low = {k.strip().lower(): v for k, v in r.items() if k}
        norm = {}
        for field, names in ALIASES.items():
            for n in names:
                if n in low:
                    norm[field] = low[n]
                    break
        out.append(norm)
    return out


def path_of(url: str) -> str:
    p = urlparse(url).path if "://" in url else url
    return p if p.endswith("/") else p + "/"


def page_index() -> dict[str, dict]:
    """page-id -> {url, title, cluster} from the content itself, so keys resolve to pages."""
    sys.path.insert(0, str(ROOT))
    from hm import model
    return {p.id: {"url": p.url, "title": p.meta.get("h1", p.title), "cluster": p.meta.get("cluster", "")}
            for p in model.load_pages()}


def analyse(gsc, prev, clicks, bookings, pages) -> list[dict]:
    by_url = {v["url"]: k for k, v in pages.items()}
    m = defaultdict(lambda: {"impressions": 0, "clicks": 0, "ctr": 0.0, "position": 0.0,
                             "prev_clicks": 0, "cta_clicks": 0, "bookings": 0, "commission": 0.0,
                             "placements": defaultdict(int)})
    for r in gsc:
        u = path_of(r.get("page", ""))
        d = m[u]
        d["impressions"] = _num(r.get("impressions"))
        d["clicks"] = _num(r.get("clicks"))
        d["ctr"] = _num(r.get("ctr")) if r.get("ctr") else (
            100 * d["clicks"] / d["impressions"] if d["impressions"] else 0)
        d["position"] = _num(r.get("position"))
    for r in prev:
        m[path_of(r.get("page", ""))]["prev_clicks"] = _num(r.get("clicks"))

    def resolve(key: str):
        k = KEY.match((key or "").strip())
        if not k or k["page"] not in pages:
            return None, None
        return pages[k["page"]]["url"], k["placement"]

    for r in clicks:
        u, pl = resolve(r.get("key", ""))
        if u:
            n = _num(r.get("count"))
            m[u]["cta_clicks"] += n
            m[u]["placements"][pl] += n
    for r in bookings:
        u, _ = resolve(r.get("key", ""))
        if u:
            m[u]["bookings"] += _num(r.get("bookings"))
            m[u]["commission"] += _num(r.get("commission"))

    actions = []
    for u, d in m.items():
        pid = by_url.get(u)
        title = pages[pid]["title"] if pid else u
        cluster = pages[pid]["cluster"] if pid else "—"
        base = {"url": u, "title": title, "cluster": cluster, **{k: d[k] for k in
                ("impressions", "clicks", "ctr", "position", "cta_clicks", "bookings")}}
        if d["bookings"] > 0:
            actions.append({**base, "rule": 1, "action": f"予約あり。同じクラスター（{cluster}）で隣接する記事を増やす。"})
        if d["cta_clicks"] >= 10 and d["bookings"] == 0:
            top = max(d["placements"], key=d["placements"].get) if d["placements"] else "—"
            actions.append({**base, "rule": 2, "action": f"予約ボタンは押されているが予約がない（最多: {top}）。施設と検索意図が合っているか、予約先の画面を確認。"})
        if 5 <= d["position"] <= 15 and d["impressions"] >= 100:
            actions.append({**base, "rule": 3, "action": "5〜15位。表・一次情報・内部リンクを足して深さで勝つ。"})
        if d["impressions"] >= 500 and d["ctr"] < 1.5:
            actions.append({**base, "rule": 4, "action": "表示は多いがクリック率が低い。タイトルと説明文を検索意図に合わせて書き直す。"})
        if d["clicks"] >= 100 and d["cta_clicks"] == 0 and pid:
            actions.append({**base, "rule": 5, "action": "流入はあるが予約ボタンが押されていない。商業意図の有無とCTAの位置を見直す。"})
        if d["prev_clicks"] >= 30 and d["clicks"] < 0.7 * d["prev_clicks"]:
            actions.append({**base, "rule": 6, "action": f"クリックが前期間比 {d['clicks']:.0f}/{d['prev_clicks']:.0f} に減少。情報の鮮度と検索結果の変化を確認。"})
    return sorted(actions, key=lambda a: (a["rule"], -a["impressions"]))


def to_markdown(actions: list[dict]) -> str:
    if not actions:
        return "# Growth actions\n\nNo page met an action threshold in these exports.\n"
    lines = ["# Growth actions", "", "| # | Page | Cluster | Imp | Clicks | CTR | Pos | CTA clicks | Bookings | Action |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for a in actions:
        lines.append(f"| {a['rule']} | [{a['title']}]({a['url']}) | {a['cluster']} | {a['impressions']:.0f} | "
                     f"{a['clicks']:.0f} | {a['ctr']:.1f}% | {a['position']:.1f} | {a['cta_clicks']:.0f} | "
                     f"{a['bookings']:.0f} | {a['action']} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsc", required=True)
    ap.add_argument("--gsc-prev")
    ap.add_argument("--clicks")
    ap.add_argument("--bookings")
    ap.add_argument("--out", default=str(ROOT / "reports" / "growth-actions.md"))
    a = ap.parse_args()
    acts = analyse(read(a.gsc), read(a.gsc_prev), read(a.clicks), read(a.bookings), page_index())
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(acts), encoding="utf-8")
    print(f"{len(acts)} action(s) -> {out}")
    for x in acts[:10]:
        print(f"  [{x['rule']}] {x['url']}  {x['action']}")


if __name__ == "__main__":
    main()
