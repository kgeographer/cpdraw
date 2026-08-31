"""Orchestrate: fetch -> normalise -> parse -> persist a Source + MapImages."""

from django.db import transaction
from django.utils import timezone

from main.models import MapImage, Source, WorkState

from .client import fetch as _default_fetch
from .exceptions import ParseError
from .normalize import normalize
from .parse import ImageData, lang_str, parse_info_json, parse_manifest


@transaction.atomic
def ingest_source(uri, *, project, owner, fetcher=_default_fetch) -> Source:
    """Fetch `uri`, create and return a Source with one or more MapImages.

    `fetcher` is injectable so tests can feed fixtures without a network call.
    """
    fr = fetcher(uri)

    if fr.kind == "image_service" and isinstance(fr.doc, dict):
        return _ingest_image_service(uri, fr, project=project, owner=owner)

    if not isinstance(fr.doc, dict):
        raise ParseError(f"{uri} did not return a JSON object (kind={fr.kind})")

    doc, log = normalize(fr.doc, fr.final_uri)
    try:
        sd = parse_manifest(doc)
    except ParseError as exc:
        return _ingest_degraded(uri, fr, doc, log, exc, project=project, owner=owner)

    src = _new_source(project, owner, uri, fr,
                      Source.IngestKind.MANIFEST, sd.iiif_version, log)
    src.iiif_label = sd.label
    src.iiif_metadata = sd.metadata
    src.iiif_rights = sd.rights
    src.iiif_summary = sd.summary
    src.iiif_required_statement = sd.required_statement
    src.nav_date = sd.nav_date
    src.save()

    for seq, img in enumerate(sd.images):
        _new_image(src, seq, img, needs_metadata=not (img.width and img.height))
    return src


def _ingest_image_service(uri, fr, *, project, owner) -> Source:
    img = parse_info_json(fr.doc)
    src = _new_source(
        project, owner, uri, fr, Source.IngestKind.IMAGE_SERVICE, "3",
        [{"rule": "image_service_only",
          "note": "ingested a bare Image service; metadata must be supplied by hand"}],
    )
    src.save()
    _new_image(src, 0, img, needs_metadata=True)
    return src


def _ingest_degraded(uri, fr, doc, log, exc, *, project, owner) -> Source:
    """Manifest unusable but an image service can be salvaged (scoping doc §6a)."""
    salvaged = _salvage_image_service(doc) or _salvage_image_service(fr.doc)
    if not salvaged:
        raise exc
    log = list(log) + [{
        "rule": "degraded_to_image_service",
        "note": f"manifest unusable ({exc}); fell back to a salvaged image service",
    }]
    src = _new_source(project, owner, uri, fr, Source.IngestKind.MANIFEST, "3", log)
    src.iiif_label = lang_str(doc.get("label"))
    src.iiif_metadata = doc.get("metadata") or []
    src.save()
    _new_image(src, 0, ImageData(image_service_uri=salvaged), needs_metadata=True)
    return src


# --- persistence helpers ------------------------------------------------

def _new_source(project, owner, uri, fr, kind, version, log) -> Source:
    return Source(
        project=project,
        owner=owner,
        ingest_uri=uri,
        ingest_kind=kind,
        iiif_version=version,
        fetched_at=timezone.now(),
        raw_document=fr.text,
        normalization_log=log,
    )


def _new_image(src, seq, img: ImageData, *, needs_metadata) -> MapImage:
    mi = MapImage.objects.create(
        source=src,
        seq=seq,
        canvas_uri=img.canvas_uri,
        image_service_uri=img.image_service_uri,
        width=img.width,
        height=img.height,
        label=img.label,
        needs_metadata=needs_metadata,
    )
    WorkState.objects.create(image=mi)
    return mi


def _salvage_image_service(node) -> str:
    """Depth-first hunt for any IIIF Image service id in a broken document."""
    if isinstance(node, dict):
        t = str(node.get("type") or node.get("@type") or "")
        if t.lower().startswith("imageservice"):
            sid = node.get("id") or node.get("@id")
            if sid:
                return str(sid)
        for v in node.values():
            found = _salvage_image_service(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _salvage_image_service(v)
            if found:
                return found
    return ""
