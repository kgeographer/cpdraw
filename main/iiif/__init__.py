"""IIIF ingest for CPDraw (WO-0.2).

Fetch a IIIF Presentation Manifest or a bare Image service, tolerate real-world
messiness (scoping doc §6a), and materialise it as a Source + one or more
MapImages.

Public entry points:
    fetch(uri)                            -> FetchResult
    normalize(doc, source_uri)            -> (doc, log)
    parse_manifest(doc)                   -> SourceData
    parse_info_json(doc)                  -> ImageData
    ingest_source(uri, project=, owner=)  -> main.models.Source
"""

from .client import FetchResult, fetch
from .exceptions import FetchError, IngestError, ParseError
from .ingest import Preflight, ingest_source, preflight
from .normalize import normalize
from .parse import ImageData, SourceData, parse_info_json, parse_manifest

__all__ = [
    "FetchResult",
    "fetch",
    "FetchError",
    "IngestError",
    "ParseError",
    "ingest_source",
    "preflight",
    "Preflight",
    "normalize",
    "ImageData",
    "SourceData",
    "parse_info_json",
    "parse_manifest",
]
