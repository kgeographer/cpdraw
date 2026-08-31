import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from main.iiif import normalize, parse_info_json, parse_manifest
from main.iiif.client import FetchResult, sniff_kind
from main.iiif.exceptions import ParseError
from main.iiif.ingest import ingest_source
from main.iiif.parse import detect_version
from main.models import Project, Source

FIX = Path(__file__).parent / "fixtures"
User = get_user_model()


def load(name):
    return json.loads((FIX / name).read_text())


def fetch_result(name, kind=None):
    text = (FIX / name).read_text()
    doc = json.loads(text)
    return FetchResult(
        requested_uri=f"https://example.test/{name}",
        final_uri=f"https://polona.pl/{name}",
        status_code=200,
        content_type="application/json",
        text=text,
        doc=doc,
        kind=kind or sniff_kind(doc),
    )


def fake_fetcher(manifest_fixture, info_fixture=None):
    """A URL-routing fetcher: `.../info.json` -> info_fixture (or FetchError),
    anything else -> manifest_fixture."""
    from main.iiif.exceptions import FetchError

    def _fetch(uri):
        if uri.rstrip("/").endswith("/info.json"):
            if info_fixture is None:
                raise FetchError(f"no info.json fixture for {uri}")
            return fetch_result(info_fixture, "image_service")
        return fetch_result(manifest_fixture, "manifest")

    return _fetch


class SniffTests(TestCase):
    def test_manifest_and_info_json(self):
        self.assertEqual(sniff_kind(load("polona_manifest.json")), "manifest")
        self.assertEqual(sniff_kind(load("polona_info.json")), "image_service")


class NormalizeTests(TestCase):
    def test_lowercase_manifest_type_canonicalised_and_logged(self):
        doc = load("polona_manifest.json")
        self.assertEqual(doc["type"], "manifest")            # fixture really is broken
        out, log = normalize(doc, "https://polona.pl/x")
        self.assertEqual(out["type"], "Manifest")
        self.assertTrue(any(e["rule"] == "type_casing" for e in log))

    def test_correctly_cased_types_are_not_touched(self):
        _, log = normalize(load("polona_manifest.json"), "https://polona.pl/x")
        # exactly one fix: the top-level `type`. Canvas/AnnotationPage are fine.
        self.assertEqual([e for e in log if e["rule"] == "type_casing"].__len__(), 1)

    def test_polona_placeholder_ids_noted(self):
        _, log = normalize(load("polona_manifest.json"), "https://polona.pl/x")
        self.assertTrue(any(e["rule"] == "polona.placeholder_ids" for e in log))

    def test_input_not_mutated(self):
        doc = load("polona_manifest.json")
        normalize(doc, "https://polona.pl/x")
        self.assertEqual(doc["type"], "manifest")


class ParseManifestTests(TestCase):
    def setUp(self):
        self.doc, _ = normalize(load("polona_manifest.json"), "https://polona.pl/x")

    def test_detects_v3(self):
        self.assertEqual(detect_version(self.doc), "3")

    def test_two_canvases_two_images(self):
        self.assertEqual(len(parse_manifest(self.doc).images), 2)

    def test_recto_image_service_and_dims(self):
        recto = parse_manifest(self.doc).images[0]
        self.assertEqual(
            recto.image_service_uri,
            "https://polona.pl/iiif/3/cf2d49d7-1d3a-448d-abb2-190d6bd01af8",
        )
        self.assertEqual((recto.width, recto.height), (15919, 12357))
        self.assertEqual(recto.label, "[1r]")

    def test_source_label_and_metadata(self):
        sd = parse_manifest(self.doc)
        self.assertIn("Galicyja i Lodomeryja", sd.label)
        self.assertEqual(len(sd.metadata), 24)

    def test_no_images_raises(self):
        with self.assertRaises(ParseError):
            parse_manifest({"@context": "http://iiif.io/api/presentation/3/context.json",
                            "type": "Manifest", "items": []})


class ParseInfoJsonTests(TestCase):
    def test_info_json_to_imagedata(self):
        img = parse_info_json(load("polona_info.json"))
        self.assertEqual((img.width, img.height), (15919, 12357))
        self.assertTrue(img.image_service_uri.endswith("cf2d49d7-1d3a-448d-abb2-190d6bd01af8"))


class RumseyV2Tests(TestCase):
    """A clean IIIF Presentation 2 manifest (David Rumsey) — the happy path,
    and a foil to Polona: nothing to normalise."""

    def setUp(self):
        self.doc = load("rumsey_manifest.json")

    def test_sniffed_as_manifest(self):
        self.assertEqual(sniff_kind(self.doc), "manifest")

    def test_detects_v2(self):
        self.assertEqual(detect_version(self.doc), "2")

    def test_clean_manifest_produces_empty_normalization_log(self):
        _, log = normalize(self.doc, "https://www.davidrumsey.com/x")
        self.assertEqual(log, [])

    def test_parse_v2_one_canvas(self):
        sd = parse_manifest(self.doc)
        self.assertEqual(sd.iiif_version, "2")
        self.assertEqual(sd.label, "Europe.")
        self.assertEqual(len(sd.images), 1)
        img = sd.images[0]
        self.assertEqual(
            img.image_service_uri,
            "https://www.davidrumsey.com/luna/servlet/iiif/RUMSEY~8~1~37247~1210240",
        )
        self.assertEqual((img.width, img.height), (6762, 5888))
        self.assertTrue(img.canvas_uri.endswith("/canvas/c1"))

    def test_v2_attribution_becomes_required_statement(self):
        sd = parse_manifest(self.doc)
        self.assertEqual(sd.required_statement["value"],
                         "David Rumsey Historical Map Collection")


class IngestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ingest_tester")
        cls.project = Project.objects.create(owner=cls.user, title="T", label="t")

    def test_polona_manifest_ingest(self):
        src = ingest_source(
            "https://polona.pl/.../manifest",
            project=self.project, owner=self.user,
            fetcher=fake_fetcher("polona_manifest.json", "polona_info.json"),
        )
        self.assertEqual(src.ingest_kind, Source.IngestKind.MANIFEST)
        self.assertEqual(src.iiif_version, "3")
        self.assertEqual(src.images.count(), 2)
        self.assertTrue(src.raw_document)
        self.assertIsNotNone(src.fetched_at)
        self.assertIn("Galicyja i Lodomeryja", src.iiif_label)
        self.assertEqual(len(src.iiif_metadata), 24)
        self.assertTrue(any(e["rule"] == "type_casing" for e in src.normalization_log))

        recto = src.images.get(seq=0)
        self.assertEqual((recto.width, recto.height), (15919, 12357))
        self.assertFalse(recto.needs_metadata)
        self.assertEqual(recto.workstate.status, "unstarted")
        # per-canvas info.json was fetched, cached, and cleared quality:
        self.assertIsNotNone(recto.info_json)
        self.assertEqual(recto.quality_notes, [])

        verso = src.images.get(seq=1)
        self.assertEqual((verso.width, verso.height), (7969, 6235))

    def test_rumsey_v2_manifest_ingest(self):
        # no info.json fixture routed -> quality assessed from manifest w/h alone
        src = ingest_source(
            "https://www.davidrumsey.com/.../manifest",
            project=self.project, owner=self.user,
            fetcher=fake_fetcher("rumsey_manifest.json"),
        )
        self.assertEqual(src.ingest_kind, Source.IngestKind.MANIFEST)
        self.assertEqual(src.iiif_version, "2")
        self.assertEqual(src.images.count(), 1)
        self.assertEqual(src.iiif_label, "Europe.")
        self.assertEqual(src.normalization_log, [])
        self.assertEqual(src.iiif_required_statement["value"],
                         "David Rumsey Historical Map Collection")
        img = src.images.get(seq=0)
        self.assertEqual((img.width, img.height), (6762, 5888))
        self.assertFalse(img.needs_metadata)
        self.assertEqual(img.workstate.status, "unstarted")
        self.assertIsNone(img.info_json)
        self.assertIn("low_res", {n["code"] for n in img.quality_notes})

    def test_rumsey_with_real_info_json_flags_large_tiles(self):
        src = ingest_source(
            "https://www.davidrumsey.com/.../manifest",
            project=self.project, owner=self.user,
            fetcher=fake_fetcher("rumsey_manifest.json", "rumsey_info.json"),
        )
        img = src.images.get(seq=0)
        self.assertIsNotNone(img.info_json)
        self.assertEqual({n["code"] for n in img.quality_notes},
                         {"low_res", "large_tiles"})

    def test_bare_image_service_needs_manual_metadata(self):
        src = ingest_source(
            "https://polona.pl/iiif/3/cf2d49d7",
            project=self.project, owner=self.user,
            fetcher=lambda uri: fetch_result("polona_info.json", "image_service"),
        )
        self.assertEqual(src.ingest_kind, Source.IngestKind.IMAGE_SERVICE)
        self.assertEqual(src.images.count(), 1)
        img = src.images.get(seq=0)
        self.assertTrue(img.needs_metadata)
        self.assertEqual((img.width, img.height), (15919, 12357))

    def test_degrades_when_no_canvas_image_but_service_salvageable(self):
        broken = {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "type": "manifest",
            "label": {"en": ["Broken"]},
            "metadata": [{"label": "x", "value": "y"}],
            "items": [{
                "type": "Canvas",
                "thumbnail": [{"id": "t", "type": "Image", "service": [
                    {"id": "https://img.test/svc", "type": "ImageService3"}]}],
                "items": [{"type": "AnnotationPage", "items": [
                    {"type": "Annotation", "motivation": "painting",
                     "body": {"type": "Image"}}]}],   # no service, no /full/ id
            }],
        }
        fr = FetchResult("u", "u", 200, "application/json", json.dumps(broken), broken, "manifest")
        src = ingest_source("u", project=self.project, owner=self.user, fetcher=lambda uri: fr)
        self.assertEqual(src.images.count(), 1)
        self.assertEqual(src.images.get(seq=0).image_service_uri, "https://img.test/svc")
        self.assertTrue(src.images.get(seq=0).needs_metadata)
        self.assertTrue(any(e["rule"] == "degraded_to_image_service"
                            for e in src.normalization_log))

    def test_non_json_response_raises(self):
        fr = FetchResult("u", "u", 200, "text/html", "<html>nope</html>", None, "unknown")
        with self.assertRaises(ParseError):
            ingest_source("u", project=self.project, owner=self.user, fetcher=lambda uri: fr)
