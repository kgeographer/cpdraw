# WO-0.3 — Draw page: OpenSeadragon renders a MapImage

**Status:** working spec, for review. Decomposes scoping-doc §10 Phase 0 "WO-0.3 —
Draw tab: OpenSeadragon renders the target map unrectified". Section references (§)
are to `docs/CPDraw — scoping document.md`.

**Scope:** get one `MapImage` onto the screen in a pannable/zoomable OpenSeadragon
viewer, fed by its IIIF Image service. **Not** in scope: annotation tools (WO-0.4),
the polished Project → Source → MapImage picker (WO-0.5), anything geo.

---

## 1. Open decisions

1. **How is the MapImage chosen?** Minimal: a route `/draw/<int:image_id>/` → a
   `DrawView` that looks up the `MapImage` and hands its tile source to the page.
   Navigation *to* that route: add a per-`MapImage` link on the project page (the
   Sources list already there), and the admin change page. The three-level
   picker UI is WO-0.5.
2. **Tile source to OpenSeadragon.** OSD's `tileSources` accepts a IIIF
   `info.json` URL. Pass `"<MapImage.image_service_uri>/info.json"` and let OSD
   fetch it. Polona sends `access-control-allow-origin: *` (checked in WO-0.2), so
   no proxy. `MapImage.info_json` is only populated for bare-image-service
   ingests today; relying on the live fetch keeps this WO simple. (Optional
   follow-up: cache `info_json` onto the row on first render.)
3. **How the URL reaches the JS.** A `data-` attribute on the mount element
   (`<div id="cpdraw-draw-root" data-iiif="…/info.json">`), read by `main.ts`. No
   inline script.
4. **Viewer component shape.** A `Viewer.svelte` that takes a `tileSource` prop and
   news up OpenSeadragon in `onMount` (teardown in `onDestroy`). Imperative OSD,
   Svelte shell — this is the seam WO-0.4 mounts Annotorious onto (same viewer
   instance).

---

## 2. The flow

```
login → dashboard → project → (Sources list) → a MapImage link
      → /draw/<image_id>/
          DrawView: MapImage.objects.get(pk=image_id)
          → renders draw.html with data-iiif="<image_service_uri>/info.json"
          → {% vite_asset 'src/draw/main.ts' %} loads the bundle
          → main.ts reads data-iiif, mounts <Viewer tileSource=…/>
          → OpenSeadragon streams tiles from the IIIF service; pan / zoom
```

Phase 0 target: `Source #1` (Polona *Galicyja i Lodomeryja*), `MapImage` seq 0
(recto), `https://polona.pl/iiif/3/cf2d49d7-1d3a-448d-abb2-190d6bd01af8`,
15919 × 12357. The verso (seq 1) is ignorable (§10).

---

## 3. Page content & flow

Terminology: a **Source** is the manifest — bibliographic metadata, the "add
source" action, and (for now) its Django-admin change page. A **MapImage** is
one canvas within it — the thing you *open* in the viewer; `WorkState.status` is
per-MapImage. "Map" colloquially = a MapImage.

Two entry points to the viewer, both landing on `/draw/<image_id>/`:

### Dashboard — a "Maps" section below Projects

A flat table of every MapImage across the user's projects — the "grab the next
one" path, and the demo-friendly view for Braga.

| Project | Source | Image | Size | Status | Actions |
|---|---|---|---|---|---|
| galicia | Galicyja i Lodomeryja | [1r] | 15919×12357 | ● unstarted | **Open** · Metadata |

- **Open** → `/draw/<image_id>/`.
- **Metadata** → the Source's admin change page (a read-only Source detail page
  is a later WO / WO-0.5).
- **Status** → `WorkState.status` badge (unstarted / in-progress / complete).
  **Inert until WO-0.4** — nothing advances it yet.
- "Image" column shows the canvas label, or "—" when the Source has a single
  image. Ordering: in-progress, then unstarted, then complete (fall back to
  project → source → seq).

### Project page — MapImages under each Source

The Sources list (already there) gains, under each Source, its MapImage(s):
canvas label · size · status badge · **Open** → `/draw/<id>/`. This is the
canonical drill-down; keeps the Source → MapImage hierarchy visible.

### Draw page header

A strip above the viewer: Source label · image label · "← back to project" · a
status control (set in-progress / complete) whose value the two lists above
reflect. The status control is wired but does nothing useful until WO-0.4.

### Straddles

The dashboard section and the project-page list are content, not viewer wiring —
they overlap WO-0.5 territory. Speccing them here because they're small and the
viewer is unreachable without at least one of them; both ship in WO-0.3.

---

## 4. Frontend (`frontend/`)

- **Dependency:** `openseadragon` (5.x — satisfies `@annotorious/openseadragon`'s
  peer range for WO-0.4), `@types/openseadragon` dev. Pin exact.
- **`src/draw/main.ts`** — replaces the WO-0.1 smoke body: read `#cpdraw-draw-root`
  `data-iiif`, mount `Viewer.svelte` with it. Drop the `@allmaps/transform`
  import and `SmokeProbe.svelte` (Allmaps returns in Phase 1).
- **`src/draw/Viewer.svelte`** — prop `tileSource: string`; `onMount` →
  `OpenSeadragon({ element, tileSources: tileSource, showNavigator: true,
  crossOriginPolicy: 'Anonymous', … })`; `onDestroy` → `viewer.destroy()`.
  Expose the `viewer` instance (component export / event) so WO-0.4 can attach
  Annotorious.
- HMR: editing `Viewer.svelte` should re-init cleanly (destroy + recreate).

## 5. Backend

- **`main/views.py`** — `DrawView(LoginRequiredMixin, DetailView)` (or a function
  view) on `MapImage`; context: `iiif_info_url = f"{image.image_service_uri}/info.json"`,
  the image, its source, dims. Per-project permission checks deferred to WO-0.5 —
  `login_required` only for now.
- **`main/urls.py`** — `path('<int:image_id>/', views.DrawView.as_view(), name='draw-image')`.
  Keep the bare `draw` name pointing at a landing/placeholder (or redirect to the
  dashboard) so `base.html`'s navbar link still resolves.
- **`main/templates/main/draw.html`** — extends `base.html`; an `extra_head` block
  with `{% load django_vite %}{% vite_hmr_client %}{% vite_asset 'src/draw/main.ts' %}`;
  body is the mount div with `data-iiif`, in a large container
  (`height: calc(100vh - <navbar>)` or a fixed `78vh`), plus a small caption
  (source label · image label · dims).
- **`project_update.html`** — under each Source, list its `MapImage`s as links to
  `/draw/<id>/`.

## 6. Remove (WO-0.1 scaffolding)

`/draw/_wo01/` route (`wo01-pipeline-check`), `main/templates/main/wo01_pipeline_check.html`,
`src/draw/SmokeProbe.svelte`. CLAUDE.md's WO-0.1 section already flags these for
removal here.

## 7. Sequencing

1. `pnpm --dir frontend add openseadragon` (+ `-D @types/openseadragon`).
2. `Viewer.svelte` + rewrite `main.ts`; delete `SmokeProbe.svelte`.
3. `DrawView` + `/draw/<int:image_id>/` route; `draw.html` real content + header strip.
4. Dashboard "Maps" section; MapImage list under each Source on the project page (§3).
5. Delete the `_wo01` scaffolding.
6. Verify dev (Vite dev server) **and** built (`pnpm build` + `DEBUG=False`) modes.

## 8. Deliverable

login → project **galicia** → open `MapImage` seq 0 → the unrectified Galicia scan
renders in OpenSeadragon; smooth pan/zoom; tiles stream from `polona.pl`; the
navigator thumbnail shows. Works in both dev and built modes. No annotation tools
yet.

## 9. Open questions carried forward

- Multi-canvas navigation (prev/next within a Source) — a later nicety; the
  per-image route + project-page links suffice for Phase 0.
- ~~Caching `info_json` onto the `MapImage`~~ — done: ingest now fetches each
  canvas's `info.json` best-effort and stores it, alongside a quality advisory
  (`main/iiif/quality.py` → `MapImage.quality_notes`, surfaced with a ⚠ in the
  Maps list / project page and an alert in the Draw header).
- Per-project view permissions — WO-0.5.
