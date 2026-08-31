# CPDraw

A fresh, independent Django project — **not** a migration of its predecessor. Read
`docs/CPDraw — scoping document.md` in full before doing any design or implementation work;
it is the spec, and this file is only a pointer to it and to a few facts the scoping doc doesn't
cover (repo/environment provenance, sibling-project boundaries, naming gotchas).

Per-session activity logs live in `logs/session_log_YYYYMMDD.md` — narrative notes on what
changed and *why*, plus gotchas and follow-ups. Worth reading when picking up prior work, and
worth appending to at the end of a working session. Keep the detail there, not here.

## Provenance

Cloned from `../lpdraw` (itself formerly "whgdraw" / "linkedplaces.draw", a 2020-era proof of
concept, dependency-refreshed and now live at `draw.computingplace.org`), then **fully
detached**: fresh `git init`, no shared history, no shared git remote. The clone inherited
Django/GeoDjango scaffolding worth keeping (auth, `Project`/`ProjectUser`, the
`Placetype`/`ProjectPlacetype`/`MapPlacetype` AAT-vocabulary scoping, the LPF export logic) per
the scoping doc's Open Question 2 — but the core domain model
(`Map`/`Feature` → `Source`/`MapImage`/`Annotation`/`Georeference`/`WorkState`) is being
replaced, not extended. Expect to delete/rewrite most of `main/models.py` and the Draw-page
views/templates; keep the auth, project-membership, and placetype/LPF-export code as the parts
worth preserving.

**`../lpdraw` is a read-only reference from this project's perspective.** It's a live,
separately deployed app (`draw.computingplace.org`) with its own GitHub repo
(`kgeographer/lpdraw`) — don't edit it from a CPDraw session; copy code across deliberately when
reusing something.

## Environment (already set up)

- `.venv/` — dedicated venv for this project, `requirements.txt` already installed into it.
- `.env` / `cpdraw/local_settings.py` — already populated (gitignored, not committed): a fresh
  `SECRET_KEY` generated for this project, local Postgres connection. Mapbox tokens
  intentionally omitted — the inherited Leaflet/Mapbox Draw view is legacy code CPDraw's
  OpenSeadragon-based viewer replaces, not something to fix up.
- Local Postgres db **`cpdraw`** — empty, PostGIS enabled, migrations applied against the
  *inherited* (soon to be replaced) models. No real data was carried over from lpdraw; the
  domain model changed too much for that to make sense (see scoping doc Open Question 2).

**Naming gotcha:** there are three different things called "cpdraw" — this project's directory,
this project's local db, and (unrelatedly, a pre-existing inconsistency) the *lpdraw* app's
production database name on the deployment VM. If a task involves the VM or lpdraw's data, be
explicit about which one is meant.

## Frontend build (WO-0.1 — done)

`frontend/` is a Vite project (see `frontend/README.md` for the full picture). Bridged into
Django templates by **django-vite** — `DJANGO_VITE` block in `cpdraw/settings.py`, tags in
templates. Toolchain deliberately pinned to **Node 22 / Vite 5 / Svelte 4** to match
Annotorious v3.8.9's runtime (the point/polyline plugin in WO-0.4 compiles against it) — do
not bump ahead of Annotorious.

- **Node** is installed keg-only via Homebrew. Interactive shells get it from `~/.zshrc`;
  a non-interactive command needs `export PATH="/opt/homebrew/opt/node@22/bin:$PATH"` first.
  pnpm is via Corepack (`pnpm`, not `npm`).
- **Dev = two processes:** `python manage.py runserver` **and** `pnpm --dir frontend dev`
  (Vite on :5173, HMR). With `DEBUG=True` django-vite points `<script>` at the dev server.
- **Prod:** `pnpm --dir frontend build` (writes `frontend/dist/` + manifest) **before**
  `collectstatic`. With `DEBUG=False` django-vite emits hashed tags served from
  `/static/frontend/`.
- **Smoke page:** `/draw/_wo01/` — throwaway, proves ESM-Allmaps + Svelte both load. Delete
  it, `SmokeProbe.svelte`, and the `wo01-pipeline-check` route when WO-0.3 lands the real
  OpenSeadragon viewer.
- This is build-time Node only; runtime Node for `@allmaps/cli` is still Open Question 3.

## Key decisions already made (see scoping doc for full reasoning)

- Image-space (unrectified IIIF source, pixel coordinates) is canonical; geo-space is derived
  and regenerated when georeferencing improves. Never the reverse.
- Viewer: **OpenSeadragon**, not Leaflet — Leaflet only reappears later (Phase 1+) as an
  optional geo-space viewer over already-derived output.
- Annotation UI: **Annotorious v3**, adopted (not a build-vs-buy question). It ships polygon and
  rectangle; point and polyline need a small plugin — evaluated and confirmed **plugin-feasible,
  no fork required** in `docs/annotorious_check_findings.md`. That plugin is Svelte-authored
  (Annotorious v3 is internally Svelte), so the frontend build tooling in WO-0.1 needs to be
  Svelte-capable specifically (e.g. Vite + `@sveltejs/vite-plugin-svelte`), which the scoping
  doc's §8 doesn't spell out — treat that as settled, not open.
- Georeferencing/transform: **Allmaps** (`@allmaps/transform`, `@allmaps/cli`), invoked
  server-side from Django. Default to a low-order polynomial transform, not
  `thinPlateSpline` — see scoping doc §7b for why (cartographic displacement is evidence, not
  error to remove).
- The user knows both Rainer Simon (Annotorious) and Bert Spaan (Allmaps) personally — gaps in
  either library are a feature conversation, not necessarily something to work around alone. An
  email to Rainer about the point/polyline plugin approach is pending a reply as of 2026-08-29.

## Phase 0 target

Miczyński, *Galicyja i Lodomeryja* (Rzeszów, 1872), Biblioteka Narodowa via Polona. Image
service `https://polona.pl/iiif/3/cf2d49d7-1d3a-448d-abb2-190d6bd01af8`, 15919×12357,
ImageService3 level 2. The manifest is deliberately malformed (lowercase `"type": "manifest"`,
`example.org` placeholder IDs) — see scoping doc §6a — and is meant to exercise the
normalization/graceful-degradation requirement immediately rather than being swapped for a
clean manifest first.

## Ground-truth experiment (independent of CPDraw's build — can run any time)

The `lpdraw` Bregel geometries (`bregel_37`, `bregel_39`) are a ready-made degrade-and-
reconstruct evaluation corpus, runnable without any CPDraw code. Spec is in the scoping doc,
§10 Phase 3 "Evaluation corpus"; framing in `docs/GPT_20260828.txt`. `docs/guided-extraction.md`
writes up the semi-automated "few guide points → traced boundary" branch this eval is for,
and how to evaluate it; `notebooks/` holds the work (own venv, the "Draw2" track).
