// Bridges Annotorious's create/update/delete events to the CPDraw annotation
// API, and loads existing annotations back onto the viewer.
//
// The CPDraw row's `w3c` column holds the annotation object exactly as
// Annotorious emits it, so load is a straight `setAnnotations(rows.map(w3c))`
// and there's no lossy conversion.

import { csrfToken } from './csrf';

const API = '/api/annotations/';

type AnyAnno = Record<string, any>;

function geometryKind(a: AnyAnno): { geometry_type: string; feature_role: string } {
  const t = String(a?.target?.selector?.type || '').toUpperCase();
  if (t.includes('POLYLINE')) return { geometry_type: 'polyline', feature_role: 'label' };
  return { geometry_type: 'polygon', feature_role: 'region' };
}

async function req(url: string, opts: RequestInit = {}) {
  const r = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
    ...opts,
  });
  if (!r.ok) throw new Error(`${opts.method ?? 'GET'} ${url} → ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

export interface Store {
  /** CPDraw pk for an Annotorious annotation id, if persisted. */
  pkOf(annoId: string): number | undefined;
  /** PATCH arbitrary CPDraw fields (name, feature_role, placetype, …). */
  patch(annoId: string, fields: Record<string, unknown>): Promise<void>;
}

export function attachStore(anno: any, imageId: number): Store {
  const idMap = new Map<string, number>();

  req(`${API}?image=${imageId}`)
    .then((rows: AnyAnno[]) => {
      for (const row of rows) if (row.w3c?.id) idMap.set(row.w3c.id, row.id);
      anno.setAnnotations(rows.map((r) => r.w3c));
    })
    .catch((e) => console.error('[cpdraw] load annotations failed', e));

  anno.on('createAnnotation', async (a: AnyAnno) => {
    try {
      const row = await req(API, {
        method: 'POST',
        body: JSON.stringify({ image: imageId, name: '', ...geometryKind(a), w3c: a }),
      });
      idMap.set(a.id, row.id);
    } catch (e) {
      console.error('[cpdraw] create failed', e);
    }
  });

  anno.on('updateAnnotation', async (a: AnyAnno) => {
    const pk = idMap.get(a.id);
    if (pk) await req(`${API}${pk}/`, { method: 'PATCH', body: JSON.stringify({ w3c: a }) })
      .catch((e) => console.error('[cpdraw] update failed', e));
  });

  anno.on('deleteAnnotation', async (a: AnyAnno) => {
    const pk = idMap.get(a.id);
    if (pk) {
      await req(`${API}${pk}/`, { method: 'DELETE' }).catch((e) => console.error('[cpdraw] delete failed', e));
      idMap.delete(a.id);
    }
  });

  return {
    pkOf: (annoId) => idMap.get(annoId),
    async patch(annoId, fields) {
      const pk = idMap.get(annoId);
      if (pk) await req(`${API}${pk}/`, { method: 'PATCH', body: JSON.stringify(fields) });
    },
  };
}
