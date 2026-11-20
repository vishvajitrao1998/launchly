"""Static choices and validators for the product details form."""
import re
from urllib.parse import urlparse

from django.utils.text import slugify

PLATFORMS = [   # (key, label, icon)
    ("web", "Web app", "🌐"), ("mobile", "Mobile app", "📱"), ("ios", "iOS", "🍎"), ("android", "Android", "🤖"),
    ("desktop", "Desktop app", "🖥️"), ("extension", "Browser extension", "🧩"), ("api", "API / SDK", "🔌"),
]
PLATFORM_MAP = {k: (label, icon) for k, label, icon in PLATFORMS}

SOCIAL = [      # (key, label, allowed domains)
    ("x", "X (Twitter)", ("x.com", "twitter.com")), ("linkedin", "LinkedIn", ("linkedin.com",)),
    ("github", "GitHub", ("github.com",)), ("instagram", "Instagram", ("instagram.com",)),
    ("youtube", "YouTube", ("youtube.com", "youtu.be")), ("facebook", "Facebook", ("facebook.com", "fb.com")),
    ("discord", "Discord", ("discord.gg", "discord.com")),
]

MAX_TAGS = 5
TAG_RE = re.compile(r"^\w[\w .+#&-]*$", re.UNICODE)


def tag_slug(name):
    return slugify(name.replace("+", " plus ").replace("#", " sharp ").replace("&", " and "))[:40]


def normalize_tag(raw):
    name = re.sub(r"\s+", " ", str(raw or "")).strip().lstrip("#").strip()
    if not 2 <= len(name) <= 30 or not TAG_RE.match(name) or not tag_slug(name):
        raise ValueError(f"“{name or raw}” isn't a valid tag (2-30 letters, numbers or . + # & -).")
    return name


def clean_social(data):
    """Keeps only known networks, and only links that really point to that network."""
    out = {}
    for key, label, domains in SOCIAL:
        url = str((data or {}).get(key) or "").strip()
        if not url:
            continue
        if len(url) > 200:
            raise ValueError(f"{label}: the link is too long.")
        u = urlparse(url if "://" in url else "https://" + url)
        host = (u.hostname or "").lower()
        if u.scheme not in ("http", "https") or not any(host == d or host.endswith("." + d) for d in domains):
            raise ValueError(f"{label}: enter a valid {domains[0]} link.")
        out[key] = u.geturl()
    return out