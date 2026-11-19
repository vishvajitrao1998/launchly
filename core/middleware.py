class NoIndexApiMiddleware:
    """API and admin responses can be crawled (pages need the API to render) but must not be indexed."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/admin/")):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response