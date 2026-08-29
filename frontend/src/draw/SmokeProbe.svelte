<script lang="ts">
  // WO-0.1 smoke component. Proves the Svelte compile + mount path works.
  // Deleted in WO-0.3 when the real OpenSeadragon viewer lands here.
  export let allmapsExports: string[] = [];
  const mountedAt = new Date().toISOString();
</script>

<div class="probe">
  <h1>CPDraw frontend pipeline — OK</h1>
  <ul>
    <li>Svelte component compiled and mounted <time>{mountedAt}</time></li>
    <li><code>@allmaps/transform</code> ESM import executed (see console)</li>
    <li>exports seen: <code>{allmapsExports.join(', ') || '(none)'}</code></li>
  </ul>
  <p class="note">
    This page is WO-0.1 scaffolding at <code>/draw/_wo01/</code>. It is not
    wired into any nav and gets removed when WO-0.3 puts the real viewer here.
  </p>
</div>

<style>
  .probe {
    font: 14px/1.5 system-ui, -apple-system, sans-serif;
    max-width: 44rem;
    margin: 2.5rem auto;
    padding: 1.25rem 1.5rem;
    border: 2px solid #2e7d32;
    border-radius: 8px;
    background: #f1f8f2;
    color: #1b3a1d;
  }
  h1 {
    font-size: 1.15rem;
    margin: 0 0 0.75rem;
    color: #2e7d32;
  }
  ul {
    margin: 0;
    padding-left: 1.25rem;
  }
  code {
    background: #fff;
    padding: 0 0.25rem;
    border-radius: 3px;
    border: 1px solid #cfe3d0;
  }
  .note {
    margin: 0.75rem 0 0;
    font-size: 0.85rem;
    color: #4a6b4c;
  }
</style>
