# CPDraw frontend

Vite build for CPDraw's browser code. It exists because the libraries CPDraw is
committed to — the `@allmaps/*` packages (ESM-only, with their own npm dependency
trees) and Annotorious v3 (authored in Svelte) — cannot be loaded the way the
predecessor loaded its JS (CDN `<script>` tags + jQuery globals). Established in
**WO-0.1**.

## Toolchain

| Tool | Version | Why pinned there |
|---|---|---|
| Node | 22.x (`.nvmrc` / `engines`) | LTS; Vite 5 needs ≥ 20.19 / 22.12 |
| pnpm | 11.24.0 (`packageManager`) | via Corepack (`corepack enable pnpm`) |
| Vite | 5.x | matches `@annotorious/openseadragon` 3.8.9's build |
| Svelte | 4.x | **must** match Annotorious's runtime — our point/polyline |
| `@sveltejs/vite-plugin-svelte` | 3.x | drawing tools (WO-0.4) compile against it |

Do not bump Vite/Svelte ahead of this line until Annotorious v3 does; the
plugin components we register into Annotorious share its Svelte runtime and a
mismatch breaks silently. See the header comment in `vite.config.ts`.

Node 22 is installed keg-only via Homebrew, so interactive shells need it on
PATH (added to `~/.zshrc` in WO-0.1):

```sh
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
```

## Layout

```
frontend/
  vite.config.ts        base = /static/frontend/ ; entry = src/draw/main.ts
  pnpm-workspace.yaml    build-script triage (esbuild allowed; rest blocked)
  src/
    draw/
      main.ts            entry point (WO-0.1 smoke: import @allmaps/transform + mount Svelte)
      SmokeProbe.svelte  throwaway probe component — deleted in WO-0.3
  dist/                  build output (gitignored); dist/.vite/manifest.json is what Django reads
```

## Commands

```sh
pnpm install          # after cloning, or when package.json changes
pnpm dev              # Vite dev server on :5173 with HMR — run alongside runserver
pnpm build            # production bundle -> dist/ + dist/.vite/manifest.json
pnpm check            # svelte-check + tsc, no emit
pnpm approve-builds   # re-run if a dependency bump adds a new install script
```

## How it reaches the browser (django-vite)

`whgdraw/settings.py` has a `DJANGO_VITE` block; `django_vite` is in
`INSTALLED_APPS`. Templates load assets with:

```django
{% load django_vite %}
{% vite_hmr_client %}                    {# dev only; renders nothing in prod #}
{% vite_asset 'src/draw/main.ts' %}      {# manifest key = the Rollup input path #}
```

- **`DEBUG=True`** → `dev_mode` on → tags point at `http://localhost:5173/static/frontend/...`.
  Requires `pnpm dev` running. Two processes: `manage.py runserver` + `pnpm dev`.
- **`DEBUG=False`** → tags are built from `dist/.vite/manifest.json` (hashed
  filenames) and served from `/static/frontend/` by WhiteNoise.

The `/static/frontend/` prefix is wired in three places that must agree:
`vite.config.ts` `base`, `DJANGO_VITE["default"]["static_url_prefix"]`, and the
`('frontend', frontend/dist/)` entry in `STATICFILES_DIRS`.

## Deploy

`pnpm install --frozen-lockfile && pnpm build` **before** `manage.py collectstatic`.
This is build-time Node only — unrelated to the separate runtime-Node question
for `@allmaps/cli` in Phase 1 (scoping doc Open Question 3).

## WO-0.1 smoke page

`/draw/_wo01/` (`main/templates/main/wo01_pipeline_check.html`, route in
`main/urls.py`). No auth, not in any nav. It proves the build can (1) execute an
ESM-only Allmaps package in the browser and (2) mount a Svelte component.
Remove it and `SmokeProbe.svelte` when WO-0.3 puts the real OpenSeadragon
viewer on the Draw page.
