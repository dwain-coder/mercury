"""Structured data, sitemap, robots.

Rules this module holds to:
  - The Hotel appears only as what a page is ABOUT, with sameAs pointing to the operator's own
    site. Nothing marks this publication as the hotel.
  - No Review, Rating or AggregateRating — the site publishes neither.
  - FAQPage only when the FAQ is actually rendered on the page ({{faq}} was used).
"""

from __future__ import annotations

import json


def _org(r) -> dict:
    return {
        "@type": "Organization",
        "name": r.cfg.get("publisher") or r.cfg.get("name"),
        "url": r.cfg.get("base_url").rstrip("/") + "/about/",
    }


def jsonld(r, page, trail) -> str:
    base = r.cfg.get("base_url").rstrip("/")
    url = base + page.url
    graph = []

    if trail:
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": t, "item": base + u}
                for i, (u, t) in enumerate(trail, 1)
            ],
        })

    if page.url == "/":
        graph.append({
            "@type": "WebSite", "@id": base + "/#website", "name": r.cfg.get("name"),
            "url": base + "/", "inLanguage": "ja", "publisher": _org(r),
        })

    if page.type == "property":
        ent = r.entities[page.meta["property"]]
        graph.append({
            "@type": "WebPage", "@id": url, "url": url, "name": page.title,
            "description": page.meta["description"], "inLanguage": page.lang,
            "dateModified": page.updated.isoformat(),
            "isPartOf": {"@id": base + "/#website"},
            "about": {
                "@type": "Hotel",
                "name": ent.name,
                "address": {
                    "@type": "PostalAddress", "addressCountry": "JP",
                    "postalCode": ent.postal_code, "addressRegion": ent.region,
                    "addressLocality": ent.locality, "streetAddress": ent.address,
                },
                "sameAs": [ent.official_url],
            },
        })
    elif page.type in ("article", "comparison"):
        graph.append({
            "@type": "Article", "headline": page.h1, "description": page.meta["description"],
            "inLanguage": page.lang, "mainEntityOfPage": url,
            "datePublished": page.meta.get("published", page.updated).isoformat(),
            "dateModified": page.updated.isoformat(),
            "author": _org(r), "publisher": _org(r),
        })
    else:
        graph.append({
            "@type": "AboutPage" if page.type == "about" else
                     "ContactPage" if page.type == "contact" else "CollectionPage",
            "name": page.title, "url": url, "inLanguage": page.lang,
            "description": page.meta["description"],
        })

    if page.meta.get("_faq_visible"):
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": _plain(a)}}
                for q, a in page.meta["_faq_rendered"]
            ],
        })

    doc = {"@context": "https://schema.org", "@graph": graph}
    return ('<script type="application/ld+json">'
            + json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "</script>")


def _plain(s: str) -> str:
    import re
    s = re.sub(r"<sup[^>]*>.*?</sup>", "", s)          # citation markers
    return re.sub(r"<[^>]+>", "", s).strip()


def sitemap(base: str, pages) -> str:
    urls = "\n".join(
        f"  <url><loc>{base}{p.url}</loc><lastmod>{p.updated.isoformat()}</lastmod></url>"
        for p in pages if not p.meta.get("noindex")
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n")


def robots(base: str) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
