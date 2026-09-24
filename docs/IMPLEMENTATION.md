# hotelmercury.jp — production implementation plan

Written 2026-09-24 after inspecting the approved local build. Short by design; the code is the
detail.

## 1. What the approved build already gets right (kept)

- Static output, no database / plugin / PHP surface. Stays.
- Independent-guide positioning, third-person copy, 広告 labels, `rel="sponsored noopener"`.
- The banned-identity guard in the build (`489.jp`, `e-concierge`, the old phone/fax/mail,
  公式 in titles). Kept and widened.
- One central booking helper, placement IDs, Travelpayouts widget with Jon's marker `416241`.
- Fixed-ratio image slots so photography drops in without layout change.
- The hotel one-pager with anchored sections in the shibuyahotel order (Jon approved) — kept
  intact, moved to `/hotel/hotel-mercury-asakusabashi/` (§5).

## 2. What had to change

| Problem found in the approved build | Fix |
|---|---|
| Copy carried **stale or invented facts**: 2019-era prices (5,000円〜), walking times I estimated (柳橋まで5分, コース60〜80分), "女性向けアロママッサージ", room details from the scraped old site | Every figure now comes from a **fact registry with a named source and retrieval date**. The gate fails the build on any bare number-with-unit (分, 円, ㎡, 室, m/km) in prose that is not a registered fact. Unknowns are stated as unknown. |
| Jalan listing `yad319908` now resolves to a **different hotel** | Removed as a source. Current sources: Tabist booking page, hotelmercury.info, Toei timetable, organisers' own sites. |
| Content lived in one 700-line Python file | Pages are `content/pages/**.html` with TOML front matter; properties, sources, backlog are TOML. Adding a hotel or an area is a new file, not a code change. |
| `?sub_id=` was appended to a `tpx.li` short link — **unverified** that Travelpayouts passes it through | Booking URL is a **template**: if it contains `{subid}` the helper substitutes it (Travelpayouts reads SubID as the marker suffix, `416241.<subid>`, the same mechanism the widget already uses). A short link without `{subid}` is left untouched rather than mangled. Click attribution does not depend on it — see §3. |
| Contact form posted to `#` with a "preview" note; booking link `PENDING-MERCURY` | Real integration, single config value each. `--release` **refuses to build** while any required value is unset. Preview builds show a banner listing what is missing; release output never contains placeholders. |
| Visual language drifted toward the patterns the brief rules out: pill buttons, numbered three-card "reasons" row, rounded card grids, dark sticky chrome, full-bleed hero headline | Editorial redesign: masthead + section rule nav, answer-first page heads, fact panels, hairline tables with source lines, index rows instead of card grids, rectangular CTAs, one bordered booking module per decision point. |
| No measurement of which article / placement / property produces clicks | Umami (already Novatise's analytics) click events declared as `data-umami-event-*` attributes — no custom JS. Travelpayouts SubID carries the same key for bookings. `monitor.py` joins GSC + clicks + bookings into an action list. |
| No way to decide what to write next | Transparent opportunity score over a backlog file; `python build.py board` writes the editorial board (HTML + CSV). |

## 3. Architecture

```
content/site.toml            publication config — the only place release values live
content/sources.toml         every citable source: publisher, URL, retrieved date, kind
content/properties/*.toml    one file per property; facts keyed and sourced
content/pages/**.html        TOML front matter + HTML body with {{shortcodes}}
content/backlog.toml         planned articles with scoring factors (not rendered)

hm/model.py     loaders + dataclasses
hm/booking.py   the ONLY place an affiliate URL is built
hm/render.py    layout, components, shortcodes, citations, TOC
hm/seo.py       JSON-LD, sitemap, robots
hm/gate.py      quality gate + internal-link graph
hm/score.py     opportunity model + editorial board

build.py        python build.py [--release] | check | board
monitor.py      GSC / Umami / Travelpayouts CSV exports -> "what to improve next"
tests/          node-free self-checks (python tests/test_hm.py)
```

Attribution key used everywhere: `hm-<page-id>-<placement>`. It is the Umami event property, the
Travelpayouts SubID (when the booking URL allows it) and the `data-hm-cta` attribute the gate
counts.

## 4. URL map (one intent per URL)

| URL | Type | Intent / target |
|---|---|---|
| `/` | index | publication front page — navigation by intent, featured property |
| `/hotel/` | comparison | 浅草橋 ホテル — how to choose, criteria, property index |
| `/hotel/hotel-mercury-asakusabashi/` | property | ホテルマーキュリー 浅草橋 — the conversion page (Jon's one-pager structure) |
| `/area/` | hub | areas and how they connect |
| `/area/asakusabashi/` | article | 浅草橋 どんな街 — core destination guide |
| `/area/asakusabashi/dolls/` | article | 浅草橋 人形 |
| `/area/asakusabashi/wholesale/` | article | 浅草橋 問屋街 |
| `/area/asakusabashi/sumida-river/` | article | 隅田川テラス 浅草橋 |
| `/access/` | hub | 浅草橋駅 アクセス |
| `/access/haneda/` | article | 羽田空港 浅草橋 |
| `/access/narita/` | article | 成田空港 浅草橋 |
| `/guide/` | hub | practical guides index |
| `/guide/asakusabashi-vs-asakusa/` | comparison | 浅草橋 浅草 どっちに泊まる |
| `/guide/events/` | article | 浅草橋 周辺 祭り |
| `/blog/` | index | every article, grouped by intent |
| `/about/` `/contact/` `/en/` | trust / inbound | |

The old `/area/gourmet/` article is **not published**: it depended on generic claims about
restaurants nobody on the team has verified on foot. It sits in the backlog with the reason.
Every property lives at `/hotel/<property>/`, including Hotel Mercury — see §5 for why it is
not at `/`.

## 5. Trademark finding and what it changed

J-PlatPat, 2026-09-24, marks containing マーキュリー in similar-group 42A01 (lodging):

| Reg. | Mark | Class | Owner | Status |
|---|---|---|---|---|
| 3130305 | HOTEL MERCURY／ホテル マーキュリー | 42 (pre-2002 lodging) | 株式会社早川物産インターナショナル | live |
| 5756845 | マーキュリーホテル | 43, 45 | 株式会社ウラノス | live |

Booking intermediation (宿泊施設の提供の契約の媒介又は取次ぎ) sits in the same 42A01 group, so
using the name as *our* mark would be exposure. Changes made:

- `/` is the publication's front page, not the hotel page. The domain root no longer presents
  as "the Hotel Mercury site".
- Site name, nav, masthead, `og:site_name`, Organization schema: 浅草橋ホテルガイド only. The
  gate (`check_brand` + the identity-surface check) fails the build otherwise.
- The hotel name appears only descriptively — the subject of a guide page, in full current form
  (Tabist ホテルマーキュリー 浅草橋).
- Trademark notice: footer on every page, a note under the property page byline, and a section
  on `/about/#trademarks` citing the registration.

**Residual, not fixable in code:** the domain string is identical to a live registered hotel
mark. That is the fact pattern for a JP-DRP complaint and 不正競争防止法 2条1項19号. The rebuild
gives a real "legitimate interest" argument (independent guide, no impersonation, bookings sent
to the property), but only counsel can size the risk. The structural hedge is available at any
time: the build is domain-agnostic (`base_url`), so the publication can move to a neutral domain
with hotelmercury.jp 301-redirecting.

## 6. Acceptance

`python build.py check` must pass (gate), `python tests/test_hm.py` must pass, and
`python build.py --release` must succeed once the four config values are set.
