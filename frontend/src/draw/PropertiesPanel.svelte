<script lang="ts">
  import { onMount } from 'svelte';
  import type { Store } from './annotationStore';

  export let anno: any;
  export let store: Store;
  export let projectId: number;

  let vocab: Array<{ id: number; source_label: string; aat_term: string }> = [];
  let sel: any = null;   // the selected Annotorious annotation
  let row: any = null;   // its CPDraw fields
  let status = '';

  onMount(async () => {
    try {
      vocab = await fetch(`/api/project-placetypes/?project=${projectId}`,
        { credentials: 'same-origin' }).then((r) => r.json());
    } catch (e) { console.error('[cpdraw] vocab load failed', e); }

    anno.on('selectionChanged', (selected: any[]) => load(selected?.[0] ?? null));
  });

  async function load(a: any) {
    sel = a;
    row = null;
    if (!a) return;
    // a freshly-drawn annotation's POST may still be in flight
    let pk = store.pkOf(a.id);
    for (let i = 0; !pk && i < 25; i++) {
      await new Promise((r) => setTimeout(r, 120));
      pk = store.pkOf(a.id);
    }
    if (!pk) { status = 'could not resolve this annotation'; return; }
    status = 'loading…';
    row = await fetch(`/api/annotations/${pk}/`, { credentials: 'same-origin' }).then((r) => r.json());
    status = '';
  }

  let saveTimer: ReturnType<typeof setTimeout>;
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      if (!sel || !row) return;
      status = 'saving…';
      try {
        await store.patch(sel.id, {
          name: row.name ?? '',
          name_normalized: row.name_normalized ?? '',
          feature_role: row.feature_role,
          placetype: row.placetype ?? null,
          certainty: row.certainty ?? '',
        });
        status = 'saved';
      } catch (e) {
        console.error(e);
        status = 'save failed';
      }
    }, 400);
  }
</script>

<aside class="panel">
  {#if !sel}
    <p class="hint">Select an annotation to name and type it.</p>
  {:else if !row}
    <p class="hint">{status || 'preparing…'}</p>
  {:else}
    <label>Name
      <input bind:value={row.name} on:input={save} />
    </label>
    <label>Normalized
      <input bind:value={row.name_normalized} on:input={save} placeholder="optional editorial form" />
    </label>
    <label>Role
      <select bind:value={row.feature_role} on:change={save}>
        <option value="region">region</option>
        <option value="label">label</option>
        <option value="boundary">boundary</option>
      </select>
    </label>
    <label>Type
      <select bind:value={row.placetype} on:change={save}>
        <option value={null}>—</option>
        {#each vocab as v}
          <option value={v.id}>{v.source_label}{#if v.aat_term} · {v.aat_term}{/if}</option>
        {/each}
      </select>
    </label>
    <label>Certainty
      <select bind:value={row.certainty} on:change={save}>
        <option value="">—</option>
        <option value="certain">certain</option>
        <option value="likely">likely</option>
        <option value="uncertain">uncertain</option>
      </select>
    </label>
    <p class="status">{status}</p>
  {/if}
</aside>

<style>
  .panel {
    width: 260px; flex: 0 0 auto; padding: .75rem .9rem;
    border-left: 1px solid #ddd; background: #fff; overflow-y: auto;
    font: 13px system-ui, sans-serif;
  }
  .hint { color: #777; }
  label { display: block; margin-bottom: .6rem; }
  label input, label select {
    display: block; width: 100%; margin-top: .15rem;
    font: inherit; padding: .2rem .35rem; border: 1px solid #bbb; border-radius: 4px;
  }
  .status { color: #2e6da4; min-height: 1em; }
</style>
