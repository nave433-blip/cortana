"""Track 4 tests: deep research planner/gatherer/citation validation.

Search, fetch, and LLM calls are mocked — no network.
"""
import pytest

import core.research as research


FAKE_SEARCH = """Title: Alpha page
Link: https://example.com/alpha
Snippet: alpha snippet here
---
Title: Beta page
Link: https://example.org/beta
Snippet: beta snippet here
"""


# ---------------------------------------------------------------- parsing

def test_parse_search_links():
    links = research.parse_search_links(FAKE_SEARCH)
    assert len(links) == 2
    assert links[0]["url"] == "https://example.com/alpha"
    assert links[1]["title"] == "Beta page"


def test_parse_search_links_empty():
    assert research.parse_search_links("") == []
    assert research.parse_search_links("No web results found.") == []


# ---------------------------------------------------------------- citations

def test_validate_citations_keeps_valid():
    report, stripped = research._validate_citations("See [1] and [2].", 2)
    assert stripped == 0
    assert report == "See [1] and [2]."


def test_validate_citations_strips_out_of_range():
    report, stripped = research._validate_citations(
        "Claim one [1]. Fabricated [7] and [99].", 2)
    assert stripped == 2
    assert "[7]" not in report and "[99]" not in report
    assert "[1]" in report
    assert "[citation unavailable]" in report


# ---------------------------------------------------------------- planner

def test_plan_queries_fallback(monkeypatch):
    import core.brain as brain
    def _raise(*a, **k):
        raise RuntimeError("no llm")
    monkeypatch.setattr(brain, "think_structured", _raise)
    assert research.plan_queries("some topic") == ["some topic"]


def test_plan_queries_bounded(monkeypatch):
    import core.brain as brain
    payload = '{"queries": ["a", "b", "c", "d", "e", "f"]}'
    monkeypatch.setattr(brain, "think_structured",
                        lambda *a, **k: {"ok": True, "text": payload})
    assert research.plan_queries("t", max_queries=4) == ["a", "b", "c", "d"]


# ---------------------------------------------------------------- gather

def test_gather_sources(monkeypatch):
    import tools.search as search_mod
    import tools.browser as browser_mod
    monkeypatch.setattr(search_mod, "web_search", lambda q: FAKE_SEARCH)
    monkeypatch.setattr(browser_mod, "fetch_text",
                        lambda url, timeout=20: {
                            "text": "alpha page content about widgets " * 50,
                            "backend": "http"})
    srcs = research.gather_sources("widgets", ["widgets info"],
                                   max_pages=2, show_progress=False)
    assert len(srcs) == 2
    assert srcs[0]["url"] == "https://example.com/alpha"
    assert len(srcs[0]["snippet"]) <= research.SNIPPET_CHARS
    # dedupe: same URL twice -> one source
    srcs2 = research.gather_sources(
        "widgets", ["q1", "q2"], max_pages=8, show_progress=False)
    urls = [s["url"] for s in srcs2]
    assert len(urls) == len(set(urls))


def test_gather_sources_skips_failed_fetch(monkeypatch):
    import tools.search as search_mod
    import tools.browser as browser_mod
    monkeypatch.setattr(search_mod, "web_search", lambda q: FAKE_SEARCH)

    def _fetch(url, timeout=20):
        if "alpha" in url:
            raise RuntimeError("fetch down")
        return {"text": "beta content", "backend": "http"}
    monkeypatch.setattr(browser_mod, "fetch_text", _fetch)
    srcs = research.gather_sources("t", ["q"], show_progress=False)
    assert [s["url"] for s in srcs] == ["https://example.org/beta"]


def test_gather_sources_respects_max_pages(monkeypatch):
    import tools.search as search_mod
    import tools.browser as browser_mod
    big = "\n---\n".join(
        f"Title: P{i}\nLink: https://example.com/p{i}\nSnippet: s{i}"
        for i in range(10))
    monkeypatch.setattr(search_mod, "web_search", lambda q: big)
    monkeypatch.setattr(browser_mod, "fetch_text",
                        lambda url, timeout=20: {"text": "content " * 100,
                                                "backend": "http"})
    srcs = research.gather_sources("t", ["q"], max_pages=3, show_progress=False)
    assert len(srcs) == 3


# ---------------------------------------------------------------- compile

def test_compile_report_no_sources():
    res = research.compile_report("topic", [])
    assert res["ok"] is False


def test_compile_report_strips_bad_citations(monkeypatch):
    import core.brain as brain
    monkeypatch.setattr(
        brain, "think_structured",
        lambda *a, **k: {"ok": True,
                         "text": "## Summary\nReal [1]. Fake [42]."})
    srcs = [{"url": "https://example.com/a", "title": "A", "snippet": "s"}]
    res = research.compile_report("t", srcs)
    assert res["ok"] is True
    assert "[42]" not in res["report"]
    assert res["stripped_citations"] == 1
    assert "removed" in res["report"]


# ---------------------------------------------------------------- end to end

def test_run_research_end_to_end(monkeypatch):
    monkeypatch.setattr(research, "plan_queries", lambda t, max_queries=4: ["q1"])
    monkeypatch.setattr(research, "gather_sources",
                        lambda *a, **k: [{"url": "https://example.com/a",
                                          "title": "A", "snippet": "s"}])
    monkeypatch.setattr(research, "compile_report",
                        lambda t, s: {"ok": True, "report": "REPORT",
                                      "stripped_citations": 0})
    res = research.run_research("topic")
    assert res["ok"] is True
    assert res["report"] == "REPORT"
    assert len(res["sources"]) == 1


def test_run_research_empty_topic():
    assert research.run_research("  ")["ok"] is False


def test_run_research_no_sources(monkeypatch):
    monkeypatch.setattr(research, "plan_queries", lambda t, max_queries=4: ["q"])
    monkeypatch.setattr(research, "gather_sources", lambda *a, **k: [])
    res = research.run_research("topic")
    assert res["ok"] is False
    assert "next_steps" in res
