"""Static checks on the portal's HTML. Regression for #25 (password in URL)."""
from html.parser import HTMLParser
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "app" / "api" / "permitpass" / "web"
PAGES = sorted(WEB.glob("*.html"))


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.forms.append({"method": (a.get("method") or "get").lower(), "id": a.get("id"), "password": False})
        elif tag == "input" and a.get("type") == "password" and self.forms:
            self.forms[-1]["password"] = True


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_forms_with_passwords_never_submit_by_get(page):
    parser = _Forms()
    parser.feed(page.read_text())
    leaky = [f["id"] for f in parser.forms if f["password"] and f["method"] != "post"]
    assert not leaky, f"{page.name}: password forms that would put credentials in the URL: {leaky}"


def test_login_page_has_a_password_form():
    """Guards the test above against silently checking nothing."""
    parser = _Forms()
    parser.feed((WEB / "index.html").read_text())
    assert any(f["password"] for f in parser.forms)
