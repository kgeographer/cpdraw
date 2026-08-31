"""Load the LPF-supported AAT feature-type vocabulary into the Placetype table.

    python manage.py load_aat_feature_types

Source: main/data/feature-types-AAT_20230609.tsv, a verbatim copy of
github.com/LinkedPasts/linked-places-format/feature-types-AAT_20230609.tsv —
the subset of Getty AAT that LPF / WHG accept. Idempotent; safe to re-run.
"""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from main.models import Placetype

TSV = Path(__file__).resolve().parents[2] / "data" / "feature-types-AAT_20230609.tsv"


class Command(BaseCommand):
    help = "Populate Placetype from the LPF AAT feature-types TSV (idempotent)."

    def handle(self, *args, **opts):
        created = updated = skipped = 0
        with TSV.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                aat_id = (row.get("aat_id") or "").strip()
                if not aat_id:                       # branch-header rows
                    skipped += 1
                    continue
                parent = (row.get("parent") or "").strip()
                # (the upstream TSV has one duplicate aat_id — 300006084, "dam"
                #  and "aqueduct"; update_or_create keeps whichever comes last.)
                _, was_created = Placetype.objects.update_or_create(
                    aat_id=int(aat_id),
                    defaults={
                        "parent_id": int(parent) if parent else None,
                        "term": (row.get("term") or "").strip(),
                        "term_full": (row.get("term_full") or "").strip()[:100],
                        "note": (row.get("note") or "").strip(),
                    },
                )
                created += was_created
                updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f"Placetype: {created} created, {updated} updated "
            f"({skipped} header rows skipped). Total {Placetype.objects.count()}."
        ))
