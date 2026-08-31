"""Retrieve a IIIF document and take a first guess at what it is."""

import json
from dataclasses import dataclass

import requests

from .exceptions import FetchError

USER_AGENT = "CPDraw/0.1 (+https://github.com/kgeographer/cpdraw)"
DEFAULT_TIMEOUT = 20


@dataclass
class FetchResult:
    requested_uri: str
    final_uri: str            # after redirects
    status_code: int
    content_type: str
    text: str                 # body exactly as received
    doc: dict | None          # parsed JSON object, or None if the body isn't one
    kind: str                 # 'manifest' | 'image_service' | 'unknown'


def fetch(uri: str, *, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    headers = {
        "Accept": "application/ld+json, application/json;q=0.9, */*;q=0.1",
        "User-Agent": USER_AGENT,
    }
    try:
        resp = requests.get(uri, headers=headers, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        raise FetchError(f"could not fetch {uri}: {exc}") from exc
    if resp.status_code >= 400:
        raise FetchError(f"{uri} returned HTTP {resp.status_code}")

    text = resp.text
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    doc = parsed if isinstance(parsed, dict) else None

    return FetchResult(
        requested_uri=uri,
        final_uri=str(resp.url),
        status_code=resp.status_code,
        content_type=resp.headers.get("Content-Type", ""),
        text=text,
        doc=doc,
        kind=sniff_kind(doc),
    )


def sniff_kind(doc) -> str:
    """Cheap structural guess. The parsers do the real validation."""
    if not isinstance(doc, dict):
        return "unknown"

    if doc.get("protocol") == "http://iiif.io/api/image":
        return "image_service"

    ctx = doc.get("@context")
    ctx_str = " ".join(ctx) if isinstance(ctx, list) else str(ctx or "")
    if "api/image" in ctx_str and "api/presentation" not in ctx_str:
        return "image_service"
    if "api/presentation" in ctx_str:
        return "manifest"

    type_ = str(doc.get("type") or doc.get("@type") or "").lower()
    if "manifest" in type_ or "items" in doc or "sequences" in doc:
        return "manifest"
    if {"width", "height"} <= doc.keys() and "sizes" in doc:
        return "image_service"
    return "unknown"
