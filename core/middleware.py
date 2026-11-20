from django.middleware.clickjacking import XFrameOptionsMiddleware


class NoIndexApiMiddleware:
    """API and admin responses can be crawled (pages need the API to render) but must not be indexed."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/admin/")):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class EmbedFrameMiddleware(XFrameOptionsMiddleware):
    """Normal clickjacking protection everywhere, except /embed/, which exists to be shown inside other sites."""

    def process_response(self, request, response):
        if request.path.startswith("/embed/"):
            return response
        return super().process_response(request, response)