"""Read a (normalised) IIIF document into plain dataclasses. No Django here."""

from dataclasses import dataclass, field

from .exceptions import ParseError


@dataclass
class ImageData:
    image_service_uri: str
    canvas_uri: str = ""
    width: int | None = None
    height: int | None = None
    label: str = ""


@dataclass
class SourceData:
    iiif_version: str                       # '2' | '3'
    label: str = ""
    metadata: list = field(default_factory=list)
    rights: str = ""
    summary: str = ""
    required_statement: dict | None = None
    nav_date: str = ""
    images: list[ImageData] = field(default_factory=list)


def detect_version(doc: dict) -> str:
    ctx = doc.get("@context")
    ctx_str = " ".join(ctx) if isinstance(ctx, list) else str(ctx or "")
    if "presentation/2" in ctx_str or "sequences" in doc:
        return "2"
    return "3"


def parse_manifest(doc: dict) -> SourceData:
    sd = _parse_v2(doc) if detect_version(doc) == "2" else _parse_v3(doc)
    if not sd.images:
        raise ParseError("manifest has no canvas with a usable image service")
    return sd


def parse_info_json(doc: dict) -> ImageData:
    svc = doc.get("id") or doc.get("@id")
    if not svc:
        raise ParseError("info.json has no id")
    return ImageData(
        image_service_uri=str(svc),
        width=_as_int(doc.get("width")),
        height=_as_int(doc.get("height")),
    )


# --- Presentation 3 -----------------------------------------------------

def _parse_v3(doc: dict) -> SourceData:
    sd = SourceData(
        iiif_version="3",
        label=lang_str(doc.get("label")),
        metadata=doc.get("metadata") or [],
        rights=str(doc.get("rights") or ""),
        summary=lang_str(doc.get("summary")),
        required_statement=doc.get("requiredStatement"),
        nav_date=str(doc.get("navDate") or ""),
    )
    for canvas in doc.get("items") or []:
        img = _v3_image_from_canvas(canvas)
        if img:
            sd.images.append(img)
    return sd


def _v3_image_from_canvas(canvas: dict) -> ImageData | None:
    body = None
    for page in canvas.get("items") or []:
        for anno in page.get("items") or []:
            if anno.get("motivation") in (None, "painting") and isinstance(anno.get("body"), dict):
                body = anno["body"]
                break
        if body:
            break
    if body is None:
        return None
    svc = _image_service_uri(body)
    if not svc:
        return None
    return ImageData(
        image_service_uri=svc,
        canvas_uri=str(canvas.get("id") or ""),
        width=_as_int(canvas.get("width")) or _as_int(body.get("width")),
        height=_as_int(canvas.get("height")) or _as_int(body.get("height")),
        label=lang_str(canvas.get("label")),
    )


def _image_service_uri(body: dict) -> str:
    svc = body.get("service")
    entries = svc if isinstance(svc, list) else ([svc] if isinstance(svc, dict) else [])
    for entry in entries:
        if isinstance(entry, dict):
            sid = entry.get("id") or entry.get("@id")
            if sid:
                return str(sid)
    # fall back to an IIIF Image request URL, e.g. .../full/max/0/default.jpg
    bid = body.get("id") or body.get("@id")
    if isinstance(bid, str) and "/full/" in bid:
        return bid.split("/full/")[0]
    return ""


# --- Presentation 2 ---------------------------------------------------

def _parse_v2(doc: dict) -> SourceData:
    sd = SourceData(
        iiif_version="2",
        label=lang_str(doc.get("label")),
        metadata=doc.get("metadata") or [],
        rights=str(doc.get("license") or doc.get("rights") or ""),
        summary=lang_str(doc.get("description")),
        required_statement=(
            {"label": "Attribution", "value": doc["attribution"]}
            if doc.get("attribution") else None
        ),
        nav_date=str(doc.get("navDate") or ""),
    )
    seqs = doc.get("sequences") or []
    canvases = seqs[0].get("canvases", []) if seqs else []
    for canvas in canvases:
        images = canvas.get("images") or []
        if not images:
            continue
        service = (images[0].get("resource") or {}).get("service") or {}
        sid = ""
        if isinstance(service, dict):
            sid = service.get("@id") or service.get("id") or ""
        if not sid:
            continue
        sd.images.append(ImageData(
            image_service_uri=str(sid),
            canvas_uri=str(canvas.get("@id") or ""),
            width=_as_int(canvas.get("width")),
            height=_as_int(canvas.get("height")),
            label=lang_str(canvas.get("label")),
        ))
    return sd


# --- helpers --------------------------------------------------------

def lang_str(value) -> str:
    """Collapse a IIIF label/summary value to a single string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "@value" in value:                       # v2 {"@value": ..., "@language": ...}
            return str(value["@value"])
        for vals in value.values():                 # v3 language map {lang: [str, ...]}
            if isinstance(vals, list) and vals:
                return str(vals[0])
            if isinstance(vals, str):
                return vals
    if isinstance(value, list) and value:
        return lang_str(value[0])
    return ""


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
