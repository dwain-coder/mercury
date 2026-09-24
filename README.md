# hotelmercury.jp — 浅草橋ホテルガイド

Independent hotel and area guide for Asakusabashi, Tokyo, monetised through Travelpayouts
booking links. Static output — no CMS, no database, no PHP. Design and rationale:
`docs/IMPLEMENTATION.md`.

```bash
python build.py                 # preview -> dist/  (banner lists unset config; photo slots visible)
python build.py --lenient       # preview even while the gate fails (work in progress)
python build.py check           # quality gate only
python build.py --release       # production build — refuses to run until config is complete
python build.py board           # editorial board -> reports/editorial-board.{html,csv}
python monitor.py --gsc pages.csv [--gsc-prev prev.csv] [--clicks clicks.csv] [--bookings tp.csv]
python tests/test_hm.py         # self-checks
python -m http.server 8787 --directory dist
```

## The experiences

| Where | What | Built with |
|---|---|---|
| `/` | **Street Atlas** — editorial neighbourhood map (OSM stations, rivers, bridges, sights, walking rings) + magazine sections | build-time SVG (`hm/geo.py`) |
| `/hotel/hotel-mercury-asakusabashi/#basecamp` | **Basecamp** — close-up map + what is within 5 / 10 / 15 / 30 min and one train ride | SVG + computed bands |
| `/choose/` | **泊まる街を選ぶ** — 6 areas scored only on documented attributes; full table + arithmetic shown | `content/geo/neighbourhoods.toml` + `assets/js/choose.js` |
| `/guide/24-hours-in-asakusabashi/` | **24 Hours** — a day told hour by hour; background moves dawn → night | CSS only |
| every article | Magazine template: answer-first head, TOC, sourced facts, related, sources | `hm/render.py` |

No Three.js: every question these pages answer is two-dimensional, and SVG/CSS answers it
faster, sharper and accessibly. Walking times are straight-line distance ÷ 80 m/min (the
real-estate advertising standard) and are labelled as such wherever they appear.

## Photos

`content/photos.toml` — Wikimedia Commons only, CC0 / PD / CC BY / CC BY-SA (anything else is
refused by the tool). Each photo prints author, licence link and source.

```bash
python tools/commons.py search "Kaminarimon"
python tools/commons.py fetch <slot> "File:....jpg" "alt text" "caption"
```

The hotel's own photos are not on Commons and no licensed API exists (Travelpayouts retired
Hotellook). Room/exterior slots stay empty — collapsed in release — until a shoot or photos
licensed from the property. Do not reuse OTA-CDN images.

## Video, texture, motion

- **YouTube** — `content/videos.toml` + `{{youtube <key>}}`. Each id verified through YouTube's
  oEmbed endpoint (public, embeddable); prefer official channels (台東区公式チャンネル). Click-to-
  play facade: nothing loads from YouTube until play, then `youtube-nocookie.com`.
- **Hotel photos via Travelpayouts** — `booking.hotel_widget_src` in site.toml (optional): the
  script src of a Booking.com hotel-card widget Jon generates in Travelpayouts → Tools → Widgets.
  Shows the property's licensed photos inside Booking's frame. The affiliate *marker* (416241)
  cannot fetch images; the Hotellook photo API is retired.
- **Grounds** — night by default; cream sections are tinted per cluster (生成り, 砂色, 白藍, 桜色…)
  with paper grain, and fade in/out of night. Stop-motion film: `python tools/stopmotion.py`.
- **Scroll motion** — blocks slide up slowly as they enter (`assets/css/motion.css`): scroll-driven
  CSS where supported, IntersectionObserver fallback, off under reduced motion, never hides
  content without JS.

## Before the first release — four values, one file

`content/site.toml` (or the matching `HM_*` environment variable):

| Key | What | Env |
|---|---|---|
| `publisher` | Real legal or trading name of whoever runs the site | `HM_PUBLISHER` |
| `contact_endpoint` | Static-form endpoint (Formspree-style or a Cloudflare Worker) | `HM_CONTACT_ENDPOINT` |
| `booking.url` | Travelpayouts link for the property. Put `{subid}` in the marker (`marker=416241.{subid}`) to get per-placement booking attribution | `HM_BOOKING_URL` |
| `analytics.website_id` | Umami website id (tracker: analytics.novatise.com) | `HM_ANALYTICS_WEBSITE_ID` |

## Adding content

- **A fact** → `content/properties/<id>.toml` or `content/areas/<id>.toml`, with a `source` from
  `content/sources.toml`. Pages quote it as `{{fact <entity>.<key>}}`. Typing a number with a
  unit (分, 円, ㎡, 室, min, m²…) straight into prose fails the build.
- **An article** → `content/pages/<section>/<slug>.html`: TOML front matter between `+++`
  lines, then HTML. Copy an existing article's front matter; `related` needs two or more
  pages, and `target_query` must not belong to any other page.
- **An idea** → `content/backlog.toml` with its nine scoring factors. `python build.py board`.
- **A photo** → `content/photos.toml` keyed by the slot name used in `{{photo <key>}}`
  (`src`, `alt`, `width`, `height`, `credit`). Unfilled slots show in preview and vanish in release.
- **A hotel** → a new `content/properties/<id>.toml` and a page at `/hotel/<slug>/`.

Shortcodes: `fact`, `cite`, `button`, `book`, `widget`, `property`, `photo`, `diagram`,
`pages`, `faq`, `byline`, `publisher`, `contact-form`.

## Trademark

「ホテルマーキュリー」/「HOTEL MERCURY」 is a live registered mark for lodging (登録第3130305号,
株式会社早川物産インターナショナル; checked on J-PlatPat 2026-09-24). The site therefore never
uses the name as its own identity: the publication is 浅草橋ホテルガイド, the root `/` is the
publication front page, the hotel guide lives at `/hotel/hotel-mercury-asakusabashi/`, and
the gate fails if マーキュリー/Mercury appears in the masthead, nav, `og:site_name` or brand
config. The name appears only to identify the hotel being written about. The domain string
itself remains the residual exposure (JP-DRP / 不正競争防止法 2条1項19号) — see
`docs/IMPLEMENTATION.md` §5.

## Deploy

Static files: copy `dist/` (from `--release`) into the Hestia docroot for hotelmercury.jp on the
static nginx template, behind Cloudflare. Old URLs from the scraped site: `/guide/` →
`/hotel/hotel-mercury-asakusabashi/#guestroom`, `/restaurant/` → `…#restaurant`,
`/areaguide/` → `/area/asakusabashi/`; 410 for `/page9596/`, `/_templates/*`,
`/_administrator/*`. Use a Cloudflare redirect rule rather than box config.
