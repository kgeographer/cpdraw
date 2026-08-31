"""Ingest a IIIF Manifest or Image service into a project from the CLI.

    python manage.py ingest_source <uri> --project <label> [--as <username>]
    python manage.py ingest_source <uri> --project <label> --from-file path/to/manifest.json

`--from-file` skips the network and reads the document from disk, recording
<uri> as the source's ingest_uri (handy against saved fixtures).
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from main.iiif import ingest_source
from main.iiif.client import FetchResult, sniff_kind
from main.iiif.exceptions import IngestError
from main.models import Project

User = get_user_model()


class Command(BaseCommand):
    help = "Fetch a IIIF Manifest or Image service and create a Source + MapImages."

    def add_arguments(self, parser):
        parser.add_argument("uri")
        parser.add_argument("--project", required=True, help="Project.label")
        parser.add_argument("--as", dest="username", default=None,
                            help="owner username (default: the project owner)")
        parser.add_argument("--from-file", dest="from_file", default=None,
                            help="read the document from this path instead of fetching")

    def handle(self, *args, uri, project, username, from_file, **opts):
        try:
            proj = Project.objects.get(label=project)
        except Project.DoesNotExist:
            raise CommandError(f"no Project with label {project!r}")

        owner = proj.owner
        if username:
            try:
                owner = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"no user {username!r}")

        fetcher = _file_fetcher(uri, from_file) if from_file else None

        try:
            kwargs = {"project": proj, "owner": owner}
            if fetcher:
                kwargs["fetcher"] = fetcher
            src = ingest_source(uri, **kwargs)
        except IngestError as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(
            f"Source #{src.pk}  {src}  "
            f"({src.get_ingest_kind_display()}, IIIF v{src.iiif_version})"
        ))
        for mi in src.images.all():
            self.stdout.write(
                f"  #{mi.seq}  {mi.image_service_uri}  "
                f"{mi.width}x{mi.height}  needs_metadata={mi.needs_metadata}"
            )
        for entry in src.normalization_log:
            self.stdout.write(self.style.WARNING(f"  ~ {entry['rule']}: {entry['note']}"))


def _file_fetcher(uri, path):
    text = Path(path).read_text()
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    doc = doc if isinstance(doc, dict) else None
    result = FetchResult(
        requested_uri=uri, final_uri=uri, status_code=200,
        content_type="application/json", text=text, doc=doc,
        kind=sniff_kind(doc),
    )
    return lambda _uri: result
