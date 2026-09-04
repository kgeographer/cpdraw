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
- **Draw entry:** `frontend/src/draw/main.ts` → `Viewer.svelte` mounts OpenSeadragon over the
  IIIF service named by the mount div's `data-iiif` attr (WO-0.3). The WO-0.1 `_wo01` smoke
  page is gone.
- This is build-time Node only; runtime Node for `@allmaps/cli` is still Open Question 3.

## Domain model & ingest (WO-0.2 — in progress)

The predecessor's `Map` / `Feature` / `Name` are gone. Live model in `main/models.py`:
`Project` / `ProjectUser` / `Placetype` / `ProjectPlacetype` (kept) → `Source` → `MapImage` →
`WorkState`. `Source` keeps the raw IIIF document verbatim plus a `normalization_log`;
CPDraw-authored metadata sits alongside manifest-derived fields and never overwrites them.
Working spec: `docs/WO_0.2.md`.

- IIIF ingest is **Python** (`main/iiif/`): `fetch` → `normalize` (tolerant, per-host quirks) →
  `parse_manifest` / `parse_info_json` (Presentation 2 and 3) →
  `ingest_source(uri, project=, owner=)`. Graceful-degradation branch per scoping doc §6a.
- Drive it: `manage.py ingest_source <uri> --project <label> [--from-file path]`, or the
  "add source" form on the project page (`/project_update/<id>`).
- The Leaflet stack is gone: `django-leaflet` / `django-geojson`, the Mapbox token settings,
  the `cpdraw/static/js/leaflet*` tree, the `TILES_URL` tile route, and the Leaflet-era Draw
  page / Map-Feature CRUD / CSV-LPF export. `reverse-geocoder` + `geojson` kept for the
  Phase 1 LPF rebuild.
- **WO-0.3 done:** `/draw/<image_id>/` renders a `MapImage` in OpenSeadragon
  (`frontend/src/draw/{main.ts,Viewer.svelte}`). Ingest also stores a per-image quality
  advisory (`main/iiif/quality.py` → `MapImage.quality_notes`), and `add_source` preflights —
  a very-low-res warning gates behind an "add anyway" tick.

## Annotation & vocabulary (WO-0.4 — done)

Working spec: `docs/WO_0.4.md`.

- `/draw/<image_id>/` mounts Annotorious v3 (`@annotorious/openseadragon` +
  `@annotorious/plugin-tools`) on the OSD viewer. `frontend/src/draw/`: `App.svelte` (toolbar
  Region→polygon / Label-boundary→path / Select), `Viewer.svelte`, `annotationStore.ts`
  (load + CRUD → `/api/annotations/`), `PropertiesPanel.svelte` (name / role / type /
  certainty, debounced PATCH).
- `Annotation` model (image-space pixel geometry): `w3c` blob as Annotorious emits it +
  extracted columns. Two orthogonal type axes — `feature_role` (CPDraw enum: region / label /
  boundary / site; never in LPF) and `placetype` → `ProjectPlacetype`.
- `ProjectPlacetype` = the project's own vocab: `source_label` (free text) + **nullable**
  `aattype` AAT mapping (the WHG LP-TSV `types[]` / `aat_types[]` pattern). Managed at
  `/project/<pk>/types/`; new projects seed Bregel's five.
- Master AAT = the LPF-supported subset. `manage.py load_aat_feature_types` loads
  `main/data/feature-types-AAT_20230609.tsv` into `Placetype` (idempotent; run once after
  migrate).
- API is plain DRF (`/api/annotations/`, `/api/project-placetypes/`,
  `/api/placetypes/search/`) — session auth, `IsAuthenticated`, no pagination.

## Auth, projects, roles (WO-0.5 — done; Phase 0 complete)

Working spec: `docs/WO_0.5.md` (§9 = as-built).

- **Auth is Django-conventional.** `accounts/`: `SignupForm(UserCreationForm)` +
  `RegisterView`; `LoginView` / `LogoutView` / `PasswordChange*` / `PasswordReset*` from
  `django.contrib.auth.views`. Reset email = console backend in dev (`DEFAULT_FROM_EMAIL`
  set; SMTP is deploy-time). Auth-template overrides live in the project-level
  `templates/registration/` (they must beat the copies `django.contrib.admin` ships).
- **Roles** on `ProjectUser`: `owner | editor | annotator` (`main/choices.TEAMROLES`).
  `Project.owner` (FK) is an implicit owner. `Project` carries `role_of(user)` +
  `can_edit_metadata` / `can_add_sources` / `can_manage_vocabulary` / `can_edit_annotation`;
  `Project.objects.visible_to(user)` (superuser → all, else owned ∪ membership). Template
  gating via `main/templatetags/project_perms.py`. Superuser = `is_superuser` only.
- **Enforcement is at the Django view layer** (project create/update/delete, `add_source`,
  `project_placetypes`). The DRF endpoints still just use `IsAuthenticated` — object-level
  permission classes are WO-0.6.
- **`Project` spatial scope** (`scope_ccodes` / `scope_bbox` / `scope_note`, all optional;
  `ProjectForm` via `SimpleArrayField`) — the WO_0.2.md §1a carry-over. No map picker
  (Phase 1, when §7a consumes it).
- **`MapImagePlacetype`** — per-map narrowing of the project vocab. "No rows = inherit the
  full set"; `MapImage.available_placetypes`. **Table + helper only this WO** — the
  annotation-picker filter and editor UI are a later WO.
- `ProjectCreateView` writes a `ProjectUser(role='owner')` row and seeds Bregel's five.

## Next — WO-0.6

Join keys / invite flow (`ProjectInvite`, `/join/<key>/`, owner mint-revoke UI);
object-level DRF permission classes on `/api/annotations/` + `/api/project-placetypes/`
(rebuild `accounts/permissions.py`, deleted in WO-0.5); the `MapImagePlacetype` read path +
editor UI; front-end library modernisation (Bootstrap 4 → 5, drop jQuery/jQuery-UI, fix the
`http://ajax.googleapis.com` mixed-content link); read-only Source detail page (retire the
`/admin/` links). Point capture is Phase 1 (a CPDraw OSD overlay, §9.1).

## Key decisions already made (see scoping doc for full reasoning)

- Image-space (unrectified IIIF source, pixel coordinates) is canonical; geo-space is derived
  and regenerated when georeferencing improves. Never the reverse.
- Viewer: **OpenSeadragon**, not Leaflet — Leaflet only reappears later (Phase 1+) as an
  optional geo-space viewer over already-derived output.
- Annotation UI: **Annotorious v3**, adopted (not a build-vs-buy question). Polygon + rectangle
  ship in the base package; **polyline** ships in `@annotorious/plugin-tools` (in use since
  WO-0.4). **Point: CPDraw builds its own OSD overlay** — not an Annotorious `Point` primitive,
  not PR #443 (decided 2026-09-02). Annotorious is Svelte-authored internally, so the frontend
  build tooling in WO-0.1 must be Svelte-capable (Vite + `@sveltejs/vite-plugin-svelte`) —
  settled, not open. Full story + correspondence: `docs/annotorious/` (`README.md` is the index).
- Georeferencing/transform: **Allmaps** (`@allmaps/transform`, `@allmaps/cli`), invoked
  server-side from Django. Default to a low-order polynomial transform, not
  `thinPlateSpline` — see scoping doc §7b for why (cartographic displacement is evidence, not
  error to remove).
- The user knows both Rainer Simon (Annotorious) and Bert Spaan (Allmaps) personally — gaps in
  either library are a feature conversation, not something to work around alone. Rainer replied
  (2026-08-31 → 09-03, `docs/annotorious/rainer_20260903.txt`): a v3→v4 rewrite is coming
  (DeckGL renderer, OpenLayers connector); polyline is covered by `plugin-tools`; point is
  CPDraw's own overlay to build. Also flagged `@annotorious/plugin-magnetic-outline` (OpenCV.js
  contour tracing) as worth trying — see `docs/guided-extraction.md`.

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
