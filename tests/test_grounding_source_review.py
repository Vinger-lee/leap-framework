from datetime import date
from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest


def review_script():
    try:
        from scripts import review_grounding_sources
    except ImportError as exc:
        pytest.fail(f"Grounding review command is missing: {exc}", pytrace=False)
    return review_grounding_sources


@pytest.fixture
def course():
    return {
        "course_id": "test-course",
        "status": "approved",
        "reviewed_on": "2026-11-15",
        "review_due_on": "2027-05-14",
        "sources": {
            "limit": {
                "edition": "Example edition",
                "url": "https://openstax.org/book/limit",
                "markers": ["One-sided limits", "the left and the right"],
            },
        },
    }


@pytest.mark.parametrize(
    ("html", "expected_status", "expected_exit"),
    [
        ("<h2>ONE-SIDED limits</h2><p>the left&nbsp;and <em>the right</em></p>", "available", 0),
        ("<h2>One-sided limits</h2><script>the left and the right</script>", "changed", 1),
    ],
)
def test_review_requires_markers_in_page_text(course, capsys, html, expected_status, expected_exit):
    result = review_script().review(course, date(2026, 11, 15), lambda url: html)

    assert result == expected_exit
    assert f"limit: {expected_status}" in capsys.readouterr().out


@pytest.mark.parametrize(("error", "expected_status", "expected_exit"), [
    (URLError("offline"), "unavailable", 2),
    (HTTPError("https://openstax.org/book/limit", 410, "Gone", {}, None), "changed", 1),
])
def test_unreachable_page_can_be_transient_or_confirmed_gone(
    course, capsys, error, expected_status, expected_exit,
):
    def fetch(url):
        raise error

    result = review_script().review(course, date(2026, 11, 15), fetch)

    assert result == expected_exit
    assert f"limit: {expected_status}" in capsys.readouterr().out


def test_source_availability_does_not_extend_expired_review_window(course, capsys):
    result = review_script().review(
        course, date(2027, 5, 14), lambda url: "One-sided limits, the left and the right",
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "2027-05-14" in output
    assert "limit: available" in output
    assert len(output.split("revision=", 1)[1].split()[0]) == 64


def test_expired_review_window_takes_precedence_over_temporary_network_failure(course, capsys):
    def fetch(url):
        raise URLError("offline")

    assert review_script().review(course, date(2027, 5, 14), fetch) == 1
    output = capsys.readouterr().out
    assert "outside its approved review window" in output
    assert "limit: unavailable" in output


@pytest.mark.parametrize("url", [
    "http://openstax.org/book/limit",
    "https://openstax.org.example.org/limit",
    "https://author@" "openstax.org/book/limit",
    "https://openstax.org:8443/book/limit",
])
def test_review_rejects_unapproved_sources_before_fetching(course, url):
    course["sources"]["limit"]["url"] = url

    def fetch(url):
        pytest.fail("Unapproved URL reached the fetcher")

    assert review_script().review(course, date(2026, 11, 15), fetch) == 1


def test_withdrawn_pack_does_not_contact_sources(course):
    course["status"] = "withdrawn"

    def fetch(url):
        pytest.fail("Withdrawn source reached the fetcher")

    assert review_script().review(course, date(2026, 11, 15), fetch) == 1


@pytest.mark.parametrize("destination", [
    "http://openstax.org/book/new-limit",
    "https://ocw.mit.edu/book/new-limit",
    "https://elsewhere.invalid/book/new-limit",
])
def test_redirects_must_stay_on_approved_original_https_domain(monkeypatch, destination):
    script = review_script()
    start = "https://openstax.org/book/limit"

    def open_page(request, *, timeout):
        assert request.full_url == start
        return response(status=302, location=destination)

    monkeypatch.setattr(script, "build_opener", lambda *handlers: SimpleNamespace(open=open_page))

    with pytest.raises(URLError):
        script.fetch_page(start)


def response(body=b"", *, status=200, location=None):
    page = BytesIO(body)
    page.status = status
    page.headers = Message()
    page.headers["Content-Type"] = "text/html; charset=utf-8"
    if location:
        page.headers["Location"] = location
    return page


def test_fetch_rejects_oversized_response(monkeypatch):
    script = review_script()
    monkeypatch.setattr(script, "MAX_PAGE_BYTES", 8)
    monkeypatch.setattr(script, "build_opener", lambda *handlers: SimpleNamespace(
        open=lambda *args, **kwargs: response(b"123456789"),
    ))

    with pytest.raises(URLError):
        script.fetch_page("https://openstax.org/book/limit")
