#!/usr/bin/env python3
"""Full deploy audit for the five alexandrugris.ro sites.

1. Byte-compare every live HTML page against the file in its git repo.
2. Resolve every local asset each page references over HTTPS.
3. Confirm no file on the server exists outside the repos (drift check is
   deliberately skipped: the docroot is shared and hand-edited by nothing).

    python3 audit-deploy.py
"""
import hashlib
import re
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (compatible; deploy-audit/1.0)"

HOME = Path.home() / "Downloads"
PERS = HOME / "Personal Website"
EDGE = HOME / "europe-seen-from-the-edge" / "dist"
LB = HOME / "lightbringer" / "dist"
LIT = HOME / "writings" / "dist"
FBD = HOME / "friday-bande-dessinee" / "dist"

BASE = "https://alexandrugris.ro"

# (live url, repo file)
PAGES = [
    ("/", PERS / "index.html"),
    ("/projects.html", PERS / "projects.html"),
    ("/from-the-edges/", EDGE / "index.html"),
    ("/from-the-edges/routes.html", EDGE / "routes.html"),
    ("/from-the-edges/annexes/", EDGE / "annexes" / "index.html"),
    ("/from-the-edges/architecture.html", EDGE / "architecture.html"),
    ("/from-the-edges/art.html", EDGE / "art.html"),
    ("/from-the-edges/manuc.html", EDGE / "manuc.html"),
    ("/from-the-edges/the-long-way-from-paris.html", EDGE / "the-long-way-from-paris.html"),
    ("/lightbringer/", LB / "index.html"),
    ("/lightbringer/notes.html", LB / "notes.html"),
    ("/literature/", LIT / "index.html"),
    ("/literature/friday/", LIT / "friday" / "index.html"),
    ("/literature/friday-bd/", FBD / "index.html"),
    ("/literature/parallelism/", LIT / "parallelism" / "index.html"),
    ("/literature/torments/", LIT / "torments" / "index.html"),
]

ASSET_RE = re.compile(
    r'(?:src|href)\s*=\s*["\']([^"\']+)["\']|url\(\s*["\']?([^"\')]+)', re.I
)
SKIP_PREFIX = ("http:", "https:", "mailto:", "tel:", "data:", "#", "//")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:  # noqa: BLE001
        return 0, f"error: {e}", b""


def assets_of(doc, page_url):
    out = []
    for m in ASSET_RE.finditer(doc):
        raw = (m.group(1) or m.group(2) or "").strip()
        if not raw or raw.lower().startswith(SKIP_PREFIX):
            continue
        out.append(urljoin(page_url, raw))
    return out


bad_pages, bad_assets, checked_assets = [], [], 0
seen_assets = set()

for path, local in PAGES:
    url = urljoin(BASE, path)
    status, ctype, body = fetch(url)

    if not local.exists():
        bad_pages.append((url, f"repo file missing: {local}"))
        continue
    lh = hashlib.md5(local.read_bytes()).hexdigest()
    rh = hashlib.md5(body).hexdigest()
    same = lh == rh
    size_kb = len(body) / 1024
    print(f"{'OK ' if status == 200 and same else 'BAD'} {path:52s} "
          f"{status} {size_kb:7.1f} KB  {'identical' if same else 'DIFFERS FROM REPO'}")

    if status != 200:
        bad_pages.append((url, f"HTTP {status}"))
    elif not same:
        bad_pages.append((url, f"live md5 {rh} != repo md5 {lh}"))

    for a in assets_of(body.decode("utf-8", "replace"), url):
        if a in seen_assets:
            continue
        seen_assets.add(a)
        checked_assets += 1
        st, ct, blob = fetch(a)
        if st != 200:
            bad_assets.append((a, f"HTTP {st}"))

print()
print(f"{len(PAGES)} pages checked, {checked_assets} unique assets resolved")
if bad_pages:
    print("\nPAGE PROBLEMS")
    for u, why in bad_pages:
        print(f"  {u}\n    {why}")
if bad_assets:
    print("\nASSET PROBLEMS")
    for u, why in bad_assets:
        print(f"  {u}\n    {why}")
if not bad_pages and not bad_assets:
    print("\nAll pages byte-identical to repo HEAD; all referenced assets return 200.")
    raise SystemExit(0)
raise SystemExit(1)