<script lang="ts">
  import Viewer from './Viewer.svelte';
  import PropertiesPanel from './PropertiesPanel.svelte';
  import type { Store } from './annotationStore';

  export let tileSource: string;
  export let imageId: number;
  export let projectId: number;

  let viewer: Viewer;
  let anno: any = null;
  let store: Store | null = null;
  let active: 'polygon' | 'path' | null = null;

  function tool(t: 'polygon' | 'path' | null) {
    active = active === t ? null : t;
    viewer.setTool(active);
  }

  function onReady(e: CustomEvent<{ anno: any; store: Store }>) {
    anno = e.detail.anno;
    store = e.detail.store;
  }
</script>

<div class="draw-app">
  <div class="toolbar">
    <button class:on={active === 'polygon'} on:click={() => tool('polygon')}>Region</button>
    <button class:on={active === 'path'} on:click={() => tool('path')}>Label / boundary</button>
    <button class:on={active === null} on:click={() => tool(null)}>Select</button>
  </div>
  <div class="body">
    <div class="viewer-wrap" class:drawing={active}>
      <Viewer bind:this={viewer} {tileSource} {imageId} on:ready={onReady} />
    </div>
    {#if anno && store}
      <PropertiesPanel {anno} {store} {projectId} />
    {/if}
  </div>
</div>

<style>
  .draw-app { display: flex; flex-direction: column; width: 100%; height: 100%; }
  .toolbar {
    flex: 0 0 auto; display: flex; gap: .4rem; padding: .35rem .5rem;
    border-bottom: 1px solid #ddd; background: #fafafa;
  }
  .toolbar button {
    font: 13px system-ui, sans-serif; padding: .2rem .6rem;
    border: 1px solid #bbb; border-radius: 4px; background: #fff; cursor: pointer;
  }
  .toolbar button.on { background: #2e6da4; color: #fff; border-color: #2e6da4; }
  .body { flex: 1 1 auto; min-height: 0; display: flex; }
  .viewer-wrap { flex: 1 1 auto; min-width: 0; position: relative; }

  /* while a drawing tool is active: crosshair over the map + a coloured frame */
  .viewer-wrap.drawing :global(.openseadragon-canvas),
  .viewer-wrap.drawing :global(.openseadragon-canvas *),
  .viewer-wrap.drawing :global(.a9s-annotationlayer),
  .viewer-wrap.drawing :global(.a9s-annotationlayer *),
  .viewer-wrap.drawing :global(.a9s-osd-selectionlayer),
  .viewer-wrap.drawing :global(.a9s-gl-canvas) {
    cursor: crosshair !important;
  }
  .viewer-wrap.drawing::after {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    border: 2px solid #2e6da4;
  }
</style>
