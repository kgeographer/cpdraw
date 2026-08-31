# WO-0.4 — annotation capture (Annotorious + plugin-tools)

**Status:** working spec, for review. Decomposes scoping-doc §10 Phase 0 "WO-0.4 —
Annotorious + `@annotorious/plugin-tools` wired in; annotation capture (linestring
and polygon) with name and type; persist image coordinates". § refs are to
`docs/CPDraw — scoping document.md`.

**Scope:** draw **polygon** and **polyline** annotations on a `MapImage` in the
OpenSeadragon viewer, give each a name and a type, persist the geometry in
**image (pixel) coordinates**, and reload them on return. **Not** in scope:
point capture (deferred, §9.1 → Phase 1), georeferencing / reconciliation
(Phase 1), LPF export (Phase 1), per-image type scoping, multi-user locking
(Phase 2).

---

## 1. Decisions (settled in discussion)

1. **Storage is hybrid.** The `Annotation` row is CPDraw's source of truth (§5):
   a `w3c` JSONB blob holding the annotation exactly as Annotorious emits it
   (target = an `SvgSelector` in pixel space; bodies) **plus** extracted columns
   (`geometry_type`, `name`, `feature_role`, `placetype`, `certainty`, `when`,
   provenance). No external format is the storage format; W3C and LPF are
   projections.
2. **Two type axes, orthogonal.**
   - **`feature_role`** — a small CPDraw-internal enum: `region` (polygon),
     `label` (linestring — a letterspacing extent gesture, directional, no
     width, §4), `boundary` (linestring tracing a drawn border), `site` (point,
     deferred). Defaulted from geometry type; a single toggle disambiguates a
     linestring (label vs boundary). **Never appears in LPF** — it drives
     capture UX and the Phase-1 derivation (buffer labels, densify borders).
   - **`placetype`** — FK to **`ProjectPlacetype`**, the project's *own*
     vocabulary: `source_label` (free text, any language — "plaza", "peoples",
     a tribe name) + a **nullable** `aattype` mapping into the master AAT table.
     This is the WHG LP-TSV `types[]` / `aat_types[]` pattern: always show the
     user's term, carry an AAT (or later a GeoNames fclass) when one exists.
3. **Master AAT vocabulary = the LPF-supported subset.** Commit
   `feature-types-AAT_20230609.tsv` (from the LPF repo) and load it into the
   inherited `Placetype` table via a `load_aat_feature_types` management
   command. It maps 1:1 to `Placetype` (`aat_id`, `parent_id`, `term`,
   `term_full`, `note`).
4. **`ProjectPlacetype.aattype` becomes nullable** (currently `default=-1`,
   required). A project term often has no clean AAT match.
5. **Annotation persistence is a DRF API.** `AnnotationViewSet` at
   `/api/annotations/?image=<id>` — CRUD, image-scoped, `IsAuthenticated`.
   The wire format is CPDraw-native JSON; the Annotorious shape lives only in
   `w3c`. Frontend maps between the two.
6. **Properties UI is a CPDraw side panel, not a custom Annotorious editor.**
   A Svelte panel bound to Annotorious's `selectionChanged`. Cleaner in a
   Svelte host, and it's where the project-vocab lookup lives. (Spike: v3
   selection events / lifecycle in a non-React host — step 5.)

---

## 2. Model

### `Annotation` (new — replaces the predecessor's `Feature`)

| field | type | notes |
|---|---|---|
| `image` | FK → `MapImage` (CASCADE) | annotations attach to a canvas (§3) |
| `geometry_type` | char choices | `polygon` \| `polyline` (`point` later) |
| `feature_role` | `TextChoices` | `REGION` \| `LABEL` \| `BOUNDARY` \| `SITE` |
| `name` | char | verbatim transcription (§4) |
| `name_normalized` | char, blank | optional editorial normalisation, kept separate |
| `placetype` | FK → `ProjectPlacetype`, null | may be untyped mid-work |
| `certainty` | char choices, blank | annotator's confidence in the *reading* (≠ georef confidence) |
| `when` | JSONB, null | per-feature temporal override (timespan shape, §3) |
| `w3c` | JSONB | annotation as Annotorious emits it — the pixel geometry lives here |
| `bbox` | JSONB, null | `[x0,y0,x1,y1]` extracted for cheap filtering |
| `created_by` | FK → user (PROTECT) | per-feature provenance — LPF wants it (§4) |
| `modified_by` | FK → user, null | |
| `created` / `modified` | datetime | `auto_now_add` / `auto_now` |

`db_table = 'annotations'`.

### `ProjectPlacetype` — one change

`aattype = FK(Placetype, to_field='aat_id', null=True, blank=True)` (drop
`default=-1`).

### Not in WO-0.4

- `MapPlacetype` (per-image type scoping) — project-level vocab suffices for
  Phase 0.
- `Georeference` — Phase 1.

Migration: `Annotation` + the `ProjectPlacetype.aattype` change.

---

## 3. Backend

- **`main/management/commands/load_aat_feature_types.py`** — reads a committed
  `main/data/feature-types-AAT_20230609.tsv`, upserts `Placetype` rows
  (idempotent). Run once after migrate; documented in CLAUDE.md.
- **`api` — annotation CRUD.**
  - `AnnotationSerializer`: CPDraw-native fields + `w3c`. On write, store `w3c`
    and extract `geometry_type` + `bbox` from its selector; take name / role /
    placetype / certainty / when from the request.
  - `AnnotationViewSet(ModelViewSet)`: `get_queryset()` requires `?image=`;
    `perform_create` sets `created_by` and advances the image's `WorkState`
    (`unstarted → in_progress`) on its first annotation; `perform_update` sets
    `modified_by`.
  - `api/urls.py`: `/api/annotations/`.
- **Project vocabulary management** (server-rendered for Phase 0):
  - a "project types" page off the project page: list the project's
    `ProjectPlacetype`s, add a new one (enter `source_label`, optionally
    search-and-pick an AAT).
  - `/api/placetypes/search/?q=` — filters the master `Placetype` by
    `term__icontains`, returns `[{aat_id, term, term_full}]` for the autocomplete.
- **Project create** seeds a starter `ProjectPlacetype` set (the Bregel 5:
  historical region, inhabited place, archaeological site, dynasty, cultural
  group) — the still-open WO_0.2.md §1a decision, resolved here.

---

## 4. Frontend (`frontend/`)

- **Deps:** `@annotorious/openseadragon@3.8.9`, `@annotorious/plugin-tools@1.6.0`
  (pin exact; Svelte 4 / Vite 5 lockstep, already pinned). Import both CSS files.
- **`Viewer.svelte`** — on the existing `ready` event: `const anno =
  createOSDAnnotator(viewer, {...})`; `mountPlugin(anno)` (adds `line`, `path`,
  `ellipse`); expose `anno` (event / prop) for the panel and the storage glue.
- **`src/draw/annotationStore.ts`** — the storage adapter:
  - `load(imageId)` → GET `/api/annotations/?image=` → `anno.setAnnotations(rows.map(toAnnotorious))`.
  - subscribe `createAnnotation` / `updateAnnotation` / `deleteAnnotation` →
    POST / PUT / DELETE (CSRF header). Keep an id map (CPDraw row ↔ Annotorious id).
- **`src/draw/PropertiesPanel.svelte`** — subscribes to `selectionChanged`;
  renders for the selected annotation: `name`, `feature_role` toggle (defaulted
  from geometry), `placetype` picker (the project vocab, `source_label` with the
  AAT term as a hint), `certainty`, `when`. On change → PUT the row (and, where
  it affects rendering, `anno.updateAnnotation`).
- **`main.ts`** — mount `Viewer` + `PropertiesPanel` into the two-column layout.
- Tool buttons: CPDraw buttons calling `anno.setDrawingTool('polygon' | 'path')`
  (skip Annotorious's own toolbar for now).
- `pnpm check` stays clean.

---

## 5. Page & flow

`draw.html` body becomes two columns: the OSD viewer (left, most of the width)
and a properties panel (right, collapsible). A small tool row: **Region**
(polygon) / **Label or boundary** (path).

```
open /draw/<image_id>/
  → load existing annotations, render on the image
  → pick a tool, draw a polygon → it's selected
  → panel: name = "", role = region (default), type = (project vocab), …
  → fill in → PUT; WorkState -> in_progress; header + list badges update
  → draw a polyline → role toggle: label | boundary
  → reload the page → everything persists, in pixel coordinates
```

A "manage types" link on the project page → the `ProjectPlacetype` list + add
form.

---

## 6. Sequencing

1. `load_aat_feature_types` command + committed TSV → master `Placetype`.
2. `Annotation` model + `ProjectPlacetype.aattype` nullable + migration.
3. `AnnotationViewSet` + serializer + tests (CRUD, `?image` scoping, `created_by`,
   WorkState advance).
4. Project-types page + `/api/placetypes/search/`; project-create seeds the
   starter vocab.
5. Frontend: Annotorious + plugin-tools in `Viewer.svelte`; `annotationStore.ts`;
   round-trip a single polygon (draw → POST → reload → GET → re-render).
6. `PropertiesPanel.svelte`: selection binding; name / role / type / certainty /
   when.
7. Verify on the Galicia recto (`/draw/1/`): trace the border as a polygon and a
   label as a polyline, name + type each, reload → both persist; `WorkState`
   reads "in progress".

---

## 7. Deliverable (§10 outcome)

login → open the Galicia recto → trace the border and a label, name + type each
from the project's vocabulary → reload → both persist in image-space pixel
coordinates. The project's type list is editable and each entry carries an
optional AAT mapping. `WorkState` shows "in progress".

---

## 8. Open questions carried forward

- **Point capture** — Phase 1, as a CPDraw-owned OpenSeadragon overlay layer
  (§9.1), not an Annotorious tool.
- **Per-image type scoping** (`MapPlacetype` equivalent) — deferred.
- **GeoNames `fclass`** as an alternative to AAT on `ProjectPlacetype` — later.
- **W3C Web Annotation export** to external annotation tools (beyond storing the
  `w3c` blob) — not needed for Phase 0.
- **Annotorious v3 editor/lifecycle depth** in a Svelte host — resolve in the
  step-5 spike; fall back to a fully CPDraw-side panel if v3's hooks are awkward.
- **Annotorious v4 rewrite** (DeckGL renderer, OpenLayers connector) — a watch
  item; do not build deep dependencies on v3 internals beyond the public
  `registerDrawingTool` / event API.
