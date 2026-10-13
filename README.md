# alexandrugris.ro

Personal website for Alexandru Gris: technology, teams, and the long view.

The current version is a responsive static site built with plain HTML and CSS. Its visual direction deliberately evolves the existing site: serif typography, burgundy accents, generous whitespace, the original portrait, and the long-running **From the Trenches** identity.

## Preview locally

From this directory, run:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Structure

- `index.html` — complete site and styles
- `assets/hero-city-park.webp` — homepage hero photograph
- `assets/portrait.webp` — portrait reused from the existing site
- `assets/alexandru-gris-curriculum-vitae.pdf` — curriculum vitae, linked from the About section

## Estate

This repo is one of five that publish to **alexandrugris.ro**, and it owns
the deploy script (`tools/deploy.sh`) plus the audit, preview-check and
sitemap tooling that the estate-wide deploy runs against every site. The
estate map and the verified deploy procedure live in
[AGENTS.md](AGENTS.md); this is the high-level picture.

| Repo | Docroot path | Source on the live host |
| --- | --- | --- |
| `alexandrugris/alexandrugris.ro` (this) | `/` | `~/Downloads/Personal Website` |
| `alexandrugris/europe-seen-from-the-edge` | `/from-the-edges/` | `~/Downloads/europe-seen-from-the-edge` |
| `alexandrugris/the-light-bringer-diptych` | `/lightbringer/` | `~/Downloads/lightbringer` |
| `alexandrugris/writings` | `/literature/` | `~/Downloads/literary-sites/writings` |
| `alexandrugris/friday-bande-dessinee` | `/literature/friday-bd/` | `~/Downloads/friday-bande-dessinee` |

## Next steps

- Refine homepage copy and navigation
- Decide how writing from the two existing archives should be consolidated
- Add dedicated Principles, Writing, Work, and About pages if useful
