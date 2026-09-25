#!/usr/bin/env python3
"""浅草橋ホテルガイド (hotelmercury.jp) — build.

    python build.py              preview build -> dist/   (review pages shown, banner lists
                                                            unset config, photo slots visible)
    python build.py --release    production build -> dist/ (fails on any unset required
                                                            config, placeholder or gate error)
    python build.py check        run the quality gate only
    python build.py board        write the editorial board -> reports/

Content lives in content/. See docs/IMPLEMENTATION.md for the model.
"""

from __future__ import annotations

import argparse
import shutil
import sys

from hm import gate, model, score, seo
from hm.render import Renderer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIST = model.ROOT / "dist"
REPORTS = model.ROOT / "reports"


def compile_site(release: bool):
    cfg = model.load_config()
    sources = model.load_sources()
    entities = model.load_entities()
    pages = model.load_pages()

    errs = (gate.check_brand(cfg) + gate.check_sources(sources)
            + gate.check_pages(pages, entities, published_only=True)
            + gate.check_backlog(pages, model.load_backlog()))
    if release:
        errs += [f"config: '{k}' is required for release ({why})"
                 for k, why in model.Config.REQUIRED.items() if not cfg.get(k)]

    visible = [p for p in pages if p.status == "published" or (not release and p.status == "review")]
    r = Renderer(cfg, sources, entities, visible, preview=not release)
    for p in visible:
        p.html = r.render(p)
    errs += r.errors
    errs += gate.check_rendered(visible, {p.url for p in pages}, release)
    errs += gate.check_graph(visible)
    return cfg, visible, pages, errs


def write(cfg, pages, release=False):
    DIST.mkdir(exist_ok=True)
    for child in DIST.iterdir():        # clear contents, keep the dir (a preview server may hold it)
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    for p in pages:
        out = DIST / p.url.strip("/") / "index.html" if p.url != "/" else DIST / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(p.html, encoding="utf-8")
    # Release never ships the stamped demo photos (unlicensed): not referenced, not fetchable.
    shutil.copytree(model.ROOT / "assets", DIST / "assets",
                    ignore=shutil.ignore_patterns("demo") if release else None)
    base = cfg.get("base_url").rstrip("/")
    (DIST / "sitemap.xml").write_text(seo.sitemap(base, pages), encoding="utf-8")
    (DIST / "robots.txt").write_text(seo.robots(base), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="build", choices=["build", "check", "board"])
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--lenient", action="store_true",
                    help="preview only: write dist/ even when the gate fails (work in progress)")
    a = ap.parse_args()

    if a.cmd == "board":
        rows = score.rows(model.load_pages(), model.load_backlog())
        c, h = score.write_board(rows, REPORTS)
        print(f"editorial board: {len(rows)} items -> {h}")
        for row in rows[:10]:
            print(f"  {row['priority']:>3}  {row['status']:<10} {row['article']}")
        return

    cfg, visible, all_pages, errs = compile_site(a.release)
    if errs:
        print(f"GATE FAILED — {len(errs)} problem(s):")
        for e in errs:
            print("  - " + e)
        if a.release or a.cmd == "check" or not a.lenient:
            sys.exit(1)
        print("(--lenient: writing preview anyway)")
    if a.cmd == "check":
        print(f"gate clean: {len(visible)} pages")
        return
    write(cfg, visible, a.release)
    ctas = sum(p.html.count("data-hm-cta=") for p in visible)
    held = [p.id for p in all_pages if p not in visible]
    mode = "RELEASE" if a.release else "preview"
    print(f"{mode}: {len(visible)} pages -> {DIST}")
    print(f"booking CTAs: {ctas}  |  not published: {', '.join(held) or 'none'}")
    if not a.release:
        req = cfg.missing(model.Config.REQUIRED)
        if req:
            print("unset required config (release will refuse): " + ", ".join(req))
        rec = cfg.missing(model.Config.RECOMMENDED)
        if rec:
            print("unset recommended config: " + ", ".join(rec))


if __name__ == "__main__":
    main()
