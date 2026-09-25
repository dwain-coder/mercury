"""Self-checks for the hotelmercury build. No framework:  python tests/test_hm.py

Values that look like config below (a booking URL, an endpoint, a website id) are test
fixtures for an in-memory release compile. Nothing here writes to dist/.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build  # noqa: E402
import monitor  # noqa: E402
from hm import gate, model, score  # noqa: E402
from hm.booking import Booking, attribution_key  # noqa: E402


def test_priority_bounds():
    best = {k: (5 if w > 0 else 1) for k, w in score.WEIGHTS.items()}
    worst = {k: (1 if w > 0 else 5) for k, w in score.WEIGHTS.items()}
    assert score.priority(best) == 100
    assert score.priority(worst) == 0
    try:
        score.priority({**best, "demand": 6})
        raise AssertionError("out-of-range factor accepted")
    except ValueError:
        pass


def test_attribution_key():
    assert attribution_key("area-dolls", "article-end") == "hm-area-dolls-article-end"
    assert attribution_key("A B/C", "hero") == "hm-a-b-c-hero"
    assert len(attribution_key("x" * 200, "hero")) <= 60


class _Cfg:
    def __init__(self, url): self.url = url
    def get(self, k, d=""): return self.url if k == "booking.url" else "1"


class _Page:
    id, type, lang, meta = "p", "article", "ja", {"cluster": "transit"}


def test_booking_url_template():
    b = Booking(_Cfg("https://tp.media/r?marker=416241.{subid}&u=x"), preview=False)
    assert b.url(_Page, "hero") == "https://tp.media/r?marker=416241.hm-p-hero&u=x"
    short = Booking(_Cfg("https://booking.tpx.li/AbCd"), preview=False)
    assert short.url(_Page, "hero") == "https://booking.tpx.li/AbCd"     # never mangled
    html = short.button(_Page, "hero", "見る")
    for must in ('rel="sponsored noopener"', "広告", 'data-umami-event="booking-click"',
                 'data-umami-event-key="hm-p-hero"', 'data-hm-cta="hero"'):
        assert must in html, must
    try:
        short.button(_Page, "made-up", "x")
        raise AssertionError("unknown placement accepted")
    except ValueError:
        pass


def _page(body, **meta):
    base = {"id": "t", "url": "/t/", "type": "article", "title": "t", "description": "d",
            "status": "published", "updated": model.dt.date(2026, 1, 1), "cluster": "district",
            "intent": "informational", "target_query": "q", "related": ["/a/", "/b/"]}
    base.update(meta)
    return model.Page(path=Path("t.html"), meta=base, body=body)


def test_gate_catches_problems():
    errs = gate.check_pages([_page("駅から徒歩5分です。")], {}, True)
    assert any("unsourced figure" in e for e in errs), errs
    errs = gate.check_pages([_page("{{fact hotel-mercury.time_haneda}}で着きます。")], {}, True)
    assert not any("unsourced" in e for e in errs), errs
    errs = gate.check_pages([_page("この記事では浅草橋を紹介します。")], {}, True)
    assert any("filler" in e for e in errs)
    errs = gate.check_pages([_page("当ホテルは駅前です。")], {}, True)
    assert any("identity" in e for e in errs)
    errs = gate.check_pages([_page("x", title="ホテル公式サイト")], {}, True)
    assert any("公式" in e for e in errs)


def test_brand_check():
    class C:
        def get(self, k): return {"name": "ホテルマーキュリーガイド"}.get(k, "")
    assert gate.check_brand(C())


def test_real_content_passes_gate():
    _, visible, _, errs = build.compile_site(release=False)
    assert not errs, errs
    assert len(visible) >= 15


def test_release_requires_config_and_strips_placeholders():
    from hm import model
    req = model.Config.REQUIRED
    model.Config.REQUIRED = {"_unset_for_test": "x"}
    try:
        _, _, _, errs = build.compile_site(release=True)
        assert any("required for release" in e for e in errs)
    finally:
        model.Config.REQUIRED = req
    # Live config (no deep link, no analytics) ships: CTAs use the widget fallback.
    _, visible, _, errs = build.compile_site(release=True)
    assert not errs, errs
    home = next(p for p in visible if p.url == "/")
    assert 'href="/hotel/#book"' in home.html and "data-website-id" not in home.html
    fixtures = {
        "HM_PUBLISHER": "テスト運営者",
        "HM_CONTACT_ENDPOINT": "https://forms.example.invalid/f/test",
        "HM_BOOKING_URL": "https://tp.media/r?marker=416241.{subid}&u=test",
        "HM_ANALYTICS_WEBSITE_ID": "00000000-0000-0000-0000-000000000000",
    }
    old = {k: os.environ.get(k) for k in fixtures}
    os.environ.update(fixtures)
    try:
        _, visible, _, errs = build.compile_site(release=True)
        assert not errs, errs
        for p in visible:
            for bad in ("data-hm-unset", "写真枠", "preview", "PENDING"):
                assert bad not in p.html, (p.id, bad)
        home = next(p for p in visible if p.url == "/")
        assert 'data-website-id="00000000' in home.html
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_monitor_rules():
    pages = {"access-haneda": {"url": "/access/haneda/", "title": "羽田", "cluster": "transit"},
             "hotel-mercury": {"url": "/hotel/hotel-mercury-asakusabashi/", "title": "施設", "cluster": "hotels"}}
    gsc = [{"page": "https://hotelmercury.jp/access/haneda/", "impressions": "2,000", "clicks": "10",
            "ctr": "0.5%", "position": "8.2"},
           {"page": "https://hotelmercury.jp/hotel/hotel-mercury-asakusabashi/", "impressions": "300",
            "clicks": "40", "ctr": "13%", "position": "3"}]
    clicks = [{"key": "hm-hotel-mercury-room-single", "count": "25"}]
    bookings = [{"key": "hm-access-haneda-article-end", "bookings": "2", "commission": "1200"}]
    acts = monitor.analyse(gsc, [], clicks, bookings, pages)
    rules = {(a["url"], a["rule"]) for a in acts}
    assert ("/access/haneda/", 1) in rules          # earns bookings
    assert ("/access/haneda/", 3) in rules          # position 5–15
    assert ("/access/haneda/", 4) in rules          # poor CTR
    assert ("/hotel/hotel-mercury-asakusabashi/", 2) in rules   # clicks, no bookings


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok ", fn.__name__)
    print(f"{len(fns)} checks passed")
