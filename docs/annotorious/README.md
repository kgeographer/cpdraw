# Annotorious integration — notes, decisions, correspondence

CPDraw's annotation layer is **Annotorious v3** (`@annotorious/openseadragon` +
`@annotorious/plugin-tools`), adopted, not a build-vs-buy question. Karl knows
Rainer Simon (author/maintainer) personally, so gaps are a conversation, not a
thing to work around alone. This folder is the single home for what's been
decided and why; the scoping doc and the WO specs point here rather than each
carrying a drifting copy.

## Current state of the decisions

- **Polygon + rectangle** ship in the base package. **Polyline** (`path` tool,
  `ShapeType.POLYLINE`, open `<path>` with no `Z`, round-trips through the W3C
  `SvgSelector`) ships in **`@annotorious/plugin-tools`** and works through the
  OpenSeadragon connector via `mountPlugin(anno)` — no CPDraw code, no fork.
  This covers every Phase 0 geometry, the label linestring included. **In use
  since WO-0.4.**
- **Point: CPDraw builds its own.** Annotorious has no point tool on any
  release, and a real one needs a `Point` primitive + non-scaling overlay in the
  core first (PR `annotorious/annotorious#443` did this but was only ever on a
  since-deleted feature branch). **Decision (2026-09-02, `rainer_20260903.txt`):
  CPDraw wires a separate point maker as a CPDraw-owned OpenSeadragon overlay
  and does *not* attempt an Annotorious `Point` primitive or pursue #443.** The
  eventual Annotorious rewrite (below) is the real fix if it ever matters.
  Point capture is Phase 1 (the georeferencing substrate), off the Phase 0 path.
- **Build tooling** must be Svelte-capable (Annotorious v3 is internally Svelte;
  the plugin is Svelte-authored) — Vite + `@sveltejs/vite-plugin-svelte`,
  settled in WO-0.1.
- **Watch item — the v3 → v4 rewrite.** Rainer is rewriting Annotorious
  (with Claude): DeckGL rendering engine (~100k annotations in one view), an
  **OpenLayers connector** alongside OpenSeadragon, and possibly easier work
  with non-IIIF georeferenced material. IIIF stays his main focus for now. Don't
  build deep dependencies on v3 internals beyond the public
  `registerDrawingTool` / `registerShapeEditor` / event API.

## Things to try (raised by Rainer, not yet evaluated)

- **`@annotorious/plugin-magnetic-outline`** — OpenCV.js "smart scissors" /
  magnetic contour tracing, works through the OSD connector. Classical CV, not
  ML; degrades to hand-tracing cleanly. Rainer thinks CPDraw's map scans suit it.
  A concrete **Path A** mechanism for `guided-extraction.md`, and a possible
  Phase 1 feature (magnetic boundary tracing for annotators) rather than only a
  Phase 3 eval baseline. Demo: <https://liiive.now> — paste a IIIF URL, pick the
  scissors tool (toolbar: select · rect · polygon · ellipse · **scissors** ·
  scissors-dashed · trash · undo/redo), click a start point, move the mouse once
  the spinner stops. Repo: <https://github.com/annotorious/plugin-magnetic-outline>
- **VLM bounding boxes** — Rainer got accurate bboxes for map place-names and
  symbols from Qwen 3.8 (~Aug 2026); polygons untested. Supports the Phase 3
  machine-assist premise and the "place a few guide points, 'find the border'"
  idea in `guided-extraction.md`.

## Contents

| File | What |
|---|---|
| `annotorious_check.md` | The original assessment brief (2026-08-29): can point + polyline be plugins or is a fork needed? |
| `annotorious_check_findings.md` | The answer — registry/lifecycle dig, `file:line` evidence. Partly superseded (found `plugin-tools`; point decision has since firmed — see above). |
| `rainer_20260903.txt` | Correspondence with Rainer, Aug 31 – Sep 3 2026: the rewrite, `plugin-tools`, magnetic-outline, VLM bboxes, and Karl's "own point maker" decision. |

New correspondence: add as `rainer_YYYYMMDD.txt` (or `.md`) and list it here.
