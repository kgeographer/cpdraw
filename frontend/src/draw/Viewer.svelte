<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import OpenSeadragon from 'openseadragon';
  import { createOSDAnnotator } from '@annotorious/openseadragon';
  import { mountPlugin as mountToolsPlugin } from '@annotorious/plugin-tools';
  import '@annotorious/openseadragon/annotorious-openseadragon.css';
  import '@annotorious/plugin-tools/annotorious-plugin-tools.css';
  import { attachStore, type Store } from './annotationStore';

  /** IIIF Image `info.json` URL (or anything OSD's `tileSources` accepts). */
  export let tileSource: string;
  /** MapImage pk — annotations are scoped to it. */
  export let imageId: number;

  const dispatch = createEventDispatcher<{ ready: { anno: any; store: Store } }>();

  let host: HTMLDivElement;
  let viewer: OpenSeadragon.Viewer | undefined;
  let anno: any;
  let failed = false;

  onMount(() => {
    viewer = OpenSeadragon({
      element: host,
      tileSources: tileSource,
      crossOriginPolicy: 'Anonymous',
      showNavigationControl: false,
      showNavigator: true,
      navigatorPosition: 'TOP_RIGHT',
      minZoomImageRatio: 0.4,
      visibilityRatio: 1,
      gestureSettingsMouse: { clickToZoom: false },
    });
    viewer.addHandler('open-failed', () => { failed = true; });

    anno = createOSDAnnotator(viewer, { drawingEnabled: false });
    mountToolsPlugin(anno);
    const store = attachStore(anno, imageId);
    dispatch('ready', { anno, store });
  });

  onDestroy(() => {
    try { anno?.destroy?.(); } catch { /* noop */ }
    viewer?.destroy();
    viewer = undefined;
  });

  /** Enable a drawing tool ('polygon' | 'path'), or pass null to return to select. */
  export function setTool(tool: 'polygon' | 'path' | null) {
    if (!anno) return;
    if (tool) {
      anno.setDrawingEnabled(true);
      anno.setDrawingTool(tool);
    } else {
      anno.setDrawingEnabled(false);
    }
  }
</script>

<div class="osd-viewer">
  <div bind:this={host} class="osd-host"></div>
  {#if failed}
    <p class="osd-error">Could not load the image service:<br /><code>{tileSource}</code></p>
  {/if}
</div>

<style>
  .osd-viewer { position: relative; width: 100%; height: 100%; background: #1b1b1b; }
  .osd-host { width: 100%; height: 100%; }
  .osd-error {
    position: absolute; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; color: #f5f5f5;
    font: 14px/1.5 system-ui, sans-serif; text-align: center;
  }
</style>
