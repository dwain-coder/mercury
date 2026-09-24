#!/usr/bin/env python3
"""Wikimedia Commons photo sourcing — licence-safe by construction.

    python tools/commons.py search "Kaminarimon"           # list candidates with licences
    python tools/commons.py fetch <slot-key> "File:X.jpg" "alt text" ["caption"]

`fetch` downloads a rendition, writes 1400px and 700px WebP files (srcset), and writes the slot into
content/photos.toml with author, licence and source URL. Only licences that allow commercial
reuse are accepted (CC0, public domain, CC BY, CC BY-SA); anything else is refused, so a
page can never ship a photo it is not allowed to use. BY / BY-SA require attribution — the
site prints `credit` under every photo.

A person chooses each image (`search`, look, then `fetch`). Nothing is picked automatically.
"""

from __future__ import annotations

import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img" / "cc"
MANIFEST = ROOT / "content" / "photos.toml"
API = "https://commons.wikimedia.org/w/api.php"
UA = "hotelmercury-guide-build/1.0 (https://hotelmercury.jp; dwain@novatise.com)"
OK_LICENCE = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)? [0-9.]+)", re.I)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def api(**params) -> dict:
    params.update(format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _plain(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def info(titles: list[str], width: int = 1600) -> list[dict]:
    d = api(action="query", titles="|".join(titles), prop="imageinfo",
            iiprop="url|size|extmetadata|mime", iiurlwidth=width)
    out = []
    for p in d["query"]["pages"]:
        if "imageinfo" not in p:
            continue
        ii = p["imageinfo"][0]
        md = ii.get("extmetadata", {})
        out.append({
            "title": p["title"],
            "licence": _plain(md.get("LicenseShortName", {}).get("value", "")),
            "licence_url": _plain(md.get("LicenseUrl", {}).get("value", "")),
            # first line only: Commons' Artist field often carries camera EXIF text after it
            "artist": (_plain(md.get("Artist", {}).get("value", "")).splitlines() or ["不明"])[0].strip() or "不明",
            "w": ii["width"], "h": ii["height"], "mime": ii.get("mime", ""),
            "thumb": ii.get("thumburl", ii["url"]),
            "page": ii.get("descriptionurl", ""),
        })
    return out


def search(q: str, n: int = 12) -> list[dict]:
    d = api(action="query", list="search", srsearch=f"filetype:bitmap {q}", srnamespace=6, srlimit=n)
    titles = [h["title"] for h in d["query"]["search"]]
    return info(titles) if titles else []


def fetch(slot: str, title: str, alt: str, caption: str = "") -> None:
    rec = info([title])
    if not rec:
        sys.exit(f"not found: {title}")
    r = rec[0]
    if not OK_LICENCE.match(r["licence"]):
        sys.exit(f"REFUSED — licence '{r['licence']}' is not cleared for commercial reuse")
    req = urllib.request.Request(r["thumb"], headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=60).read()
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((1400, 1400))
    IMG.mkdir(parents=True, exist_ok=True)
    out = IMG / f"{slot}.webp"
    im.save(out, "WEBP", quality=70, method=6)
    small = im.copy()
    small.thumbnail((700, 700))                       # phones get this via srcset
    small.save(IMG / f"{slot}-700.webp", "WEBP", quality=68, method=6)
    credit = f"写真：{r['artist']}／{r['licence']}（Wikimedia Commons）"
    entry = (
        f'\n[{slot}]\nsrc = "/assets/img/cc/{slot}.webp"\nalt = {json.dumps(alt, ensure_ascii=False)}\n'
        f'caption = {json.dumps(caption, ensure_ascii=False)}\n'
        f'credit = {json.dumps(credit, ensure_ascii=False)}\n'
        f'licence = {json.dumps(r["licence"])}\nlicence_url = {json.dumps(r["licence_url"])}\n'
        f'source = {json.dumps(r["page"])}\nwidth = {im.width}\nheight = {im.height}\n'
    )
    text = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else (
        "# Photo slots -> files. Every entry carries its licence and source; see tools/commons.py.\n")
    # replace an existing entry for this slot
    text = re.sub(rf"\n\[{re.escape(slot)}\]\n(?:[^\[].*\n?)*", "", text)
    MANIFEST.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")
    print(f"{slot}: {out.name} {im.width}x{im.height} {out.stat().st_size // 1024}KB — {credit}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        for r in search(sys.argv[2]):
            ok = "OK " if OK_LICENCE.match(r["licence"]) else "-- "
            print(f"{ok}{r['w']}x{r['h']:<5} {r['licence']:<14} {r['title']}")
    elif len(sys.argv) >= 5 and sys.argv[1] == "fetch":
        fetch(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "")
    else:
        print(__doc__)
