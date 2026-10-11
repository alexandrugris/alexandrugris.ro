#!/usr/bin/env python3
"""Build the hardened nginx vhost for alexandrugris.ro.

Changes, all of them additive except the X-XSS-Protection removal:

1. The port-80 default_server no longer serves /var/www/html to any hostname.
   It rejects with 444 (nginx's "close without response"). Previously
   `Host: evil.example` returned 200 and the full homepage, because the
   Debian default vhost matched everything.
2. A new 443 default_server does the same over TLS. Without it, an unmatched
   SNI still landed on the site vhost.
3. X-XSS-Protection: 1; mode=block is dropped. It is deprecated, ignored by
   current browsers, and historically introduced XSS vectors in older engines.
   CSP supersedes it.
4. Content-Security-Policy is added in REPORT-ONLY mode first, so nothing is
   blocked while we measure. Flip MODE to "enforce" once the browser test is clean.
5. Permissions-Policy denies camera/mic/geolocation etc. Nothing on the estate
   uses them.
6. etag off stops the default ETag from leaking inode number and file size.

The new headers are added BOTH at server level and inside the image location,
because nginx's add_header does not merge: a location that declares any
add_header drops the whole inherited set. The image location already redeclares
the security headers for that reason.

Nothing external is loaded by any page on the estate -- no CDN fonts, no
third-party scripts, no remote images -- so 'self' is genuinely sufficient.
The external URLs across the history site are <a href> hyperlinks to sources,
which CSP does not govern.
"""
import re
import sys
from pathlib import Path

MODE = sys.argv[1] if len(sys.argv) > 1 else "report-only"
if MODE not in ("report-only", "enforce"):
    sys.exit(f"MODE must be report-only or enforce, got {MODE!r}")

CSP = ("default-src 'self'; "
       "img-src 'self' data:; "
       # style-src needs 'unsafe-inline' (2 pages use inline <style>, 1 uses a
       # style= attribute) and fonts.googleapis.com, because The Light Bringer
       # pulls its fonts through an @import inside styles.css.
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       # font-src needs fonts.gstatic.com for the woff2 files that @import serves.
       "font-src 'self' https://fonts.gstatic.com; "
       "script-src 'self'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; "
       "frame-ancestors 'self'; upgrade-insecure-requests")

if MODE == "report-only":
    NEW = [f'add_header Content-Security-Policy-Report-Only "{CSP}" always;']
else:
    NEW = [f'add_header Content-Security-Policy "{CSP}" always;']

PERMS = ('add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), '
         'payment=(), usb=(), interest-cohort=()" always;')

src = Path("/Users/alexgris/.mavis/workspace/tmp/nginx-current.conf")
s = src.read_text(encoding="utf-8")


def sub1(pattern, repl, label):
    """Replace exactly one occurrence or abort."""
    global s
    new, n = re.subn(pattern, repl, s, count=1, flags=re.M)
    if n != 1:
        sys.exit(f"FAILED: {label} matched {n} times")
    s = new
    print(f"  ok  {label}")


# ---- 1. port-80 default server: reject instead of serving -------------------
# Brace-match the block rather than regex it: nested location blocks mean a
# non-greedy pattern stops at the wrong closing brace.
m = re.search(r"# Default server configuration\n(?:#\n)*server \{", s)
if not m:
    sys.exit("FAILED: could not locate the default server block")
start = m.start()
i = s.index("{", m.end() - 1)
depth = 0
for j in range(i, len(s)):
    if s[j] == "{":
        depth += 1
    elif s[j] == "}":
        depth -= 1
        if depth == 0:
            end = j + 1
            break
else:
    sys.exit("FAILED: unbalanced braces in the default server block")

new_default = """# Unknown-hostname rejector. Added 2026-10-11.
#
# This used to be the stock Debian default vhost: it served /var/www/html to
# server_name _ , so ANY Host header -- `curl -H "Host: evil.example"` --
# returned 200 with the full homepage. Harmless today because every page uses
# relative URLs and every OG tag hardcodes the canonical host, but it is exactly
# the shape that enables Host-header cache poisoning the moment a proxy or a
# cache is put in front. 444 is nginx's "close the connection with no response".
server {
\tlisten 80 default_server;
\tlisten [::]:80 default_server;
\tserver_name _;
\treturn 444;
}"""
s = s[:start] + new_default + s[end:]
print(f"  ok  port-80 default vhost now rejects (444) [{start}:{end}]")

# ---- 2. remove X-XSS-Protection from the real vhost -----------------------
n = len(re.findall(r'^\s*add_header X-XSS-Protection.*\n', s, re.M))
s = re.sub(r'^\s*add_header X-XSS-Protection.*\n', '', s, flags=re.M)
print(f"  ok  removed X-XSS-Protection ({n} occurrence)")

# ---- 3. add the new headers to the real vhost -----------------------------
anchor = '\tadd_header Referrer-Policy "strict-origin-when-cross-origin" always;'
occ = s.count(anchor)
if occ == 0:
    sys.exit("FAILED: server-level anchor not found")
# Replace the FIRST occurrence (server level) only; the image location is handled next.
s = s.replace(anchor, anchor + "\n\t" + "\n\t".join(NEW) + "\n\t" + PERMS, 1)
print(f"  ok  added CSP ({MODE}) + Permissions-Policy to server level")

# ---- 4. mirror them inside the image location ----------------------------
# Locate the `location ~ \.(gif|jpg|png)$` block and insert just before its
# closing brace. That block re-declares the whole add_header set (space-indented,
# unlike the server block), so it must carry the new headers too or images would
# be served without CSP.
lm = re.search(r"location ~ \\\.\(gif\|jpg\|png\)\$ \{", s)
if not lm:
    sys.exit("FAILED: image location not found")
i = s.index("{", lm.end() - 1)
depth = 0
close = None
for j in range(i, len(s)):
    if s[j] == "{":
        depth += 1
    elif s[j] == "}":
        depth -= 1
        if depth == 0:
            close = j
            break
if close is None:
    sys.exit("FAILED: unbalanced braces in the image location")
indent = " " * 16
add = "\n" + "\n".join(indent + h for h in NEW + [PERMS])
s = s[:close] + add + "\n        " + s[close:]
print("  ok  mirrored CSP + Permissions-Policy into the image location")

# ---- 5. etag off ----------------------------------------------------------
em = re.search(r"^([ \t]*)server_name alexandrugris\.ro blog\.alexandrugris\.ro "
               r"www\.alexandrugris\.ro;.*$", s, re.M)
if not em:
    sys.exit("FAILED: site server_name line not found")
pad = em.group(1)
s = s[:em.start()] + (
    f"{pad}server_name alexandrugris.ro blog.alexandrugris.ro www.alexandrugris.ro; "
    "# managed by Certbot\n\n"
    f"{pad}# The default ETag leaks inode number and file size. Nothing here needs\n"
    f"{pad}# revalidation-by-ETag; Last-Modified plus Cache-Control do the job.\n"
    f"{pad}etag off;"
) + s[em.end():]
print("  ok  etag off")

# ---- 6. new 443 default_server -------------------------------------------
if "443 default_server" not in s:
    s = s.rstrip("\n") + """

# Unknown SNI over TLS, added 2026-10-11. Without this block an unmatched SNI
# still reached the real vhost above, because that one had no default_server
# marker and simply won by being first.
#
# HTTP/2 is declared on the listen line, NOT with `http2 on;` -- that directive
# only exists from nginx 1.25.1 and this box runs 1.14.0, so using it would make
# nginx -t fail outright.
server {
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;
    server_name _;
    ssl_certificate     /etc/letsencrypt/live/alexandrugris.ro/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/alexandrugris.ro/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;
    return 444;
}
"""
    print("  ok  added 443 default_server rejector")

dest = Path(f"/Users/alexgris/.mavis/workspace/tmp/nginx-hardened-{MODE}.conf")
dest.write_text(s, encoding="utf-8")
print(f"\nwrote {dest}")