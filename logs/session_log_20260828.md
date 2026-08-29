# Session log — 2026-08-28

Goal: take the dependency-refreshed `restore` branch from a working local
checkout to a tagged, publicly hosted `v1` demo at `draw.computingplace.org`,
and split off planning material for a second, experimental track ("Draw2").

## Repo cleanup and branch consolidation

- Confirmed the local password for the sole existing user (`karlg`) by
  querying `auth_user` directly, then reset it (`karlg` / `tracing`) since
  the interactive `changepassword` prompt doesn't work in a non-interactive
  shell.
- `restore` (5 commits of dependency-refresh/bugfix work) had never been
  pushed anywhere; a local `main` branch existed but was stale (old
  `master` + one snapshot commit). Fast-forwarded `main` to `restore`.
- First push to `LinkedPasts/draw` was blocked by GitHub push protection:
  a live Mapbox access token hardcoded in `main/templates/main/draw.html`.

## Secret remediation

Found and removed, all previously present in tracked files:
- Two Mapbox `pk.` tokens and one Mapbox `sk.` (secret-scope) token,
  hardcoded in `draw.html` and `home.html` across several commits.
- A hardcoded Django `SECRET_KEY` in `settings.py` (already shadowed in
  practice by `local_settings.py`'s own key, but still present in the
  tracked file).

Fix: moved both Mapbox tokens to `local_settings.py` (already-gitignored,
matches the project's existing settings/local_settings split), wired them
through `DrawView`'s context into the template with `escapejs`. Replaced
the hardcoded `SECRET_KEY` with an obviously-fake placeholder, since the
real one already lived only in `local_settings.py`.

Since the secrets were embedded across several historical commits, not
just the tip, used `git filter-repo --replace-text` to scrub all four
values from every commit reachable from any local branch (installed via
`pip install git-filter-repo` into the project venv). Verified with a
full-history grep for Mapbox/AWS/Google-style token patterns and any
`SECRET_KEY=`/`PASSWORD=` literals before pushing. `main` pushed clean.

**Follow-up not done this session:** the Mapbox tokens were live and
public in `LinkedPasts/draw`'s `master` branch for ~6 years; today's
cleanup stops further exposure via `main` but doesn't undo that. They
should be rotated in the Mapbox dashboard regardless.

## GitHub administration

Installed `gh` CLI (via Homebrew) and authenticated (device-code flow) to
do the rest from the terminal:
- Set `main` as the default branch on `LinkedPasts/draw`, deleted `master`
  (which still held the unscrubbed history).
- Swept 8 dead 2020-era branches (`admin`, `download`, `features`, `misc`,
  `placetypes`, `save`, `types`, `v2`) plus stale Dependabot branches.
- Tagged `v1` on `main`.
- Transferred the repo `LinkedPasts/draw` → `kgeographer/draw` (old URL
  now 301-redirects). Confirmed the `v1` tag survived the transfer.

**Follow-up not done this session:** GitHub reported 39 Dependabot
vulnerability alerts (4 critical, 13 high) on the pushed history — not
triaged.

## Static files: whitenoise

Added `whitenoise` so nginx can just proxy everything to gunicorn (no
separate static-file location block needed), matching the project's
"no frontend build tooling" character.

First attempt used `whitenoise.storage.CompressedManifestStaticFilesStorage`
(content-hashed filenames for cache-busting) and broke `collectstatic`:
several vendored JS files (`easyprint.js`, `FileSaver.min.js`, etc.)
contain `//# sourceMappingURL=...` comments pointing at `.map` files that
were never actually shipped, and the Manifest storage hard-fails on any
missing reference — `WHITENOISE_MANIFEST_STRICT` does *not* cover this
path (it only affects a different runtime lookup). Fixed by dropping to
`whitenoise.storage.CompressedStaticFilesStorage` (compression only, no
manifest/hashing, no reference-scanning) rather than patching around
vendored files.

## VM deployment (Hetzner, `kgeographer-1`)

Surveyed the existing box first rather than guessing: Ubuntu 24.04,
nginx + gunicorn-behind-reverse-proxy pattern already used for several
other `*.computingplace.org` subdomains and `cedop`/`glos`, Postgres
17.9 with PostGIS 3.6 already installed, certbot already in use, no
Docker, no `gh` CLI (installed one, above).

- DNS: user added an A record `draw.computingplace.org` → `46.225.125.25`
  in Namecheap.
- Cloned `kgeographer/draw` to `/var/www/draw` (HTTPS, not SSH — repo is
  public, avoided needing to provision an SSH key on the VM).
- venv at `/home/karlg/envs/draw`, `pip install -r requirements.txt`.
- Created Postgres db `cpdraw`, enabled the `postgis` extension. GDAL/GEOS
  are on the system ld path here (unlike the Mac dev setup), so no
  `GDAL_LIBRARY_PATH`/`GEOS_LIBRARY_PATH` needed in `.env`.
- Wrote `local_settings.py` (production `ALLOWED_HOSTS`, `DEBUG = False`,
  a freshly generated `SECRET_KEY`, the two Mapbox tokens) and `.env`
  (`PG*` vars) directly on the VM — neither is tracked in git.
- `python manage.py migrate`, then `collectstatic`.
- `pg_dump`'d the local `cpdraw` database (2 projects, 48 maps, 1051
  features, 1 user) and `pg_restore`'d it onto the VM's fresh `cpdraw`;
  row counts matched exactly.
- systemd unit `draw.service` running gunicorn on `127.0.0.1:8003`
  (8001/8002 already used by other apps on this box), modeled on the
  existing `edops.service` pattern. `enable --now`.
- nginx vhost `draw.computingplace.org`, `certbot --nginx` for TLS —
  confirmed HTTPS 200, HTTP→HTTPS redirect, static assets serving.

## Tile pyramid gap

After initial deploy, traced feature data loaded but the rectified
Bregel map tile overlays didn't. Root cause was two separate issues:

1. The tile pyramids (`tiles/bregel/`, 14 map sets, ~913 MB, ~152,500
   files) live in a gitignored directory — never part of the repo, so
   the clone didn't bring them over.
2. Independent of the missing files, `whgdraw/urls.py` only registers the
   `/tiles/` route `if settings.DEBUG` — and production correctly runs
   with `DEBUG = False`, so Django would never have served them anyway.

Fixed by treating tiles the way large static binary trees should be
handled in production: nginx serves `/tiles/` directly from disk via an
`alias`, bypassing Django/gunicorn entirely (a better fit here than
whitenoise — these are large files requested constantly during
pan/zoom). Copied the tile directory to the VM with `rsync`. (First
rsync attempt was launched with a stray inner `&` inside an
already-backgrounded shell command, which caused the harness to report
it "complete" after only ~22 MB transferred; the actual rsync process
was still alive and unaffected, just untracked — restarted the wait
properly and let it finish. Final byte count and file count matched
local exactly.) Verified tiles load with a real screenshot of the
`bregel_19` map showing the rectified overlay and all 1051 traced
features.

## Draw2 planning docs

Retrieved a shared ChatGPT conversation (`docs/GPT_20260828.txt`) via
WebFetch/manual paste — the ChatGPT share URL doesn't render server-side,
so the user exported it as text — discussing AI-assisted boundary
extraction from historical maps (VLM-guided segmentation via
SAM2/MapSAM/SMOL-MapSeg, human-in-the-loop refinement, provenance/
confidence at the segment level). Spot-checked the specific papers/
projects it cited (SMOL-MapSeg, MapSAM/MapSAM2, the Xia et al.
topological-vectorization paper, mapKurator, Allmaps) via web search —
all real, one minor date error (SMOL-MapSeg is Aug 2025, not "this
month"/Aug 2026 as claimed). Added this alongside the existing
`docs/redesign-brief.md` as reference material for a separate,
not-yet-started experimental track ("Draw2"), kept deliberately apart
from the Draw v1 app itself.

## End state

- `kgeographer/draw`, single branch `main`, tagged `v1`, secret-free
  history.
- Live at `https://draw.computingplace.org` — TLS, traced feature data,
  rectified map tiles, static assets, login all confirmed working.
- Outstanding: rotate the long-exposed Mapbox tokens; triage the 39
  Dependabot alerts; decide Draw2's repo/branch structure and start the
  boundary-extraction experiment described in the planning docs.
