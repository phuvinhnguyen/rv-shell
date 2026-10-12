#!/usr/bin/env python3
"""rv papers: file research PDFs in an Obsidian vault.

    rv papers                 file every new PDF in the papers folder now
    rv papers scan --dry-run  show what would be renamed, change nothing
    rv papers enable          file them automatically as they arrive (systemd)
    rv papers disable         stop doing that
    rv papers status          what is set up, what was filed
    rv papers file PDF        file one PDF from anywhere

A new PDF (say 2404.02151v4.pdf from Zen's Save In) is identified by its
arXiv id (file name, or first page) or a DOI on its first page, then:
  * renamed  "2025 - Andriushchenko et al - Jailbreaking … Attacks (ICLR 2025).pdf"
  * noted    Papers/Notes/<title>.md with authors, venue, links, abstract and
             BibTeX, linking back to the PDF (an existing note is never touched)

Metadata comes from arXiv (title, authors, abstract, BibTeX; the venue from
"Accepted at ICLR 2025"-style comments) and, for published papers, the DOI
(Crossref + doi.org BibTeX). With an API key in settings → papers, Semantic
Scholar or OpenAlex also fill in the venue; their keyless tiers are rate-
limited to the point of being unusable. Standard library + pdftotext.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402

STATE = rvlib.DATA_HOME / "papers.json"
UNITS = Path.home() / ".config/systemd/user"
UA = "rv-papers/1 (Debian; +https://github.com/phuvinhnguyen/rv-shell)"
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?!\d)")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+[^\s\"<>.,;)])")
VENUES = ("NeurIPS|NIPS|ICML|ICLR|ACL|EMNLP|NAACL|EACL|AACL|COLING|COLM|CVPR|ICCV|ECCV|WACV|BMVC|AAAI|IJCAI|"
          "KDD|WWW|WSDM|SIGIR|CIKM|RecSys|AISTATS|UAI|CoRL|RSS|ICRA|IROS|MICCAI|MIDL|ISBI|TMLR|JMLR|TPAMI|"
          "Interspeech|ICASSP|LREC|CHI|UIST|FAccT|USENIX Security|CCS|NDSS|S&P|OSDI|SOSP|MLSys|ISCA|"
          "Nature|Science|PNAS|Cell")
VENUE_RE = re.compile(rf"\b({VENUES})\b[\s'’-]*((?:19|20)?\d{{2}})?", re.I)


# ------------------------------------------------------------------ settings

def prefs() -> dict:
    p = rvlib.settings().get("papers", {})
    vault = rvlib.expand(p.get("vault", "~/Documents/Obsidian Vault"))
    return {
        "vault": vault,
        "folder": vault / p.get("folder", "Papers"),
        "notes": vault / p.get("notes", "Papers/Notes"),
        "rename": p.get("rename", "{year} - {authors} - {title} ({venue})"),
        "s2": p.get("semanticScholarKey", ""),
        "openalex": p.get("openalexKey", ""),
    }


# -------------------------------------------------------------------- fetch

_last_arxiv = 0.0


def get(url: str, accept: str = "*/*", headers: dict | None = None, timeout: float = 20) -> str:
    request = Request(url, headers={"User-Agent": UA, "Accept": accept, **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return response.read(5_000_000).decode(response.headers.get_content_charset() or "utf-8", "replace")


def try_get(*args, **kwargs) -> str:
    try:
        return get(*args, **kwargs)
    except Exception:
        return ""


def arxiv(arxiv_id: str) -> dict | None:
    """Title, authors, year, abstract, comment, DOI and BibTeX from arXiv."""
    global _last_arxiv
    wait = 3 - (time.monotonic() - _last_arxiv)  # arXiv asks for ≥3 s between calls
    if wait > 0:
        time.sleep(wait)
    _last_arxiv = time.monotonic()
    xml = try_get(f"https://export.arxiv.org/api/query?id_list={arxiv_id}")
    if not xml:
        return None
    try:
        entry = ET.fromstring(xml).find("a:entry", ATOM)
    except ET.ParseError:
        return None
    if entry is None or entry.find("a:title", ATOM) is None:
        return None

    def text(path: str) -> str:
        node = entry.find(path, ATOM)
        return " ".join((node.text or "").split()) if node is not None else ""
    meta = {
        "title": text("a:title"),
        "authors": [" ".join((a.findtext("a:name", "", ATOM)).split()) for a in entry.findall("a:author", ATOM)],
        "year": text("a:published")[:4],
        "abstract": text("a:summary"),
        "comment": text("arxiv:comment"),
        "journal_ref": text("arxiv:journal_ref"),
        "doi": text("arxiv:doi"),
        "arxiv": arxiv_id,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "bibtex": try_get(f"https://arxiv.org/bibtex/{arxiv_id}").strip(),
    }
    return meta if meta["title"] else None


def crossref(doi: str) -> dict | None:
    raw = try_get(f"https://api.crossref.org/works/{quote(doi)}", "application/json")
    try:
        work = json.loads(raw)["message"]
    except (ValueError, KeyError):
        return None
    authors = [" ".join(filter(None, (a.get("given"), a.get("family")))) for a in work.get("author", [])]
    year = str(((work.get("issued") or {}).get("date-parts") or [[""]])[0][0] or "")
    abstract = re.sub(r"<[^>]+>", "", work.get("abstract", "") or "")
    return {
        "title": " ".join((work.get("title") or [""])[0].split()),
        "authors": authors, "year": year, "abstract": " ".join(abstract.split()),
        "venue": " ".join((work.get("short-container-title") or work.get("container-title") or [""])[0].split()),
        "doi": doi, "url": f"https://doi.org/{doi}", "comment": "", "journal_ref": "",
    }


def doi_bibtex(doi: str) -> str:
    return try_get(f"https://doi.org/{doi}", "application/x-bibtex").strip()


def venue_from_text(*texts: str) -> str:
    """'Accepted at ICLR 2025' → 'ICLR 2025'; workshops are marked."""
    for text in texts:
        if not text:
            continue
        match = VENUE_RE.search(text)
        if match:
            name = next((v for v in VENUES.split("|") if v.lower() == match.group(1).lower()), match.group(1))
            name = {"NIPS": "NeurIPS"}.get(name, name)
            year = match.group(2) or ""
            if len(year) == 2:
                year = "20" + year
            workshop = " Workshop" if re.search(r"workshop", text, re.I) else ""
            return f"{name} {year}".strip() + workshop
    return ""


def venue_online(meta: dict, keys: dict) -> str:
    """Semantic Scholar / OpenAlex, only with an API key (keyless tiers are exhausted)."""
    if keys.get("s2") and (meta.get("arxiv") or meta.get("doi")):
        ident = f"arXiv:{meta['arxiv']}" if meta.get("arxiv") else f"DOI:{meta['doi']}"
        raw = try_get(f"https://api.semanticscholar.org/graph/v1/paper/{ident}?fields=venue,year,publicationVenue",
                      "application/json", {"x-api-key": keys["s2"]})
        try:
            data = json.loads(raw)
            venue = (data.get("publicationVenue") or {}).get("name") or data.get("venue") or ""
            if venue and venue.lower() not in ("arxiv", "arxiv.org"):
                short = venue_from_text(venue) or venue
                return short if re.search(r"\d{4}", short) else f"{short} {data.get('year') or ''}".strip()
        except ValueError:
            pass
    if keys.get("openalex") and meta.get("title"):
        raw = try_get("https://api.openalex.org/works?per_page=1&search=" + quote(meta["title"])
                      + f"&api_key={keys['openalex']}", "application/json")
        try:
            work = json.loads(raw)["results"][0]
            source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")
            if source and "arxiv" not in source.lower():
                return venue_from_text(source) or f"{source} {work.get('publication_year', '')}".strip()
        except (ValueError, KeyError, IndexError):
            pass
    return ""


# ----------------------------------------------------------------- identify

def first_pages(pdf: Path) -> str:
    if not shutil.which("pdftotext"):
        return ""
    try:
        return subprocess.run(["pdftotext", "-l", "2", str(pdf), "-"], capture_output=True, text=True,
                              timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def identify(pdf: Path) -> tuple[str, str]:
    """('arxiv', id) or ('doi', doi) or ('', '')."""
    match = ARXIV_RE.search(pdf.stem)
    if match:
        return "arxiv", match.group(1) + (match.group(2) or "")
    text = first_pages(pdf)
    match = re.search(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", text)
    if match:
        return "arxiv", match.group(1)
    match = DOI_RE.search(text)
    if match:
        return "doi", match.group(1)
    return "", ""


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def pdf_info(pdf: Path) -> dict:
    if not shutil.which("pdfinfo"):
        return {}
    out = rvlib.output(["pdfinfo", str(pdf)], timeout=15)
    info = {}
    for line in out.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            info[key.strip()] = value.strip()
    return info


def arxiv_by_title(title: str) -> dict | None:
    """An arXiv paper whose title matches exactly (ignoring case/punctuation)."""
    global _last_arxiv
    wait = 3 - (time.monotonic() - _last_arxiv)
    if wait > 0:
        time.sleep(wait)
    _last_arxiv = time.monotonic()
    words = " ".join(re.findall(r"[A-Za-z0-9]+", title)[:12])
    xml = try_get("https://export.arxiv.org/api/query?max_results=5&search_query=" + quote(f'ti:"{words}"'))
    try:
        entries = ET.fromstring(xml).findall("a:entry", ATOM) if xml else []
    except ET.ParseError:
        entries = []
    for entry in entries:
        found = " ".join((entry.findtext("a:title", "", ATOM)).split())
        ident = entry.findtext("a:id", "", ATOM).rsplit("/abs/", 1)[-1]
        if norm(found) == norm(title) and ident:
            return arxiv(ident)
    return None


def from_pdf_metadata(pdf: Path) -> dict | None:
    """Last resort: the title/authors embedded in the PDF (CVF, ACL Anthology…)."""
    info = pdf_info(pdf)
    title = info.get("Title", "").strip()
    if len(title) < 8:
        return None
    authors = [a.strip() for a in re.split(r";|,| and ", info.get("Author", "")) if a.strip()]
    meta = arxiv_by_title(title)
    if meta:
        return meta
    return {"title": title, "authors": authors, "year": "", "abstract": "", "comment": "", "journal_ref": "",
            "doi": "", "url": "", "bibtex": ""}


def lookup(pdf: Path, keys: dict) -> dict | None:
    kind, ident = identify(pdf)
    meta = None
    if kind == "arxiv":
        meta = arxiv(ident)
        if meta and meta.get("doi"):  # published version: prefer its BibTeX and venue
            published = crossref(meta["doi"])
            if published and published.get("venue"):
                meta["venue"] = venue_from_text(published["venue"]) or published["venue"]
            meta["bibtex"] = doi_bibtex(meta["doi"]) or meta["bibtex"]
    elif kind == "doi":
        meta = crossref(ident)
        if meta:
            meta["bibtex"] = doi_bibtex(ident)
    else:
        meta = from_pdf_metadata(pdf)
    if not meta:
        return None
    # The file name and first page often say it outright: "…_CVPR_2025_paper.pdf",
    # "This CVPR paper is the Open Access version".
    meta["venue"] = (meta.get("venue") or venue_from_text(meta.get("comment", ""), meta.get("journal_ref", ""))
                     or venue_from_text(pdf.stem.replace("_", " "))
                     or venue_online(meta, keys)
                     or (venue_from_text(first_pages(pdf)[:600]) if kind == "" else "") or "arXiv")
    if not meta.get("bibtex"):
        meta["bibtex"] = make_bibtex(meta)
    # "ICLR 2025" is the year to cite, not the first arXiv upload.
    venue_year = re.search(r"\b(19|20)\d{2}\b", meta["venue"])
    if venue_year:
        meta["year"] = venue_year.group(0)
    meta["bibtex"] = published_bibtex(meta)
    return meta


def make_bibtex(meta: dict) -> str:
    authors = meta.get("authors") or ["Unknown"]
    key = norm(authors[0].split()[-1]) + (meta.get("year") or "") + norm(meta.get("title", "").split()[0] if meta.get("title") else "")
    journal = (meta.get("venue") or "").split()[:1] and meta["venue"].split()[0] in JOURNALS
    kind, field = ("article", "journal") if journal else ("inproceedings", "booktitle")
    lines = [f"@{kind}{{{key},", f"  title={{{meta.get('title', '')}}},", f"  author={{{' and '.join(authors)}}},"]
    if meta.get("venue") and meta["venue"] != "arXiv":
        lines.append(f"  {field}={{{meta['venue']}}},")
    if meta.get("year"):
        lines.append(f"  year={{{meta['year']}}},")
    if meta.get("url"):
        lines.append(f"  url={{{meta['url']}}},")
    return "\n".join(lines) + "\n}"


JOURNALS = {"TMLR", "JMLR", "TPAMI", "Nature", "Science", "PNAS", "Cell"}


def published_bibtex(meta: dict) -> str:
    """arXiv's @misc → @inproceedings/@article once the venue is known."""
    bib = meta.get("bibtex") or ""
    if not bib.startswith("@misc") or meta.get("venue", "arXiv") == "arXiv":
        return bib
    journal = meta["venue"].split()[0] in JOURNALS
    field = "journal" if journal else "booktitle"
    bib = re.sub(r"^@misc", "@article" if journal else "@inproceedings", bib)
    bib = re.sub(r"year=\{\d{4}\}", f"year={{{meta['year']}}}", bib)
    return re.sub(r"(title=\{.*?\},)", rf"\1\n      {field}={{{meta['venue']}}},", bib, count=1, flags=re.S)


# -------------------------------------------------------------------- write

def safe(text: str, limit: int = 140) -> str:
    text = re.sub(r"\s*:\s*", " - ", text)          # "SpikeLLM: Scaling" → "SpikeLLM - Scaling"
    text = re.sub(r'[\\/*?"<>|\n\r\t]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:limit].rstrip(" .-")


def author_label(authors: list[str]) -> str:
    if not authors:
        return "Unknown"
    last = authors[0].split()[-1] if authors[0].split() else authors[0]
    return last + (" et al" if len(authors) > 2 else f" & {authors[1].split()[-1]}" if len(authors) == 2 else "")


def new_name(meta: dict, pattern: str) -> str:
    fields = {"year": meta.get("year") or "n.d.", "authors": author_label(meta.get("authors", [])),
              "first": author_label(meta.get("authors", [])[:1]), "title": safe(meta.get("title", ""), 120),
              "venue": meta.get("venue") or "arXiv", "arxiv": meta.get("arxiv", ""), "doi": meta.get("doi", "")}
    name = pattern.format(**fields)
    name = re.sub(r"\(\s*\)", "", name)
    return safe(name, 200)


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 100):
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def yaml_str(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def note_text(meta: dict, pdf_rel: str) -> str:
    authors = meta.get("authors", [])
    lines = ["---",
             f"title: {yaml_str(meta.get('title', ''))}",
             "authors:"] + [f"  - {yaml_str(a)}" for a in authors] + [
             f"year: {meta.get('year') or ''}",
             f"venue: {yaml_str(meta.get('venue', ''))}"]
    if meta.get("arxiv"):
        lines.append(f"arxiv: {yaml_str(meta['arxiv'])}")
    if meta.get("doi"):
        lines.append(f"doi: {yaml_str(meta['doi'])}")
    lines += [f"url: {meta.get('url', '')}",
              f'pdf: "[[{pdf_rel}]]"',
              f"added: {dt.date.today().isoformat()}",
              "status: unread",
              "tags:", "  - paper",
              "---", "",
              f"# {meta.get('title', '')}", "",
              f"**Authors:** {', '.join(authors)}  ",
              f"**Venue:** {meta.get('venue', '')} · {meta.get('year', '')}  ",
              f"**PDF:** [[{pdf_rel}|open]] · **Link:** {meta.get('url', '')}", ""]
    if meta.get("abstract"):
        lines += ["## Abstract", "", meta["abstract"], ""]
    lines += ["## Notes", "", "", "## BibTeX", "", "```bibtex", meta.get("bibtex") or "", "```", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------- flow

def load_state() -> dict:
    data = rvlib.read_json(STATE, {})
    return data if isinstance(data, dict) else {}


def ready(pdf: Path) -> bool:
    """A complete PDF: starts with %PDF and has stopped growing."""
    try:
        size = pdf.stat().st_size
        with pdf.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return False
        time.sleep(1.5)
        return pdf.stat().st_size == size and size > 0
    except OSError:
        return False


def existing_note(folder: Path, title: str) -> Path | None:
    key = norm(title)
    for note in folder.glob("*.md") if folder.is_dir() else []:
        if norm(note.stem) == key:
            return note
    return None


def update_links(vault: Path, old: str, new: str) -> list[Path]:
    """Rewrite [[…old.pdf…]] links in every note; originals are backed up first."""
    backup = Path.home() / ".local/state/rv/papers-backup" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    changed = []
    for note in vault.rglob("*.md"):
        if ".obsidian" in note.parts or ".trash" in note.parts:
            continue
        try:
            text = note.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if old in text:
            target = backup / note.relative_to(vault)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            note.write_text(text.replace(old, new))
            changed.append(note)
    return changed


def file_pdf(pdf: Path, p: dict, state: dict, quiet: bool = False, dry: bool = False) -> str:
    if not ready(pdf):
        return "skipped (not a finished PDF)"
    meta = lookup(pdf, p)
    if not meta:
        state[pdf.name] = {"status": "unknown", "at": dt.datetime.now().isoformat(timespec="seconds")}
        return "no arXiv id or DOI found — left as is"
    new = p["folder"] / (new_name(meta, p["rename"]) + ".pdf")
    if new != pdf:
        new = unique(new)
    note = existing_note(p["notes"], meta.get("title", "")) or p["notes"] / (safe(meta.get("title", new.stem), 150) + ".md")
    if dry:
        return f"→ {new.name}\n      note: {note.name}{' (exists, kept)' if note.exists() and note.stat().st_size else ''}"
    p["folder"].mkdir(parents=True, exist_ok=True)
    relinked = []
    if new != pdf:
        shutil.move(str(pdf), str(new))
        relinked = update_links(p["vault"], pdf.name, new.name)
    p["notes"].mkdir(parents=True, exist_ok=True)
    rel = new.relative_to(p["vault"]).as_posix() if new.is_relative_to(p["vault"]) else str(new)
    if not note.exists() or note.stat().st_size == 0:  # fill empty placeholders too
        note.write_text(note_text(meta, rel))
    state[new.name] = {"status": "filed", "from": pdf.name, "note": note.name, "venue": meta.get("venue"),
                       "relinked": [str(n.relative_to(p["vault"])) for n in relinked],
                       "at": dt.datetime.now().isoformat(timespec="seconds")}
    if not quiet:
        rvlib.notify("Paper filed", f"{meta.get('title', '')}\n{meta.get('venue', '')} · {author_label(meta.get('authors', []))}")
    return f"→ {new.name}" + (f"\n      links updated in: {', '.join(n.name for n in relinked)}" if relinked else "")


def scan(verbose: bool = True, dry: bool = False) -> int:
    p = prefs()
    if not p["folder"].is_dir():
        print(f"rv papers: {p['folder']} does not exist (settings → papers.folder)", file=sys.stderr)
        return 1
    state = load_state()
    todo = [f for f in sorted(p["folder"].iterdir())
            if f.is_file() and f.suffix.lower() == ".pdf" and f.name not in state]
    for pdf in todo:
        result = file_pdf(pdf, p, state, quiet=not verbose, dry=dry)
        if not dry:
            rvlib.write_json(STATE, state)
        if verbose:
            print(f"{pdf.name}  {result}")
    if verbose and not todo:
        print("Nothing new.")
    return 0


# ------------------------------------------------------------------- systemd

def systemd_path(path: Path) -> str:
    # Path= values are taken whole (spaces are fine there); only % needs escaping.
    return str(path).replace("%", "%%")


def enable() -> int:
    p = prefs()
    p["folder"].mkdir(parents=True, exist_ok=True)
    UNITS.mkdir(parents=True, exist_ok=True)
    (UNITS / "rv-papers.path").write_text(f"""[Unit]
Description=rv: watch the Obsidian papers folder for new PDFs

[Path]
PathModified={systemd_path(p['folder'])}
Unit=rv-papers.service

[Install]
WantedBy=default.target
""")
    (UNITS / "rv-papers.service").write_text(f"""[Unit]
Description=rv: rename new paper PDFs and create their Obsidian notes

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 "{systemd_path(Path(__file__).resolve())}" scan --quiet
""")
    for cmd in (["daemon-reload"], ["enable", "--now", "rv-papers.path"]):
        status, out = rvlib.run(["systemctl", "--user", *cmd])
        if status:
            print(f"systemctl {' '.join(cmd)}: {out}", file=sys.stderr)
            return 1
    print(f"Watching {p['folder']} — new PDFs are filed automatically.")
    return 0


def disable() -> int:
    rvlib.run(["systemctl", "--user", "disable", "--now", "rv-papers.path"])
    for unit in ("rv-papers.path", "rv-papers.service"):
        (UNITS / unit).unlink(missing_ok=True)
    rvlib.run(["systemctl", "--user", "daemon-reload"])
    print("Stopped watching.")
    return 0


def status() -> int:
    p = prefs()
    active = rvlib.output(["systemctl", "--user", "is-active", "rv-papers.path"]).strip()
    print(f"folder   {p['folder']}\nnotes    {p['notes']}\nwatching {active or 'no'}")
    for name, info in sorted(load_state().items(), key=lambda kv: kv[1].get("at", ""))[-10:]:
        print(f"  {info.get('at', '')[:16]}  {info.get('status'):<8} {name}")
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "scan"
    if command == "scan":
        return scan(verbose="--quiet" not in argv, dry="--dry-run" in argv)
    if command == "enable":
        return enable()
    if command == "disable":
        return disable()
    if command == "status":
        return status()
    if command == "file" and len(argv) > 2:
        state = load_state()
        print(file_pdf(rvlib.expand(argv[2]).resolve(), prefs(), state))
        rvlib.write_json(STATE, state)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
