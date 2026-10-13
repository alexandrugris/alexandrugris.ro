#!/usr/bin/env python3
"""Regenerate sitemap.xml for alexandrugris.ro from the five site repos.

lastmod comes from the git commit date of the file that produces each page,
so it is accurate at generation time. Re-run after deploying a change to any
page; the sitemap lives in the Personal Website repo but reads git dates from
all five, so it must be regenerated, committed and pushed there.

    python3 make-sitemap.py
"""
import subprocess
from pathlib import Path

HOME = Path.home() / "Downloads"
PERS = HOME / "Personal Website"
EDGE = HOME / "europe-seen-from-the-edge"
LB = HOME / "lightbringer"
LIT = HOME / "writings"
FBD = HOME / "friday-bande-dessinee"
BASE = "https://alexandrugris.ro"

# (live path, repo, file that renders it, priority)
PAGES = [
    ("/",                             PERS, "index.html",                     "1.0"),
    ("/projects.html",                 PERS, "projects.html",                  "0.8"),
    ("/from-the-edges/",               EDGE, "dist/index.html",                "1.0"),
    ("/from-the-edges/routes.html",    EDGE, "dist/routes.html",               "0.8"),
    ("/from-the-edges/the-long-way-from-paris.html", EDGE, "dist/the-long-way-from-paris.html", "0.9"),
    ("/from-the-edges/manuc.html",     EDGE, "dist/manuc.html",                "0.9"),
    ("/from-the-edges/architecture.html", EDGE, "dist/architecture.html",       "0.9"),
    ("/from-the-edges/art.html",       EDGE, "dist/art.html",                  "0.9"),
    ("/from-the-edges/annexes/",       EDGE, "dist/annexes/index.html",        "0.8"),
    ("/lightbringer/",                 LB,   "dist/index.html",                "1.0"),
    ("/lightbringer/notes.html",       LB,   "dist/notes.html",                "0.7"),
    ("/literature/",                   LIT,  "dist/index.html",                "1.0"),
    ("/literature/friday/",            LIT,  "dist/friday/index.html",         "0.8"),
    ("/literature/friday-bd/",         FBD,  "dist/index.html",                "0.8"),
    ("/literature/parallelism/",       LIT,  "dist/parallelism/index.html",    "0.8"),
    ("/literature/torments/",          LIT,  "dist/torments/index.html",       "0.8"),
]


def lastmod(repo: Path, rel: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%ad", "--date=short", "--", rel],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return out or "1970-01-01"


rows = []
for path, repo, rel, prio in PAGES:
    if not (repo / rel).exists():
        raise SystemExit(f"missing source for {path}: {repo / rel}")
    rows.append(
        f"  <url>\n"
        f"    <loc>{BASE}{path}</loc>\n"
        f"    <lastmod>{lastmod(repo, rel)}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>{prio}</priority>\n"
        f"  </url>"
    )

# A duplicated <loc> is a real defect that still validates as XML and still
# deploys, so it has to be caught here rather than by a search engine.
seen: set[str] = set()
dupes: list[str] = []
for path, _repo, _rel, _prio in PAGES:
    if path in seen:
        dupes.append(path)
    seen.add(path)
if dupes:
    raise SystemExit(f"duplicate PAGES entries: {', '.join(dupes)}")

xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "\n".join(rows)
    + "\n</urlset>\n"
)

dest = PERS / "sitemap.xml"
dest.write_text(xml, encoding="utf-8")
print(f"wrote {dest} ({len(PAGES)} urls, {len(xml)} bytes)")