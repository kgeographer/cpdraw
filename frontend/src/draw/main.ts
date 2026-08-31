// Draw-page entry (WO-0.3). Mounts the OpenSeadragon viewer over the IIIF
// Image service named by the mount element's `data-iiif` attribute.
//
// WO-0.4 will attach Annotorious to the same viewer instance via the `ready`
// event Viewer.svelte dispatches.

import Viewer from './Viewer.svelte';

const target = document.getElementById('cpdraw-draw-root');

if (!target) {
  console.warn('[cpdraw] #cpdraw-draw-root not found — nothing mounted');
} else {
  const tileSource = target.dataset.iiif;
  if (!tileSource) {
    console.error('[cpdraw] #cpdraw-draw-root has no data-iiif attribute');
  } else {
    new Viewer({ target, props: { tileSource } });
  }
}
