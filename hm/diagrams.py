"""Route and neighbourhood diagrams.

Built as HTML lists, not images: they reflow on a phone, a screen reader reads them in order,
and every label is text Google can see. Only station order and line connections are drawn —
facts that do not change and do not need a source note. No distances, no times.
"""

ASAKUSA_LINE = [
    # (station, number) in running order. A01–A06 (西馬込〜高輪台) are omitted: airport
    # through-trains join and leave the line at 泉岳寺 and 押上.
    ("泉岳寺", "A07"), ("三田", "A08"), ("大門", "A09"), ("新橋", "A10"), ("東銀座", "A11"),
    ("宝町", "A12"), ("日本橋", "A13"), ("人形町", "A14"), ("東日本橋", "A15"),
    ("浅草橋", "A16"), ("蔵前", "A17"), ("浅草", "A18"), ("本所吾妻橋", "A19"), ("押上", "A20"),
]


def asakusa_line() -> str:
    rows = []
    for name, num in ASAKUSA_LINE:
        cls = ' class="is-here"' if name == "浅草橋" else ""
        branch = ""
        if name == "泉岳寺":
            branch = '<span class="line__branch">京急線に直通 → 羽田空港</span>'
        if name == "押上":
            branch = '<span class="line__branch">京成線に直通 → 成田空港</span>'
        rows.append(f'<li{cls}><b>{name}</b><span class="line__n">{num}</span>{branch}</li>')
    return (
        '<figure class="diagram"><figcaption>都営浅草線と空港直通の接続（泉岳寺〜押上）</figcaption>'
        f'<ol class="line">{"".join(rows)}</ol>'
        '<p class="diagram__note">駅の並びと直通先のみを示した模式図です。すべての列車が空港まで直通するわけではありません。</p>'
        '</figure>'
    )


def neighbours() -> str:
    return (
        '<figure class="diagram"><figcaption>浅草橋のとなり駅</figcaption>'
        '<div class="nb">'
        '<div class="nb__line"><p class="nb__l">JR総武線（各駅停車）</p>'
        '<ol class="nb__st"><li>秋葉原</li><li class="is-here">浅草橋</li><li>両国</li></ol></div>'
        '<div class="nb__line"><p class="nb__l">都営浅草線</p>'
        '<ol class="nb__st"><li>東日本橋</li><li class="is-here">浅草橋</li><li>蔵前</li><li>浅草</li></ol></div>'
        '</div>'
        '<p class="diagram__note">秋葉原・両国はJRで1駅、蔵前は都営線で1駅、浅草は2駅です。</p>'
        '</figure>'
    )


def sumida_bridges() -> str:
    br = [
        ("両国橋", "神田川の河口より下流側"),
        ("柳橋", "神田川が隅田川に注ぐ地点。浅草橋駅から最も近い"),
        ("蔵前橋", ""),
        ("厩橋", ""),
        ("駒形橋", ""),
        ("吾妻橋", "浅草の最寄り。対岸に東京スカイツリー方面"),
    ]
    rows = "".join(
        f'<li{" class=\"is-here\"" if n == "柳橋" else ""}><b>{n}</b>'
        f'{f"<span>{d}</span>" if d else ""}</li>' for n, d in br)
    return (
        '<figure class="diagram"><figcaption>隅田川に架かる橋の並び（南 → 北）</figcaption>'
        f'<ol class="bridges">{rows}</ol>'
        '<p class="diagram__note">柳橋は神田川に架かる橋。隅田川沿いを北へ歩くと、上の順に橋をくぐります。</p>'
        '</figure>'
    )
