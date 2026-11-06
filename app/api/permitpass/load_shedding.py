"""Load shedding (#36): when a worker already has MAX_IN_FLIGHT requests, answer 503 at once.

Under overload a fast "busy, retry in 2 s" is better than queueing: the stress test showed queued requests
waiting up to 60 s while the median stayed at 10 ms. /health is never shed, so orchestrators don't kill a
worker just for being busy.
"""
import json

EXEMPT = ("/health",)
BUSY = json.dumps({"detail": "Server busy, please retry shortly"}).encode()


class LoadSheddingMiddleware:
    def __init__(self, app, max_in_flight: int):
        self.app, self.max_in_flight, self.in_flight = app, max_in_flight, 0
        self.shed = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.max_in_flight <= 0 or scope["path"] in EXEMPT:
            return await self.app(scope, receive, send)
        if self.in_flight >= self.max_in_flight:
            self.shed += 1
            await send({"type": "http.response.start", "status": 503, "headers": [
                (b"content-type", b"application/json"), (b"retry-after", b"2"),
                (b"content-length", str(len(BUSY)).encode()), (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": BUSY})
            return
        self.in_flight += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.in_flight -= 1
