#!/usr/bin/env python3
"""Check Open Graph / Twitter Card tags the way a social scraper reads them.

Fetches each URL, pulls the og: tags out of <head> in the same order a crawler
would, then fetches the og:image and validates it. Re-run any time after a
deploy; it needs no login and no third-party service.

    python3 check-previews.py [url ...]
"""
import sys
import urllib.request
import urllib.error
import html
import re
from io import BytesIO

UA = "Mozilla/5.0 (compatible; preview-check/1.0)"

# Crawlers that matter, and the hard limits they enforce.
MAX_IMAGE_BYTES = 8 * 1024 * 1024          # Facebook refuses anything larger
MIN_IMAGE_SIDE = 200                       # below this cards render as a blob
SOFT_TITLE = 95                            # past this Facebook truncates with "..."
SOFT_DESC = 300                            # past this it truncates too


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.headers, r.read()


def meta_tags(doc):
    head = re.search(r"<head.*?</head>", doc, re.S | re.I)
    if not head:
        head = re.search(r"<html.*", doc, re.S | re.I)
    head = head.group(0) if head else doc
    tags = {}
    for m in re.finditer(r"<meta\b[^>]*>", head, re.I):
        tag = m.group(0)
        prop = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        cont = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        if prop and cont:
            tags.setdefault(prop.group(1).lower(), html.unescape(cont.group(1)))
    canon = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
                      head, re.I)
    tags["<link rel=canonical>"] = html.unescape(canon.group(1)) if canon else None
    return tags


def check(url):
    problems, warns, notes = [], [], []
    out = {"url": url}

    try:
        status, _, body = fetch(url)
    except Exception as exc:                      # noqa: BLE001
        return {"url": url, "fatal": f"could not fetch: {exc}"}

    doc = body.decode("utf-8", "replace")
    out["http"] = status
    if status != 200:
        problems.append(f"page returned HTTP {status}")

    t = meta_tags(doc)
    out["title"] = t.get("og:title")
    out["desc"] = t.get("og:description")
    out["image"] = t.get("og:image")
    out["card"] = t.get("twitter:card")
    out["canonical"] = t.get("<link rel=canonical>")

    for key in ("og:type", "og:url", "og:site_name", "og:title",
                "og:description", "og:image", "og:image:width",
                "og:image:height", "twitter:card", "twitter:image"):
        if not t.get(key):
            problems.append(f"missing {key}")
    if not t.get("<link rel=canonical>"):
        warns.append("no <link rel=canonical>")

    if t.get("og:image") and not t["og:image"].startswith("https://"):
        problems.append("og:image is not an absolute https:// URL")
    if t.get("og:url") and t["og:url"].rstrip("/") != url.rstrip("/"):
        warns.append(f"og:url ({t['og:url']}) differs from the fetched URL")
    if t.get("<link rel=canonical>") and t.get("og:url") and \
       t["<link rel=canonical>"] != t["og:url"]:
        warns.append("canonical and og:url disagree")
    if t.get("og:image") and t.get("twitter:image") and \
       t["og:image"] != t["twitter:image"]:
        warns.append("og:image and twitter:image differ")

    if t.get("og:title") and len(t["og:title"]) > SOFT_TITLE:
        warns.append(f"og:title is {len(t['og:title'])} chars, may truncate")
    if t.get("og:description") and len(t["og:description"]) > SOFT_DESC:
        warns.append(f"og:description is {len(t['og:description'])} chars, may truncate")

    # now validate the image itself, the way the crawler would fetch it
    if t.get("og:image"):
        try:
            st, hdr, blob = fetch(t["og:image"])
            ctype = (hdr.get("Content-Type") or "").split(";")[0]
            out["img_http"] = st
            out["img_type"] = ctype
            out["img_kb"] = len(blob) // 1024
            if st != 200:
                problems.append(f"og:image returned HTTP {st}")
            if not ctype.startswith("image/"):
                problems.append(f"og:image content-type is {ctype!r}")
            if ctype == "image/webp":
                warns.append("og:image is WebP - Facebook and LinkedIn will not render it")
            if len(blob) > MAX_IMAGE_BYTES:
                problems.append(f"og:image is {len(blob)//1024} KB, over the 8 MB limit")
            try:
                from PIL import Image
                with Image.open(BytesIO(blob)) as im:
                    out["img_size"] = im.size
                    if min(im.size) < MIN_IMAGE_SIDE:
                        warns.append(f"og:image is only {im.size[0]}x{im.size[1]}")
                    if im.format and im.format.upper() not in ("JPEG", "PNG"):
                        warns.append(f"og:image format is {im.format}")
            except ImportError:
                notes.append("Pillow not installed - skipped dimension check")
            except Exception as exc:              # noqa: BLE001
                warns.append(f"og:image did not decode ({exc})")
        except Exception as exc:                  # noqa: BLE001
            problems.append(f"og:image could not be fetched: {exc}")

    out["problems"], out["warns"], out["notes"] = problems, warns, notes
    return out


def main(urls):
    print(f"{'SCRAPE RESULT':<78}\n")
    bad = 0
    for url in urls:
        r = check(url)
        print(url)
        if r.get("fatal"):
            print(f"    FATAL  {r['fatal']}\n")
            bad += 1
            continue
        print(f"    HTTP {r['http']}   title: {r['title']}")
        if r.get("desc"):
            print(f"    description ({len(r['desc'])} chars): {r['desc'][:88]}")
        print(f"    card: {r['card']}   canonical: {r.get('canonical', '-')}")
        if r.get("img_http"):
            print(f"    image: HTTP {r['img_http']}  {r['img_type']}  "
                  f"{r['img_kb']} KB  {r.get('img_size', '?')}")
        for p in r["problems"]:
            print(f"    PROBLEM  {p}")
        for w in r["warns"]:
            print(f"    warn     {w}")
        for n in r["notes"]:
            print(f"    note     {n}")
        if r["problems"]:
            bad += 1
            print("    -> WILL NOT RENDER CLEANLY")
        elif r["warns"]:
            print("    -> renders; see warnings")
        else:
            print("    -> OK")
        print()
    print("=" * 78)
    print(f"{len(urls) - bad}/{len(urls)} pages render cleanly with no problems.")
    return 1 if bad else 0


if __name__ == "__main__":
    default = [
        "https://alexandrugris.ro/",
        "https://alexandrugris.ro/projects.html",
        "https://alexandrugris.ro/from-the-edges/",
        "https://alexandrugris.ro/lightbringer/",
        "https://alexandrugris.ro/literature/",
        "https://alexandrugris.ro/literature/friday-bd/",
    ]
    sys.exit(main(sys.argv[1:] or default))