"""The atlas: an editorial neighbourhood map rendered to inline SVG at build time.

Why SVG and not a 3D scene: every question the map answers — where is the hotel, which
station, how far is the river, what is one train ride away — is two-dimensional. Build-time
SVG is crisp at any size, readable by screen readers through the legend, costs no runtime
JavaScript, and works identically on a phone.

Data: content/geo/places.toml (OSM points) and content/geo/rivers.json (OSM centrelines).
Walking figures are computed here — straight-line distance ÷ 80 m/min, the Japanese
real-estate advertising standard — and every place they appear says so.
"""

from __future__ import annotations

import html
import json
import math
import tomllib

from .model import CONTENT

WALK_M_PER_MIN = 80
RINGS = [(400, "5分"), (800, "10分"), (1200, "15分")]


class Atlas:
    def __init__(self):
        data = tomllib.loads((CONTENT / "geo" / "places.toml").read_text(encoding="utf-8"))
        self.lines = data.pop("lines")
        self.places = data
        self.rivers = json.loads((CONTENT / "geo" / "rivers.json").read_text(encoding="utf-8"))["rivers"]
        self.hotel = self.places["hotel-mercury"]

    # ------------------------------------------------------------------ geometry

    @staticmethod
    def metres(a, b) -> float:
        """Haversine distance between two {lat, lon} points."""
        r = 6371000
        p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
        dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(h))

    def walk_min(self, pid: str) -> tuple[int, int]:
        m = self.metres(self.hotel, self.places[pid])
        return round(m / 10) * 10, max(1, math.ceil(m / WALK_M_PER_MIN))

    def _proj(self, box):
        lat0 = (box[0] + box[2]) / 2
        kx = math.cos(math.radians(lat0))
        w, h = 1000, 1000 * (box[2] - box[0]) / ((box[3] - box[1]) * kx)

        def f(lat, lon):
            return (round((lon - box[1]) / (box[3] - box[1]) * w, 1),
                    round((box[2] - lat) / (box[2] - box[0]) * h, 1))
        # metres -> svg units, for rings and the scale bar
        m_per_unit = (box[3] - box[1]) * 111320 * kx / w
        return f, w, round(h), m_per_unit

    # ------------------------------------------------------------------ svg

    def svg(self, mode: str = "wide") -> tuple[str, list[str]]:
        box = (35.6900, 139.7700, 35.7160, 139.8135) if mode == "wide" else \
              (35.6905, 139.7770, 35.7075, 139.7985)
        P, W, H, mpu = self._proj(box)
        out = []

        # water — the rivers are centrelines, drawn as broad strokes
        for name, segs in self.rivers.items():
            width = 26 if name == "隅田川" else 9
            if mode != "wide":
                width *= 1.8
            for seg in segs:
                d = "M" + " L".join(f"{x},{y}" for x, y in (P(a, b) for a, b in seg))
                out.append(f'<path class="a-water" d="{d}" stroke-width="{width:.0f}"/>')
        sx, sy = P(35.7040, 139.7978) if mode == "wide" else P(35.7020, 139.7955)
        out.append(f'<text class="a-river" x="{sx}" y="{sy}" transform="rotate(62 {sx} {sy})">隅 田 川</text>')

        # walking rings around the hotel
        hx, hy = P(self.hotel["lat"], self.hotel["lon"])
        for r, label in RINGS:
            rr = r / mpu
            out.append(f'<circle class="a-ring" cx="{hx}" cy="{hy}" r="{rr:.1f}"/>')
            out.append(f'<text class="a-ringlabel" x="{hx}" y="{hy - rr - 5:.1f}" text-anchor="middle">{label}</text>')

        # rail lines
        for lid, ln in self.lines.items():
            pts = [P(self.places[s]["lat"], self.places[s]["lon"]) for s in ln["stations"]]
            d = "M" + " L".join(f"{x},{y}" for x, y in pts)
            out.append(f'<path class="a-case" d="{d}"/>')
            out.append(f'<path class="a-line" data-line="{lid}" d="{d}" stroke="{ln["color"]}"/>')

        # places
        legend, n = [], 0
        for pid, p in self.places.items():
            x, y = P(p["lat"], p["lon"])
            if not (0 <= x <= W and 0 <= y <= H):
                continue
            k = p["kind"]
            if mode == "wide" and k == "shop":
                continue    # shops sit on top of the station at this scale; the close-up map has them
            name = html.escape(p["name"])
            lb = p.get("label", {})
            if k == "hotel":
                out.append(f'<g class="a-hotel" data-place="{pid}"><rect x="{x-9}" y="{y-9}" width="18" height="18"/>'
                           f'<text x="{x}" y="{y+4.5}">宿</text>'
                           f'<text class="a-hotellabel" x="{x+14}" y="{y-12}">{name}</text></g>')
            elif k == "station":
                out.append(f'<g class="a-st" data-place="{pid}"><circle cx="{x}" cy="{y}" r="6"/>'
                           f'<text x="{x + lb.get("dx", 9)}" y="{y + lb.get("dy", 18)}" '
                           f'text-anchor="{lb.get("anchor", "start")}">{name}</text></g>')
            elif k == "bridge":
                out.append(f'<g class="a-br" data-place="{pid}"><circle cx="{x}" cy="{y}" r="2.5"/>'
                           f'<text x="{x + lb.get("dx", -8)}" y="{y + lb.get("dy", 3)}" '
                           f'text-anchor="{lb.get("anchor", "end")}">{name}</text></g>')
            else:
                n += 1
                out.append(f'<g class="a-pin a-{k}" data-place="{pid}"><circle cx="{x}" cy="{y}" r="10"/>'
                           f'<text x="{x}" y="{y+4}">{n}</text></g>')
                legend.append(pid)

        # scale bar (500 m) and attribution
        bar = 500 / mpu
        out.append(f'<g class="a-scale"><path d="M24,{H-30} h{bar:.1f}"/>'
                   f'<text x="24" y="{H-38}">500m</text></g>')
        out.append(f'<text class="a-attr" x="{W-12}" y="{H-12}" text-anchor="end">© OpenStreetMap contributors</text>')
        out.append(f'<g class="a-north" transform="translate({W-40},46)"><path d="M0,-18 L7,8 L0,3 L-7,8 Z"/><text y="24">N</text></g>')

        svg = (f'<svg class="atlas__svg" viewBox="0 0 {W} {H}" role="img" '
               f'aria-labelledby="atlas-t"><title id="atlas-t">浅草橋周辺の地図。宿、駅、隅田川と主な名所の位置</title>'
               + "".join(out) + "</svg>")
        return svg, legend

    # ------------------------------------------------------------------ html blocks

    def figure(self, mode: str = "wide", caption: str = "") -> str:
        svg, legend = self.svg(mode)
        items = []
        for i, pid in enumerate(legend, 1):
            p = self.places[pid]
            m, mins = self.walk_min(pid)
            label = html.escape(p["name"])
            link = f'<a href="{p["page"]}">{label}</a>' if p.get("page") else label
            items.append(f'<li data-place="{pid}"><b>{i}</b>{link}<span>直線約{m:,}m・徒歩目安{mins}分</span></li>')
        return (
            f'<figure class="atlas atlas--{mode}">'
            f'<div class="atlas__map">{svg}</div>'
            f'<figcaption class="atlas__cap">{caption}</figcaption>'
            f'<ol class="atlas__legend">{"".join(items)}</ol>'
            f'<p class="atlas__note">輪は宿からの直線距離で400m・800m・1200m（分速80mで5・10・15分）。'
            f'路線は駅どうしを直線で結んだ模式線です。徒歩の目安は直線距離から求めたもので、実際の道のりはこれより長くなります。</p>'
            f'</figure>'
        )

    def zones(self) -> list[tuple[str, list[tuple[str, int, int]]]]:
        """Basecamp: places grouped by computed straight-line walking time from the hotel.
        The hotel's own stations are excluded — their walking times come from the property's
        published figures, not from a station-centre coordinate."""
        skip = {"hotel-mercury", "st-asakusabashi-jr", "st-asakusabashi-toei"}
        bands = [(5, "徒歩5分圏"), (10, "徒歩10分圏"), (15, "徒歩15分圏"), (30, "徒歩30分圏")]
        out = {label: [] for _, label in bands}
        for pid, p in self.places.items():
            if pid in skip or p["kind"] == "station":
                continue
            m, mins = self.walk_min(pid)
            for limit, label in bands:
                if mins <= limit:
                    out[label].append((pid, m, mins))
                    break
        return [(label, sorted(out[label], key=lambda t: t[1])) for _, label in bands]
