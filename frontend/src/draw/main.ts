// Draw-page entry (WO-0.3 / WO-0.4). Mounts the OpenSeadragon viewer + the
// Annotorious annotation layer over the IIIF service named by the mount
// element's data- attributes.

import App from './App.svelte';

// The header status badge is server-rendered at page load. The first annotation
// flips WorkState unstarted -> in_progress in AnnotationViewSet.perform_create;
// reflect that in the badge here rather than making the user reload.
window.addEventListener('cpdraw:annotation-created', () => {
  const el = document.getElementById('draw-status');
  if (!el || el.dataset.status === 'in_progress' || el.dataset.status === 'complete') return;
  el.dataset.status = 'in_progress';
  el.innerHTML = '<span class="badge badge-primary">in progress</span>';
});

const target = document.getElementById('cpdraw-draw-root');

if (!target) {
  console.warn('[cpdraw] #cpdraw-draw-root not found — nothing mounted');
} else {
  const tileSource = target.dataset.iiif;
  const imageId = Number(target.dataset.imageId);
  const projectId = Number(target.dataset.projectId);
  if (!tileSource || !imageId || !projectId) {
    console.error('[cpdraw] #cpdraw-draw-root needs data-iiif, data-image-id, data-project-id');
  } else {
    new App({ target, props: { tileSource, imageId, projectId } });
  }
}
