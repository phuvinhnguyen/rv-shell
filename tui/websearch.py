#!/usr/bin/env python3
"""DuckDuckGo search for the launcher: `websearch.py QUERY` prints JSON.

The first row is a quick answer (DuckDuckGo's Instant Answer API, or the
best result's snippet), followed by the results from DuckDuckGo's
non-JavaScript page. Both are fetched at once; any failure yields fewer
rows, never a hang. Ported from raven-shell's raven_core.duckduckgo_search.
Standard library only.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402

# DuckDuckGo serves a CAPTCHA to bot-like agents on its non-JS page; send a
# plain desktop identity. No cookies or profile data are sent.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def result_url(value: str) -> str:
    """Unwrap DuckDuckGo's /l/?uddg= redirect links."""
    candidate = urljoin("https://html.duckduckgo.com/", value.strip())
    parsed = urlparse(candidate)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            candidate, parsed = target, urlparse(target)
    return candidate if parsed.scheme in ("http", "https") and parsed.netloc else ""


def url_key(value: str) -> tuple[str, str, str]:
    parsed = urlparse(value)
    return parsed.netloc.casefold().removeprefix("www."), parsed.path.rstrip("/"), parsed.query


class ResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.capture = ""
        self.buffer: list[str] = []
        self.pending = ""

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        values = {k: v or "" for k, v in attrs}
        classes = set(values.get("class", "").split())
        if "result__a" in classes:
            self.capture, self.buffer = "title", []
            self.pending = result_url(values.get("href", ""))
        elif "result__snippet" in classes and self.results:
            self.capture, self.buffer = "snippet", []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self.capture:
            return
        text = " ".join("".join(self.buffer).split())
        if self.capture == "title" and text and self.pending:
            self.results.append({"kind": "web", "title": text[:200], "snippet": "", "url": self.pending})
        elif self.capture == "snippet" and self.results:
            self.results[-1]["snippet"] = text[:400]
        self.capture, self.buffer, self.pending = "", [], ""


class LiteParser(HTMLParser):
    """lite.duckduckgo.com: links with class result-link, snippets in td.result-snippet."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.capture = ""
        self.buffer: list[str] = []
        self.pending = ""

    def handle_starttag(self, tag, attrs):
        values = {k: v or "" for k, v in attrs}
        classes = set(values.get("class", "").split())
        if tag == "a" and "result-link" in classes:
            self.capture, self.buffer, self.pending = "title", [], result_url(values.get("href", ""))
        elif tag == "td" and "result-snippet" in classes and self.results:
            self.capture, self.buffer = "snippet", []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if not self.capture or tag != ("a" if self.capture == "title" else "td"):
            return
        text = " ".join("".join(self.buffer).split())
        if self.capture == "title" and text and self.pending:
            self.results.append({"kind": "web", "title": text[:200], "snippet": "", "url": self.pending})
        elif self.capture == "snippet":
            self.results[-1]["snippet"] = text[:400]
        self.capture, self.buffer, self.pending = "", [], ""


def fetch(url: str, timeout: float, form: dict | None = None) -> str:
    try:
        request = Request(url, data=urlencode(form).encode() if form else None,
                          headers={"User-Agent": USER_AGENT,
                                   "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"})
        with urlopen(request, timeout=timeout) as response:
            return response.read(2_000_000).decode(response.headers.get_content_charset() or "utf-8", "replace")
    except (OSError, ValueError):
        return ""


def search(query: str, limit: int = 6, locale: str = "wt-wt", timeout: float = 6.0) -> list[dict[str, str]]:
    query = query.strip()
    if not query:
        return []
    q = quote_plus(query)
    html_url = f"https://html.duckduckgo.com/html/?q={q}&kl={quote_plus(locale)}"
    answer_url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&no_redirect=1&skip_disambig=1"
    with ThreadPoolExecutor(max_workers=2) as pool:
        html_future = pool.submit(fetch, html_url, timeout)
        answer_future = pool.submit(fetch, answer_url, timeout)
        html_text, answer_text = html_future.result(), answer_future.result()

    parser = ResultsParser()
    try:
        parser.feed(html_text)
    except (ValueError, AssertionError):
        parser.results = []
    if not parser.results:
        # The HTML page answers rapid repeat searches with a bot check; the
        # lite page usually still works.
        parser = LiteParser()
        try:
            parser.feed(fetch("https://lite.duckduckgo.com/lite/", timeout, {"q": query, "kl": locale}))
        except (ValueError, AssertionError):
            parser.results = []
    # The same page often appears twice (http/https, a #fragment, a mirror).
    results, seen = [], set()
    for item in parser.results:
        keys = {url_key(item["url"]), item["title"].casefold()}
        if not keys & seen:
            seen |= keys
            results.append(item)

    answer, source = "", ""
    try:
        payload = json.loads(answer_text) if answer_text else {}
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        for text_key, source_key in (("Answer", "AbstractURL"), ("AbstractText", "AbstractURL"),
                                     ("Definition", "DefinitionURL")):
            text = " ".join(str(payload.get(text_key) or "").split())
            if text:
                answer, source = text[:700], result_url(str(payload.get(source_key) or ""))
                break
    out: list[dict[str, str]] = []
    if answer:
        out.append({"kind": "answer", "title": "Quick answer", "snippet": answer,
                    "url": source or f"https://duckduckgo.com/?q={q}"})
        results = [r for r in results if not source or url_key(r["url"]) != url_key(source)]
    elif results and results[0]["snippet"]:
        top = results.pop(0)
        out.append({"kind": "answer", "title": top["title"], "snippet": top["snippet"], "url": top["url"]})
    return out + results[:limit]


def main(argv: list[str]) -> int:
    query = " ".join(argv[1:])
    prefs = rvlib.settings().get("launcher", {})
    rows = search(query, int(prefs.get("webResults", 6)), str(prefs.get("webLocale", "wt-wt")))
    print(json.dumps(rows, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
