from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class _Writes(UserRateThrottle):
    """Counts only requests that change data, so reading a page never uses up the allowance."""
    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


class VoteThrottle(UserRateThrottle):
    scope = "vote"


class PayThrottle(UserRateThrottle):
    scope = "pay"


class SubmitThrottle(_Writes):
    scope = "submit"


class AccountThrottle(_Writes):
    scope = "account"


class PasswordThrottle(_Writes):
    scope = "password"


BASE = [AnonRateThrottle, UserRateThrottle]   # keep the global limits when a view adds its own