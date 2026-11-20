"""Page metadata (title, description, canonical, Open Graph, Twitter, JSON-LD) for every page."""
import json
import re

from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

SITE = getattr(settings, "SITE_NAME", "LetsPublic")
TAGLINE = "Discover and Launch new Products"

# Pages that must never appear in search results
PRIVATE = ("/dashboard", "/settings", "/billing", "/analytics", "/review", "/revenue", "/submit", "/login",
           "/signup", "/password-reset", "/reset", "/verify", "/auth", "/admin", "/api", "/razorpay")

PAGES = {   # url_name -> (title, description)
    "home": (None, "Discover today's top product launches, upvote your favourites and launch your own product on {site}. "
                   "Free to launch, with optional Premium launches and ad slots."),
    "pricing": ("Pricing and Premium Launch Plans", "Launch for free, or upgrade for a gold Premium badge, priority review and more "
                "launches. Plans and ad slot pricing in INR and USD."),
    "advertise": ("Advertise Your Product", "Book a hero banner, spotlight, sidebar or category slot and put your product in front of "
                  "makers and early adopters. Live availability and instant booking."),
    "top": ("Top Products: daily, weekly and monthly", "The most upvoted products launched today, yesterday, this week and this month."),
    "products": ("Browse all Products", "Browse every product launched on {site}, ranked by upvotes or newest first."),
    "about": ("About us", "{site} is a home for new products. Learn how we help makers get their first users, feedback and momentum."),
    "contact": ("Contact us", "Questions about a launch, billing or advertising? Get in touch with the {site} team."),
    "privacy": ("Privacy Policy", "How {site} collects, uses and protects your personal data."),
    "disclaimer": ("Disclaimer", "Important information about user-submitted content, sponsored placements and external links on {site}."),
    "guide": ("Launch Guide", "A practical checklist for launching your product on {site}: what to prepare, when to launch and how to get upvotes."),
}


def _static(path):
    try:
        return static(path)
    except ValueError:                       # manifest storage without collectstatic: don't crash the page
        return settings.STATIC_URL + path


def abs_url(u):
    if not u:
        return ""
    if u.startswith(("http://", "https://")):
        return u
    return settings.SITE_URL.rstrip("/") + (u if u.startswith("/") else "/" + u)


def clip(text, n=158):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(".,;:- ") + "…"


def _strip(x):
    """Drop None values so optional fields (image, datePublished) don't appear as null."""
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if v is not None}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def ld(data):
    """JSON-LD that is safe to drop inside <script>."""
    s = json.dumps(_strip(data), ensure_ascii=False, separators=(",", ":"))
    return mark_safe(s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def organization():
    return {"@context": "https://schema.org", "@type": "Organization", "name": SITE, "url": settings.SITE_URL.rstrip("/"),
            "sameAs": [v for v in getattr(settings, "SOCIAL_LINKS", {}).values() if v]}


def website():
    base = settings.SITE_URL.rstrip("/")
    return {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": base,
            "potentialAction": {"@type": "SearchAction", "target": f"{base}/?q={{search_term_string}}",
                                "query-input": "required name=search_term_string"}}


def breadcrumbs(items):
    """items = [(name, path), ...] from the home page down to the current page."""
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": abs_url(p)} for i, (n, p) in enumerate(items)]}


def build(request, title=None, description=None, image=None, canonical=None, noindex=None,
          og_type="website", card="summary_large_image", jsonld=None):
    name = getattr(getattr(request, "resolver_match", None), "url_name", None)
    page_title, page_desc = PAGES.get(name, (None, None))

    if title is None:
        title = f"{SITE} : {TAGLINE}" if name == "home" else f"{page_title} · {SITE}" if page_title else SITE
    description = clip(description or (page_desc.format(site=SITE) if page_desc else f"{SITE}: {TAGLINE}."))

    if noindex is None:                      # default: private pages, error pages and unknown pages stay out of Google
        noindex = name is None or request.path.startswith(PRIVATE)
    noindex = bool(noindex or getattr(settings, "SEO_NOINDEX", False))

    return {"title": title, "description": description, "canonical": abs_url(canonical or request.path),
            "image": abs_url(image or _static("img/og-default.png")), "noindex": noindex, "og_type": og_type,
            "twitter_card": card, "site": SITE, "jsonld": [ld(x) for x in (jsonld or [])]}