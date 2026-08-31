# WO-0.2 — domain model, IIIF ingest, Leaflet teardown

**Status:** working spec, for review. Decomposes scoping-doc WO-0.2 and folds in the
Leaflet removal that WO-0.2/0.3/0.5 collectively imply. Section references (§) are to
`docs/CPDraw — scoping document.md`.

**Scope of this doc:** the schema and the ingest pipeline that get an IIIF manifest into
CPDraw as `Source` + `MapImage`, the project/map selection that surfaces it, and the
inherited Leaflet stack that comes out on the way. **Not** in scope: annotation capture and
drawing tools (WO-0.4), OpenSeadragon viewer wiring beyond "image renders" (WO-0.3),
anything georeferencing (Phase 1).

---

## 1. Decisions

1. **IIIF parsing — Python. Decided 2026-08-29.** §8 names `@allmaps/iiif-parser`
   "wrapped in the normalization layer," but that library is JS, Django is Python, and it
   is a *strict* parser that rejects the Phase 0 target manifest outright (§6a). Parsing
   happens once per source ingest — not hot-path, not compute-heavy — and the
   tolerant/quirks/degradation layer (§6a) is custom work in either language, so Node buys
   little here. Going Python keeps runtime Node out of Django's request path until Phase 1,
   where the Django→Node junction gets a deliberate design for `@allmaps/cli` (subprocess
   vs. supervised sidecar). Implementation note: put it behind one internal entry point
   (`parse_manifest(raw_json) -> SourceData`) so a Node parse step can be swapped in later
   without touching callers. Runtime Node stays a Phase 1 question (scoping-doc Open
   Question 3).

## 1a. Still open (need Karl)

2. **Project creation — capture spatial scope + placetype vocab now, or stub?** §3 attaches
   both to `Project`. Neither is *used* until Phase 1 (gazetteer lookup) / WO-0.4
   (annotation typing). Proposal: add the fields now, make them optional in the create
   form, don't build vocab-management UI yet.
3. **`Source` scope — project-local or shared?** §3's tree puts `Source` under `Project`.
   Proposal: project-local. The same manifest added to two projects = two `Source` rows.
   Revisit if it becomes a pain.

---

## 2. The flow (Karl's list, reconciled with §3 / §6b)

```
create user
  → user logs in
  → user creates Project           (metadata ~ existing Project; + optional spatial
                                     scope, + optional placetype vocab)
  → user adds a Source to Project   ("add map"): supply a Manifest URI *or* an
                                     info.json / Image-service URI
      → CPDraw fetches, stores raw, normalizes, parses
      → creates one Source + N MapImage (N = canvas count; 1 for a bare image service)
      → on manifest failure but working image service: still create a MapImage from
        info.json, flag it for manual metadata
  → Source + its MapImages appear in the project's map list
  → user picks Project → Source → MapImage
  → the IIIF image renders (unrectified) in the map window   [WO-0.3]
  → (drawing tools: WO-0.4)
```

Key correction to the original sketch: **"add map" adds a `Source`, which fans out to one
or more `MapImage`s.** The predecessor's `Map` conflated these (§3). The picker is three
levels — project → source → image — not two.

---

## 3. Domain model changes

### Keep (per CLAUDE.md — the parts worth preserving)

- `User` (Django auth), `Project`, `ProjectUser` (roles: creator | owner | member)
- `Placetype` / `ProjectPlacetype` / `MapPlacetype` — AAT vocabulary scoping
- LPF export logic and its `reverse-geocoder` country-code step (geo-space; dormant until
  Phase 1 but not deleted)

### Replace

| Predecessor | CPDraw | Notes |
|---|---|---|
| `Map` | `Source` + `MapImage` | the core split (§3) |
| `Feature` (typed PostGIS geom columns + JSONB props) | `Annotation` (image-space geometry in JSONB) | §3, §8 "Postgres JSONB for annotations"; built in **WO-0.4**, not here |
| — | `Georeference`, `WorkState` | §3; `Georeference` is Phase 1. `WorkState` stub now (see below) |

### Drop or defer

- `Name` (per-atlas autocomplete index) — not in the scoping doc. Defer; revisit if
  annotation-time name entry wants it.
- Tile-pyramid serving (`TILES_URL` / `TILES_ROOT` + the DEBUG-only route) — CPDraw never
  tiles. Delete.

### `Source` — fields

- **Manifest-derived** (populated on fetch, never overwritten by CPDraw — §3): `label`,
  `attribution`, `rights`, `metadata` (the IIIF `metadata` array, verbatim), `navDate`.
- **CPDraw-authored** (sit alongside): CPDraw title/citation fields analogous to the
  existing `Project`/`Map` metadata; `when` as a JSONB timespan (§3 — follows the
  predecessor's `when`/`when_constant`; two derivations: publication date for a map *from*
  history, asserted period for a map *of* history).
- **Provenance of the ingest**: `raw_manifest` (the document exactly as fetched,
  unmodified — §3, §6a), `normalization_log` (what the quirks layer changed and why),
  `ingest_source_uri`, `ingest_kind` (`manifest` | `image-service`), `fetched_at`.
- **Spatial scope override** (§3): optional; inherits from `Project` if unset.

### `MapImage` — fields

- `source` FK
- Canvas identity: `canvas_uri` (or null when degraded from a bare image service),
  `image_service_uri`, `info_json` (retained), `width`, `height`
- Per-image metadata overrides (§3): optional `label`, `when` override
- `needs_manual_metadata` flag (set when created via the degradation path)
- ordering within the source (canvas sequence)

### `WorkState` — stub

§3: assignment, status, lock. Phase 0 is single-user, but create one row per `MapImage` on
ingest with `status = 'unstarted'` so the map list can show progress. Assignment/lock
fields can exist unused.

### Migrations

The local `cpdraw` DB is empty — no data carried from lpdraw (CLAUDE.md). So this is a
**model rewrite + regenerated migrations**, not a data migration. Expect to drop the
inherited `main` migrations and start fresh (or squash), since nearly every table in
`main/models.py` changes.

---

## 4. IIIF ingest pipeline

Ordered stages, each independently testable:

1. **Accept** a Manifest URI **or** an Image-service / `info.json` URI (§6a). Sniff which:
   try to fetch as JSON; a `@context` / `items` / `sequences` shape ⇒ manifest; an
   `info.json`-shaped doc (`@context` IIIF image, `width`/`height`, `sizes`/`tiles`) ⇒
   image service.
2. **Fetch + store raw.** Persist the untouched bytes before anything else (§3, §6a).
3. **Normalize** (tolerant parsing — §6a): case-insensitive `type` matching; leniency
   about properties CPDraw doesn't need; a small **per-provider quirks layer** keyed off
   the host (Polona: lowercase `"type": "manifest"`, `example.org` placeholder IDs on
   annotation pages, canvas IDs pointing at `info.json`). The quirks layer is a legitimate
   component; maintaining patched copies of manifests is not (§6a).
4. **Parse** → extract: source-level label/metadata/rights/navDate; the canvas list; per
   canvas the image-service URI + `width`/`height`.
5. **Create** one `Source` + N `MapImage` + N `WorkState`. Populate manifest-derived
   fields; leave CPDraw-authored fields empty.
6. **Graceful degradation** (§6a): if stage 3–4 fails but a reachable image service /
   `info.json` can be found (either supplied directly, or salvaged from the broken
   manifest), create a single `MapImage` from `info.json` with `needs_manual_metadata =
   True` rather than refusing the map.

### Prerequisite check (§10 target note)

Before building the viewer on Polona: confirm
`https://polona.pl/iiif/3/cf2d49d7-1d3a-448d-abb2-190d6bd01af8/info.json` resolves and that
the image server sends `Access-Control-Allow-Origin`. No CORS ⇒ OpenSeadragon can't fetch
tiles cross-origin ⇒ a same-origin proxy becomes part of WO-0.3's scope. **Not yet run.**

### First test case

The Polona manifest for Miczyński's *Galicyja i Lodomeryja* — malformed on purpose (§6a),
so it exercises the degradation branch immediately. Second canvas is a blank verso; ignore
it (§10).

---

## 5. Leaflet teardown — inventory

Everything in the inherited tree that assumes Leaflet / the tile-pyramid model:

- `django-leaflet` in `INSTALLED_APPS` (and any `LEAFLET_CONFIG`)
- `main/templates/main/draw.html` — the Leaflet + Mapbox-Draw page (replaced by the
  OpenSeadragon Draw page, WO-0.3)
- `cpdraw/static/js/leaflet*`, `leaflet-draw/`, `leaflet-image.js`, `easyprint.js`,
  `leaflet.ajax.min.js`, `spin.umd.js`, the `tags/` bootstrap-tagsinput bundle if only the
  Draw page used it
- `DrawView` injecting `mapbox_token_mb` / `mapbox_token_kg` into context; the
  `MAPBOX_TOKEN_*` settings and their `local_settings.py` values
- `cpdraw/urls.py`: the `if settings.DEBUG: urlpatterns += static(TILES_URL, ...)` block;
  `TILES_URL` / `TILES_ROOT` in settings
- `main/urls.py`: the `feature_*` routes and `DrawView` / `draw` view — replaced by the new
  Source/MapImage views
- `main/views.py`: `createFeature` / `updateFeature` / `deleteFeature`, the `Feature` /
  `Name` imports, `reverse_geocoder` usage that isn't LPF-export

### Open

- **`djgeojson`** — feeds `Feature` geometry to the Leaflet layer. Likely drops with
  `Feature`; confirm nothing in LPF export uses it.
- **`api/` app** (`MapNamesView`, DRF serializers) — annotation CRUD in WO-0.4 will
  probably be an API (the frontend is a real build now, §5 wants W3C Web Annotation
  in/out). Keep the app; expect to rewrite its contents.
- **`reverse-geocoder`** — keep (LPF export country codes, Phase 1).

### Sequencing

1. Add `Source` / `MapImage` / `WorkState` models alongside the old ones; regenerate
   migrations against the empty DB.
2. New views / templates / URLs for project-create, add-source, the three-level picker.
3. WO-0.3 puts OpenSeadragon on the new Draw page.
4. Delete `Map` / `Feature` / `Name`, the Leaflet static assets, `django-leaflet`, the
   Mapbox token plumbing, the tile route — once nothing references them.

Given it's a fork with an empty DB (CLAUDE.md), step 1 can be a wholesale replacement
rather than a careful coexistence.

---

## 6. Deliverable for WO-0.2

login → create project → add the Polona Galicia manifest → it ingests (via the degradation
path, since the manifest is malformed) → the map list shows the source and its one usable
image → selecting it leaves a `MapImage` ready for WO-0.3 to render. No Leaflet, no Mapbox
token, no tile route left in the tree.
