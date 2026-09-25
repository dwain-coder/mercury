"""Layout, components and shortcodes.

Pages are HTML fragments. Anything that has to be consistent — a booking link, a fact, a
citation, a photo slot, a list of related pages — is a {{shortcode}}, so it is rendered by
exactly one function.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import shlex
import tomllib

from . import diagrams, geo, seo
from .booking import Booking
from .model import CONTENT, ROOT, Config, Entity, Page, Source


def asset(url: str) -> str:
    """/assets/... + ?v=<content hash>. The origin serves css/js with a 10-year Expires, so
    a changed file must change URL or returning browsers keep the old one."""
    return f"{url}?v={hashlib.sha256((ROOT / url.lstrip('/')).read_bytes()).hexdigest()[:10]}"

CLUSTERS = {
    "hotels": "ホテル",
    "stay": "泊まる場所を決める",
    "transit": "空港・交通",
    "district": "浅草橋を知る",
    "walks": "歩く",
    "events": "季節・行事",
    "compare": "エリア比較",
    "inbound": "English",
    "about": "このサイトについて",
    "hub": "ガイド",
}

# The publication's identity surfaces (this nav, the masthead, og:site_name) name the
# publication only. A property's name — including 「ホテルマーキュリー」, a registered
# trademark — appears only as the subject of a page, never as a label for the site.
NAV = [
    ("/hotel/", "浅草橋のホテル"),
    ("/area/", "エリア"),
    ("/access/", "アクセス"),
    ("/choose/", "街を選ぶ"),
    ("/guide/24-hours-in-asakusabashi/", "24時間"),
    ("/guide/", "ガイド"),
    ("/blog/", "読みもの"),
    ("/en/", "English"),
]

FOOT_NAV = [
    ("ガイド", [("/hotel/", "浅草橋のホテルの選び方"), ("/area/asakusabashi/", "浅草橋エリアガイド"),
                ("/access/", "浅草橋へのアクセス"), ("/guide/", "旅の実用ガイド"), ("/blog/", "読みもの一覧")]),
    ("このサイトについて", [("/about/", "運営と編集方針"), ("/about/#ads", "広告・アフィリエイトについて"),
                     ("/about/#corrections", "訂正の方針"), ("/about/#sources", "出典と情報の扱い")]),
]


def jdate(d: dt.date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


class Renderer:
    def __init__(self, cfg: Config, sources: dict[str, Source], entities: dict[str, Entity],
                 pages: list[Page], preview: bool):
        self.cfg = cfg
        self.sources = sources
        self.entities = entities
        self.pages = pages
        self.by_url = {p.url: p for p in pages}
        self.by_id = {p.id: p for p in pages}
        self.preview = preview
        self.booking = Booking(cfg, preview)
        f = CONTENT / "photos.toml"
        self.photos = tomllib.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        # Stamped stand-ins for the property's own photography (tools/demo_photos.py). They are
        # unlicensed, so they exist in the preview only; a release build drops them entirely
        # (and the gate still bans the marker, in case one is ever pasted in by hand).
        demo = CONTENT / "photos-demo.toml"
        if preview and demo.exists():
            self.photos.update(tomllib.loads(demo.read_text(encoding="utf-8")))
        self.errors: list[str] = []
        self.atlas = geo.Atlas()
        svg = (CONTENT.parent / "assets" / "img" / "mark.svg").read_text(encoding="utf-8")
        svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).strip()
        self.mark = svg.replace("<svg ", '<svg class="mast__mark" aria-hidden="true" focusable="false" ', 1)

    # ------------------------------------------------------------------ citations

    def cite(self, page: Page, source_id: str) -> str:
        if source_id not in self.sources:
            self.errors.append(f"{page.id}: cites unknown source '{source_id}'")
            return ""
        if source_id not in page.cited:
            page.cited.append(source_id)
        n = page.cited.index(source_id) + 1
        return f'<sup class="cite"><a href="#src-{n}" aria-label="出典{n}">{n}</a></sup>'

    def fact(self, page: Page, dotted: str, bare: bool = False) -> str:
        ent_id, _, key = dotted.partition(".")
        ent = self.entities.get(ent_id)
        if not ent or key not in ent.facts:
            self.errors.append(f"{page.id}: unknown fact '{dotted}'")
            return ""
        f = ent.facts[key]
        src = self.sources.get(f.source)
        caveat = ""
        if src and src.kind == "archive":
            caveat = f'<span class="caveat">（{html.escape(f.note or "旧案内。現行未確認")}）</span>'
        value = f'<span class="fact" data-fact="{dotted}">{html.escape(f.value)}</span>'
        return value if bare else value + caveat + self.cite(page, f.source)

    # ------------------------------------------------------------------ shortcodes

    SC = re.compile(r"\{\{\s*([a-z][a-z-]*)\s*(.*?)\}\}", re.S)

    def shortcodes(self, page: Page, text: str) -> str:
        def repl(m):
            name, rest = m.group(1), m.group(2).strip()
            args, kw = [], {}
            for tok in shlex.split(rest):
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    kw[k] = v
                else:
                    args.append(tok)
            fn = getattr(self, "sc_" + name.replace("-", "_"), None)
            if not fn:
                self.errors.append(f"{page.id}: unknown shortcode '{name}'")
                return ""
            return fn(page, *args, **kw)
        return self.SC.sub(repl, text)

    def sc_fact(self, page, dotted):
        return self.fact(page, dotted)

    def sc_cite(self, page, source_id):
        return self.cite(page, source_id)

    def sc_button(self, page, placement, label="空室と料金を見る", prop="hotel-mercury"):
        return self.booking.button(page, placement, label, prop)

    def sc_book(self, page, placement="article-end", title=None, label="空室と料金を見る",
                prop="hotel-mercury", facts="access_toei,access_jr,checkin"):
        ent = self.entities[prop]
        title = title or f"{ent.name}の予約情報"
        lines = []
        for k in facts.split(","):
            k = k.strip()
            label_k = FACT_LABELS.get(k, "")
            lines.append((f"{label_k}：" if label_k else "") + self.fact(page, f"{prop}.{k}"))
        return self.booking.module(page, placement, title, lines, label, prop)

    def sc_publisher(self, page):
        name = self.cfg.get("publisher")
        if name:
            return html.escape(name)
        # Preview only — release refuses to build without a publisher.
        return '<span class="preview-only">運営者名（site.toml の publisher を設定）</span>'

    def sc_byline(self, page):
        ja = page.lang == "ja"
        return (f'<p class="byline"><time datetime="{page.updated}">'
                f'{"最終更新 " + jdate(page.updated) if ja else "Updated " + page.updated.isoformat()}</time>'
                f'<span>{"浅草橋ホテルガイド編集部" if ja else "Asakusabashi Stay Guide"}</span>'
                f'<a href="/about/#ads">{"広告を含みます" if ja else "Contains affiliate links"}</a></p>')

    def sc_atlas(self, page, mode="wide", caption=""):
        return self.atlas.figure(mode, caption + self.cite(page, "osm"))

    def sc_basecamp(self, page):
        """The hotel as the centre: what is within each walking band, then one train ride."""
        cols = []
        for label, items in self.atlas.zones():
            if not items:
                continue
            lis = []
            for pid, m, mins in items:
                pl = self.atlas.places[pid]
                name = html.escape(pl["name"])
                name = f'<a href="{pl["page"]}">{name}</a>' if pl.get("page") else name
                lis.append(f"<li>{name}<span>直線約{m:,}m</span></li>")
            cols.append(f'<section class="bc__band"><p class="bc__h">{label}</p><ul>{"".join(lis)}</ul></section>')
        train = (
            '<section class="bc__band bc__band--train"><p class="bc__h">電車ですぐ</p><ul>'
            '<li><a href="/guide/asakusabashi-vs-asakusa/">浅草</a><span>都営浅草線で2駅</span></li>'
            '<li>蔵前<span>都営浅草線で1駅</span></li>'
            '<li>秋葉原<span>JR総武線で1駅</span></li>'
            '<li>両国<span>JR総武線で1駅</span></li>'
            '<li>東京スカイツリー（押上）<span>都営浅草線で4駅</span></li>'
            '<li><a href="/access/haneda/">羽田空港</a>・<a href="/access/narita/">成田空港</a><span>直通列車で乗り換えなし</span></li>'
            '</ul></section>'
        )
        stations = (f'<section class="bc__band bc__band--home"><p class="bc__h">駅</p><ul>'
                    f'<li>都営浅草線<span>{self.fact(page, "hotel-mercury.access_toei")}</span></li>'
                    f'<li>JR総武線<span>{self.fact(page, "hotel-mercury.access_jr")}</span></li></ul></section>')
        note = (f'<p class="bc__note">駅以外の距離は地図データ{self.cite(page, "osm")}から求めた直線距離で、'
                f'徒歩の目安は分速80mで換算しています。実際の道のりはこれより長くなります。</p>')
        return f'<div class="bc">{stations}{"".join(cols)}{train}</div>{note}'

    def sc_choose(self, page):
        """「泊まる街を選ぶ」: documented attributes x the reader's choices, scored in the open.
        Works without JavaScript as a comparison table; with it, ranks the areas live."""
        nb = tomllib.loads((CONTENT / "geo" / "neighbourhoods.toml").read_text(encoding="utf-8"))
        traits, areas = nb["traits"], nb["area"]
        # cite everything the table relies on, so the source list is complete
        for a in areas.values():
            for sid in a["lines_source"] + [a["airport_source"]] + list(a["traits"].values()):
                self.cite(page, sid)
        data = {k: {"name": a["name"], "lines": a["lines"], "haneda": a["haneda_direct"],
                    "narita": a["narita_direct"], "traits": list(a["traits"]),
                    "page": a.get("page", ""), "hotels": a.get("hotels", [])}
                for k, a in areas.items()}
        purpose = "".join(
            f'<label class="chip"><input type="checkbox" name="trait" value="{k}"><span>{html.escape(v)}</span></label>'
            for k, v in traits.items())
        form = f"""<form class="choose" id="choose" onsubmit="return false">
<fieldset><legend><b>1</b>旅の目的（いくつでも）</legend><div class="chips">{purpose}</div></fieldset>
<fieldset><legend><b>2</b>重視すること（いくつでも）</legend><div class="chips">
<label class="chip"><input type="checkbox" name="need" value="haneda"><span>羽田から乗り換えなし</span></label>
<label class="chip"><input type="checkbox" name="need" value="narita"><span>成田から乗り換えなし</span></label>
<label class="chip"><input type="checkbox" name="need" value="lines"><span>使える路線が多い</span></label>
<label class="chip chip--off" title="根拠となるデータがないため採点していません"><input type="checkbox" disabled><span>料金の安さ</span></label>
<label class="chip chip--off" title="根拠となるデータがないため採点していません"><input type="checkbox" disabled><span>静かさ</span></label>
</div><p class="choose__why">料金と静かさは、街ごとに比べられる公開データがないため採点に使っていません。</p></fieldset>
<fieldset><legend><b>3</b>だれと行くか</legend><div class="chips">
<label class="chip"><input type="radio" name="who" value="solo"><span>ひとり</span></label>
<label class="chip"><input type="radio" name="who" value="two"><span>2人</span></label>
<label class="chip"><input type="radio" name="who" value="group"><span>3人以上・家族</span></label>
</div><p class="choose__why">同行者は街の点数には影響しません。宿の部屋タイプを案内するときに使います。</p></fieldset>
</form>
<section class="choose__out" id="choose-out" aria-live="polite" hidden></section>"""
        rows = []
        for k, a in areas.items():
            tr = "、".join(traits[t] for t in a["traits"])
            rows.append(
                f'<tr><th>{html.escape(a["name"])}</th><td>{"、".join(a["lines"])}</td>'
                f'<td>{"あり" if a["haneda_direct"] else "なし"}</td><td>{"あり" if a["narita_direct"] else "なし"}</td>'
                f'<td>{tr}</td></tr>')
        table = (f'<figure class="tbl" id="choose-table"><figcaption>採点に使っている街ごとの特徴</figcaption>'
                 f'<div class="tablewrap"><table><thead><tr><th>街</th><th>路線</th><th>羽田直通</th><th>成田直通</th><th>特徴</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>'
                 f'<p class="tsrc">採点：選んだ目的に当てはまる特徴1つにつき2点、選んだ空港に乗り換えなしで行ければ2点、'
                 f'「路線が多い」を選んだ場合は4路線以上で1点。同点の場合は並び順のとおりです。</p></figure>')
        hotel_cards = "".join(
            f'<template id="hotel-{hid}">{self.sc_property(page, hid, "comparison")}</template>'
            for a in areas.values() for hid in a.get("hotels", []))
        blob = json.dumps({"areas": data, "traits": traits}, ensure_ascii=False)
        return (form + table + hotel_cards +
                f'<script type="application/json" id="choose-data">{blob}</script>')

    def sc_youtube(self, page, key):
        """A YouTube video as a click-to-play facade: one thumbnail until the reader presses
        play, then a youtube-nocookie iframe. Without JavaScript the link opens YouTube."""
        f = CONTENT / "videos.toml"
        vids = tomllib.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        v = vids.get(key)
        if not v:
            self.errors.append(f"{page.id}: unknown video '{key}' (add it to content/videos.toml)")
            return ""
        vid, title = v["id"], html.escape(v["title"])
        return (f'<figure class="yt"><a class="yt__play" data-yt="{vid}" href="https://www.youtube.com/watch?v={vid}" '
                f'target="_blank" rel="noopener" aria-label="動画を再生：{title}">'
                f'<img src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg" alt="" width="480" height="360" loading="lazy">'
                f'<span class="yt__btn" aria-hidden="true"></span></a>'
                f'<figcaption>{title}<span class="credit">動画：{html.escape(v["channel"])}（YouTube）</span></figcaption></figure>')

    def sc_hotelwidget(self, page):
        """Travelpayouts hotel widget (Booking.com hotel card) — shows the property's own
        licensed photos inside Booking's frame. One config value: the script src Jon copies
        from Travelpayouts → Tools → Widgets. Optional; renders nothing until set."""
        src = self.cfg.get("booking.hotel_widget_src")
        if not src:
            if self.preview:
                return ('<p class="preview-only">（施設写真ウィジェット：site.toml の '
                        'booking.hotel_widget_src にTravelpayoutsのウィジェットURLを入れると、ここに表示されます）</p>')
            return ""
        return (f'<section class="widget widget--hotel" aria-label="施設の写真と空室" data-hm-cta="widget">'
                f'<p class="widget__h">施設の写真と空室<small class="adtag">広告</small></p>'
                f'<script async src="{html.escape(src)}" charset="utf-8"></script>'
                f'<p class="widget__note">写真と料金は外部の予約サービス（Booking.com）が表示します。</p></section>')

    def sc_arrival(self, page, prop="hotel-mercury"):
        """着いてから、チェックインまで — landing time -> estimated arrival at the hotel -> where
        that falls against the check-in window. Every figure comes from the fact registry; the
        only assumption (time from landing to boarding the train) is the reader's to adjust, and
        the arithmetic is printed with the result."""
        import re as _re
        ent = self.entities[prop]
        # last number in the value: "A4出口から徒歩1分" -> 1, "約40分" -> 40
        mins = lambda k: int(_re.findall(r"\d+", ent.facts[k].value)[-1])
        ci = _re.findall(r"(\d{1,2}):(\d{2})", ent.facts["checkin"].value)
        data = {
            "haneda": mins("time_haneda"), "narita": mins("time_narita"),
            "walk": max(mins("access_toei"), mins("access_jr")),
            "open": int(ci[0][0]) * 60 + int(ci[0][1]), "close": int(ci[1][0]) * 60 + int(ci[1][1]),
        }
        return f"""<section class="arr" id="arrival-planner" aria-labelledby="arr-h">
<p class="arr__k">Arrival planner</p>
<h2 id="arr-h">着いてから、チェックインまで</h2>
<p class="arr__lede">着陸時刻を入れると、宿に着く時刻の目安と、チェックインの受付時間（{self.fact(page, prop + ".checkin")}）に間に合うかを計算します。</p>
<form class="arr__form" onsubmit="return false">
<label class="arr__f"><span>空港</span><select name="ap">
<option value="haneda-dom">羽田空港（国内線）</option>
<option value="haneda-intl">羽田空港（国際線）</option>
<option value="narita">成田空港</option></select></label>
<label class="arr__f"><span>着陸時刻</span><input type="time" name="land" value="20:30" required></label>
<label class="arr__f arr__f--wide"><span>着陸から電車に乗るまで（入国審査・荷物の受け取り。自分の見込みで調整）<b class="arr__buf-v"></b></span>
<input type="range" name="buf" min="10" max="150" step="5" value="30"></label>
</form>
<div class="arr__out" aria-live="polite"></div>
<p class="arr__note">空港からの所要時間は施設が案内する目安（羽田{self.fact(page, prop + ".time_haneda")}、成田{self.fact(page, prop + ".time_narita")}）、駅から宿までは{self.fact(page, prop + ".access_jr")}で計算しています。直通列車の有無や終電は時間帯で変わるため、当日の時刻表で確認してください{self.cite(page, "toei-a16-timetable")}。</p>
<script type="application/json" class="arr__data">{json.dumps(data)}</script>
</section>"""

    def sc_walk(self, page, place):
        """Straight-line distance from the hotel to an atlas place, with the walking estimate
        (80 m/min) and the map source — so prose can quote a distance without typing a number."""
        if place not in self.atlas.places:
            self.errors.append(f"{page.id}: unknown place '{place}'")
            return ""
        m, mins = self.atlas.walk_min(place)
        ja = page.lang == "ja"
        txt = (f"宿から直線約{m:,}m（徒歩の目安{mins}分）" if ja
               else f"about {m:,} m in a straight line from the hotel (roughly a {mins}-minute walk)")
        return f'<span class="fact">{txt}</span>{self.cite(page, "osm")}'

    def sc_widget(self, page, title="日付を入れて空室と料金を比較"):
        return self.booking.widget(page, title)

    def sc_property(self, page, prop="hotel-mercury", placement="related-hotel"):
        ent = self.entities[prop]
        rows = "".join(
            f"<tr><th>{FACT_LABELS[k]}</th><td>{self.fact(page, f'{prop}.{k}')}</td></tr>"
            for k in ("access_toei", "rooms_total", "checkin", "breakfast")
        )
        return (
            f'<section class="propcard"><p class="propcard__k">ホテルガイド</p>'
            f'<p class="propcard__h"><a href="{ent.page}">{html.escape(ent.name)}</a></p>'
            f'<table class="propcard__t">{rows}</table>'
            f'<p class="propcard__act"><a class="more" href="{ent.page}">施設ガイドを読む</a>'
            f'{self.booking.button(page, placement, "空室と料金を見る", prop)}</p></section>'
        )

    def share_image(self, page) -> str:
        for key in page.meta.get("_photos_used", []):
            p = self.photos.get(key)
            if p and not p.get("demo"):
                return p["src"]
        return "/assets/img/share.png"

    def sc_photo(self, page, key, label="", ratio="", cls=""):
        """A licensed photo from content/photos.toml, or — in preview only — an empty slot.
        Every photo carries its credit and licence link: CC BY / BY-SA require attribution."""
        p = self.photos.get(key)
        if p:
            page.meta.setdefault("_photos_used", []).append(key)
            w, h = p["width"], p["height"]
            small = p["src"].replace(".webp", "-700.webp")
            lic = (f'<a href="{html.escape(p["licence_url"])}" rel="license noopener" target="_blank">{html.escape(p["licence"])}</a>'
                   if p.get("licence_url") else html.escape(p.get("licence", "")))
            author = html.escape(p["credit"].split("／")[0])
            origin = html.escape(p.get("origin", "Wikimedia Commons"))
            credit = (f'<span class="credit">{author}／{lic}／'
                      f'<a href="{html.escape(p["source"])}" rel="noopener" target="_blank">{origin}</a></span>')
            cap = html.escape(p.get("caption", ""))
            if p.get("demo"):
                cap += "（デモ用の参考画像。本番では差し替えます）"
                cls = (cls + " photo--demo").strip()
            style = f' style="--ratio:{ratio}"' if ratio else ""
            return (f'<figure class="photo{" " + cls if cls else ""}"{style}>'
                    f'<img src="{p["src"]}" srcset="{small} 700w, {p["src"]} {w}w" '
                    f'sizes="(max-width: 767px) 100vw, 900px" alt="{html.escape(p["alt"])}" '
                    f'width="{w}" height="{h}" loading="lazy" decoding="async">'
                    f'<figcaption>{cap}{credit}</figcaption></figure>')
        if not self.preview:
            return ""       # release: an unshot photo is simply absent, never a placeholder
        return (f'<figure class="photo photo--slot" style="--ratio:{ratio or "16/9"}" data-photo="{key}">'
                f'<span>写真枠：{html.escape(label or key)}</span></figure>')

    def sc_diagram(self, page, name):
        fn = getattr(diagrams, name.replace("-", "_"), None)
        if not fn:
            self.errors.append(f"{page.id}: unknown diagram '{name}'")
            return ""
        return fn()

    def sc_pages(self, page, ids="", under="", heading="", types=""):
        chosen = []
        if types:
            want = set(types.split(","))
            chosen = sorted((p for p in self.pages if p.type in want and self._visible(p)),
                            key=lambda p: (p.updated, p.url), reverse=True)
        if ids:
            for i in ids.split(","):
                p = self.by_id.get(i.strip())
                if not p:
                    self.errors.append(f"{page.id}: pages lists unknown id '{i.strip()}'")
                elif self._visible(p):
                    chosen.append(p)
        if under:
            chosen += [p for p in self.pages
                       if p.url.startswith(under) and p.url != under and self._visible(p)
                       and p not in chosen]
        return self.index_rows(chosen, heading)

    def sc_faq(self, page):
        items = page.meta.get("faq", [])
        if not items:
            self.errors.append(f"{page.id}: {{faq}} used but no faq in front matter")
            return ""
        page.meta["_faq_visible"] = True
        rendered = [(i["q"], self.shortcodes(page, i["a"])) for i in items]
        page.meta["_faq_rendered"] = rendered      # schema quotes exactly what is shown
        body = "".join(f"<dt>{html.escape(q)}</dt><dd>{a}</dd>" for q, a in rendered)
        return f'<dl class="faq">{body}</dl>'

    def sc_contact_form(self, page):
        endpoint = self.cfg.get("contact_endpoint")
        action = f' action="{html.escape(endpoint)}"' if endpoint else ""
        return f"""<form class="form" method="post"{action}>
<p class="form__hp" aria-hidden="true"><label>空欄のままにしてください<input type="text" name="_gotcha" tabindex="-1" autocomplete="off"></label></p>
<label>お名前<input type="text" name="name" autocomplete="name" required maxlength="80"></label>
<label>メールアドレス<input type="email" name="email" autocomplete="email" required maxlength="120"></label>
<label>ご用件<select name="topic"><option>記事内容の誤りの指摘</option><option>掲載情報の更新依頼</option><option>その他</option></select></label>
<label>内容<textarea name="message" rows="7" required maxlength="4000"></textarea></label>
<button class="btn-plain" type="submit">送信する</button>
</form>"""

    # ------------------------------------------------------------------ lists

    def _visible(self, p: Page) -> bool:
        return p.status == "published" or (self.preview and p.status == "review")

    def index_rows(self, pages: list[Page], heading: str = "") -> str:
        if not pages:
            return ""
        rows = []
        for p in pages:
            k = CLUSTERS.get(p.meta.get("cluster", ""), "")
            rows.append(
                f'<li class="idx__row"><span class="idx__k">{k}</span>'
                f'<a class="idx__t" href="{p.url}">{html.escape(p.nav_title)}</a>'
                f'<span class="idx__d">{html.escape(p.meta.get("dek_short", p.meta.get("description", "")))}</span>'
                f'<time class="idx__u" datetime="{p.updated}">{jdate(p.updated)}</time></li>'
            )
        h = f'<h2 class="idx__h">{heading}</h2>' if heading else ""
        return f'{h}<ul class="idx">{"".join(rows)}</ul>'

    # ------------------------------------------------------------------ page parts

    def breadcrumbs(self, page: Page) -> tuple[str, list[tuple[str, str]]]:
        if page.url == "/":
            return "", []
        trail = [("/", "トップ")]
        parts = [x for x in page.url.strip("/").split("/") if x]
        acc = "/"
        for part in parts[:-1]:
            acc += part + "/"
            if acc in self.by_url:
                trail.append((acc, self.by_url[acc].nav_title))
        trail.append((page.url, page.nav_title))
        items = "".join(
            f'<li><a href="{u}">{html.escape(t)}</a></li>' if i < len(trail) - 1
            else f'<li aria-current="page">{html.escape(t)}</li>'
            for i, (u, t) in enumerate(trail)
        )
        return f'<nav class="crumbs" aria-label="パンくず"><ol>{items}</ol></nav>', trail

    def head_block(self, page: Page, crumbs: str) -> str:
        if page.meta.get("custom_head"):
            return crumbs
        k = CLUSTERS.get(page.meta.get("cluster", ""), "")
        dek = page.meta.get("dek", "")
        dek_html = f'<p class="dek">{self.shortcodes(page, dek)}</p>' if dek else ""
        ja = page.lang == "ja"
        meta = self.sc_byline(page)
        return (f'{crumbs}<header class="phead"><p class="kicker">{k}</p>'
                f'<h1>{html.escape(page.h1)}</h1>{dek_html}{meta}</header>')

    def toc(self, body: str) -> str:
        heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
        if len(heads) < 3:
            return ""
        items = "".join(f'<li><a href="#{i}">{re.sub("<[^>]+>", "", t)}</a></li>' for i, t in heads)
        return f'<nav class="toc" aria-label="目次"><p class="toc__h">目次</p><ol>{items}</ol></nav>'

    def sources_block(self, page: Page) -> str:
        if not page.cited:
            return ""
        ja = page.lang == "ja"
        items = []
        for i, sid in enumerate(page.cited, 1):
            s = self.sources[sid]
            note = f'<span class="src__note">{html.escape(s.note)}</span>' if s.note else ""
            items.append(
                f'<li id="src-{i}">{html.escape(s.publisher)}「{html.escape(s.title)}」 '
                f'<a href="{html.escape(s.url)}" rel="noopener" target="_blank">{html.escape(s.url)}</a>'
                f'（{"取得" if ja else "retrieved"} {jdate(s.retrieved) if ja else s.retrieved.isoformat()}）{note}</li>'
            )
        h = "出典・参照した情報" if ja else "Sources"
        lead = ("施設の設備・時間・料金は変わることがあります。予約前に予約サイトまたは施設の公式情報で確認してください。"
                if ja else "Facilities, times and prices change. Check the booking site or the property before booking.")
        return f'<section class="sources"><h2>{h}</h2><p>{lead}</p><ol>{"".join(items)}</ol></section>'

    def related_block(self, page: Page) -> str:
        urls = page.meta.get("related", [])
        ps = [self.by_url[u] for u in urls if u in self.by_url and self._visible(self.by_url[u])]
        missing = [u for u in urls if u not in self.by_url]
        for u in missing:
            self.errors.append(f"{page.id}: related link to missing page {u}")
        if not ps:
            return ""
        return f'<section class="related">{self.index_rows(ps, "あわせて読む" if page.lang == "ja" else "Related")}</section>'

    # ------------------------------------------------------------------ full page

    def render(self, page: Page) -> str:
        page.cited = []
        body = self.shortcodes(page, page.body)
        n = 0

        def add_id(m):
            nonlocal n
            n += 1
            return f'<h2 id="s{n}">'
        body = re.sub(r"<h2>", add_id, body)

        crumbs, trail = self.breadcrumbs(page)
        head = self.head_block(page, crumbs)
        toc = self.toc(body) if page.type in ("article", "comparison") else ""
        tail = self.related_block(page) + self.sources_block(page)

        # Grounds: the head sits on night; reading bodies on cream; related + sources back on
        # night. The 24h page carries its own light per hour, so it is never wrapped.
        day = page.meta.get("body_class") == "day"
        if page.type in ("article", "comparison") and not day:
            main = (f'<div class="wrap">{head}</div>'
                    f'<div class="wrap"><div class="ground-cream"><div class="layout">'
                    f'<article class="prose">{body}</article>'
                    f'<aside class="side">{toc}</aside></div></div></div>'
                    f'<div class="wrap tail">{tail}</div>')
        elif page.type in ("article", "comparison"):
            main = (f'<div class="wrap">{head}</div><div class="wrap layout">'
                    f'<article class="prose">{body}{tail}</article>'
                    f'<aside class="side">{toc}</aside></div>')
        elif page.type in ("about", "contact"):
            main = (f'<div class="wrap">{head}</div>'
                    f'<div class="wrap"><div class="ground-cream">{body}{tail}</div></div>')
        else:
            main = f'<div class="wrap">{head}</div><div class="wrap">{body}{tail}</div>'

        page.links = set(re.findall(r'href="(/[^"#?]*)', crumbs + body + tail))
        schema = seo.jsonld(self, page, trail)
        commercial = page.type in ("property", "comparison")
        extra = ""
        if page.type == "property":
            extra = self.booking.sticky(page, "空港から乗り換えなしの宿", "空室を見る") + self.booking.rail(page)
        elif commercial:
            extra = self.booking.sticky(page, "浅草橋のホテルを比較", "料金を比較")
        return self.layout(page, main, schema, extra)

    def layout(self, page: Page, main: str, schema: str, extra: str) -> str:
        base = self.cfg.get("base_url").rstrip("/")
        canonical = base + page.url
        title = html.escape(page.title)
        desc = html.escape(page.meta["description"])
        hreflang = ""
        if page.meta.get("alt_url"):
            other = "en" if page.lang == "ja" else "ja"
            hreflang = (f'<link rel="alternate" hreflang="{page.lang}" href="{canonical}">'
                        f'<link rel="alternate" hreflang="{other}" href="{base}{page.meta["alt_url"]}">'
                        f'<link rel="alternate" hreflang="x-default" href="{base}/">')
        robots = '<meta name="robots" content="noindex">' if page.meta.get("noindex") else ""
        wid = self.cfg.get("analytics.website_id")
        analytics = (f'<script defer src="{self.cfg.get("analytics.src")}" data-website-id="{wid}" '
                     f'data-domains="{self.cfg.get("analytics.domains")}"></script>') if wid else ""
        nav = "".join(
            f'<li><a href="{u}"{" aria-current=\"page\"" if (u == page.url or (u != "/" and page.url.startswith(u))) else ""}>{t}</a></li>'
            for u, t in NAV)
        foot_cols = "".join(
            f'<div><p class="foot__h">{h}</p><ul>' + "".join(f'<li><a href="{u}">{t}</a></li>' for u, t in links) + "</ul></div>"
            for h, links in FOOT_NAV)
        banner = ""
        if self.preview:
            miss = self.cfg.missing(Config.REQUIRED) + self.cfg.missing(Config.RECOMMENDED)
            if miss or page.status != "published":
                what = "、".join(miss) if miss else "なし"
                banner = (f'<div class="preview">プレビュー表示 — 未設定: {what}'
                          f'{" ／ このページは " + page.status if page.status != "published" else ""}'
                          f'（本番ビルドには出力されません）</div>')
        publisher = self.cfg.get("publisher") or self.cfg.get("name")
        name = self.cfg.get("name")
        return f"""<!DOCTYPE html>
<html lang="{page.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
{robots}{hreflang}
<meta property="og:type" content="{"website" if page.type in ("property", "index", "hub") else "article"}">
<meta property="og:site_name" content="{name}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="{"ja_JP" if page.lang == "ja" else "en_US"}">
<meta property="og:image" content="{self.cfg.get("base_url", "").rstrip("/")}{self.share_image(page)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Noto+Serif+JP:wght@500;600;700&display=swap">
<link rel="stylesheet" href="{asset("/assets/css/site.css")}">
<link rel="stylesheet" href="{asset("/assets/css/atlas.css")}">
<link rel="stylesheet" href="{asset("/assets/css/motion.css")}">
<link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
{schema}
{analytics}
</head>
<body class="t-{page.type} c-{page.meta.get("cluster", "hub")} {page.meta.get("body_class", "")}">
{banner}
<a class="skip" href="#main">本文へ移動</a>
<header class="mast">
  <div class="wrap mast__util"><span>{html.escape(self.cfg.get("tagline"))}</span><a href="/about/#ads">当サイトは広告を含みます</a></div>
  <div class="wrap mast__row">
    <a class="mast__name" href="/" aria-label="{name} トップ">{self.mark}<b>{name}</b><i>{html.escape(self.cfg.get("name_en"))}</i></a>
  </div>
  <nav class="mast__nav" aria-label="セクション"><ul class="wrap">{nav}</ul></nav>
  <a class="sky" href="/guide/24-hours-in-asakusabashi/" hidden><span class="sky__t"></span></a>
</header>
<main id="main">
{main}
</main>
<footer class="foot">
  <div class="wrap foot__grid">
    <div class="foot__about">
      <p class="foot__name">{name}</p>
      <p>浅草橋エリアの宿と街を紹介する独立したガイドです。掲載している宿泊施設の運営者ではなく、施設や運営会社との資本・提携関係はありません。予約ボタンは提携（アフィリエイト）リンクで、予約が成立すると当サイトに手数料が支払われます。支払額に上乗せされることはありません。</p>
    </div>
    {foot_cols}
  </div>
  <p class="wrap foot__legal">© {dt.date.today().year} {html.escape(publisher)}　／　掲載している施設名・商標は各権利者に帰属します。当サイトはそれらの権利者と関係がありません。</p>
</footer>
{extra}
<script src="{asset("/assets/js/site.js")}" defer></script>
{"".join(f'<script src="{asset(src)}" defer></script>' for src in page.meta.get("scripts", []))}
</body>
</html>
"""


FACT_LABELS = {
    "time_haneda": "羽田空港から",
    "time_narita": "成田空港から",
    "time_asakusa": "浅草から",
    "access_toei": "都営線",
    "access_jr": "JR",
    "checkin": "チェックイン",
    "checkout": "チェックアウト",
    "rooms_total": "客室",
    "breakfast": "朝食",
    "parking": "駐車場",
    "smoking": "喫煙",
    "wifi": "Wi-Fi",
    "luggage": "荷物",
}
