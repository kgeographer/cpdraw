"""Tolerant massaging of a fetched IIIF document (scoping doc §6a).

Two layers:
  * generic leniency — things any real-world manifest might get wrong
  * per-host quirks  — provider-specific fixes, keyed on hostname

Every change is appended to a log ``[{"rule": str, "note": str}, ...]``. The
input dict is never mutated; callers keep ``Source.raw_document`` verbatim.
"""

import copy
from urllib.parse import urlsplit

# Canonical casing for the Presentation-API `type` values CPDraw looks at.
_CANONICAL_TYPES = {
    "manifest": "Manifest",
    "collection": "Collection",
    "canvas": "Canvas",
    "annotationpage": "AnnotationPage",
    "annotation": "Annotation",
    "range": "Range",
}

_QUIRKS: dict[str, list] = {}


def host_quirk(hostname):
    """Register a quirk fn(doc, log) for a hostname (and its subdomains)."""
    def register(fn):
        _QUIRKS.setdefault(hostname, []).append(fn)
        return fn
    return register


def normalize(doc: dict, source_uri: str) -> tuple[dict, list[dict]]:
    out = copy.deepcopy(doc)
    log: list[dict] = []

    _fix_type_casing(out, log)

    host = (urlsplit(source_uri).hostname or "").lower()
    for registered, fns in _QUIRKS.items():
        if host == registered or host.endswith("." + registered):
            for fn in fns:
                fn(out, log)

    return out, log


def _canon_type(value: str):
    *prefix, local = value.split(":")
    canon = _CANONICAL_TYPES.get(local.lower())
    if canon is None or local == canon:
        return None
    return ":".join([*prefix, canon])


def _fix_type_casing(node, log):
    if isinstance(node, dict):
        for key in ("type", "@type"):
            val = node.get(key)
            if isinstance(val, str):
                fixed = _canon_type(val)
                if fixed is not None:
                    node[key] = fixed
                    log.append({"rule": "type_casing",
                                "note": f"{key} {val!r} -> {fixed!r}"})
        for v in node.values():
            _fix_type_casing(v, log)
    elif isinstance(node, list):
        for v in node:
            _fix_type_casing(v, log)


# --- per-provider quirks --------------------------------------------------

@host_quirk("polona.pl")
def _polona_placeholder_ids(doc, log):
    """Polona AnnotationPages carry a shared https://example.org/uuid/... id,
    duplicated across canvases. CPDraw doesn't use those ids — just note it."""
    hits = _count_ids_matching(doc, "example.org")
    if hits:
        log.append({"rule": "polona.placeholder_ids",
                    "note": f"{hits} example.org placeholder id(s) present; ignored"})


def _count_ids_matching(node, needle, acc=0):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("id", "@id") and isinstance(v, str) and needle in v:
                acc += 1
            else:
                acc = _count_ids_matching(v, needle, acc)
    elif isinstance(node, list):
        for v in node:
            acc = _count_ids_matching(v, needle, acc)
    return acc
