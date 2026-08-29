import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import { svelte, vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// CPDraw frontend build (WO-0.1).
//
// Version policy: pinned to the Vite 5 / Svelte 4 / vite-plugin-svelte 3 line
// on purpose. Those are the versions @annotorious/openseadragon 3.8.9 is built
// against (see its package.json). The point/polyline drawing tools CPDraw adds
// in WO-0.4 are Svelte components registered into Annotorious's own runtime, so
// jumping ahead to Svelte 5 / Vite 6+ here would risk silent interop breakage.
// Bump this only when Annotorious does.
//
// Django integration is via django-vite:
//   - dev  (DEBUG=True):  Django templates load modules from the Vite dev
//                         server on :5173 with HMR.
//   - prod (DEBUG=False): `pnpm build` writes dist/ + dist/.vite/manifest.json;
//                         django-vite emits hashed <script>/<link> tags that
//                         Django/WhiteNoise serve from /static/frontend/.
export default defineConfig({
  plugins: [svelte({ preprocess: vitePreprocess() })],

  // Must line up with settings.DJANGO_VITE static_url_prefix ('frontend') and
  // the ('frontend', frontend/dist) entry in STATICFILES_DIRS. django-vite
  // builds both the dev-server URL and the production static URL as
  // STATIC_URL + 'frontend/' + path, i.e. /static/frontend/... in both modes,
  // so the Vite base is the same string either way.
  base: '/static/frontend/',

  build: {
    outDir: 'dist',
    emptyOutDir: true,
    manifest: true, // -> dist/.vite/manifest.json
    rollupOptions: {
      input: {
        // Keyed in the manifest as 'src/draw/main.ts'; templates reference that.
        draw: resolve(__dirname, 'src/draw/main.ts'),
      },
    },
  },

  server: {
    port: 5173,
    strictPort: true, // fail loudly instead of drifting to :5174
    origin: 'http://localhost:5173',
    cors: true,
  },
});
