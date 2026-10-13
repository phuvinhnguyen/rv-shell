#!/usr/bin/env python3
"""rv papersearch: find research papers and file them in Obsidian.

    rv open papersearch ["query"]

Searches arXiv, the ACL Anthology (through Crossref), OpenReview and Crossref
(other publishers) at once. Browse the results, read abstracts, mark papers,
then download them (filed into the papers folder with a note, like
`rv papers`) or copy all their BibTeX to the clipboard in one go.
"""

from __future__ import annotations

import curses
import json
import re
import subprocess
import sys
import textwrap
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import papers  # noqa: E402
import rvlib  # noqa: E402

SOURCES = ["arXiv", "ACL", "OpenReview", "Crossref"]
DOWNLOADS = Path.home() / ".cache" / "rv" / "papers-download"


def paper(source: str, ident: str, title: str, authors: list[str], **extra) -> dict:
    p = {"source": source, "id": ident, "title": " ".join(title.split()), "authors": authors,
         "year": "", "venue": "", "abstract": "", "url": "", "pdf": "", "bibtex": "", "doi": "", "arxiv": ""}
    p.update(extra)
    return p


def year_of(text: str) -> str:
    match = re.search(r"\b(19|20)\d{2}\b", text or "")
    return match.group(0) if match else ""


# ------------------------------------------------------------------- sources

STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or",
        "the", "to", "via", "with"}


def search_arxiv(query: str) -> list[dict]:
    # arXiv ANDs every term, and stop words match nothing.
    words = [w for w in re.findall(r"[\w-]+", query) if w.lower() not in STOP]
    if not words:
        return []
    # A title typed out in full comes first; then every paper with all the words.
    phrase = " ".join(re.findall(r"[\w-]+", query))
    entries = []
    for n, expr in enumerate((f'ti:"{phrase}"', " AND ".join(f"all:{w}" for w in words[:10]))):
        if n:
            time.sleep(1)  # arXiv asks for gentle use
        xml = papers.get(f"https://export.arxiv.org/api/query?max_results={5 if n == 0 else 20}"
                         "&sortBy=relevance&search_query=" + quote(expr))
        entries += ET.fromstring(xml).findall("a:entry", papers.ATOM)
    out, seen = [], set()
    for entry in entries:
        text = lambda tag: " ".join((entry.findtext(tag, "", papers.ATOM) or "").split())  # noqa: E731
        ident = re.sub(r"v\d+$", "", text("a:id").rsplit("/abs/", 1)[-1])
        if not ident or ident in seen:
            continue
        seen.add(ident)
        comment, journal = text("arxiv:comment"), text("arxiv:journal_ref")
        out.append(paper("arXiv", ident, text("a:title"),
                         [" ".join((a.findtext("a:name", "", papers.ATOM)).split()) for a in entry.findall("a:author", papers.ATOM)],
                         year=text("a:published")[:4], abstract=text("a:summary"),
                         venue=papers.venue_from_text(comment, journal) or "arXiv",
                         url=f"https://arxiv.org/abs/{ident}", pdf=f"https://arxiv.org/pdf/{ident}",
                         doi=text("arxiv:doi"), arxiv=ident, comment=comment, journal_ref=journal))
    return out


CROSSREF = threading.Lock()


def crossref_items(query: str, filters: str, rows: int) -> list[dict]:
    url = (f"https://api.crossref.org/works?rows={rows}&query.bibliographic={quote(query)}"
           "&select=DOI,title,author,issued,container-title,short-container-title,abstract,link,type"
           + (f"&filter={filters}" if filters else ""))
    # Crossref's public pool takes one request at a time: ACL and Crossref take turns.
    with CROSSREF:
        for attempt in range(3):
            try:
                return json.loads(papers.get(url, "application/json", timeout=30))["message"]["items"]
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
    return []


def from_crossref(source: str, item: dict) -> dict:
    authors = [" ".join(filter(None, (a.get("given"), a.get("family")))) for a in item.get("author", [])]
    year = str(((item.get("issued") or {}).get("date-parts") or [[""]])[0][0] or "")
    abstract = " ".join(re.sub(r"<[^>]+>", " ", item.get("abstract", "") or "").split())
    abstract = re.sub(r"^Abstract\s+", "", abstract)
    venue = " ".join((item.get("container-title") or [""])[0].split())
    doi = item["DOI"]
    pdf = next((l["URL"] for l in item.get("link", []) if l.get("content-type") == "application/pdf"), "")
    return paper(source, doi, (item.get("title") or [""])[0], authors, year=year, abstract=abstract,
                 venue=venue, doi=doi, url=f"https://doi.org/{doi}", pdf=pdf)


def search_acl(query: str) -> list[dict]:
    out = []
    for item in crossref_items(query, "prefix:10.18653", 15):
        p = from_crossref("ACL", item)
        anthology = p["doi"].split("/v1/", 1)[-1] if "/v1/" in p["doi"] else ""
        if anthology:
            p.update(id=anthology, url=f"https://aclanthology.org/{anthology}/",
                     pdf=f"https://aclanthology.org/{anthology}.pdf")
        p["venue"] = acl_venue(p["venue"], p["year"])
        out.append(p)
    return out


def acl_venue(name: str, year: str) -> str:
    """'Findings of the Association for Computational Linguistics: EMNLP 2023' → 'Findings of EMNLP 2023'."""
    short = papers.venue_from_text(name)
    if short:
        if not year_of(short) and year:
            short = short.replace(" Workshop", "") + f" {year}" + (" Workshop" if "Workshop" in short else "")
        return ("Findings of " if name.lower().startswith("findings") else "") + short
    for words, venue in ACL_NAMES:
        if words in name.lower():
            return f"{venue} {year}".strip() + (" Workshop" if "workshop" in name.lower() else "")
    # "Proceedings of the 23rd Workshop on Biomedical Natural Language Processing" → the workshop's name
    name = re.sub(r"^Proceedings of the (\w+ )?(\d+(st|nd|rd|th) )?", "", name)
    if not name:
        return f"ACL Anthology {year}".strip()
    return name if year_of(name) else f"{name} {year}".strip()


ACL_NAMES = [("annual meeting of the association for computational linguistics", "ACL"),
             ("north american chapter", "NAACL"), ("european chapter", "EACL"),
             ("asia-pacific chapter", "AACL"), ("empirical methods in natural language processing", "EMNLP"),
             ("computational natural language learning", "CoNLL"), ("machine translation", "WMT"),
             ("semantic evaluation", "SemEval"), ("natural language generation", "INLG"),
             ("international conference on computational linguistics", "COLING")]


def search_crossref(query: str) -> list[dict]:
    # ACL has its own list; arXiv DOIs are already covered.
    return [from_crossref("Crossref", item) for item in crossref_items(query, "", 20)
            if not item["DOI"].startswith(("10.18653/", "10.48550/"))][:15]


def search_openreview(query: str) -> list[dict]:
    out, seen = [], set()
    # api2 holds venues since 2023, the old API the ones before.
    for base, limit in (("https://api2.openreview.net", 15), ("https://api.openreview.net", 10)):
        try:
            data = json.loads(papers.get(f"{base}/notes/search?term={quote(query)}&type=terms&content=all"
                                         f"&source=forum&limit={limit}", "application/json"))
        except Exception:
            continue
        for note in data.get("notes", []):
            c = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in note.get("content", {}).items()}
            title = c.get("title") or ""
            key = papers.norm(title)
            if not title or key in seen:
                continue
            seen.add(key)
            venue = c.get("venue") or ""
            ident = note.get("forum") or note["id"]
            out.append(paper("OpenReview", ident, title, names(c.get("authors")),
                             year=year_of(venue) or year_of(c.get("_bibtex", "")), venue=venue,
                             abstract=" ".join((c.get("abstract") or "").split()), bibtex=(c.get("_bibtex") or "").strip(),
                             url=f"https://openreview.net/forum?id={ident}",
                             pdf=f"https://openreview.net/pdf?id={ident}" if c.get("pdf") else ""))
    return out


def names(authors) -> list[str]:
    """OpenReview lists authors as strings, or as {"fullname"/"name": …} on some imports."""
    out = []
    for a in authors if isinstance(authors, list) else []:
        if isinstance(a, dict):
            a = a.get("fullname") or a.get("name") or a.get("value") or ""
        if isinstance(a, str) and a.strip():
            out.append(" ".join(a.split()))
    return out


SEARCH = {"arXiv": search_arxiv, "ACL": search_acl, "OpenReview": search_openreview, "Crossref": search_crossref}


# ------------------------------------------------------------------ details

def load_abstract(p: dict) -> None:
    if p["abstract"] or p["source"] != "ACL" or not p["url"].startswith("https://aclanthology.org/"):
        return
    page = papers.try_get(p["url"])
    match = re.search(r'acl-abstract.*?<span>(.*?)</span>', page, re.S)
    if match:
        p["abstract"] = " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split())


def complete(p: dict) -> dict:
    """Fill in the BibTeX (and arXiv's venue/year) — fetched once, when needed."""
    if p["bibtex"]:
        return p
    if p["source"] == "arXiv":
        if p["doi"]:
            published = papers.crossref(p["doi"])
            if published and published.get("venue"):
                p["venue"] = papers.venue_from_text(published["venue"]) or published["venue"]
            p["bibtex"] = papers.doi_bibtex(p["doi"])
        if not p["bibtex"]:
            p["bibtex"] = papers.try_get(f"https://arxiv.org/bibtex/{p['arxiv']}").strip()
        if year_of(p["venue"]):
            p["year"] = year_of(p["venue"])
        p["bibtex"] = papers.published_bibtex(p)
    elif p["source"] == "ACL" and p["url"].startswith("https://aclanthology.org/"):
        p["bibtex"] = papers.try_get(p["url"].rstrip("/") + ".bib").strip()
    elif p["doi"]:
        p["bibtex"] = papers.doi_bibtex(p["doi"])
    if not p["bibtex"].startswith("@"):
        p["bibtex"] = papers.make_bibtex(p)
    return p


def copy(text: str) -> bool:
    try:
        proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(text.encode(), timeout=5)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def fetch_pdf(url: str) -> bytes:
    """The PDF at url, or b"" (error, login page, browser check)."""
    try:
        with urlopen(Request(url, headers={"User-Agent": papers.UA}), timeout=60) as response:
            data = response.read(200_000_000)
    except Exception:
        return b""
    return data if data.startswith(b"%PDF-") else b""


def download(p: dict) -> str:
    """Fetch the PDF and file it like `rv papers` does. Returns a short result."""
    complete(p)
    load_abstract(p)
    data = fetch_pdf(p["pdf"]) if p["pdf"] else b""
    if not data and p["source"] != "arXiv":
        # OpenReview only serves PDFs to browsers that pass its check, publishers
        # often need a login: the same paper on arXiv usually has it.
        twin = papers.arxiv_by_title(p["title"])
        if twin:
            data = fetch_pdf(f"https://arxiv.org/pdf/{twin['arxiv']}")
            p["arxiv"] = p["arxiv"] or twin["arxiv"]
    if not data:
        link = p["pdf"] or p["url"]
        if link:
            rvlib.spawn(["xdg-open", link])  # with Save In → the papers folder, the watcher files it
            return "opened in the browser — save it into the papers folder"
        return "no PDF link"
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS / (papers.safe(p["title"], 80) + ".pdf")
    target.write_bytes(data)
    meta = {k: p[k] for k in ("title", "authors", "year", "abstract", "url", "doi", "arxiv", "bibtex")}
    meta["venue"] = p["venue"] or ("arXiv" if p["source"] == "arXiv" else "")
    state = papers.load_state()
    result = papers.file_pdf(target, papers.prefs(), state, quiet=True, meta=meta)
    rvlib.write_json(papers.STATE, {**papers.load_state(), **state})
    return result.splitlines()[0].lstrip("→ ").strip()


# ------------------------------------------------------------------------ UI

class PaperSearch(rvlib.App):
    title = "Papers"
    interval = 0.25
    keys_hint = "/ search  ␣ mark  ⏎ abstract  b copy BibTeX  d download  o open  u unmark"

    def __init__(self, query: str) -> None:
        super().__init__()
        self.query = query
        self.results: dict[str, list[dict]] = {}
        self.errors: dict[str, str] = {}
        self.pending: set[str] = set()
        self.marked: dict[str, dict] = {}   # key → paper, in the order marked
        self.generation = 0
        self.asked = False
        self.lock = threading.Lock()
        self.update_tabs()

    @staticmethod
    def key(p: dict) -> str:
        return p["source"] + ":" + p["id"]

    def update_tabs(self) -> None:
        counts = {s: len(self.results.get(s, [])) for s in SOURCES}
        self.tabs = ["All"] + [f"{s} {counts[s]}" if s in self.results else s for s in SOURCES] + [f"Marked {len(self.marked)}"]

    # Searching runs in threads; the list redraws as each source answers.
    def search(self, query: str) -> None:
        self.query = query.strip()
        if not self.query:
            return
        self.generation += 1
        generation = self.generation
        self.results, self.errors, self.pending = {}, {}, set(SOURCES)
        self.index = self.scroll = 0
        for source in SOURCES:
            threading.Thread(target=self._search, args=(source, generation), daemon=True).start()

    def _search(self, source: str, generation: int) -> None:
        try:
            found, error = SEARCH[source](self.query), ""
        except Exception as e:  # network, bad JSON/XML
            found, error = [], e.__class__.__name__
        with self.lock:
            if generation != self.generation:
                return
            self.results[source] = found
            if error:
                self.errors[source] = error
            self.pending.discard(source)

    def refresh(self) -> None:
        if not self.asked and not self.query:
            self.asked = True  # ask once, on opening
            query = self.prompt("Search papers")
            if query:
                self.search(query)
        self.title = f"Papers — {self.query}" if self.query else "Papers"
        self.update_tabs()

    def rows(self) -> list[rvlib.Row]:
        with self.lock:
            name = (["All"] + SOURCES + ["Marked"])[self.tab]
            if name == "Marked":
                return [self.row(p) for p in self.marked.values()]
            rows = []
            for source in (SOURCES if name == "All" else [name]):
                found = self.results.get(source, [])
                if name == "All":
                    state = ("searching…" if source in self.pending else
                             f"failed ({self.errors[source]})" if source in self.errors else
                             f"{len(found)} found" if self.query else "")
                    rows.append(rvlib.Row(f"{source}  {state}", header=True))
                elif source in self.pending:
                    rows.append(rvlib.Row("Searching…", header=True))
                rows += [self.row(p) for p in (found[:6] if name == "All" else found)]
                if name == "All" and len(found) > 6:
                    rows.append(rvlib.Row(f"  … {len(found) - 6} more in the {source} tab (Tab)", header=True))
            return rows

    def row(self, p: dict) -> rvlib.Row:
        mark = "●" if self.key(p) in self.marked else " "
        first = p["authors"][0].split()[-1] if p["authors"] and p["authors"][0].split() else ""
        venue = p["venue"] if len(p["venue"]) <= 28 else p["venue"][:27] + "…"
        value = " · ".join(filter(None, (venue or p["year"], first)))
        return rvlib.Row(f"{mark} {p['title']}", value, data=p, colour=rvlib.GOOD if mark == "●" else 0)

    def detail(self, row: rvlib.Row | None) -> list[str]:
        if row is None or not row.data:
            if not self.query:
                return ["Press / to search arXiv, ACL, OpenReview and Crossref."]
            return []
        p = row.data
        width = max(20, self.screen.getmaxyx()[1] - 8)
        authors = ", ".join(p["authors"][:8]) + (f" +{len(p['authors']) - 8}" if len(p["authors"]) > 8 else "")
        lines = [authors or "(no authors listed)", " · ".join(filter(None, (p["venue"], p["year"], p["source"])))]
        abstract = p["abstract"] or ("Enter loads the abstract." if p["source"] == "ACL" else "No abstract.")
        wrapped = textwrap.wrap(abstract, width)
        lines += wrapped[:3] + (["…  (Enter: full abstract)"] if len(wrapped) > 3 else [])
        return lines

    # Actions -------------------------------------------------------------------
    def chosen(self, row: rvlib.Row | None) -> list[dict]:
        if self.marked:
            return list(self.marked.values())
        return [row.data] if row and row.data else []

    def toggle(self, p: dict) -> None:
        k = self.key(p)
        if k in self.marked:
            del self.marked[k]
        else:
            self.marked[k] = p
        self.update_tabs()

    def copy_bibtex(self, items: list[dict]) -> None:
        if not items:
            return
        self.busy(f"Fetching BibTeX for {len(items)} paper{'s' if len(items) > 1 else ''}…")
        text = "\n\n".join(complete(p)["bibtex"] for p in items) + "\n"
        if copy(text):
            self.flash(f"Copied BibTeX of {len(items)} paper{'s' if len(items) > 1 else ''} — paste them all at once",
                       rvlib.GOOD)
        else:
            self.flash("Could not copy (is wl-clipboard installed?)", rvlib.BAD)

    def download(self, items: list[dict]) -> None:
        if not items:
            return

        def work() -> None:
            done = 0
            for n, p in enumerate(items, 1):
                self.flash(f"Downloading {n}/{len(items)}: {p['title'][:60]}…", rvlib.WARN, 120)
                result = download(p)
                if result.startswith(("no PDF", "opened")):
                    self.flash(f"{p['title'][:50]}: {result}", rvlib.WARN if result.startswith("opened") else rvlib.BAD, 8)
                    time.sleep(2)
                else:
                    done += 1
            folder = papers.prefs()["folder"]
            if done:
                self.flash(f"Filed {done} of {len(items)} into {folder.name}/ with notes", rvlib.GOOD, 8)
                rvlib.notify("Papers downloaded", f"{done} filed into {folder}")

        threading.Thread(target=work, daemon=True).start()

    def open_url(self, p: dict) -> None:
        if p.get("url"):
            rvlib.spawn(["xdg-open", p["url"]])
            self.flash("Opened in the browser")

    def on_key(self, key: int, row: rvlib.Row | None) -> None:
        p = row.data if row else None
        if key in (ord("/"), ord("s")):
            query = self.prompt("Search papers", self.query)
            if query:
                self.search(query)
                self.tab = 0
        elif key == ord(" ") and p:
            self.toggle(p)
            self.move(1)
        elif key in rvlib.ENTER and p:
            self.reader(p)
        elif key == ord("b"):
            self.copy_bibtex(self.chosen(row))
        elif key == ord("d"):
            self.download(self.chosen(row))
        elif key == ord("o") and p:
            self.open_url(p)
        elif key == ord("u") and self.marked:
            self.marked.clear()
            self.update_tabs()
            self.flash("Unmarked all")

    def intercept(self, key: int) -> int | None:
        if key == ord("r"):  # `r` re-runs the search
            self.search(self.query)
            return None
        return key

    def reader(self, p: dict) -> None:
        """Full-screen view of one paper: title, authors, venue, abstract."""
        if not p["abstract"]:
            self.busy("Loading abstract…")
            load_abstract(p)
        s = self.screen
        top = 0
        s.timeout(-1)
        try:
            while True:
                h, w = s.getmaxyx()
                width = max(20, w - 6)
                marked = self.key(p) in self.marked
                lines: list[tuple[str, int]] = []
                lines += [(t, rvlib.attr(rvlib.TITLE, curses.A_BOLD)) for t in textwrap.wrap(p["title"], width)]
                lines += [(t, rvlib.attr(rvlib.ACCENT)) for t in textwrap.wrap(", ".join(p["authors"]) or "(no authors)", width)]
                lines += [(" · ".join(filter(None, (p["venue"], p["year"], p["source"]))), rvlib.attr(rvlib.DIM)),
                          (p["url"], rvlib.attr(rvlib.DIM)), ("", 0)]
                for para in (p["abstract"] or "No abstract available.").split("\n"):
                    lines += [(t, 0) for t in textwrap.wrap(para, width)] or [("", 0)]
                body = h - 4
                top = max(0, min(top, len(lines) - body))
                s.erase()
                for n, (text, attribute) in enumerate(lines[top:top + body]):
                    self.put(1 + n, 3, text, w - 6, attribute)
                self.put(h - 2, 2, "─" * (w - 4), w - 4, rvlib.attr(rvlib.DIM))
                hint = ("● marked  " if marked else "") + "␣ mark  b copy BibTeX  d download  o open  j/k scroll  q back"
                if self.message and time.monotonic() < self.message_until:
                    self.put(h - 1, 2, self.message, w - 4, rvlib.attr(self.message_colour, curses.A_BOLD))
                else:
                    self.put(h - 1, 2, hint, w - 4, rvlib.attr(rvlib.GOOD if marked else rvlib.DIM))
                s.refresh()
                key = s.getch()
                if key in (ord("q"), 27, ord("h"), curses.KEY_LEFT):
                    return
                if key in (ord("j"), curses.KEY_DOWN):
                    top += 1
                elif key in (ord("k"), curses.KEY_UP):
                    top -= 1
                elif key in (curses.KEY_NPAGE, ord("f")):
                    top += body - 1
                elif key in (curses.KEY_PPAGE,):
                    top -= body - 1
                elif key == ord(" "):
                    self.toggle(p)
                elif key == ord("b"):
                    self.copy_bibtex([p])
                elif key == ord("d"):
                    self.download([p])
                    self.flash("Downloading in the background…", rvlib.WARN)
                elif key == ord("o"):
                    self.open_url(p)
        finally:
            s.timeout(self._timeout())


def main() -> None:
    app = PaperSearch(" ".join(sys.argv[1:]))
    if app.query:
        app.search(app.query)
    app.start()


if __name__ == "__main__":
    rvlib.guard(main)
