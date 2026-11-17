"""Check the review window and source markers for the bundled calculus pack."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from queue import Empty, SimpleQueue
import ssl
import sys
from threading import Thread
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from leap.runtime.grounding import reviewed_course, revision

APPROVED_HOSTS = frozenset({"openstax.org", "ocw.mit.edu"})
MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_REDIRECTS = 2
PAGE_TIMEOUT = 10
SOCKET_TIMEOUT = 5
REDIRECTS = (301, 302, 303, 307, 308)


def approved_host(url: str) -> str | None:
    if not isinstance(url, str) or not url.isascii() or "\\" in url:
        return None
    if any(ord(char) <= 32 or ord(char) == 127 for char in url):
        return None
    try:
        parts = urlsplit(url)
        if (parts.scheme == "https" and parts.hostname in APPROVED_HOSTS
                and parts.netloc.lower() in {parts.hostname, f"{parts.hostname}:443"}):
            return parts.hostname
    except ValueError:
        return None
    return None


class _ManualRedirects(HTTPRedirectHandler):
    # urllib normally drains redirect bodies before opening the destination.
    def http_error_302(self, request, response, code, message, headers):
        return response

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def fetch_page(url: str) -> str:
    host = approved_host(url)
    if host is None:
        raise URLError("source URL is outside the approved HTTPS hosts")
    deadline = monotonic() + PAGE_TIMEOUT
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), _ManualRedirects())
    for redirects in range(MAX_REDIRECTS + 1):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("page deadline expired")
        request = Request(url, headers={
            "Accept": "text/html, application/xhtml+xml",
            "User-Agent": "LEAP-Source-Review/1.0",
        })
        with opener.open(request, timeout=min(remaining, SOCKET_TIMEOUT)) as response:
            if response.status in REDIRECTS:
                location = response.headers.get("Location")
                if not location or redirects == MAX_REDIRECTS:
                    raise URLError("source redirects exceeded the allowed limit")
                url = urljoin(url, location)
                if approved_host(url) != host:
                    raise URLError("redirect left the original approved HTTPS host")
                continue

            if response.status != 200 or response.headers.get_content_type() not in {
                "text/html", "application/xhtml+xml",
            }:
                raise URLError("source did not serve a complete HTML page")
            body = response.read(MAX_PAGE_BYTES + 1)
            if len(body) > MAX_PAGE_BYTES:
                raise URLError("source response exceeded the byte limit")
            length = response.headers.get("Content-Length")
            if length is not None and length.lstrip("0") != str(len(body)).lstrip("0"):
                raise URLError("source response was incomplete")
            try:
                return body.decode(response.headers.get_content_charset() or "utf-8")
            except (LookupError, UnicodeError) as exc:
                raise URLError("source response could not be decoded") from exc
    raise URLError("source redirects exceeded the allowed limit")


def deadline_fetch(url: str) -> str:
    # A socket timeout alone does not bound DNS lookup or slow responses.
    # The command can exit even if a timed-out fetch is still in a system call.
    results: SimpleQueue[str | Exception] = SimpleQueue()

    def run() -> None:
        try:
            results.put(fetch_page(url))
        except Exception as exc:
            results.put(exc)

    Thread(target=run, daemon=True).start()
    try:
        result = results.get(timeout=PAGE_TIMEOUT)
    except Empty:
        raise TimeoutError("page deadline expired") from None
    if isinstance(result, Exception):
        raise result
    return result


class _PageText(HTMLParser):
    ignored_tags = {"head", "script", "style", "template"}
    block_tags = {"article", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p", "section", "td"}

    def __init__(self) -> None:
        super().__init__()
        self.fragments: list[str] = []
        self.ignored: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored_tags:
            self.ignored.append(tag)
        elif tag in self.block_tags and not self.ignored:
            self.fragments.append(" ")

    def handle_endtag(self, tag):
        if self.ignored and tag == self.ignored[-1]:
            self.ignored.pop()
        elif tag in self.block_tags and not self.ignored:
            self.fragments.append(" ")

    def handle_data(self, data):
        if not self.ignored:
            self.fragments.append(data)


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def review(course: dict, today: date, fetch: Callable[[str], str]) -> int:
    print(f"{course['course_id']} revision={revision(course)} "
          f"reviewed={course['reviewed_on']} due={course['review_due_on']} (UTC)")
    if course["status"] != "approved":
        print("Source pack is not approved.")
        return 1

    reviewed_on = date.fromisoformat(course["reviewed_on"])
    due_on = date.fromisoformat(course["review_due_on"])
    needs_review = not reviewed_on <= today < due_on
    unavailable = False
    if needs_review:
        print("Source pack is outside its approved review window.")
    for source_id, source in course["sources"].items():
        url, edition, markers = source["url"], source["edition"], source["markers"]
        if approved_host(url) is None or not edition.strip() or not markers or any(not normalize(m) for m in markers):
            print(f"{source_id}: changed (invalid URL, edition or markers in source pack)")
            needs_review = True
            continue
        try:
            html = fetch(url)
        except HTTPError as exc:
            with exc:
                status = "changed" if exc.code in (404, 410) else "unavailable"
                print(f"{source_id}: {status} ({edition}, HTTP {exc.code})")
                needs_review |= status == "changed"
                unavailable |= status == "unavailable"
            continue
        except (OSError, HTTPException) as exc:
            reason = exc.reason if isinstance(exc, URLError) else exc
            detail = type(reason).__name__ if isinstance(reason, Exception) else "unable to read source page"
            print(f"{source_id}: unavailable ({edition}, {detail})")
            unavailable = True
            continue

        parser = _PageText()
        parser.feed(html)
        parser.close()
        page_text = normalize("".join(parser.fragments))
        missing = [marker for marker in markers if normalize(marker) not in page_text]
        if missing:
            print(f"{source_id}: changed ({edition}, missing markers: {', '.join(missing)})")
            needs_review = True
        else:
            print(f"{source_id}: available ({edition}, all markers found)")

    print("Use the source pages to review the teaching claims before updating the pack manually.")
    if needs_review:
        return 1
    return 2 if unavailable else 0


def main() -> int:
    argparse.ArgumentParser(
        description=__doc__,
        epilog="Exit 0: checks passed. Exit 1: manual review required. Exit 2: source reachability unresolved.",
    ).parse_args()
    return review(reviewed_course(), datetime.now(timezone.utc).date(), deadline_fetch)


if __name__ == "__main__":
    raise SystemExit(main())
