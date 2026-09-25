"""Track D tests: optional browser capability.

All backends are mocked — no Playwright/Chromium install and no live
network needed. Each test pins the backend preference order and the
honest capability reporting of every API.
"""
import sys
import types

import pytest

import tools.browser as browser_mod
from tools.browser import (
    backend_status,
    browse,
    fetch_text,
    probe_backend,
    screenshot,
)


@pytest.fixture()
def fresh_backend(monkeypatch):
    """Reset the cached backend probe for each test."""
    monkeypatch.setattr(browser_mod, "_BACKEND", None)
    monkeypatch.setattr(browser_mod, "_CHROMIUM_EXE", None)
    yield
    monkeypatch.setattr(browser_mod, "_BACKEND", None)
    monkeypatch.setattr(browser_mod, "_CHROMIUM_EXE", None)


def _install_fake_playwright(monkeypatch, page):
    class FakePW:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @property
        def chromium(self):
            return types.SimpleNamespace(launch=lambda: _FakeBrowser(page))

    fake_sync = types.ModuleType("playwright.sync_api")
    fake_sync.sync_playwright = FakePW
    fake_top = types.ModuleType("playwright")
    fake_top.sync_api = fake_sync
    monkeypatch.setitem(sys.modules, "playwright", fake_top)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync)


class _FakePage:
    def __init__(self):
        self.calls = []

    def goto(self, url, timeout=None):
        self.calls.append(("goto", url))

    def inner_text(self, selector):
        self.calls.append(("inner_text", selector))
        return "Hello rendered world"

    def title(self):
        return "Fake Title"

    def click(self, selector, timeout=None):
        self.calls.append(("click", selector))

    def fill(self, selector, value, timeout=None):
        self.calls.append(("fill", selector, value))

    def wait_for_timeout(self, ms):
        self.calls.append(("wait", ms))

    def screenshot(self, path=None):
        self.calls.append(("screenshot", path))
        with open(path, "wb") as f:
            f.write(b"PNG")


class _FakeBrowser:
    def __init__(self, page):
        self._page = page

    def new_page(self, viewport=None):
        return self._page

    def close(self):
        pass


# ----
# ---------------------------------------------------------------- probing

def test_playwright_preferred_when_installed(monkeypatch, fresh_backend):
    page = _FakePage()
    _install_fake_playwright(monkeypatch, page)
    assert probe_backend() == "playwright"


def test_chromium_used_when_no_playwright(monkeypatch, fresh_backend):
    assert "playwright" not in sys.modules
    monkeypatch.setattr(browser_mod.shutil, "which",
                        lambda exe: "/usr/bin/chromium" if exe == "chromium" else None)
    assert probe_backend() == "chromium"


def test_http_fallback_when_nothing_installed(monkeypatch, fresh_backend):
    assert "playwright" not in sys.modules
    monkeypatch.setattr(browser_mod.shutil, "which", lambda exe: None)
    assert probe_backend() == "http"
    status = backend_status()
    assert status["rendering"] is False
    assert status["screenshots"] is False
    assert status["automation"] is False
    assert status["install"]  # guidance present


# ---------------------------------------------------------------- fetch_text

class _FakeHeaders:
    def get_content_charset(self):
        return "utf-8"


class _FakeHTTPResp:
    def __init__(self, body):
        self._body = body
        self.headers = _FakeHeaders()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_text_http_strips_tags_no_js_claim(monkeypatch, fresh_backend):
    monkeypatch.setattr(browser_mod.shutil, "which", lambda exe: None)
    html = (b"<html><head><script>var x=1;</script></head>"
            b"<body><h1>Hi</h1><p>plain text</p></body></html>")
    monkeypatch.setattr(browser_mod.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeHTTPResp(html))
    r = fetch_text("https://example.com")
    assert r["ok"] is True
    assert r["backend"] == "http"
    assert r["rendered_js"] is False  # never claims JS rendering
    assert "Hi" in r["text"] and "plain text" in r["text"]
    assert "<h1>" not in r["text"] and "var x=1" not in r["text"]


def test_fetch_text_uses_playwright_when_available(monkeypatch, fresh_backend):
    page = _FakePage()
    _install_fake_playwright(monkeypatch, page)
    r = fetch_text("https://example.com")
    assert r["ok"] is True
    assert r["backend"] == "playwright"
    assert r["rendered_js"] is True
    assert r["text"] == "Hello rendered world"


def test_fetch_text_rejects_non_http_scheme(fresh_backend):
    with pytest.raises(ValueError):
        fetch_text("file:///etc/passwd")


# ---------------------------------------------------------------- screenshot

def test_screenshot_http_backend_gives_install_guidance(monkeypatch, fresh_backend):
    monkeypatch.setattr(browser_mod.shutil, "which", lambda exe: None)
    r = screenshot("https://example.com", "/tmp/x.png")
    assert r["ok"] is False
    assert "install" in r and r["install"]
    assert "Screenshots" in r["error"]


def test_screenshot_chromium_invokes_binary(monkeypatch, fresh_backend, tmp_path):
    assert "playwright" not in sys.modules
    monkeypatch.setattr(browser_mod.shutil, "which",
                        lambda exe: "/usr/bin/chromium" if exe == "chromium" else None)
    calls = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **kw):
        calls["argv"] = argv
        out = tmp_path / "shot.png"
        out.write_bytes(b"PNG")
        return _Proc()

    monkeypatch.setattr(browser_mod.subprocess, "run", fake_run)
    r = screenshot("https://example.com", str(tmp_path / "shot.png"))
    assert r["ok"] is True and r["backend"] == "chromium"
    assert any(a.startswith("--screenshot=") for a in calls["argv"])


def test_screenshot_playwright(monkeypatch, fresh_backend, tmp_path):
    page = _FakePage()
    _install_fake_playwright(monkeypatch, page)
    target = tmp_path / "pw.png"
    r = screenshot("https://example.com", str(target))
    assert r["ok"] is True and r["backend"] == "playwright"
    assert ("screenshot", str(target)) in page.calls


# ---------------------------------------------------------------- browse

def test_browse_requires_playwright(monkeypatch, fresh_backend):
    monkeypatch.setattr(browser_mod.shutil, "which", lambda exe: None)
    r = browse("https://example.com", [{"type": "text"}])
    assert r["ok"] is False
    assert "install" in r


def test_browse_playwright_action_primitives(monkeypatch, fresh_backend):
    page = _FakePage()
    _install_fake_playwright(monkeypatch, page)
    r = browse("https://example.com", [
        {"type": "click", "selector": "#go"},
        {"type": "fill", "selector": "#q", "value": "hi"},
        {"type": "wait", "ms": 50},
        {"type": "text"},
        {"type": "title"},
        {"type": "bogus"},
    ])
    assert r["ok"] is True and r["backend"] == "playwright"
    kinds = [x["type"] for x in r["results"]]
    assert kinds == ["click", "fill", "wait", "text", "title", "bogus"]
    assert r["results"][3]["text"] == "Hello rendered world"
    assert r["results"][4]["title"] == "Fake Title"
    assert "error" in r["results"][5]
