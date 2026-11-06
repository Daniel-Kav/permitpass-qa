"""Security headers on every response (fixes #26, found by the ZAP baseline scan)."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",          # no inline scripts: page logic lives in /*.js files
    "style-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

ALWAYS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",   # verify links carry the signature: don't leak them via Referer
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# FastAPI's interactive docs load Swagger UI from a CDN, so they get the basics but not CSP/COEP
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
STATIC_ASSETS = (".css", ".js", ".png", ".svg", ".ico", ".woff2")


def cache_policy(path: str, content_type: str) -> str:
    if path.endswith(STATIC_ASSETS):
        return "public, max-age=300"
    if content_type.startswith("text/html"):
        return "no-cache"
    return "no-store"   # API responses can contain personal data


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        for name, value in ALWAYS.items():
            response.headers.setdefault(name, value)
        if not path.startswith(DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", CSP)
            response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
        response.headers.setdefault("Cache-Control", cache_policy(path, response.headers.get("content-type", "")))
        return response
