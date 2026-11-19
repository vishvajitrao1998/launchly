from django.conf import settings

from . import seo
from .services import display_name, mask_email

SOCIAL_LABELS = {"facebook": "Facebook", "x": "X", "instagram": "Instagram",
                 "linkedin": "LinkedIn", "youtube": "YouTube"}


def site(request):
    u = request.user
    return {
        "display_name": display_name(u) if u.is_authenticated else "",
        "masked_email": mask_email(u.email) if u.is_authenticated else "",
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "google_enabled": bool(settings.GOOGLE_CLIENT_ID),
        "social_links": [{"key": k, "label": SOCIAL_LABELS[k], "url": v}
                         for k, v in settings.SOCIAL_LINKS.items() if v],
        "seo": seo.build(request),
    }