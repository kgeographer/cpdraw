class IngestError(Exception):
    """Base class for IIIF ingest failures."""


class FetchError(IngestError):
    """The resource could not be retrieved (network error, non-2xx, timeout)."""


class ParseError(IngestError):
    """Retrieved, but not readable as the expected IIIF type."""
