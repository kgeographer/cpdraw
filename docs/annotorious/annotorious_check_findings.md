# Annotorious v3 — point/polyline extensibility assessment

> **Partly superseded.** Two updates since this was written:
>
> - **2026-08-29:** found `@annotorious/plugin-tools`
>   (`github.com/annotorious/plugin-tools`, not linked from `annotorious.dev` at
>   the time). It ships a working **polyline** (`path`) tool for both the Image
>   and OpenSeadragon annotators, so section (b)'s "build two Svelte components,
>   a few days" for polyline no longer applies — CPDraw just depends on the
>   plugin (done in WO-0.4).
> - **2026-09-02:** the **point** question is settled — CPDraw builds its own
>   OpenSeadragon point overlay and does **not** pursue an Annotorious `Point`
>   primitive or PR `#443`. So both section (b) point options (Ellipse-as-point
>   *and* new-ShapeType) and section (c) are moot. Rainer's v3→v4 rewrite may add
>   a native point tool later. See `README.md` in this folder and
>   `rainer_20260903.txt`.
>
> The registry / lifecycle analysis below (Q1–Q4) still holds as a description of
> how v3 extensibility works.

---

Repo examined: `/Users/karlg/Documents/repos/annotorious` (v3 monorepo, tag/version
3.8.9 per `package.json`). All paths below are relative to that repo root.
Did not find a published plugin that already adds point/polyline tools —
checked `annotorious.dev`, the GitHub repo/discussions, and the CHANGELOG
(no hits for "polyline", "point tool", or "point shape").

## Q1 — Registry or hardcoded unions?

Registry, for the tool and editor and geometry-math layers — genuinely
runtime-extensible, not compile-time unions:

- **Drawing tools**: `packages/annotorious/src/annotation/tools/drawingToolsRegistry.ts:8-19`.
  A `Map<DrawingTool, {tool, opts}>` seeded with `rectangle` and `polygon`.
  `export const registerTool = (name, tool, opts) => REGISTERED.set(...)`.
  Critically, the key type is `export type DrawingTool = 'rectangle' | 'polygon' | string;`
  (line 6) — the union includes a bare `string`, so a new tool name is not
  fighting the type system.
- **Editors**: `packages/annotorious/src/annotation/editors/editorsRegistry.ts:6-14`.
  Same pattern: `Map<ShapeType, SvelteComponent>`, `registerEditor(shapeType, editor)`.
  Seeded with RECTANGLE, POLYGON, MULTIPOLYGON.
- **Shape math** (area/hit-testing): `packages/annotorious/src/model/core/shapeUtils.ts:9-19`.
  `const Utils: {[key:string]: ShapeUtil<any>} = {}`, `registerShapeUtil(type: ShapeType | string, util)`.
  Note the key type explicitly allows `string`, not just `ShapeType`.

Both `registerTool` and `registerEditor` are re-exported as **public,
documented-shape instance methods** on the annotator itself, not internal
plumbing a plugin has to reach into:
- `registerDrawingTool` — `packages/annotorious/src/Annotorious.ts` (interface
  at the `registerDrawingTool(name, tool, opts?)` declaration; implementation
  `const registerDrawingTool = (name, tool, opts) => registerTool(name, tool, opts)`).
- `registerShapeEditor` — same file, `registerShapeEditor(shapeType, editor)` /
  `const registerShapeEditor = (shapeType, editor) => registerEditor(shapeType, editor)`
  (`Annotorious.ts:34,146-147,194`).

**The one non-registry, closed location** is SVG (W3C Web Annotation)
serialization: `packages/annotorious/src/model/w3c/svg/SVGSelector.ts`.
`parseSVGSelector` (string-sniffing `if/else` chain, ~line 210) and
`serializeSVGSelector` (`switch (shape.type)`, ~line 246) are hardcoded
per-type dispatch with no registration hook. This is the one file a
genuinely novel shape type would need to touch (see Q3).

## Q2 — Polygon traced through its full lifecycle

| Layer | File(s) | Pluggable? |
|---|---|---|
| Drawing tool / interaction | `annotation/tools/polygon/RubberbandPolygon.svelte` | Yes — registered via `registerTool('polygon', RubberbandPolygon)`, `drawingToolsRegistry.ts:16` |
| Geometry model | `model/core/polygon/Polygon.ts` (interface only) | N/A (just a TS type; any shape can define its own) |
| Hit testing / area | `model/core/polygon/polygonUtils.ts` (registers via `registerShapeUtil(ShapeType.POLYGON, ...)`, same pattern as `polylineUtils.ts:150` below) | Yes |
| Editing/handle layer | `annotation/editors/polygon/PolygonEditor.svelte` (329 lines: drag vertex, add midpoint via shared `MidpointHandle` component, delete vertex) | Yes — registered via `registerEditor(ShapeType.POLYGON, PolygonEditor)`, `editorsRegistry.ts:10` |
| SVG rendering (idle, non-selected annotation) | `annotation/shapes/Polygon.svelte`, dispatched from `annotation/SVGAnnotationLayer.svelte:8` | **Closed-ish** — `SVGAnnotationLayer.svelte` imports each shape component by name; a new shape type needs a line added here (small, but not a runtime registry) |
| SVG rendering (selected-state overlay, OSD package) | `annotorious-openseadragon/src/annotation/svg/selection/shapes/SelectedPolygon.svelte`, dispatched from `SVGSelectionLayer.svelte` via `if/else if` on `a.target.selector.type` | **Closed** — same pattern, hardcoded per-type branch, `SVGSelectionLayer.svelte:~65-80` |
| Serialization to/from W3C `SvgSelector` | `model/w3c/svg/SVGSelector.ts`, `parseSVGPolygon`/`serializeSVGSelector`'s `POLYGON` case | **Closed** — see Q1 |

So: tool and editor are cleanly pluggable via public registries. Three
locations are closed hardcoded dispatch (`SVGAnnotationLayer.svelte`, OSD's
`SVGSelectionLayer.svelte`, and `SVGSelector.ts`) — but as Q3 shows, for
**polyline specifically all three already have a case**, so this closed-ness
doesn't block the point/polyline work; it would only matter for a shape
type with no existing branch anywhere.

## Q3 — Does polyline already fit the geometry/selector model?

**Yes, essentially completely — polyline is fully modeled, hit-tested, and
serialized already; only the drawing tool and editor are missing.**

- **Geometry model** exists: `model/core/polyline/Polyline.ts`. Not a flat
  point list — `PolylinePoint` supports `type: 'CORNER'|'CURVE'` with
  optional bezier `inHandle`/`outHandle`, and `PolylineGeometry.closed?: boolean`.
  This is a superset of what a straight-segment linestring needs.
- **Hit-testing/area** exists and self-registers:
  `model/core/polyline/polylineUtils.ts:150` — `registerShapeUtil(ShapeType.POLYLINE, PolylineUtil)`.
  `intersects()` (lines 15-24) explicitly branches on `geom.closed`: if open,
  it does buffered distance-to-path-segment testing (`isPointNearPath`,
  line ~92) rather than point-in-polygon. `area()` returns `0` when `!geom.closed`
  (lines 8-10). **This is exactly the "open path, no fill, no interior" model
  the label-linestring case needs** — it was evidently designed with the
  open case as a first-class citizen, not a bolt-on.
- **SVG serialization already round-trips**, specifically without forcing
  closure:
  - Serialize: `SVGSelector.ts:296-298`, `ShapeType.POLYLINE` case calls
    `computeSVGPath` (`polylineUtils.ts:~127-160`), which only appends the
    `Z` close command `if (geom.closed)` (line ~154). An open polyline
    serializes as a plain open `<path d="M ... L ...">`, correctly.
  - Parse: `SVGSelector.ts:~95-113` (`parseSVGPathToPolyline`) →
    `pathParser.ts`'s `svgPathToPolyline`, which sets `closed = true` only
    on an explicit `Z` command (line ~245) and otherwise leaves it `false`.
  - The dispatch heuristic in `parseSVGSelector` (`SVGSelector.ts:~215`)
    that decides "polyline vs. polygon" for an incoming `<path>` is:
    `includes(' C ') || includes(' A ') || !includes('Z')` → polyline;
    else → polygon. An open straight-line path (no curves, no `Z`) correctly
    falls into the polyline branch via the `!includes('Z')` clause.
- **Idle rendering** already wired: `SVGAnnotationLayer.svelte:8` imports
  `Polyline` from `./shapes` alongside the other shape components — so an
  existing `Polyline` annotation already renders correctly today, even
  though nothing can draw one interactively yet.
- **OSD selected-state rendering already wired too**:
  `annotorious-openseadragon/src/annotation/svg/selection/shapes/SelectedPolyline.svelte`
  exists and is dispatched from `SVGSelectionLayer.svelte` via an explicit
  `ShapeType.POLYLINE` branch (confirmed by reading the file directly).

Net: of the six lifecycle stages in Q2, only **drawing tool** and **editor**
have no polyline entry anywhere in the codebase. Everything else — model,
math, both serialization directions, and both rendering layers (base +
OSD) — is done.

## Q4 — OpenSeadragon connector: delegate or duplicate?

**Delegates.** `annotorious-openseadragon`'s `Annotorious.ts` does not keep
its own tool/editor registry; `registerDrawingTool` and `registerShapeEditor`
on the OSD-wrapped instance are thin pass-throughs to the same
`registerTool`/`registerEditor` functions imported from `@annotorious/annotorious`
(confirmed via `grep` on `packages/annotorious-openseadragon/src/Annotorious.ts`:
`import { getTool, listDrawingTools, registerTool, ... } from '@annotorious/annotorious'`,
then `registerDrawingTool = (name, tool, opts) => registerTool(name, tool, opts)`).
`package.json` for `annotorious-openseadragon` lists `@annotorious/annotorious`
as a direct dependency, not a duplicated fork of its model/registry code.

The one place OSD carries its **own** per-shape-type code is the
selected-annotation highlight overlay (`SVGSelectionLayer.svelte`, hardcoded
`if/else if` on `ShapeType`, same closed-dispatch pattern noted in Q2/Q3) —
but as shown in Q3, polyline already has an entry there
(`SelectedPolyline.svelte`), so this doesn't add work for the polyline case.

Conclusion: registering a new drawing tool or editor once, at the top level
via `anno.registerDrawingTool(...)` / `anno.registerShapeEditor(...)`, makes
it available in the OSD-wrapped annotator with no OSD-specific code needed
for polyline. (This would not hold for a brand-new shape type absent from
`SVGSelectionLayer.svelte`'s branch list — see the point discussion below.)

---

## Deliverable

### (a) Verdict

**Plugin-feasible for polyline. Point is a smaller, still-plugin-feasible
question, but with one caveat below.** Neither requires a fork or invasive
changes to the library.

### (b) Plugin interface and effort estimate

**Polyline** — build two Svelte components and register them; no upstream
changes needed at all.

1. A drawing-tool component, contract taken directly from the existing
   `RubberbandPolygon.svelte` (`annotation/tools/polygon/RubberbandPolygon.svelte`,
   229 lines):
   - Props: `addEventListener(type, fn, capture?)`, `drawingMode: DrawingMode`
     (`'click'|'drag'`), `transform: Transform` (`.elementToImage(x,y)` converts
     pointer coords to image space), `viewportScale: number`.
   - Owns all interaction state internally (points array, live cursor,
     optional close-distance snapping) and renders its own live preview SVG.
   - On completion, dispatches a Svelte `create` event carrying the finished
     `Shape` — for polyline, a `{type: ShapeType.POLYLINE, geometry: {points: PolylinePoint[], closed: false, bounds}}`.
   - This is materially *simpler* than the polygon version: drop the
     closing/snap-to-first-point logic (unless an optional closed-loop mode
     is wanted) and construct `PolylinePoint[]` (`{type:'CORNER', point:[x,y]}`)
     instead of a flat coordinate array.
   - Register: `anno.registerDrawingTool('polyline', PolylineTool)`.
2. An editor component, contract taken from `PolygonEditor.svelte`
   (`annotation/editors/polygon/PolygonEditor.svelte`, 329 lines): props
   `shape`, `computedStyle`, `transform`, `viewportScale`, `svgEl`; dispatches
   a `change` event with the updated shape on every drag/add/delete. Vertex
   drag and midpoint-insertion logic can reuse the already-exported,
   shape-agnostic `MidpointHandle`/`Handle` components (`annotation/editors/index.ts`)
   rather than reimplementing hit math. The main difference from the polygon
   editor is not treating the first/last vertex as connected.
   - Register: `anno.registerShapeEditor(ShapeType.POLYLINE, PolylineEditor)`.

Effort estimate: on the order of adapting two existing, well-scoped files
(~230 and ~330 lines respectively) rather than designing from nothing — a
few days of focused work including testing the curved/bezier `PolylinePoint`
paths interact correctly with a straight-segment-only editor, not weeks.
No PR to the maintainer is required; this ships as CPDraw's own plugin code
using the public `registerDrawingTool`/`registerShapeEditor` API.

**Point** — smaller in interaction complexity, but has no existing model
in the codebase at all (unlike polyline). Two paths, in order of
preference:

- **Reuse an existing, fully end-to-end shape as the point primitive.**
  `Ellipse` is completely done (model, hit-testing, both serialization
  directions, both rendering layers — same shape as the RECTANGLE/POLYGON
  rows in Q2's table, just not spelled out at length above since it wasn't
  asked about). A "point" tool that places a fixed-small-radius `Ellipse`
  on click needs only a trivial drawing tool (single pointer-down handler,
  no editor needed beyond drag-to-reposition, which `SelectedEllipse`-style
  handling may already cover) and **zero changes to `SVGSelector.ts`**,
  because ELLIPSE already has a case there. This is the path I'd recommend.
- **A genuine new `ShapeType.POINT`.** Cleaner semantically, but this is
  the one case that lands on the closed dispatch surfaces from Q1/Q2:
  `SVGSelector.ts`'s parse/serialize switch, `SVGAnnotationLayer.svelte`'s
  shape-component imports, and OSD's `SVGSelectionLayer.svelte` would each
  need a new branch. None of these are large (each existing case is
  ~10-20 lines, following an established pattern like the `LINE` case
  added alongside `POLYLINE`), but they're edits to vendored package
  source, not consumer-side registrations — see (c).

### (c) If upstream changes are needed (point-as-new-ShapeType path only)

Only relevant if you reject the Ellipse-as-point approach above. Three
files, all following a pattern already used for `LINE`/`POLYLINE` (i.e. not
a novel design, closely mirrorable):

1. `packages/annotorious/src/model/w3c/svg/SVGSelector.ts` — add a
   `parseSVGPoint`-style branch to `parseSVGSelector`'s dispatch chain
   (e.g. sniff `<circle r="0">` or a dedicated tiny convention) and a
   `ShapeType.POINT` case to `serializeSVGSelector`'s switch. Smallest,
   most mechanical of the three.
2. `packages/annotorious/src/annotation/SVGAnnotationLayer.svelte` — add
   `Point` to the shape-component import list and its dispatch (need to
   read the render-dispatch portion of this file, not yet inspected in
   detail — flagged as unknown below).
3. `packages/annotorious-openseadragon/src/annotation/svg/selection/SVGSelectionLayer.svelte`
   — add a `ShapeType.POINT` branch and a `SelectedPoint.svelte` component,
   mirroring `SelectedLine.svelte`.

Shape of a PR: small, additive, no changes to existing shape types' code
paths — low risk of upstream rejection on architectural grounds, though I
have no visibility into Rainer Simon's actual appetite for a new core shape
type vs. steering contributors toward the Ellipse-as-point workaround.

### (d) Unknowns — not determined from source

- **`SVGAnnotationLayer.svelte`'s exact per-shape dispatch mechanism**
  (how it picks which of the six imported shape components to render for
  a given annotation) — confirmed the import list (line 8) but did not
  read the template/dispatch logic in that file. Doesn't change the verdict
  for polyline (it's already imported, so *something* there handles it),
  but I can't cite the exact line for how a new `POINT` type would be added
  there.
- **Whether `SelectedEllipse.svelte`'s drag/reposition behavior is generic
  enough to double as a "move this point" interaction**, or whether it
  assumes a resizable radius UI that would need suppressing for a
  fixed-size point use. Not read.
- **Runtime behavior, as opposed to source-level wiring** — none of this
  was exercised in a browser. The claim that polyline "just works" once a
  tool+editor are registered is strong static evidence (self-registration
  at module load, consistent typing throughout, both serialization
  directions implemented and apparently tested against each other via the
  round-trip design) but not confirmed by running code, per the
  do-not-write-code constraint on this task.
- **Whether the maintainer has unpublished/in-progress work on point or
  polyline tools** — the CHANGELOG and public repo showed nothing, but a
  private branch or roadmap discussion wouldn't be visible from a clone of
  `main`.
