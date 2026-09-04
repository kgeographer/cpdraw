# CPDraw — scoping document

**Status:** draft for review. To be decomposed into work orders for Claude Code.
**Predecessor:** `linkedplaces.draw` (Django 5.2 / GeoDjango / PostGIS / Leaflet), live at draw.computingplace.org
**Revision:** 2 — 29 August 2026

---

## 1. Purpose and scope

CPDraw is a multi-user web application for extracting spatial-temporal data from digitized
historical maps and maps of history, and publishing it as Linked Places Format (LPF) for
gazetteer ingestion.

Nothing else currently occupies this space. Batch extraction pipelines (MapReader, mapKurator)
have no human in the loop. Allmaps georeferences but does not digitize map content. Recogito
and its descendants annotate but are not map-native in this sense. QGIS does all of it and is
a desktop GIS. The gap CPDraw fills is human-in-the-loop, project-scoped, multi-user,
IIIF-native digitization producing gazetteer-ready output — and the unglamorous half of that
(users, projects, maps, roles, state) is why Django is the right substrate and why the
predecessor was built on it.

Three departures from the predecessor:

1. **Source imagery is IIIF**, fetched by manifest or image URI. No local rasters, no tile
   pyramids, no `gdal2tiles`. The application never holds an image.
2. **Annotation happens in image space**, on the unrectified source. Geography is derived
   later and is not required for the annotation work to proceed or to be durable.
3. **Georeferencing is a product of the annotation work**, not a prerequisite for it.
   Settlement points captured during annotation, reconciled against a gazetteer, yield the
   ground control points from which the transform is computed.

The third point is the load-bearing idea. It inverts the conventional pipeline
(georeference → then digitize) and means the labour of identifying places is not spent twice.

### Non-goals for v1

- Automated extraction (VLM/OCR). The architecture must not preclude it; v1 excludes it.
- Serving imagery. IIIF servers do that.
- Adjudicating between competing extents. CPDraw records attestations; it does not resolve them.

---

## 2. Coordinate spaces

Two spaces, kept explicitly distinct. Collapsing them is the characteristic design error in
this domain.

| Space | Units | Canonical? |
|---|---|---|
| **Image** | source pixels, origin top-left | **Yes** |
| **Geo** | lon/lat EPSG:4326, projected for display | No — derived |

**Rule:** image-space geometry is canonical and never overwritten. Geo geometry is a derived
cache carrying a reference to the transform version that produced it. When control points
improve, derived geometry is regenerated. This is the property the predecessor lacked, and the
reason its tile pyramids were unrecoverable when the original scans were lost.

---

## 3. Domain model (draft)

```
User
Project                  spatial scope, placetype vocabulary
  └── ProjectUser        role: creator | owner | member
  └── Source             one IIIF Manifest (or a bare Image service)
        └── MapImage     one IIIF Canvas/Image within the Source
              ├── Annotation     features drawn in image space
              ├── Georeference   control points + transform type, versioned
              └── WorkState      assignment, status, lock
```

**`Source` vs `MapImage`.** The predecessor's `Map` conflated these. A manifest may contain one
canvas or sixty — Kummersberg's *Administrativ-Karte* is 60 sheets. Annotations attach to a
`MapImage`; bibliographic metadata and temporal scope attach to `Source` and are inherited,
with per-image override.

**Metadata.** Populate `Source` from the manifest on fetch (label, attribution, rights,
`metadata` array, `navDate`). CPDraw fields sit alongside and never overwrite. **Retain the raw
manifest as fetched**, unmodified, alongside whatever normalization was applied (§6a).

**Spatial scope.** Held at `Project`, overridable at `Source`. ISO 3166-1 alpha-2 country codes,
a bounding box, or a named study area. Stated by the user, optionally seeded from manifest
metadata. This is what constrains gazetteer lookup (§7a) — it is not derived.

**Temporal.** `Source.when` as a JSONB timespan, following the predecessor. Two derivations:
publication date for a map *from* history; author-asserted period for a map *of* history (the
Bregel case). Overridable at `MapImage` and at `Annotation`. Per-feature temporality **must be
retained even where downstream consumers cannot currently render it.** Flattening expressive
capacity at a format boundary for want of a consumer is a known recurring loss; do not repeat
it here on the assumption that WHG can't yet take it.

---

## 4. Annotations

An annotation is a geometry in image space plus properties. Geometry is one of point,
linestring, or polygon. What the geometry *means* is carried by the type vocabulary, not by a
class hierarchy.

### Properties

- `name` — as it appears on the map, transcribed verbatim
- `name_normalized` — optional editorial normalization, kept separate from the transcription
- `placetype` — Getty AAT URI, scoped per project (retain `Placetype` / `ProjectPlacetype` /
  `MapPlacetype` from the predecessor)
- `when` — optional override
- `certainty` — annotator's confidence in the reading, distinct from confidence in the
  georeferencing
- provenance — `created_by`, `created_at`, `modified_*`; per-feature, because LPF wants it

### Notes

Points serve double duty: features in their own right, and the substrate for georeferencing.
More is better, and the UI should say so.

A linestring typed as a label records a cartographer's assertion of extent by letterspacing,
where no boundary was drawn. It is directional, with a long axis and no width. Buffering to a
polygon is an export-time decision, not a capture-time one — retain the line.

---

## 5. Formats and mappings

CPDraw holds one internal representation and maps to and from external formats. No external
format is the storage format.

| Direction | Format | Purpose |
|---|---|---|
| in | IIIF Presentation API (v2, v3) and Image API | source manifests and images |
| in / out | W3C Web Annotation | feature annotations; interoperability with annotation tooling |
| **in / out** | **IIIF Georeference Annotation** | **control points; the working interface to the transform layer (§7b)** |
| out | GeoJSON | derived geometry, general consumption |
| out | LPF | the target; names, typing, temporality, provenance |

Mappings are code, tested, versioned. Where a target format cannot carry something the internal
representation holds, that is recorded as a known lossy mapping rather than silently dropped.

---

## 6. Ingest and workflow

### 6a. Manifest normalization

Real-world IIIF is inconsistent, and this is not an edge case to be handled later. The
Phase 0 target map demonstrates the problem: the Polona manifest for Miczyński's *Galicyja i
Lodomeryja* declares `"type": "manifest"` in lowercase, which is invalid Presentation 3 and
causes strict parsers (including `@allmaps/iiif-parser`) to reject the whole document. It also
carries `example.org` placeholder IDs on its annotation pages, duplicated across canvases, and
canvas identifiers pointing at `info.json` rather than canvas URIs.

Requirements:

- Tolerant parsing — case-insensitive `type` matching, and general leniency about properties
  CPDraw does not need.
- **Graceful degradation** — when manifest validation fails but the image service works,
  create the `MapImage` from `info.json` and let the user supply metadata by hand rather than
  refusing the map.
- Accept **either** a Manifest URI or an Image service / `info.json` URI at ingest.
- Retain the raw document and record what was normalized.

A small per-provider quirks layer is a legitimate architectural component. Maintaining patched
copies of broken manifests is not; it does not scale past a handful of maps.

### 6b. Workflow

1. User logs in, creates or joins a `Project`, sets spatial scope and placetype vocabulary.
2. User supplies a IIIF URI. CPDraw fetches, normalizes, parses, creates one `Source` and one
   `MapImage` per canvas, populates metadata.
3. User selects a `MapImage`. It renders unrectified in the Draw tab.
4. User annotates: geometry plus name plus type, in image space.
5. Annotations persist. **No geography at this stage.** The work is complete and valuable
   without it.
6. Repeat across images and sources. `WorkState` tracks assignment and completion.
7. **Process** (§7) — reconcile, georeference, derive.
8. **Map Viewer** — derived features over a basemap, optionally with the warped source beneath.

---

## 7. Process

Three sub-steps, each independently re-runnable, each reviewable before it writes.

### 7a. Reconciliation

Match transcribed names against a gazetteer — WHG first, given its historical name-variant
coverage; the interface should not assume a single source.

Lookup is constrained by project or source spatial scope (§3). The WHG API supports several
spatial constraints; use them. Candidate sets should be small enough for review.

Output: each point annotation gains zero or more scored candidates. **Human confirmation
required before a match becomes a control point.**

### 7b. Georeferencing

Confirmed matches become control points. CPDraw emits a **IIIF Georeference Annotation**, and
that annotation is the working interface between CPDraw and the transform layer — not merely
an interop nicety.

**Transform layer: Allmaps.** `@allmaps/transform` and `@allmaps/project`, invoked server-side
via `@allmaps/cli` (`allmaps transform coordinates | svg | geojson`), which accepts a
Georeference Annotation or a GCP file plus a transformation type. Django writes the annotation,
invokes the CLI, reads geometry back. No transform code to write, and the same packages are
available in the browser later for live preview during annotation.

Rationale is not only technical. Allmaps and Annotorious are the two actively developed
libraries in this space, both authored by long-standing collaborators (Bert Spaan, Rainer
Simon). Building CPDraw on them makes it a serious user of both, and makes gaps a conversation
rather than a fork.

Fitting notes:

- Types available: `helmert`, `polynomial1/2/3`, `projective`, `thinPlateSpline`, `linear`.
- **Default to a low-order polynomial, not `thinPlateSpline`.** TPS interpolates exactly
  through the control points, which snaps every settlement onto its modern coordinate and
  erases the displacement between where the cartographer put a place and where it is. That
  displacement is evidence about the map, not error to be removed.
- Surface **per-control-point residuals** in the UI. A high residual is either a bad match or
  genuine cartographic displacement; both warrant a human look.
- Flag control points whose removal substantially improves the fit. A single mistyped or
  mismatched settlement warps a transform badly and silently; the spatial constraint in 7a
  reduces but does not eliminate this.
- `@allmaps/transform` exposes distortion measures from the transformation's partial
  derivatives. Expose them eventually — distortion analysis of the source map as a research
  byproduct. Phase 2.
- Georeferences are **versioned**. Refitting does not destroy prior transforms.

### 7c. Derivation

Apply the transform to all image-space geometry via the CLI. Non-shape-preserving transforms
require midpoint densification along segments, or traced borders straighten; `@allmaps/transform`
handles this — do not reimplement it.

Outputs: GeoJSON, LPF, and the Georeference Annotation. Publication of the annotation to
Allmaps is a deliberate user action, not a default: data published there is CC0.

---

## 8. Technology

| Concern | Direction | Confidence |
|---|---|---|
| Backend | Django 5.2 + PostGIS, carried forward | High |
| IIIF parsing | `@allmaps/iiif-parser`, wrapped in the normalization layer (§6a) | High |
| Image-space viewer | OpenSeadragon | High |
| Annotation UI | Annotorious v3 + `plugin-tools` (polygon/line); CPDraw-owned OSD overlay for points | **Adopted; scope settled — §9 item 1, `docs/annotorious/`** |
| Transform | `@allmaps/transform` / `@allmaps/project` via `@allmaps/cli` | High |
| Annotation generation | `@allmaps/annotation` | High |
| Geo-space viewer | Leaflet or MapLibre; `@allmaps/leaflet` `WarpedMapLayer` **optional**, for QA overlay of the warped source beneath derived vectors. Not required, Phase 1+. | High |
| Storage | Postgres JSONB for annotations; PostGIS for derived geo | High |

**Frontend build tooling is mandatory.** The Allmaps packages are ESM-only; the predecessor's
script-tag and jQuery approach cannot consume them. Settle this in the first work order rather
than working around it with a CDN shim.

Licensing: Allmaps packages MIT, apps GPL-3.0, published data CC0.

---

## 9. Open questions

1. **Annotorious scope — resolved (2026-08-29).** Polygon and rectangle ship in the base
   package. **Polyline (open, straight or bezier) ships in `@annotorious/plugin-tools`** and
   works through the OpenSeadragon connector via `mountPlugin(anno)` — no CPDraw code, no
   fork; `mountPlugin` only calls the public `registerDrawingTool` / `registerShapeEditor`.
   The `path` tool is `ShapeType.POLYLINE`; it serialises as a W3C `SvgSelector` `<path>`
   (open, no `Z`) and round-trips. This covers every Phase 0 geometry, the label linestring
   included. The plugin's peer deps (`@annotorious/{annotorious,openseadragon}@^3.7.22`) and
   its Svelte 4 / Vite 5 build line both match what WO-0.1 pinned.
   **Point has no implementation on any release**, and a real one needs a `Point` primitive
   plus non-scaling-overlay rendering in the Annotorious core first (PR
   `annotorious/annotorious#443` did this but lives only on a since-deleted feature branch).
   **CPDraw builds its own point maker** as a CPDraw-owned OpenSeadragon overlay and does not
   pursue an Annotorious `Point` primitive or #443 (decided 2026-09-02, after Rainer confirmed
   a v3→v4 rewrite is coming that will carry point support eventually). Point capture is Phase 1
   (the georeferencing substrate), off the Phase 0 path. Full dig + correspondence:
   `docs/annotorious/` (`README.md` is the index).
2. **Fork or fresh.** The model changes touch nearly every table. A fresh Django project reusing
   the LPF export logic and the AAT placetype scoping may be cleaner than migrating.
3. **Node in the deployment.** The CLI means Node alongside Django. Subprocess invocation vs. a
   small persistent service — decide in Phase 1.
4. **Multi-sheet.** `@allmaps/cli attach` infers control points across sheet pairs at shared
   points. Defer, don't preclude.
5. **Write path to Allmaps.** Read API confirmed (`annotations.allmaps.org`); public write
   endpoint not confirmed. Self-hosted annotations with optional export.
6. **Region typing in LPF.** Whether evidence mode needs to surface as a typed assertion about
   the region, beyond per-annotation placetype, is an open research question and the subject of
   the Braga argument. Design so it can be added; don't guess now.
7. **Hosting.** Possible future home at Pitt/ISHI. Implications for auth, deployment, and data
   ownership unexamined.

---

## 10. Phasing

### Phase 0 — Braga demonstrator (target: 23 September 2026)

Minimum viable. No georeferencing at all.

- **WO-0.1** — Frontend build tooling; establish the ESM pipeline
- **WO-0.2** — `Source` / `MapImage` model; IIIF fetch with the normalization layer (§6a);
  accept Manifest or Image URI; populate metadata. The Polona manifest exercises the failure
  branch immediately, which makes it a better first test case than a clean one.
- **WO-0.3** — Draw tab: OpenSeadragon renders the target map unrectified
- **WO-0.4** — Annotorious + `@annotorious/plugin-tools` wired in; annotation capture
  (**linestring and polygon** — point is deferred, see §9.1) with name and type; persist
  image coordinates
- **WO-0.5** — Existing auth, project, and map-list views wired through

**Target map:** Miczyński, *Galicyja i Lodomeryja*, Rzeszów 1872, Biblioteka Narodowa via Polona.
Image service `https://polona.pl/iiif/3/cf2d49d7-1d3a-448d-abb2-190d6bd01af8` — 15919 × 12357,
ImageService3 level 2. Second canvas is a blank verso; ignore it. Verify `info.json` resolves
and that the image server sends CORS headers before building on it.

Outcome: login → project → Galicia map in the CPDraw interface → border and label extents
traced and saved.

### Phase 1 — Georeferencing loop

Reconciliation against WHG within project spatial scope, control-point confirmation UI,
Georeference Annotation emission, transform via Allmaps CLI, residuals, derived geometry,
LPF export.

**Point-tool track (parallel, unscheduled).** Point capture is the georeferencing substrate,
and Annotorious has no point tool on any release (§9 item 1). CPDraw builds its own — a
CPDraw-owned OpenSeadragon overlay layer for placing/editing points, alongside the Annotorious
layer that handles lines and polygons. Not an Annotorious `Point` primitive and not PR #443;
the v3→v4 rewrite may make a native point tool available later, at which point this can be
revisited. See `docs/annotorious/`.

### Phase 2 — Multi-user workflow, distortion analysis, warped-source QA overlay, Allmaps publication

### Phase 3 — Machine assistance

Model-proposed annotations for human review. The Draw tab becomes a review tool rather than a
tracing tool. The image-space-canonical architecture makes this a UI change rather than a
rewrite: a model proposing annotations in pixel coordinates proposes exactly what a human
annotator produces.

**Evaluation corpus.** The predecessor's manually digitized Bregel Atlas geometries are a
ready-made ground truth — `bregel_37` (45 polygons) and `bregel_39` (99 linestrings), with
rectified tiles live at `draw.computingplace.org/tiles/bregel/…`. The evaluation is
degrade-and-reconstruct, not "did the machine digitize the map?": hide the finished vector,
hand the method a deliberately degraded trace (N points; ±M px positional error), and measure
recovery against the original. The same degraded inputs go to every approach tried
(SAM2 / MapSAM / classical edge-following / VLM-guided / hybrid), so the comparison is
objective. Evaluation data first; training data only much later. This corpus can be assembled
and run independently of the CPDraw build, at any time — see `docs/GPT_20260828.txt` for the
framing (and the "Draw2" experimental track kept separate from the v1 app).
