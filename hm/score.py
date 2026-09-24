"""Content opportunity model — an internal editorial priority, NOT a ranking prediction.

Each idea (published page or backlog item) is rated 1–5 on each factor by an editor. Where
real data exists (GSC impressions, DataForSEO volume) `demand_basis` says so; until then it
reads `editor-estimate` and the board shows that plainly.

    raw = 3·demand + 3·commercial + 2·proximity + 2·authority + 1·links
        + 2·differentiation + 1·seasonal − 2·competition − 1·difficulty

    priority = 100 · (raw − min) / (max − min)          → 0–100

Why these weights: the site earns on bookings, so demand and commercial intent lead;
proximity (how few clicks from this page to a booking decision) and authority (does it
strengthen the Asakusabashi cluster) come next; differentiation is weighted up because a page
that only repeats an OTA listing has no reason to rank. Competition and effort subtract.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
from pathlib import Path

WEIGHTS = {
    "demand": 3, "commercial": 3, "proximity": 2, "authority": 2, "links": 1,
    "differentiation": 2, "seasonal": 1, "competition": -2, "difficulty": -1,
}
_MIN = sum(w * (1 if w > 0 else 5) for w in WEIGHTS.values())
_MAX = sum(w * (5 if w > 0 else 1) for w in WEIGHTS.values())

FACTOR_HELP = {
    "demand": "検索需要（1=ほぼ無し〜5=大）",
    "commercial": "商業意図（予約に近い検索か）",
    "proximity": "予約判断までの近さ",
    "authority": "浅草橋クラスターを強くするか",
    "links": "内部リンクのハブになるか",
    "differentiation": "OTAにない情報を出せるか",
    "seasonal": "季節需要の強さ",
    "competition": "競合の強さ（減点）",
    "difficulty": "制作・取材の手間（減点）",
}


def priority(score: dict) -> int:
    missing = [k for k in WEIGHTS if k not in score]
    if missing:
        raise ValueError(f"score missing factors: {missing}")
    for k in WEIGHTS:
        if not 1 <= int(score[k]) <= 5:
            raise ValueError(f"score factor {k} must be 1–5")
    raw = sum(WEIGHTS[k] * int(score[k]) for k in WEIGHTS)
    return round(100 * (raw - _MIN) / (_MAX - _MIN))


def rows(pages, backlog) -> list[dict]:
    out = []
    for p in pages:
        s = p.meta.get("score")
        if not s:
            continue
        out.append({
            "article": p.meta.get("h1", p.title), "url": p.url, "status": p.status,
            "intent": p.meta.get("intent", ""), "target_query": p.meta.get("target_query", ""),
            "cluster": p.meta.get("cluster", ""), "monetisation": p.meta.get("monetisation", ""),
            "demand": s["demand"], "demand_basis": s.get("demand_basis", "editor-estimate"),
            "commercial": s["commercial"], "priority": priority(s),
            "updated": p.updated.isoformat(), "note": s.get("note", ""),
        })
    for b in backlog:
        s = b["score"]
        out.append({
            "article": b["title"], "url": b.get("url", ""), "status": b.get("status", "idea"),
            "intent": b["intent"], "target_query": b["target_query"], "cluster": b["cluster"],
            "monetisation": b.get("monetisation", ""),
            "demand": s["demand"], "demand_basis": s.get("demand_basis", "editor-estimate"),
            "commercial": s["commercial"], "priority": priority(s),
            "updated": "", "note": b.get("blocked_by", "") or s.get("note", ""),
        })
    return sorted(out, key=lambda r: (-r["priority"], r["article"]))


COLS = ["priority", "status", "article", "intent", "target_query", "cluster", "demand",
        "demand_basis", "commercial", "monetisation", "updated", "url", "note"]


def write_board(rows_: list[dict], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    c = outdir / "editorial-board.csv"
    with c.open("w", newline="", encoding="utf-8-sig") as f:      # BOM: opens cleanly in Excel
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_)
    h = outdir / "editorial-board.html"
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r[k]))}</td>" for k in COLS) + "</tr>"
        for r in rows_)
    weights = " ".join(f"<li><b>{k}</b> ×{w} — {FACTOR_HELP[k]}</li>" for k, w in WEIGHTS.items())
    h.write_text(f"""<!DOCTYPE html><html lang="ja"><meta charset="utf-8">
<title>Editorial board — 浅草橋ホテルガイド</title>
<style>body{{font:14px/1.6 system-ui,sans-serif;margin:24px;color:#1b1b1b}}table{{border-collapse:collapse;width:100%}}
th,td{{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#23355c;color:#fff;position:sticky;top:0}}
td:first-child{{font-weight:700}}ul{{columns:2}}</style>
<h1>Editorial board</h1><p>Generated {dt.date.today().isoformat()}. Priority is an internal editorial score, not a
prediction of Google ranking. <code>demand_basis = editor-estimate</code> means no search data has been attached yet.</p>
<ul>{weights}</ul>
<table><thead><tr>{"".join(f"<th>{k}</th>" for k in COLS)}</tr></thead><tbody>{body}</tbody></table>""",
                 encoding="utf-8")
    return c, h
