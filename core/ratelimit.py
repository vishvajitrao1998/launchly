"""Fixed-window rate limiting on Django's cache. Used for HTML views; DRF throttles cover /api/."""
import hashlib
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
import logging

def client_ip(request):
    """Real client IP. Behind nginx or a load balancer, set NUM_PROXIES (1 = one proxy in front)."""
    n = settings.NUM_PROXIES
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if n and xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-min(n, len(parts))]
    return request.META.get("REMOTE_ADDR", "")


def hit(key, limit, window):
    """Count one attempt. Returns (allowed, seconds_until_the_window_resets)."""
    k = "rl:" + hashlib.sha256(key.encode()).hexdigest()[:40]
    now = time.time()
    if cache.add(k, 1, window):
        cache.set(k + ":exp", now + window, window)
        return True, 0
    try:
        n = cache.incr(k)
    except ValueError:                       # the key expired between add() and incr()
        cache.add(k, 1, window)
        cache.set(k + ":exp", now + window, window)
        return True, 0
    if n > limit:
        return False, max(int((cache.get(k + ":exp") or now + window) - now), 1)
    return True, 0


def too_many(request, retry):

    if request.path.startswith("/api/"):
        resp = JsonResponse({"detail": f"Too many requests. Try again in {retry} seconds."}, status=429)
    else:
        resp = render(request, "errors/error.html", {"status": 429, "emoji": "🚦", "title": "Too many attempts",
                "message": f"For security we paused this action. Please try again in about {max(1, round(retry / 60))} minute(s)."}, status=429)
    resp["Retry-After"] = str(retry)
    logging.getLogger("django.security").warning("Rate limit hit: %s from %s", request.path, client_ip(request))
    return resp


def by_field(name):
    """Limit key from a POST field, e.g. the username or email being attacked."""
    return lambda r: (r.POST.get(name) or "").strip().lower()


def ratelimit(scope, limit, window, key="ip", methods=("POST",)):
    """@ratelimit("login", 8, 900, key=by_field("username")): max 8 POSTs per 15 min per username."""
    def deco(view):
        @wraps(view)
        def inner(request, *args, **kwargs):
            if request.method in methods:
                ident = client_ip(request) if key == "ip" else key(request)
                if ident:
                    ok, retry = hit(f"{scope}:{ident}", limit, window)
                    if not ok:
                        return too_many(request, retry)
            return view(request, *args, **kwargs)
        return inner
    return deco