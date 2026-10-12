#!/usr/bin/env bash
#
# Deploy all five alexandrugris.ro sites, regenerate the sitemap, verify.
# The five are: the personal site root, europe-seen-from-the-edge (history),
# the-light-bringer-diptych (poetry diptych), writings (literature hub) and
# friday-bande-dessinee (bande dessinée of the Friday text). The friday-
# bande-dessinee rsync destination is still TBD; until it is set, the
# fifth-site hook in this script only registers the local repo, prints a
# PENDING line in the deploy step, and includes it in the repo-state report
# when the clone is present on this host. It is deliberately optional in
# preflight so this script does not require FBD to exist before it can
# deploy the other four.
#
# Order matters: back up, deploy, regenerate lastmod from the git dates of
# what was just deployed, then verify. Regenerating the sitemap after the
# rsync means its lastmod values describe what is actually live.
#
# Deliberately does NOT commit or push. It reports which repos are dirty or
# out of sync instead, so deploying something you have not committed is a
# visible, deliberate act rather than a surprise.
#
#   ./deploy.sh            deploy and verify
#   ./deploy.sh --dry-run  show what would change, touch nothing
#   ./deploy.sh --no-backup  skip the docroot backup (you will regret it)
#
set -euo pipefail

HOST=website-root
DOCROOT=/var/www/html
BASE=https://alexandrugris.ro

HOME_DIR="$HOME/Downloads"
PERS="$HOME_DIR/Personal Website"
EDGE="$HOME_DIR/europe-seen-from-the-edge"
LB="$HOME_DIR/lightbringer"
LIT="$HOME_DIR/literary-sites/writings"
FBD="$HOME_DIR/friday-bande-dessinee"       # 5th site, deploy destination TBD

DRY=""
BACKUP=1
for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY="-n" ;;
    --no-backup) BACKUP=0 ;;
    -h|--help)   sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

RSYNC=(rsync -avz --no-owner --no-group --no-times)
[ -n "$DRY" ] && RSYNC+=(-n)

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '   \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '   \033[31mx\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight

step "Preflight"
for d in "$PERS" "$EDGE" "$LB" "$LIT"; do
  [ -d "$d" ] || die "missing repo: $d"
done
[ -x "$PERS/tools/audit-deploy.py" ] || [ -f "$PERS/tools/audit-deploy.py" ] \
  || die "missing $PERS/tools/audit-deploy.py — this script lives beside it"

# The 5th site (friday-bande-dessinee) is optional in preflight until its
# rsync destination is wired up. The four deployed sites keep the
# strict "die on missing" behaviour — only FBD is relaxed.
if [ -d "$FBD" ]; then
  echo "   5 site repos present, audit tool present"
else
  echo "   4 site repos present, audit tool present"
  warn "friday-bande-dessinee not on this host yet — the 5th-site hook is dormant"
fi

DIRTY=()
for d in "$PERS" "$EDGE" "$LB" "$LIT"; do
  [ -n "$(git -C "$d" status --porcelain)" ] && DIRTY+=("$(basename "$d")")
done
# Include FBD in the dirty report only when the clone exists here.
if [ -d "$FBD" ]; then
  [ -n "$(git -C "$FBD" status --porcelain)" ] && DIRTY+=("friday-bande-dessinee")
fi
if [ ${#DIRTY[@]} -gt 0 ]; then
  warn "uncommitted changes in: ${DIRTY[*]}"
  warn "the live site will not match git HEAD, so it is not restorable yet"
fi

# ------------------------------------------------------------------- backup

if [ "$BACKUP" -eq 1 ]; then
  step "Backup"
  TS=$(date +%Y%m%d-%H%M%S)
  BAK="/var/www/backup-$TS"           # path convention documented in AGENTS.md
  if [ -n "$DRY" ]; then
    echo "   would copy $DOCROOT -> $BAK"
  else
    ssh "$HOST" "cp -a $DOCROOT $BAK" >/dev/null 2>&1 \
      || die "backup failed — refusing to deploy over an unbacked-up docroot"
    ssh "$HOST" "ls -d $BAK" 2>/dev/null | grep -q . \
      || die "backup did not materialise on the server"
    echo "   $BAK"
  fi
else
  step "Backup"
  warn "skipped (--no-backup)"
fi

# -------------------------------------------------------------------- deploy

step "Deploy"
# Each source gets its own explicit destination. Never --delete, never the
# docroot as a whole: it holds four sub-sites this loop does not own
# (history, lightbringer, literature, friday-bande-dessinee).
deploy() {
  local src=$1 dest=$2 label=$3
  printf '   %-14s -> %s\n' "$label" "$dest"
  "${RSYNC[@]}" "$src" "$HOST:$dest" >/dev/null 2>&1 || die "rsync failed: $label"
}

for f in index.html projects.html robots.txt sitemap.xml; do
  [ -f "$PERS/$f" ] || die "missing $PERS/$f"
  deploy "$PERS/$f" "$DOCROOT/" "personal:$f"
done
deploy "$PERS/assets/"      "$DOCROOT/assets/"          "personal:assets/"

# The literature site has a real build step and its dist/ is fully derived --
# build.py starts with shutil.rmtree(DIST). Deploying dist/ without rebuilding
# first ships whatever the last build happened to produce, which is exactly
# the state that once deleted all four preview cards from dist/ without anyone
# noticing until the page went live without them.
if [ -f "$LIT/build.py" ]; then
  printf '   %-14s -> rebuild before deploy\n' "literature"
  ( cd "$LIT" && python3 build.py >/dev/null ) || die "build.py failed for the literature site"
  [ -n "$(git -C "$LIT" status --porcelain dist)" ] \
    && warn "build.py changed dist/ -- those changes are being deployed and must be committed"
fi

deploy "$EDGE/dist/"        "$DOCROOT/from-the-edges/"  "history"
deploy "$LB/dist/"          "$DOCROOT/lightbringer/"    "lightbringer"
deploy "$LIT/dist/"         "$DOCROOT/literature/"     "literature"

# Friday (bande dessinée) — REGISTERED BUT NOT YET WIRED.
# Until the rsync destination is decided, this block only prints a
# placeholder and emits a warning. Nothing is uploaded to /var/www/html
# for FBD, and audit-deploy.py does not check any FBD page. Replace
# this block with `deploy "$FBD/dist/" "$DOCROOT/<chosen-path>/"
# "friday-bd"` once the destination is set, and extend
# tools/audit-deploy.py and tools/check-previews.py to cover the new
# pages at the same time.
if [ -d "$FBD" ]; then
  printf '   %-14s -> %s\n' "friday-bd" "PENDING (destination not configured)"
  warn "friday-bande-dessinee: rsync destination not configured — skipping"
fi

if [ -n "$DRY" ]; then
  step "Dry run — stopping before sitemap and verification"
  echo "   Nothing was changed. Re-run without --dry-run to deploy."
  exit 0
fi

# --------------------------------------------------------------- permissions

step "Permissions"
ssh "$HOST" "chown -R www-data:www-data $DOCROOT && \
  find $DOCROOT -type d -exec chmod 755 {} + && \
  find $DOCROOT -type f -exec chmod 644 {} +" 2>/dev/null \
  || die "could not normalise permissions"
echo "   www-data:www-data, dirs 755, files 644"

# ------------------------------------------------------------------ sitemap

step "Sitemap"
# Runs after the deploy so lastmod reflects what is actually live.
python3 "$PERS/tools/make-sitemap.py" || die "sitemap generation failed"
deploy "$PERS/sitemap.xml" "$DOCROOT/" "sitemap"
SITEMAP=$(git -C "$PERS" status --porcelain sitemap.xml)
[ -n "$SITEMAP" ] \
  && warn "sitemap.xml changed — commit and push it in the personal repo" \
  || echo "   unchanged"

# ----------------------------------------------------------------- verify

step "Verify"
python3 "$PERS/tools/audit-deploy.py" || die "audit failed — the live site does not match the repos"

step "Repo state"
for d in "$PERS" "$EDGE" "$LB" "$LIT"; do
  b=$(git -C "$d" rev-parse --abbrev-ref HEAD)
  local_sha=$(git -C "$d" rev-parse HEAD)
  remote_sha=$(git -C "$d" ls-remote origin "$b" 2>/dev/null | cut -f1)
  n=$(git -C "$d" status --porcelain | wc -l | tr -d ' ')
  sync="in-sync"; [ "$local_sha" != "$remote_sha" ] && sync="UNPUSHED"
  dirty="clean";      [ "$n" -ne 0 ] && dirty="$n file(s) dirty"
  printf '   %-14s %-8s %-8s %s\n' "$(basename "$d")" "$b" "$sync" "$dirty"
done
# FBD is reported only when its clone is on this host; same fields.
if [ -d "$FBD" ]; then
  b=$(git -C "$FBD" rev-parse --abbrev-ref HEAD)
  local_sha=$(git -C "$FBD" rev-parse HEAD)
  remote_sha=$(git -C "$FBD" ls-remote origin "$b" 2>/dev/null | cut -f1)
  n=$(git -C "$FBD" status --porcelain | wc -l | tr -d ' ')
  sync="in-sync"; [ "$local_sha" != "$remote_sha" ] && sync="UNPUSHED"
  dirty="clean";      [ "$n" -ne 0 ] && dirty="$n file(s) dirty"
  printf '   %-14s %-8s %-8s %s\n' "friday-bd" "$b" "$sync" "$dirty"
fi

step "Preview check"
python3 "$PERS/tools/check-previews.py" \
  "$BASE/" "$BASE/projects.html" \
  "$BASE/from-the-edges/" "$BASE/from-the-edges/routes.html" \
  "$BASE/from-the-edges/annexes/" "$BASE/from-the-edges/architecture.html" \
  "$BASE/from-the-edges/art.html" "$BASE/from-the-edges/manuc.html" \
  "$BASE/from-the-edges/the-long-way-from-paris.html" \
  "$BASE/lightbringer/" "$BASE/lightbringer/notes.html" \
  "$BASE/literature/" "$BASE/literature/friday/" \
  "$BASE/literature/parallelism/" "$BASE/literature/torments/" \
  | tail -3

printf '\n\033[1mDeploy complete and verified.\033[0m\n'