# whgdraw / linkedplaces.draw — briefing for redesign spec

## What it is today

A Django 5.2 + GeoDjango/PostGIS + Leaflet app (originally "linkedplaces.draw," ALPHA 0.1,
~2020) for tracing/digitizing named features off scanned historical maps and exporting them
as Linked Places Format (LPF) for World Historical Gazetteer ingestion. Built fast for one
real job — two people (the author + an RA) digitizing the Bregel Atlas of Central Asia — but
the data model and UI were deliberately built generic, not Bregel-specific.

## Data model

- `User` (Django auth)
- `Project` — owner + `ProjectUser` collaborators with role: creator/owner/member
- `Map` — belongs to a project; title, citation metadata, `year_pub`, a `when`/`when_constant`
  JSONB temporal range, `minzoom`/`maxzoom`/`bounds`, a `tiles` boolean gate
- `Feature` — belongs to a map; point/line/polygon geometry in separate typed PostGIS columns,
  a JSONB properties blob holding name(s)/type(s)/temporal info, `placetype` as a Getty AAT
  identifier
- `Placetype` / `ProjectPlacetype` / `MapPlacetype` — scope the AAT vocabulary per project
- `Name` — a per-atlas index used for autocomplete when creating a feature

## Workflow today

Dashboard lists/creates projects → project page lists/creates maps (owner, project,
title/label, citation, `when`, zoom/bounds, a manual `tiles` checkbox) → draw page: pick
project → map, get a raster tile overlay of the georeferenced scan (Leaflet.draw
point/line/polygon tools) to trace over, save to Postgres via AJAX, geometry-editable via
drag + toolbar-save. Export per-project as CSV or LPF JSON (with reverse-geocoded country
codes).

## The load-bearing gap

Georeferencing/tiling is entirely outside the app. Historically: georeference the scan in
QGIS, run `gdal2tiles.py` by hand, drop the resulting `{z}/{x}/{y}.png` pyramid into a folder
the app serves statically. Zero in-app support for uploading a scan and rectifying it. This
project's own tile pyramids were recently recovered from a backup drive — only 8 of 48 maps
recovered, the rest (and the original scans) unlocated. That fragility is a first-order
argument for the redesign, not a side note.

## Other known rough edges

(found during a recent dependency-refresh/restore pass, all fixed on a `restore` branch)

- A couple of small pre-existing bugs: a stale field reference in the LPF export, a JS
  array-equality bug.
- A stubbed/dead popup form for editing a feature's name/type in place — geometry editing
  works fine via drag+save, but there's no live in-place property editor.
- No frontend build tooling (plain script tags, jQuery, Leaflet.draw) — a real constraint for
  whatever comes next.

## Open questions to research (not assume)

- **IIIF** as a source format for scans — many libraries/archives serve maps as IIIF Image
  API services; could remove the "host and tile the raster yourself" burden entirely.
- **Allmaps** (Bert Spaan et al.) for in-browser georeferencing / reverse rectification —
  actively developed, evaluate as a replacement for the manual QGIS→gdal2tiles pipeline.
- **Rainer Simon's annotation tooling** (Recogito-family) as a possible replacement for
  Leaflet.draw for the actual tracing/annotation UX.
- Rumsey's pre-rectified maps exist for some sources but are uneven/low quality — can't be
  relied on as the imagery pipeline.
- The overarching question: what would it take to make this a **generally hostable,
  shippable** tool — multi-project, multi-user, and crucially including the georeferencing
  step itself, not just tracing on pre-tiled maps someone prepared by hand.

## The ask

Research current state of the art on the above (IIIF, Allmaps, Recogito-family annotation
tools) and draft a loose spec — target architecture, what to keep vs. replace from the
current Project/Map/Feature/LPF-export model — usable to estimate dev time.
