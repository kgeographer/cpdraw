"""Orchestrate: fetch -> normalise -> parse -> persist a Source + MapImages."""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from main.models import MapImage, Source, WorkState

from .client import fetch as _default_fetch
from .exceptions import IngestError, ParseError
from .normalize import normalize
from .parse import ImageData, lang_str, parse_info_json, parse_manifest
from .quality import assess as assess_quality


@dataclass
class ImagePreflight:
    seq: int
    label: str
    width: int | None
    height: int | None
    notes: list = field(default_factory=list)


@dataclass
class Preflight:
    """Result of assessing a URI without writing anything."""
    kind: str
    iiif_version: str
    label: str
    images: list  # [ImagePreflight]

    @property
    def has_warnings(self) -> bool:
        return any(n["level"] == "warning" for im in self.images for n in im.notes)

    @property
    def warning_lines(self) -> list[str]:
        lines = []
        for im in self.images:
            tag = im.label or f"image {im.seq}"
            for n in im.notes:
                if n["level"] == "warning":
                    lines.append(f"{tag} — {n['message']}")
        return lines


def preflight(uri, *, fetcher=_default_fetch) -> Preflight:
    """Fetch + parse + quality-assess `uri`. No database writes."""
    fr = fetcher(uri)

    if fr.kind == "image_service" and isinstance(fr.doc, dict):
        img = parse_info_json(fr.doc)
        notes = assess_quality(img.width, img.height, fr.doc)
        return Preflight("image_service", "3", "",
                         [ImagePreflight(0, "", img.width, img.height, notes)])

    if not isinstance(fr.doc, dict):
        raise ParseError(f"{uri} did not return a JSON object (kind={fr.kind})")

    doc, _ = normalize(fr.doc, fr.final_uri)
    try:
        sd = parse_manifest(doc)
    except ParseError as exc:
        if not (_salvage_image_service(doc) or _salvage_image_service(fr.doc)):
            raise
        return Preflight("manifest", "3", lang_str(doc.get("label")),
                         [ImagePreflight(0, "", None, None, [])])

    images = []
    for seq, img in enumerate(sd.images):
        info = _try_info_json(img.image_service_uri, fetcher)
        images.append(ImagePreflight(seq, img.label, img.width, img.height,
                                     assess_quality(img.width, img.height, info)))
    return Preflight("manifest", sd.iiif_version, sd.label, images)


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
        return _ingest_degraded(uri, fr, doc, log, exc,
                                project=project, owner=owner, fetcher=fetcher)

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
        # Best-effort: fetch each canvas's info.json for the quality check and
        # to cache it on the row. A failure just means the check runs on the
        # manifest's width/height alone.
        info = _try_info_json(img.image_service_uri, fetcher)
        _new_image(src, seq, img,
                   needs_metadata=not (img.width and img.height),
                   info_json=info)
    return src


def _ingest_image_service(uri, fr, *, project, owner) -> Source:
    img = parse_info_json(fr.doc)
    src = _new_source(
        project, owner, uri, fr, Source.IngestKind.IMAGE_SERVICE, "3",
        [{"rule": "image_service_only",
          "note": "ingested a bare Image service; metadata must be supplied by hand"}],
    )
    src.save()
    _new_image(src, 0, img, needs_metadata=True, info_json=fr.doc)
    return src


def _ingest_degraded(uri, fr, doc, log, exc, *, project, owner, fetcher=None) -> Source:
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
    info = _try_info_json(salvaged, fetcher)
    _new_image(src, 0, ImageData(image_service_uri=salvaged),
               needs_metadata=True, info_json=info)
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


def _new_image(src, seq, img: ImageData, *, needs_metadata, info_json=None) -> MapImage:
    mi = MapImage.objects.create(
        source=src,
        seq=seq,
        canvas_uri=img.canvas_uri,
        image_service_uri=img.image_service_uri,
        width=img.width,
        height=img.height,
        label=img.label,
        info_json=info_json or None,
        needs_metadata=needs_metadata,
        quality_notes=assess_quality(img.width, img.height, info_json),
    )
    WorkState.objects.create(image=mi)
    return mi


def _try_info_json(image_service_uri, fetcher):
    """Fetch <service>/info.json, or None on any failure."""
    fetcher = fetcher or _default_fetch
    url = f"{image_service_uri.rstrip('/')}/info.json"
    try:
        fr = fetcher(url)
    except IngestError:
        return None
    doc = fr.doc if isinstance(fr.doc, dict) else None
    # Guard against an injected test fetcher that returns the manifest for any
    # URL: only trust a doc that looks like an Image API info.json.
    if doc and (doc.get("protocol") == "http://iiif.io/api/image"
                or "api/image" in str(doc.get("@context"))):
        return doc
    return None


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
