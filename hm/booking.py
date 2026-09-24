"""The only place an affiliate URL is built.

Every commercial element on the site comes from here, so every one carries the same four
things: the 広告 label, rel="sponsored noopener", the attribution key, and the Umami click
attributes. A template can't forget any of them because a template can't make a link.

Attribution key: hm-<page-id>-<placement>. It is
  - the Umami event property `key`        (which page + which CTA got the click)
  - the Travelpayouts SubID, when the configured URL has a {subid} slot
    (Travelpayouts reads SubID as the marker suffix: 416241.<subid>)
  - the data-hm-cta attribute the quality gate counts
"""

from __future__ import annotations

import html
import re

# Placements the site uses. Anything else is a gate error, so reports never grow a new,
# undocumented bucket nobody knows how to read.
PLACEMENTS = {
    "hero", "hotel-main", "room-single", "room-double", "room-twin", "rail", "sticky",
    "widget", "article-intro", "article-mid", "article-end", "comparison",
    "related-hotel", "faq", "area-page",
}

_SAFE = re.compile(r"[^a-z0-9-]+")


def attribution_key(page_id: str, placement: str) -> str:
    key = _SAFE.sub("-", f"hm-{page_id}-{placement}".lower()).strip("-")
    return key[:60]


class Booking:
    def __init__(self, cfg, preview: bool):
        self.cfg = cfg
        self.preview = preview

    # ---- urls

    def url(self, page, placement: str) -> str:
        tpl = self.cfg.get("booking.url")
        if not tpl:
            return ""      # see button(): the CTA falls back to the on-page search widget
        return tpl.replace("{subid}", attribution_key(page.id, placement))

    def widget_src(self, page, placement: str = "widget") -> str:
        g = self.cfg.get
        marker = f"{g('booking.widget_marker')}.{attribution_key(page.id, placement)}"
        locale = "ja" if page.lang == "ja" else "en"
        return (
            "https://tpscr.com/content?"
            f"trs={g('booking.widget_trs')}&shmarker={marker}&locale={locale}"
            f"&powered_by=true&campaign_id={g('booking.widget_campaign_id')}"
            f"&promo_id={g('booking.widget_promo_id')}"
        )

    # ---- attributes

    def _attrs(self, page, placement: str, prop: str | None) -> str:
        if placement not in PLACEMENTS:
            raise ValueError(f"{page.id}: unknown CTA placement '{placement}'")
        key = attribution_key(page.id, placement)
        a = {
            "data-hm-cta": placement,
            "data-umami-event": "booking-click",
            "data-umami-event-key": key,
            "data-umami-event-placement": placement,
            "data-umami-event-page": page.id,
            "data-umami-event-pagetype": page.type,
            "data-umami-event-cluster": page.meta.get("cluster", "-"),
            "data-umami-event-lang": page.lang,
        }
        if prop:
            a["data-umami-event-property"] = prop
        return " ".join(f'{k}="{html.escape(v)}"' for k, v in a.items())

    # ---- components

    # Where a CTA points when no deep link is configured yet: the Booking.com search widget
    # on the hotel hub, which is live and carries the same marker. Preview only — the gate
    # bans data-hm-unset, so a release build cannot ship one.
    UNSET_HREF = "/hotel/#book"

    def button(self, page, placement: str, label: str, prop: str | None = "hotel-mercury",
               cls: str = "btn-book") -> str:
        ad = "広告" if page.lang == "ja" else "Ad"
        href = self.url(page, placement)
        # The fallback stays in the same tab (it is an in-page anchor, not an outbound link),
        # but keeps rel="sponsored" so every CTA on the site is labelled identically.
        link = ('target="_blank" rel="sponsored noopener"' if href
                else 'rel="sponsored noopener" data-hm-unset="1"')
        href = href or self.UNSET_HREF
        return (
            f'<a class="{cls}" href="{html.escape(href)}" '
            f'{link} {self._attrs(page, placement, prop)}>'
            f'<span>{label}</span><small class="adtag">{ad}</small></a>'
        )

    def module(self, page, placement: str, title: str, lines: list[str], label: str,
               prop: str | None = "hotel-mercury") -> str:
        """The bordered booking module used at a decision point."""
        ja = page.lang == "ja"
        items = "".join(f"<li>{x}</li>" for x in lines)
        disc = ("予約サイトへの提携（アフィリエイト）リンクです。料金と空室は予約サイトで確認できます。"
                if ja else "Affiliate link to a booking site. Rates and availability are shown there.")
        return (
            f'<aside class="book" aria-label="{"予約" if ja else "Booking"}">'
            f'<div class="book__body"><p class="book__h">{title}</p><ul class="book__facts">{items}</ul></div>'
            f'<div class="book__act">{self.button(page, placement, label, prop)}'
            f'<p class="book__disc">{disc}</p></div></aside>'
        )

    def widget(self, page, title: str) -> str:
        ja = page.lang == "ja"
        return (
            f'<section class="widget" id="book" aria-label="{"宿泊検索" if ja else "Search"}" '
            f'data-hm-cta="widget">'
            f'<p class="widget__h">{title}<small class="adtag">{"広告" if ja else "Ad"}</small></p>'
            f'<script async src="{html.escape(self.widget_src(page))}" charset="utf-8"></script>'
            f'<p class="widget__note">{"検索結果は外部の予約サービス（Booking.com）が表示します。" if ja else "Results are served by Booking.com."}</p>'
            f'</section>'
        )

    def sticky(self, page, text: str, label: str) -> str:
        return (
            f'<div class="stickybook" hidden><span class="stickybook__t">{text}</span>'
            f'{self.button(page, "sticky", label)}</div>'
        )

    def rail(self, page) -> str:
        return (
            f'<a class="rail" href="{html.escape(self.url(page, "rail"))}" target="_blank" '
            f'rel="sponsored noopener" {self._attrs(page, "rail", "hotel-mercury")}>'
            f'<span>空室・料金</span><small>広告</small></a>'
        )
