"""Friendly error pages. HTML for browsers, JSON for /api/ requests."""
import logging
import uuid

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from . import seo

log = logging.getLogger("core")


def _wants_json(request):
    return request.path.startswith("/api/")


def _page(request, status, title, message, emoji):
    if _wants_json(request):
        return JsonResponse({"detail": message}, status=status)
    return render(request, "errors/error.html",
                  {"status": status, "title": title, "message": message, "emoji": emoji,
                   "seo": seo.build(request, title=f"{title} · {seo.SITE}", noindex=True)}, status=status)


def not_found(request, exception=None):
    return _page(request, 404, "Page not found", "The page you are looking for doesn't exist or has been moved.", "🧭")


def forbidden(request, exception=None):
    return _page(request, 403, "Access denied", "You don't have permission to open this page.", "🔒")


def bad_request(request, exception=None):
    return _page(request, 400, "Bad request", "We couldn't understand that request. Please go back and try again.", "⚠️")


def csrf_failure(request, reason=""):
    log.warning("CSRF failure on %s: %s", request.path, reason)
    return _page(request, 403, "Session expired", "Your session expired. Reload the page and try again.", "⏳")


def server_error(request):
    """Kept dependency-free on purpose: no DB, no sessions, no context processors."""
    ref = uuid.uuid4().hex[:8].upper()
    log.error("500 on %s %s [ref %s]", request.method, request.path, ref)   # django.request already logs the traceback
    if _wants_json(request):
        return JsonResponse({"detail": "Something went wrong on our side.", "ref": ref}, status=500)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Something Went Wrong · LetsLaunch</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#faf5ee;color:#2b1d16;font-family:'Segoe UI',Helvetica,Arial,sans-serif;text-align:center;padding:24px}}
.box{{max-width:460px}}h1{{font-size:2rem;margin:14px 0 8px}}p{{color:#7b665a;line-height:1.6}}
a{{display:inline-block;margin-top:18px;padding:12px 24px;border-radius:12px;background:#e0475b;color:#fff;text-decoration:none;font-weight:700}}
code{{background:#f4ebe0;padding:2px 8px;border-radius:6px}}@media(prefers-color-scheme:dark){{body{{background:#15100d;color:#f7eee5}}code{{background:#28211b}}}}</style></head>
<body><div class="box"><div style="font-size:3rem">🛠️</div><h1>Something Went Wrong</h1>
<p>It's on our side, not yours. We've been notified and are looking into it. Please try again in a few minutes.</p>
<p>Reference: <code>{ref}</code></p><a href="/">Back to home</a></div></body></html>"""
    return HttpResponse(html, status=500)