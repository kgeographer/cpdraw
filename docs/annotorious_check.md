I'm evaluating Annotorious v3 as the annotation layer for a web app that
digitizes features off historical maps. The app needs four capture tools:
point, line (polyline), polygon, and edit. Annotorious appears to ship only
rectangle and polygon.

I need to know whether point and polyline can be added as a PLUGIN, or
whether they'd require invasive changes to the library itself.

Do NOT write any code yet. This is an assessment task.

Repos and packages to look at (clone if useful):
- github.com/annotorious/annotorious — the v3 monorepo
- @annotorious/core, @annotorious/annotorious, @annotorious/openseadragon
- Check the docs at annotorious.dev and any published plugins/extensions
  first, in case this is already solved and just underdocumented.

Answer these, with file:line references as evidence rather than impressions:

1. Are shape types defined in a registry/factory that third-party code can
   extend at runtime, or are they enumerated in hardcoded unions, switch
   statements, or discriminated types across the codebase? Name the specific
   mechanism if one exists.

2. Trace one existing shape (polygon is probably clearest) through the full
   lifecycle and list every file that has to know about it:
   - the drawing tool / user interaction
   - the internal geometry representation
   - hit testing and the editing/handle layer
   - SVG rendering
   - serialization to and from W3C Web Annotation selectors
   Which of these are pluggable and which are closed?

3. A point is arguably a degenerate polygon and a polyline an unclosed one.
   Does the internal geometry model or the selector serialization already
   accommodate either, such that only the drawing UI is missing? Check the
   SvgSelector handling specifically.

4. How does the OpenSeadragon connector relate to shape definitions — does
   adding a shape require changes there too, or does it delegate?

Deliverable: a short memo (not code) covering
  (a) plugin-feasible, fork-required, or somewhere between
  (b) if plugin-feasible: what interface a plugin must implement, and a
      rough effort estimate for point + polyline
  (c) if not: precisely which files would need upstream changes, and how
      invasive — the shape of a PR to the maintainer
  (d) anything you couldn't determine from the source, stated as unknown
      rather than guessed

Context that may matter: the polyline case is not decorative. It captures a
cartographer's label spread across a region as an assertion of extent, so
the geometry is an open path with a meaningful direction and no fill. If
the library assumes closed regions with interiors anywhere in hit testing
or rendering, that's the thing most likely to bite.