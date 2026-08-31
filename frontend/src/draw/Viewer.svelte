<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import OpenSeadragon from 'openseadragon';

  /** IIIF Image `info.json` URL (or any value OSD's `tileSources` accepts). */
  export let tileSource: string;

  const dispatch = createEventDispatcher<{ ready: OpenSeadragon.Viewer }>();

  let host: HTMLDivElement;
  let viewer: OpenSeadragon.Viewer | undefined;
  let failed = false;

  onMount(() => {
    viewer = OpenSeadragon({
      element: host,
      tileSources: tileSource,
      crossOriginPolicy: 'Anonymous',
      // OSD's default zoom/home/fullscreen buttons load images from a CDN — skip
      // them for now; pan/zoom works from the mouse. The navigator (mini-map)
      // needs no images.
      showNavigationControl: false,
      showNavigator: true,
      navigatorPosition: 'TOP_RIGHT',
      minZoomImageRatio: 0.4,
      visibilityRatio: 1,
      gestureSettingsMouse: { clickToZoom: false },
    });
    viewer.addHandler('open', () => dispatch('ready', viewer!));
    viewer.addHandler('open-failed', () => {
      failed = true;
    });
  });

  onDestroy(() => {
    viewer?.destroy();
    viewer = undefined;
  });
</script>

<div class="osd-viewer">
  <div bind:this={host} class="osd-host"></div>
  {#if failed}
    <p class="osd-error">Could not load the image service:<br /><code>{tileSource}</code></p>
  {/if}
</div>

<style>
  .osd-viewer {
    position: relative;
    width: 100%;
    height: 100%;
    background: #1b1b1b;
  }
  .osd-host {
    width: 100%;
    height: 100%;
  }
  .osd-error {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #f5f5f5;
    font: 14px/1.5 system-ui, sans-serif;
    text-align: center;
  }
</style>
