"""robots.txt and sitemap.xml"""
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from .models import Category, Product

STATIC_URLS = [("/", "daily", "1.0"), ("/top/", "daily", "0.8"), ("/products/", "daily", "0.8"),
               ("/pricing/", "monthly", "0.6"), ("/advertise/", "monthly", "0.6"), ("/guide/", "monthly", "0.5"),
               ("/about/", "yearly", "0.4"), ("/contact/", "yearly", "0.4"),
               ("/privacy/", "yearly", "0.2"), ("/disclaimer/", "yearly", "0.2")]


def robots_txt(request):
    base = settings.SITE_URL.rstrip("/")
    if getattr(settings, "SEO_NOINDEX", False):          # staging / test servers
        body = "User-agent: *\nDisallow: /\n"
    else:
        # /api/ stays crawlable on purpose: our pages fill themselves from it, and Google must render them.
        # API responses carry an "X-Robots-Tag: noindex" header instead (see core/middleware.py).
        body = ("User-agent: *\n"
                "Disallow: /admin/\nDisallow: /dashboard/\nDisallow: /settings/\nDisallow: /billing/\n"
                "Disallow: /analytics/\nDisallow: /review/\nDisallow: /revenue/\nDisallow: /submit/\n"
                "Disallow: /login/\nDisallow: /signup/\nDisallow: /password-reset/\nDisallow: /reset/\n"
                "Disallow: /verify/\nDisallow: /auth/\nDisallow: /*?q=\n\n"
                f"Sitemap: {base}/sitemap.xml\n")
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    xml = cache.get("sitemap_xml")
    if xml is None:
        base = settings.SITE_URL.rstrip("/")

        def url(path, freq, prio, last=None):
            return (f"<url><loc>{escape(base + path)}</loc>" + (f"<lastmod>{last:%Y-%m-%d}</lastmod>" if last else "")
                    + f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>")

        rows = [url(p, f, pr) for p, f, pr in STATIC_URLS]
        rows += [url(f"/category/{s}/", "weekly", "0.6") for s in Category.objects.values_list("slug", flat=True)]
        live = Product.objects.live().order_by("-launch_at").values_list("slug", "updated_at")[:49000]   # protocol limit is 50,000 URLs
        rows += [url(f"/product/{s}/", "weekly", "0.7", u) for s, u in live]
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + "".join(rows) + "</urlset>")
        cache.set("sitemap_xml", xml, 3600)               # new products show up within an hour
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")