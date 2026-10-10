# AGENTS.md

Personal site for Alexandru Gris — a responsive static site built with plain HTML and inline CSS. No build step, no package manager, no framework. `index.html` **is** the deliverable; there is nothing to compile.

## Local preview

```bash
python3 -m http.server 8000     # then open http://localhost:8000
```

Python's `http.server` binds `*:8000` (all interfaces), not just localhost. That is fine on a home
network; on public Wi-Fi add `--bind 127.0.0.1`.

## Where this publishes

The live site is **self-hosted**, not a PaaS. Do not use `website_deploy` for it — that publishes a
copy somewhere else. There is no CI; deployment is a manual rsync.

- `alexandrugris.ro` and `www.alexandrugris.ro` (CNAME to the apex) → `95.217.18.236`
- That IP is the Hetzner Helsinki VPS `ubuntu-2gb-hel1-1.tailc359ee.ts.net` (Tailscale `100.117.144.64`), nginx + Certbot, docroot **`/var/www/html`**
- Nameservers are 1984hosting, but **1984hosting does not host the site** — there are no FTP/1984hosting credentials to look for
- `blog.alexandrugris.ro` is **not** served from the docroot, so deploying cannot break it. It is a **Blogger** blog behind a CNAME to `ghs.google.com` — note that `ghs.google.com` is the CNAME target for Blogger custom domains *and* for GitHub Pages, so the CNAME alone proves nothing. It answers with Google's `server: GSE` and no `x-github-request-id` header, whereas `alexandrugris.github.io` answers with `server: GitHub.com` plus an `x-github-request-id`. Do not assume blog content is pushable to GitHub.

## SSH access

`~/.ssh/config` already defines two aliases for that box:

| Alias | User | Use for |
|---|---|---|
| `website` | `alexandrugris` | read-only inspection |
| `website-root` | `root` | **deploys** — the docroot is root-owned and `alexandrugris` has no passwordless sudo |

Port 22 is firewalled off the public internet (`alexandrugris.ro:22` times out) — always go through
the Tailscale alias, never the public hostname. The first connect prints a post-quantum KEX
warning; that is noise, not a failure.

## Deploying

Back up first, then sync each source to its own explicit destination:

```bash
TS=$(date +%Y%m%d-%H%M%S)
ssh website-root "cp -a /var/www/html /var/www/backup-$TS"

cd "<repo>"
rsync -avz index.html    website-root:/var/www/html/
rsync -avz projects.html website-root:/var/www/html/
rsync -avz assets/       website-root:/var/www/html/assets/

ssh website-root 'chown -R root:root /var/www/html && \
  find /var/www/html -type d -exec chmod 755 {} + && \
  find /var/www/html -type f -exec chmod 644 {} +'
```

Deploy `index.html`, `projects.html` and `assets/`. **Never rsync with `--delete`**, and never
replace `/var/www/html` wholesale — the docroot also holds three separately deployed
sub-sites, owned by their own repositories, that this repo does not contain:

| Path | What it is | Source repo |
|---|---|---|
| `/from-the-edges/` | Europe, Seen from the Edge (history) | `~/Downloads/europe-seen-from-the-edge` |
| `/lightbringer/` | The Light Bringer diptych | `~/Downloads/lightbringer` |
| `/literature/` | Friday, Parallelism & Torments | `~/Downloads/literary-sites/writings` |

The front page links to all three from the **Media Projects** item in the primary nav,
which is a second page of this repo (`projects.html`), not a link out. Touching those
directories from here will overwrite work this repo has no copy of.

### Two traps that will bite you

1. **Trailing slash flattens the directory.** `rsync index.html assets/ host:/var/www/html/` copies
   the *contents* of `assets/` into the web root, so every `assets/...` URL 404s. Always give each
   source its own destination, as above. Check the resulting tree with `ls` before trusting a deploy.
2. **`--chmod` is unsupported on macOS rsync 2.6.9.** The modern `--chmod=F644,D755` form is
   rejected. Use the `chown` + `find`/`chmod` normalisation in the snippet.

### Verifying a deploy

Do not call a deploy done on the strength of rsync output. Check over HTTPS:

- live `index.html` is byte-identical to `git show HEAD:index.html`
- each asset returns 200 with the correct `content-type`
- binary assets match by md5: `curl -s <url> -o /tmp/x && md5 -q /tmp/x`
- the page renders with no failed requests (headless check, not just `curl`)

### Cache caveat

The nginx vhost sends `Cache-Control: max-age=72576000` (84 days) for `.gif`, `.jpg` and `.png`.
Replacing `assets/portrait.png` under the same filename will **not** appear for returning visitors —
rename the file or accept the staleness. PDFs and `.webp` are not covered.

## Conventions

- Two pages, no build step: `index.html` and `projects.html`. Each is self-contained —
  markup, inline `<style>`, and content all in the file. There are no partials, no shared
  stylesheet, and nothing to compile. The consequence is deliberate duplication of the
  `:root` tokens and the masthead/nav/footer rules across both files; if the design
  language changes, change it in both or the pages drift apart.
- The pages link to each other by relative filename (`index.html`, `projects.html`), so
  both must exist at the docroot root for navigation to work.
- The design language: serif (Georgia) for body and headings, `Inter` with system fallbacks for
  small uppercase labels, burgundy `#8d2829` accents, `--paper #fbfaf7` background, hairline rules.
  Reuse the CSS custom properties in `:root` rather than hardcoding hex values.
- New UI goes into a rule-anchored block (`border-top` + a small uppercase `.section-note` or
  `.article-meta` label), matching how the existing sections are built.
- Two breakpoint tiers: `max-width: 760px` and `max-width: 440px`. Any new grid needs both.
- Only `section.about` uses the `#f7f4ed` tinted background. Keep the paper background elsewhere.
- Documents users download live in `assets/` and are linked from the section that discusses them
  (the CV sits in About). Link them with the `download` attribute and label the meta line with the
  real page count, e.g. `PDF download · 3 pages`.
- Keep `README.md` accurate when adding or removing files. Its "Next steps" still lists *Choose
  hosting and connect alexandrugris.ro* — that is stale, hosting is already live.
