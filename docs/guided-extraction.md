# Guided extraction — the semi-automated branch, and how to evaluate it

**Status:** exploratory notes, not a commitment. Records a design discussion
(2026-08-29). Sits alongside — not instead of — CPDraw's manual digitisation path,
and is independent of the Phase 0 build.

- Background thinking: `docs/GPT_20260828.txt`
- Working code: `notebooks/eval_01_degrade_reconstruct.ipynb`
- Phase 0 (the actual near-term plan): `docs/WO_0.2.md`, scoping doc §10

---

## Two development paths

**Path B — manual digitisation (Phase 0, the plan).** Annotorious tools over the
OpenSeadragon image; the operator places every vertex. More effort per boundary, no
ML, low risk. This is what WO-0.3 / WO-0.4 build.

**Path A — guided extraction (this doc, experimental).** The operator places a
handful of guidance points along a boundary; a "find boundary" action runs a
tracing/segmentation step that returns a full vector; the operator adds points and
re-runs, or edits the result by hand. Far more experimental — needs evaluation
before it's worth building.

Not exclusive: Path A degrades to Path B whenever the machine can't help.

---

## The goal, stated correctly

**Given a rough human trace of a boundary, how well can a machine recover the full
boundary the cartographer drew — and how little guidance does it need?** The point
count is "how much hinting the method needs," which feeds interface design.

This got conflated in discussion with a *digitisation rubric* — "how many points
should a human place by hand." That is a different, trivial, non-CV heuristic
("you've placed few points for a boundary this size — add more") and is **not** part
of this.

---

## The imagined workflow

1. Load a IIIF map in the viewer.
2. Pick a boundary. Click a handful of points along it — sparse where the printed
   line is crisp, clustered where it's weak (label crossings, damage, gaps). A
   skilled operator will drop points *inside* a gap to assert the path where there is
   no ink: `----o  o  o  o----`.
3. Hit **find boundary**.
4. The system crops the IIIF region around the points, derives prompts, runs the
   tracer, and overlays a vector + confidence + flagged-uncertain segments.
5. Operator accepts, adds points and re-runs, or edits by hand.

---

## What the cartography actually looks like

Old maps almost never fill regions — the interior is full of settlements, toponyms,
terrain hachures. Region extent is carried by **boundary lines**. (In the Bregel
screenshots the red fill is Leaflet rendering the digitised polygons, not the map.)
So this is a **line-following** problem, not area segmentation:

- **Filled / coloured territory** (rare): area segmentation — SAM2 / MapSAM with
  point / box / mask prompts. The GPT doc's "easy case."
- **Thin boundary line** (the normal case): follow a curvilinear feature. Buffer the
  rough trace ±~100 px; within that corridor compute a per-pixel "is-border"
  probability; find the max-probability continuous path through it (edge / ridge
  detection, colour-distance, skeletonisation, graph shortest-path). Classical CV;
  the GPT doc's bet is this can beat a large neural model, because it collapses "find
  the frontier somewhere on this map" into "find the best line in this 200-px ribbon."

The boundary line is interrupted — vanishes under labels, runs along a river for a
stretch, changes appearance where two washes meet. In a gap there is no image
signal, so the operator's points are the only constraint and the tracer must trust
them there.

---

## Architecture (from the GPT doc)

A small service behind the app, not an LLM "skill":

```
POST /refine-geometry
  { iiif_manifest, rough_geometry, feature_type, geometry_type, label }
→ { geometry, confidence, uncertain_segments }
```

The service may call a VLM to characterise the boundary's visual class ("solid
reddish ~3 px line; ignore black hydrography and dashed administrative lines") and
runs local CV / segmentation. The app stays model-agnostic. Full chain:

```
rough geometry → spatial constraint → visual-class ID (VLM)
  → segmentation / tracing → topology / vectorisation → human correction
```

Use IIIF region requests, not the whole scan: a coarse pass (~1500 px) to read the
feature, then native-resolution strips along the predicted line. Return confident
stretches plus a few flagged-uncertain segments so the operator adjudicates rather
than traces.

---

## Libraries named in the source

- **Segmentation:** SAM2; MapSAM (public code, ~10 examples to adapt); MapSAM2;
  SMOL-MapSeg (legend-oriented prompting); SAM-REF (refine after prompting without
  recomputing the whole-image embedding).
- **Vectorisation with topology:** Xia et al. 2024, "Vectorizing historical maps
  with topological consistency" (ordered primitives → closed, non-intersecting
  polygons).
- **CV plumbing:** GDAL / rasterio, OpenCV, scikit-image, Shapely; scipy / networkx
  for corridor path-finding.
- **Frameworks / precedent:** MapReader; mapKurator.
- **Adjacent:** Allmaps (georeferencing — consume, don't build); Annotorious
  (image-space annotation).

(Checked real in the 2026-08-28 session log; SMOL-MapSeg is Aug 2025.)

---

## Evaluation

A corpus item is a raster + hand-digitised geometry pair. Hide the finished vector,
hand the method a degraded version, measure recovery.

### Corpus

The lpdraw Bregel traces: **`bregel_37`** (45 polygons over drawn tribal-territory
borders), **`bregel_39`** (99 linestrings). Snapshots committed at
`notebooks/data/`.

The GPT doc's "Bregel is a poor example, use Seshat / Cleopatra instead" aside is
**void** — it followed from a misstatement in that conversation (that the Bregel
Atlas draws no boundaries) that was never corrected. `bregel_37` traces real drawn
borders. Expect the source linework to vary crisp → faint across the 45. Pairing for
a first pass: rectified Bregel tiles + geo-space polygons (internally consistent);
working from the original scan in pixel space would need the georeference inverse.

### The loop

```
ground truth → degrade → METHOD → reconstructed geometry → measure
```

`METHOD` is a real prompted tracer (not identity — see v0 below). Metrics: area IoU,
Hausdorff, boundary-distance.

### The sweeps

- **Human effort:** N guidance points (5 / 10 / 20 / 40) × positional error. Plot
  `effort → accuracy`, look for the knee ("8 points → 80 %, 15 → 95 %, 30 → 96 %"
  ⇒ don't ask for 30).
- **Marginal return on correction:** after the first result, one positive / negative
  click at the worst error — how much does accuracy improve; then another.

### Uniform vs. skilled point placement

The GPT doc's sweep and the v0 notebook degrade by *uniform* resampling — a naive
tracer laying points evenly. A skilled operator places non-uniformly: sparse on
crisp runs, clustered at gaps and label crossings, points dropped inside gaps to
bridge them. So "N points" is not one quantity — **N placed well should beat N
placed evenly by a wide margin.** The more useful experiment is "how few
*well-placed* points," which argues for the tool proposing where to click (high
curvature, weak local signal) rather than asking for a fixed count. A faithful
degradation model would concentrate points by curvature and by local image weakness
— harder to simulate (needs the raster) but closer to real input.

### Scale note

Positional jitter of ±10–50 m on a 2,000-km-perimeter territory is negligible; that
axis only matters at a scale comparable to the tracer's corridor width. Express
perturbation relative to feature size (fraction of mean segment length / perimeter),
or in scan pixels — not fixed small metres.

---

## v0 status

`notebooks/eval_01_degrade_reconstruct.ipynb`: load one polygon, project to metres,
degrade (uniform resample + jitter), `reconstruct()` = **identity**, score IoU +
Hausdorff, sweep N × jitter.

The identity `reconstruct()` is the **zero-help baseline only** — it measures
information lost in the degraded trace itself, the line a real method has to beat.
Observed: the N-axis gradient is sane (IoU rises, Hausdorff roughly halves per
doubling of N); the jitter axis is flat, for the scale reason above. Next real step
is a genuine prompted tracer in `reconstruct()`; until then the sweep numbers are a
baseline, not a finding.

---

## Relationship to the scoping doc

Phase 3 ("Machine assistance") territory, run as the separate "Draw2" track — no
dependency on the Phase 0 / 1 build. Phase 0 is Path B.
