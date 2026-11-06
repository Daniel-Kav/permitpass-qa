"""Security headers on every kind of response. Regression for #26 (ZAP findings 10020/10021/10038/10049/10063/90004)."""
import pytest

from conftest import CITIZEN, VALID_APPLICATION

from permitpass.security_headers import CSP

COMMON = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}

# (path, auth, expected Cache-Control)
RESPONSES = [
    ("/", None, "no-cache"),                       # HTML page
    ("/verify.html", None, "no-cache"),
    ("/app.js", None, "public, max-age=300"),      # static asset
    ("/styles.css", None, "public, max-age=300"),
    ("/health", None, "no-store"),                 # API JSON
    ("/applications", CITIZEN, "no-store"),        # personal data
    ("/applications", None, "no-store"),           # 401 error response
    ("/does-not-exist", None, "no-store"),         # 404
]


@pytest.mark.parametrize("path,auth,cache", RESPONSES, ids=[f"{p}{'+auth' if a else ''}" for p, a, _ in RESPONSES])
def test_headers_on_every_response(client, path, auth, cache):
    r = client.get(path, headers=auth or {})
    for name, value in COMMON.items():
        assert r.headers.get(name) == value, f"{name} on {path}"
    assert r.headers["content-security-policy"] == CSP
    assert r.headers["cross-origin-embedder-policy"] == "require-corp"
    assert "camera=()" in r.headers["permissions-policy"]
    assert r.headers["cache-control"] == cache


def test_csp_forbids_inline_scripts_and_framing():
    assert "script-src 'self'" in CSP and "unsafe-inline" not in CSP
    assert "frame-ancestors 'none'" in CSP


def test_api_docs_keep_working_without_csp(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "content-security-policy" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_portal_pages_have_no_inline_scripts():
    from pathlib import Path
    web = Path(__file__).resolve().parents[2] / "app" / "api" / "permitpass" / "web"
    offenders = [p.name for p in web.glob("*.html") if "<script>" in p.read_text() or " on" + "click=" in p.read_text()]
    assert not offenders, f"inline scripts would be blocked by the CSP: {offenders}"


def test_post_responses_are_not_cached(client):
    r = client.post("/applications", json=VALID_APPLICATION, headers=CITIZEN)
    assert r.status_code == 201
    assert r.headers["cache-control"] == "no-store"
