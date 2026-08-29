// WO-0.1 smoke entry point.
//
// Purpose: prove the build pipeline can do the two things the legacy
// script-tag/jQuery setup could not, and which every later work order needs:
//   1. resolve and execute an ESM-only Allmaps package (with its own
//      npm dependency tree) in the browser;
//   2. compile and mount a Svelte component.
//
// Replaced in WO-0.3, when OpenSeadragon renders the real target map into
// #cpdraw-draw-root.

import * as allmapsTransform from '@allmaps/transform';
import SmokeProbe from './SmokeProbe.svelte';

const allmapsExports = Object.keys(allmapsTransform).sort();
console.log(
  '[cpdraw wo-0.1] @allmaps/transform loaded; exports:',
  allmapsExports,
);

const target = document.getElementById('cpdraw-draw-root');
if (target) {
  new SmokeProbe({ target, props: { allmapsExports } });
} else {
  console.warn('[cpdraw wo-0.1] #cpdraw-draw-root not found — nothing mounted');
}
