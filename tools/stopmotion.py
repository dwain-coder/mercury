#!/usr/bin/env python3
"""Stop-motion film for the hotel page — paper cut-outs on a desk, 8 frames a second.

    python tools/stopmotion.py [route|hotel]   -> assets/video/<film>.mp4 (+ poster.webp)

Honesty rules, same as the site:
  - Every figure on screen is read from content/properties/hotel-mercury.toml (sourced facts)
    or computed from the OSM map data. Nothing is typed in here.
  - No picture of the hotel appears: there is no licensed photo of it. The film is made of the
    things this site can stand behind — the line, the map, the facts.

Stop-motion comes from two things: a low frame rate, and every cut-out being re-placed each
frame with a tiny random offset and rotation ("boil"), the way a hand re-sets paper pieces.
"""

from __future__ import annotations

import math
import random
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from hm.geo import Atlas  # noqa: E402

W, H, FPS = 1280, 720, 8
OUT = ROOT / "assets" / "video"
FONTS = Path("C:/Windows/Fonts")
NIGHT, CREAM, INK, VERM = (43, 49, 68), (247, 244, 238), (27, 27, 27), (181, 58, 44)
PINK, YELLOW, WATER, MUTED = (232, 82, 152), (242, 197, 0), (207, 221, 227), (99, 103, 109)

FACTS = tomllib.loads((ROOT / "content/properties/hotel-mercury.toml").read_text(encoding="utf-8"))["facts"]
F = {k: v["value"] for k, v in FACTS.items()}


def font(kind: str, size: int, weight: int = 500) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / ("NotoSerifJP-VF.ttf" if kind == "serif" else "NotoSansJP-VF.ttf")), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


SERIF_XL, SERIF_L, SERIF_M = font("serif", 58, 600), font("serif", 40, 600), font("serif", 30, 600)
SANS_M, SANS_S, SANS_XS = font("sans", 26, 500), font("sans", 21, 400), font("sans", 17, 400)


def desk() -> Image.Image:
    """Cream paper with a little grain, and a soft vignette — the table the pieces sit on."""
    base = Image.new("RGB", (W, H), CREAM)
    noise = Image.effect_noise((W, H), 18).convert("L").point(lambda v: 128 + (v - 128) // 6)
    grain = Image.merge("RGB", (noise, noise, noise))
    base = Image.blend(base, grain, 0.06)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * .15, -H * .25, W * 1.15, H * 1.25), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGB", (W, H), (222, 216, 204))
    return Image.composite(base, dark, vig)


DESK = desk()


class Frame:
    def __init__(self, n: int):
        self.img = DESK.copy()
        self.rng = random.Random(n * 7919)

    def jit(self, amp: float = 1.6) -> tuple[float, float]:
        return self.rng.uniform(-amp, amp), self.rng.uniform(-amp, amp)

    def piece(self, layer: Image.Image, x: float, y: float, rot_amp: float = .6) -> None:
        """Paste a cut-out with a drop shadow and per-frame boil."""
        ang = self.rng.uniform(-rot_amp, rot_amp)
        layer = layer.rotate(ang, resample=Image.BICUBIC, expand=True)
        dx, dy = self.jit()
        alpha = layer.split()[-1]
        shadow = Image.new("RGBA", layer.size, (60, 50, 40, 0))
        shadow.putalpha(alpha.point(lambda a: a * 0.28).filter(ImageFilter.GaussianBlur(5)))
        self.img.paste(shadow, (int(x + dx + 4), int(y + dy + 6)), shadow)
        self.img.paste(layer, (int(x + dx), int(y + dy)), layer)


def card(text_lines, w, pad=26, bg=(255, 255, 255), fg=INK, head=None, accent=None, head_fg=MUTED):
    """A paper card: optional small head, then lines. Returns an RGBA layer."""
    fonts = [(SANS_XS, head_fg)] if head else []
    lines = ([head] if head else []) + text_lines
    heights = [SANS_XS.size + 10] if head else []
    for t in text_lines:
        f = SERIF_M if len(t) < 16 else SANS_M
        fonts.append((f, fg))
        heights.append(f.size + 14)
    h = pad * 2 + sum(heights)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle((0, 0, w - 1, h - 1), fill=bg + (255,))
    if accent:
        d.rectangle((0, 0, 7, h - 1), fill=accent + (255,))
    y = pad
    for (f, c), t, hh in zip(fonts, lines, heights):
        d.text((pad + (8 if accent else 0), y), t, font=f, fill=c)
        y += hh
    return layer


def text_layer(t, f, fill=INK, pad=0):
    b = f.getbbox(t)
    layer = Image.new("RGBA", (b[2] + pad * 2 + 4, b[3] + pad * 2 + 8), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad, pad), t, font=f, fill=fill)
    return layer


def mark_layer(size=140):
    """The site mark, drawn with the same geometry as assets/img/mark.svg."""
    s = size / 64
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pts = [(9 + 46 * t, 40 - 68 * t * (1 - t)) for t in [i / 40 for i in range(41)]]  # Q curve peak 23
    d.line([(x * s, y * s) for x, y in pts], fill=NIGHT, width=int(4 * s), joint="curve")
    d.line([(5 * s, 40 * s), (59 * s, 40 * s)], fill=NIGHT, width=int(3 * s))
    d.line([(13 * s, 49 * s), (27 * s, 49 * s)], fill=NIGHT + (150,), width=int(2.2 * s))
    d.line([(37 * s, 49 * s), (51 * s, 49 * s)], fill=NIGHT + (150,), width=int(2.2 * s))
    d.rectangle((27.5 * s, 29 * s, 36.5 * s, 38 * s), fill=VERM)
    return layer


def caption(fr: Frame, t: str, sub: str = ""):
    fr.piece(card([t], min(W - 160, 60 + len(t) * 30), bg=NIGHT, fg=CREAM, head=sub or None,
                  head_fg=(201, 198, 191)),
             80, H - 170, rot_amp=.3)


# ---------------------------------------------------------------- scenes

LINE = ["羽田空港", "泉岳寺", "日本橋", "浅草橋", "浅草", "押上", "成田空港"]


def scene_title(n, i):
    fr = Frame(n)
    fr.piece(mark_layer(150), W / 2 - 75, 150)
    fr.piece(text_layer("Tabist ホテルマーキュリー 浅草橋", SERIF_L), 330, 330)
    fr.piece(text_layer("空港から、部屋に入るまで", SANS_M, MUTED), 480, 400)
    return fr


def _line_base(fr: Frame):
    y = 300
    xs = [110 + i * (W - 220) / (len(LINE) - 1) for i in range(len(LINE))]
    d = ImageDraw.Draw(fr.img)
    d.line([(xs[0], y), (xs[-1], y)], fill=PINK, width=10)
    for x, name in zip(xs, LINE):
        big = name == "浅草橋"
        r = 16 if big else 11
        d.ellipse((x - r, y - r, x + r, y + r), fill=INK if big else (255, 255, 255), outline=INK, width=4)
        f = SERIF_M if big else SANS_S
        tw = f.getlength(name)
        d.text((x - tw / 2, y + 30), name, font=f, fill=INK)
    d.text((xs[0] - 10, y - 110), "京急線", font=SANS_XS, fill=MUTED)
    d.text((xs[-1] - 60, y - 110), "京成線", font=SANS_XS, fill=MUTED)
    d.text((xs[3] - 50, y - 110), "都営浅草線", font=SANS_XS, fill=MUTED)
    return xs, y


def train_layer():
    layer = Image.new("RGBA", (74, 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, 73, 33), 8, fill=VERM)
    for k in range(3):
        d.rectangle((10 + k * 20, 8, 22 + k * 20, 18), fill=CREAM)
    return layer


def scene_train(n, i, total, from_left: bool):
    fr = Frame(n)
    xs, y = _line_base(fr)
    stops = xs[0:4] if from_left else xs[3:][::-1]
    step = min(int(i / (total * .8) * (len(stops) - 1) + .0001), len(stops) - 1)  # hop station to station
    fr.piece(train_layer(), stops[step] - 37, y - 62, rot_amp=2)
    if from_left:
        caption(fr, f"羽田空港から乗り換えなし　{F['time_haneda']}", "施設が案内する目安・直通列車の場合")
    else:
        caption(fr, f"成田空港から乗り換えなし　{F['time_narita']}", "施設が案内する目安・直通列車の場合")
    return fr


ATLAS = Atlas()
BOX = (35.6915, 139.7790, 35.7055, 139.7975)


def _fit():
    lat0 = (BOX[0] + BOX[2]) / 2
    kx = math.cos(math.radians(lat0))
    geo_w, geo_h = (BOX[3] - BOX[1]) * kx, (BOX[2] - BOX[0])
    avail_w, avail_h = W - 120, H - 230          # leave the bottom strip for captions
    k = min(avail_w / geo_w, avail_h / geo_h)
    ox = (W - geo_w * k) / 2
    oy = 30 + (avail_h - geo_h * k) / 2
    return kx, k, ox, oy


KX, K, OX, OY = _fit()


def P(lat, lon):
    return OX + (lon - BOX[1]) * KX * K, OY + (BOX[2] - lat) * K


def _map_base(fr: Frame):
    d = ImageDraw.Draw(fr.img)
    for name, segs in ATLAS.rivers.items():
        for seg in segs:
            d.line([P(a, b) for a, b in seg], fill=WATER, width=46 if name == "隅田川" else 18, joint="curve")
    for ln in ATLAS.lines.values():
        pts = [P(ATLAS.places[s]["lat"], ATLAS.places[s]["lon"]) for s in ln["stations"]]
        col = PINK if "浅草線" in ln["name"] else YELLOW
        d.line(pts, fill=col, width=9, joint="curve")
    for pid in ("st-asakusabashi-jr", "st-asakusabashi-toei", "st-kuramae", "st-ryogoku"):
        pl = ATLAS.places[pid]
        x, y = P(pl["lat"], pl["lon"])
        d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(255, 255, 255), outline=INK, width=4)
        if pid == "st-asakusabashi-jr":
            continue                        # the pair shares one label, set under the Toei stop
        name = "浅草橋駅" if pid == "st-asakusabashi-toei" else pl["name"]
        d.text((x + 14, y + 12), name, font=SANS_S, fill=INK)
    return P(ATLAS.hotel["lat"], ATLAS.hotel["lon"])


def hotel_piece(size=34):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle((0, 0, size - 1, size - 1), fill=VERM)
    return layer


def scene_drop(n, i, total):
    fr = Frame(n)
    hx, hy = _map_base(fr)
    fall = max(0, 1 - i / (total * .45))                      # drops in over the first half
    bounce = abs(math.sin(i * .9)) * 10 * max(0, 1 - i / (total * .7))
    fr.piece(hotel_piece(), hx - 17, hy - 17 - fall * 380 - bounce, rot_amp=3)
    if i > total * .45:
        caption(fr, F["access_toei"], F["access_jr"])
    return fr


def scene_rings(n, i, total):
    fr = Frame(n)
    hx, hy = _map_base(fr)
    px_per_m = K / 111320            # K is px per degree of latitude
    d = ImageDraw.Draw(fr.img)
    shown = min(3, 1 + int(i / (total / 3)))
    for k, (m, label) in enumerate([(400, "5分"), (800, "10分"), (1200, "15分")][:shown]):
        r = m * px_per_m
        d.ellipse((hx - r, hy - r, hx + r, hy + r), outline=NIGHT, width=3)
        d.text((hx + r * .72 + 6, hy - r * .72 - 30), label, font=SANS_M, fill=NIGHT)
    fr.piece(hotel_piece(), hx - 17, hy - 17)
    caption(fr, "人形店・問屋は宿のすぐそば、隅田川も歩ける距離", "輪は直線距離（分速80m換算）。実際の道のりは長くなります")
    return fr


CARDS = [
    ("チェックイン", F["checkin"]),
    ("チェックアウト", F["checkout"]),
    ("客室", F["rooms_total"]),
    ("広さ", f"シングル{F['single_size']}・ツイン{F['twin_size']}"),
    ("朝食", "館内の「大戸屋ごはん処」"),
    ("荷物", "チェックイン前・チェックアウト後も預かり"),
]


def scene_cards(n, i, total):
    fr = Frame(n)
    shown = min(len(CARDS), 1 + int(i / (total / len(CARDS))))
    for k, (head, value) in enumerate(CARDS[:shown]):
        col, row = k % 3, k // 3
        x, y = 80 + col * 385, 90 + row * 250
        if k == shown - 1:                                    # newest card slides in
            frac = (i % (total / len(CARDS))) / (total / len(CARDS))
            y -= (1 - min(1, frac * 2.2)) * 120
        fr.piece(card([value], 360, head=head, accent=VERM if k == 0 else None), x, y, rot_amp=1.2)
    return fr


def scene_end(n, i):
    fr = Frame(n)
    fr.piece(mark_layer(120), W / 2 - 60, 170)
    fr.piece(text_layer("空室と料金は、予約サイトで。", SERIF_L), 390, 330)
    fr.piece(text_layer("出典：施設の公式サイト・予約ページ（2026年9月確認）／地図 © OpenStreetMap contributors",
                        SANS_XS, MUTED), 260, 420)
    return fr


SCENES = [  # (renderer, seconds)
    (lambda n, i, t: scene_title(n, i), 2.5),
    (lambda n, i, t: scene_train(n, i, t, True), 4),
    (lambda n, i, t: scene_train(n, i, t, False), 3.5),
    (lambda n, i, t: scene_drop(n, i, t), 4),
    (lambda n, i, t: scene_rings(n, i, t), 4),
    (lambda n, i, t: scene_cards(n, i, t), 7),
    (lambda n, i, t: scene_end(n, i), 3),
]


# ================================================================ film 2: the hotel itself
# "泊まる前に知っておくこと" — check-in/out, rooms, the published starting price, the seasons,
# and the practical location tips. Same honesty rules: every figure from the fact registry.

def auto_card(lines, head=None, accent=None, bg=(255, 255, 255), fg=INK, head_fg=MUTED):
    """card() sized to its longest line, so long facts never overflow."""
    widest = max(max((SERIF_M if len(t) < 16 else SANS_M).getlength(t) for t in lines),
                 SANS_XS.getlength(head) if head else 0)
    return card(lines, int(widest + 26 * 2 + (8 if accent else 0) + 6), head=head, accent=accent,
                bg=bg, fg=fg, head_fg=head_fg)


def h_title(n, i):
    fr = Frame(n)
    fr.piece(mark_layer(150), W / 2 - 75, 140)
    t = text_layer("Tabist ホテルマーキュリー 浅草橋", SERIF_L)
    fr.piece(t, W / 2 - t.width / 2, 320)
    u = text_layer("泊まる前に、知っておくこと", SANS_M, MUTED)
    fr.piece(u, W / 2 - u.width / 2, 392)
    return fr


def _clock(hh, mm, label, sub, size=250):
    layer = Image.new("RGBA", (size, size + 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size / 2
    d.ellipse((6, 6, size - 6, size - 6), fill=(255, 255, 255), outline=NIGHT, width=6)
    for k in range(12):
        a = math.radians(k * 30)
        r1, r2 = c - 18, c - (34 if k % 3 == 0 else 26)
        d.line([(c + r1 * math.sin(a), c - r1 * math.cos(a)), (c + r2 * math.sin(a), c - r2 * math.cos(a))],
               fill=NIGHT, width=4 if k % 3 == 0 else 2)
    ah = math.radians(((hh % 12) + mm / 60) * 30)
    am = math.radians(mm * 6)
    d.line([(c, c), (c + (c * .48) * math.sin(ah), c - (c * .48) * math.cos(ah))], fill=NIGHT, width=9)
    d.line([(c, c), (c + (c * .72) * math.sin(am), c - (c * .72) * math.cos(am))], fill=VERM, width=5)
    d.ellipse((c - 9, c - 9, c + 9, c + 9), fill=NIGHT)
    tw = SERIF_M.getlength(label)
    d.text((c - tw / 2, size + 6), label, font=SERIF_M, fill=INK)
    sw = SANS_S.getlength(sub)
    d.text((c - sw / 2, size + 48), sub, font=SANS_S, fill=MUTED)
    return layer


def h_clocks(n, i, total):
    fr = Frame(n)
    # the check-in clock sweeps from opening to the last time you can check in
    open_h, close_h = 15, 23
    sweep = min(1, i / (total * .7))
    mins = int((open_h * 60) + sweep * (close_h - open_h) * 60) // 30 * 30   # 30-min ticks: stop-motion
    fr.piece(_clock(mins // 60, mins % 60, "チェックイン", F["checkin"]), 250, 90, rot_amp=1)
    fr.piece(_clock(10, 0, "チェックアウト", F["checkout"]), 780, 90, rot_amp=1)
    caption(fr, "チェックインの受付は夜まで。遅い便なら到着時刻を先に確認", "受付時間は予約ページの案内")
    return fr


ROOMS = [("シングル", "single_size", 10.5), ("ダブル", "double_size", 14), ("ツイン", "twin_size", 24)]


def h_rooms(n, i, total):
    fr = Frame(n)
    shown = min(3, 1 + int(i / (total * .25)))
    x = 150
    for k, (name, key, area) in enumerate(ROOMS[:shown]):
        side = int(math.sqrt(area) * 62)            # floor plans drawn to the same scale
        layer = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rectangle((0, 0, side - 1, side - 1), fill=(255, 255, 255), outline=NIGHT, width=5)
        d.line([(side * .62, side - 5), (side - 5, side - 5)], fill=CREAM, width=7)   # the door gap
        d.text((16, 14), name, font=SERIF_M, fill=INK)
        d.text((16, 58), F[key], font=SANS_S, fill=MUTED)
        drop = 0 if k < shown - 1 else max(0, 1 - (i % max(1, int(total * .25))) / (total * .12)) * 120
        fr.piece(layer, x, 400 - side - drop, rot_amp=1.4)
        x += side + 60
    caption(fr, F["room_breakdown"], "旧運営時の内訳（総数" + F["rooms_total"] + "は現行の予約ページと一致）・広さは同じ縮尺")
    return fr


def h_price(n, i, total):
    fr = Frame(n)
    price = F["single_from_price"]
    main, _, rest = price.partition("（")                      # "シングル8,000円〜" + note
    head = "公式サイトに表示された最低料金（2026年9月確認）"
    w = int(max(SERIF_XL.getlength(main), SANS_S.getlength(head)) + 120)
    layer = Image.new("RGBA", (w, 210), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle((0, 0, w - 1, 209), fill=(255, 255, 255))
    d.rectangle((0, 0, 9, 209), fill=VERM)
    d.text((48, 28), head, font=SANS_S, fill=MUTED)
    d.text((48, 70), main, font=SERIF_XL, fill=INK)
    d.text((48, 156), "（" + rest if rest else "", font=SANS_S, fill=MUTED)
    fr.piece(layer, W / 2 - w / 2, 120, rot_amp=.8)
    if i > total * .35:
        c = auto_card(["平均料金ではありません。", "日付を入れて予約サイトで比べるのが確実です。"])
        fr.piece(c, W / 2 - c.width / 2, 390, rot_amp=1.2)
    return fr


SEASON = [(2, "節分会"), (3, "雛人形"), (5, "三社祭"), (6, "鳥越祭"), (7, "隅田川花火")]


def h_season(n, i, total):
    fr = Frame(n)
    d = ImageDraw.Draw(fr.img)
    tile, gap, x0, y0 = 78, 12, 96, 150
    hot = dict(SEASON)
    shown = min(len(SEASON), int(i / (total * .8) * len(SEASON)) + 1)
    lit = {m for m, _ in SEASON[:shown]}
    for m in range(1, 13):
        x = x0 + (m - 1) * (tile + gap)
        on = m in lit
        layer = Image.new("RGBA", (tile, tile + (60 if on else 0)), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        dl.rectangle((0, 0, tile - 1, tile - 1), fill=VERM if on else (255, 255, 255), outline=NIGHT, width=3)
        lbl = f"{m}月"
        dl.text(((tile - SANS_M.getlength(lbl)) / 2, 22), lbl, font=SANS_M, fill=(255, 255, 255) if on else INK)
        if on:
            ev = hot[m]
            f = SANS_XS
            dl.text(((tile - f.getlength(ev)) / 2, tile + 12), ev, font=f, fill=INK)
        fr.piece(layer, x, y0 - (10 if on else 0), rot_amp=1.5 if on else .4)
    caption(fr, "行事の時期は宿が埋まりやすい。日程が出たら早めに予約を", "日程は毎年主催者が発表（月は例年の目安）")
    return fr


def h_location(n, i, total):
    fr = Frame(n)
    hx, hy = _map_base(fr)
    fr.piece(hotel_piece(), hx - 17, hy - 17)
    tips = [("駅から", F["access_toei"]), ("駐車場", F["parking"]), ("荷物", F["luggage"])]
    shown = min(len(tips), 1 + int(i / (total / len(tips))))
    for k, (h, v) in enumerate(tips[:shown]):
        c = auto_card([v], head=h)
        fr.piece(c, max(40, W - c.width - 48), 60 + k * 150, rot_amp=1)   # kept inside the frame
    return fr


def h_end(n, i):
    fr = Frame(n)
    fr.piece(mark_layer(120), W / 2 - 60, 170)
    t = text_layer("空室と料金は、予約サイトで。", SERIF_L)
    fr.piece(t, W / 2 - t.width / 2, 330)
    u = text_layer("出典：施設の公式サイト・予約ページ（2026年9月確認）／地図 © OpenStreetMap contributors",
                   SANS_XS, MUTED)
    fr.piece(u, W / 2 - u.width / 2, 420)
    return fr


HOTEL_SCENES = [
    (lambda n, i, t: h_title(n, i), 2.5),
    (lambda n, i, t: h_clocks(n, i, t), 5),
    (lambda n, i, t: h_rooms(n, i, t), 6),
    (lambda n, i, t: h_price(n, i, t), 5),
    (lambda n, i, t: h_season(n, i, t), 6),
    (lambda n, i, t: h_location(n, i, t), 6),
    (lambda n, i, t: h_end(n, i), 3),
]

FILMS = {
    # name: (scenes, output stem, poster frame at seconds)
    "route": (SCENES, "mercury-stopmotion", 2.5 + 4 * .9),
    "hotel": (HOTEL_SCENES, "mercury-hotel-guide", 2.5 + 5 + 6 * .9),
}


def render(name: str):
    scenes, stem, poster_at = FILMS[name]
    with tempfile.TemporaryDirectory() as tmp:
        n = 0
        for fn, secs in scenes:
            total = int(secs * FPS)
            for i in range(total):
                fn(n, i, total).img.save(Path(tmp) / f"f{n:04d}.png")
                n += 1
        mp4 = OUT / f"{stem}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", str(Path(tmp) / "f%04d.png"), "-c:v", "libx264", "-preset", "slow",
                        "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        "-vf", "scale=1280:720", str(mp4)], check=True)
        Image.open(Path(tmp) / f"f{int(poster_at * FPS):04d}.png").save(
            OUT / f"{stem}-poster.webp", "WEBP", quality=72)
    print(f"{name}: {n} frames, {n / FPS:.1f}s -> {mp4.name} ({mp4.stat().st_size // 1024} KB)")


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(FILMS)
    for name in names:
        render(name)


if __name__ == "__main__":
    main()
