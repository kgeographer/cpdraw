# notebooks/ — the "Draw2" evaluation track

Exploratory work on **degrade-and-reconstruct evaluation** of boundary-extraction
methods, using the predecessor's hand-digitized Bregel Atlas geometries as ground
truth. This is the track scoping-doc §10 Phase 3 ("Evaluation corpus") describes as
runnable independently of the CPDraw build — it shares no code with the Django app,
but it uses the **same project virtualenv** (`../.venv`), so PyCharm's project
interpreter just works with no kernel juggling.

Framing: `docs/GPT_20260828.txt`. The loop is
`ground truth → degrade → reconstruct → measure`, and the point is an objective
metric ("how much of the original geometry is recovered?"), not "did the machine
digitize the map?".

## Environment

The notebook deps are grouped in `requirements.txt` here, but they install into the
**project `.venv`** alongside Django — kept out of the repo-root `requirements.txt`
so they never reach the VM/production install.

```sh
# from the repo root, into the existing project venv
.venv/bin/pip install -r notebooks/requirements.txt
```

Deps: `jupyterlab`, `shapely`, `numpy`, `matplotlib`, `pyproj`.

In PyCharm the notebook runs on the project interpreter — no kernel to select. If you
run it elsewhere (`jupyter lab`), use the default `python3` kernel from that same
`.venv`. `.ipynb_checkpoints/` is gitignored.

## Data

`data/*.geojson` — read-only snapshots pulled from the local **`lpdraw`** Postgres DB
(`features` table) on 2026-08-29. Committed so the notebooks are reproducible without
DB access.

| file | map id | features |
|---|---|---|
| `data/bregel_37.geojson` | 96 | 45 Polygon, 6 LineString, 6 Point |
| `data/bregel_39.geojson` | 98 | 99 LineString, 1 Point |

Each feature carries `when` and `properties` (names, types/AAT) from the original
digitization. Coordinates are EPSG:4326 (lon/lat), as traced over the rectified
tiles. Regenerate with, e.g.:

```sh
psql -d lpdraw -tAqc "select json_build_object('type','FeatureCollection',
  'features', coalesce(json_agg(f.jsonb order by f.id),'[]'::json))
  from features f where f.map = 96;" > data/bregel_37.geojson
```

## Notebooks

- `eval_01_degrade_reconstruct.ipynb` — v0 harness: load one geometry, degrade
  (vertex decimation + positional jitter), a trivial reconstruction, and the metric
  pair (area IoU + Hausdorff), computed in a projected CRS. Sweeps N points × M px
  error. No real extraction methods yet — this establishes the measurement frame.

## Note

A pre-existing bad line in `~/.matplotlib/matplotlibrc`
(`legend.edgecolor : #cccccc` parses as empty) prints a warning on import; harmless,
and the notebook overrides that key in cell 1.
