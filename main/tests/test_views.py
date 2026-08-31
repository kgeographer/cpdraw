from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from main.iiif import Preflight
from main.iiif.ingest import ImagePreflight
from main.iiif.exceptions import FetchError
from main.models import MapImage, Project, Source, WorkState


def _clean_preflight():
    return Preflight("manifest", "3", "Clean",
                     [ImagePreflight(0, "", 15919, 12357, [])])


def _marginal_preflight():
    """A source with a *gating* warning (very low resolution)."""
    return Preflight("manifest", "2", "Marginal", [ImagePreflight(
        0, "sheet 1", 3000, 2400,
        [{"level": "warning", "code": "very_low_res",
          "message": "Very low resolution (3000×2400)."}])])

User = get_user_model()


class ProjectPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("viewer", is_superuser=True)
        cls.project = Project.objects.create(owner=cls.user, title="Galicia", label="galicia")
        cls.src = Source.objects.create(
            project=cls.project, owner=cls.user,
            ingest_uri="https://x/manifest",
            ingest_kind=Source.IngestKind.MANIFEST,
            iiif_version="3", label="galicia-map", title="Galicyja i Lodomeryja",
        )
        cls.recto = MapImage.objects.create(
            source=cls.src, seq=0, label="[1r]",
            image_service_uri="https://x/iiif/a", width=15919, height=12357)
        cls.verso = MapImage.objects.create(
            source=cls.src, seq=1, label="[1v]",
            image_service_uri="https://x/iiif/b", width=6762, height=5888,
            quality_notes=[{"level": "info", "code": "low_res",
                            "message": "Moderate resolution (6762×5888)."}])
        WorkState.objects.create(image=cls.recto, status=WorkState.Status.IN_PROGRESS)
        WorkState.objects.create(image=cls.verso)  # unstarted

    def setUp(self):
        self.client.force_login(self.user)

    def test_project_page_lists_sources_with_image_count(self):
        resp = self.client.get(f"/project_update/{self.project.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["sources"]), 1)
        self.assertEqual(resp.context["sources"][0].image_count, 2)
        self.assertContains(resp, "Galicyja i Lodomeryja")
        self.assertContains(resp, "2 images")
        self.assertContains(resp, "Add source")

    def test_project_page_lists_mapimages_under_source_with_status(self):
        resp = self.client.get(f"/project_update/{self.project.id}")
        self.assertContains(resp, "[1r]")
        self.assertContains(resp, "15919&times;12357")
        self.assertContains(resp, "in progress")
        self.assertContains(resp, "unstarted")

    def test_dashboard_maps_section(self):
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 200)
        images = list(resp.context["map_images"])
        self.assertEqual(len(images), 2)
        self.assertContains(resp, ">Maps<")
        self.assertContains(resp, "galicia-map")
        self.assertContains(resp, "[1r]")
        self.assertContains(resp, "15919&times;12357")
        self.assertContains(resp, "in progress")
        self.assertContains(resp, f'href="/draw/{self.recto.id}/"')
        # the low-res verso carries a quality warning flag; the recto doesn't
        self.assertContains(resp, "Moderate resolution (6762")   # in the ⚠ title=
        self.assertEqual(resp.content.decode().count("&#9888;"), 1)

    def test_draw_header_shows_quality_flag_when_flagged(self):
        clean = self.client.get(f"/draw/{self.recto.id}/")
        self.assertNotContains(clean, "&#9888;")
        flagged = self.client.get(f"/draw/{self.verso.id}/")
        self.assertContains(flagged, "&#9888;")
        self.assertContains(flagged, "Moderate resolution (6762")

    def test_add_source_rejects_empty_uri(self):
        resp = self.client.post(f"/project/{self.project.id}/add_source/", {"uri": ""}, follow=True)
        self.assertRedirects(resp, f"/project_update/{self.project.id}")
        msgs = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("Enter a IIIF" in m for m in msgs))

    @mock.patch("main.views.preflight", side_effect=FetchError("nope: HTTP 404"))
    def test_add_source_reports_fetch_failure(self, _pf):
        resp = self.client.post(
            f"/project/{self.project.id}/add_source/",
            {"uri": "https://polona.pl/bad/manifest"}, follow=True)
        msgs = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("Ingest failed" in m for m in msgs))

    @mock.patch("main.views.preflight", side_effect=lambda uri: _clean_preflight())
    def test_add_source_clean_commits(self, _pf):
        new = Source.objects.create(
            project=self.project, owner=self.user, ingest_uri="https://y/manifest",
            ingest_kind=Source.IngestKind.MANIFEST, iiif_version="3")
        MapImage.objects.create(source=new, seq=0, image_service_uri="https://y/iiif/a")
        with mock.patch("main.views.ingest_source", return_value=new) as ing:
            resp = self.client.post(
                f"/project/{self.project.id}/add_source/",
                {"uri": "https://y/manifest"}, follow=True)
        ing.assert_called_once()
        msgs = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("Added source" in m and "1 image" in m for m in msgs))

    @mock.patch("main.views.ingest_source")
    @mock.patch("main.views.preflight", side_effect=lambda uri: _marginal_preflight())
    def test_add_source_marginal_needs_confirm(self, _pf, ing):
        before = Source.objects.count()
        resp = self.client.post(
            f"/project/{self.project.id}/add_source/",
            {"uri": "https://rumsey/marginal/manifest"}, follow=True)
        ing.assert_not_called()
        self.assertEqual(Source.objects.count(), before)
        msgs = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("looks marginal" in m and "Very low resolution" in m for m in msgs))
        # the URI is echoed back for a one-tick resubmit
        self.assertContains(resp, "rumsey/marginal/manifest")
        self.assertContains(resp, 'name="add_anyway"')

    @mock.patch("main.views.preflight")
    def test_add_source_add_anyway_skips_preflight(self, pf):
        new = Source.objects.create(
            project=self.project, owner=self.user, ingest_uri="https://y/manifest",
            ingest_kind=Source.IngestKind.MANIFEST, iiif_version="3")
        MapImage.objects.create(source=new, seq=0, image_service_uri="https://y/iiif/a")
        with mock.patch("main.views.ingest_source", return_value=new) as ing:
            self.client.post(
                f"/project/{self.project.id}/add_source/",
                {"uri": "https://y/manifest", "add_anyway": "on"}, follow=True)
        pf.assert_not_called()
        ing.assert_called_once()

    def test_add_source_requires_login(self):
        self.client.logout()
        resp = self.client.post(f"/project/{self.project.id}/add_source/", {"uri": "x"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])


class ProjectVocabTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from main.models import Placetype, ProjectPlacetype
        cls.Placetype, cls.ProjectPlacetype = Placetype, ProjectPlacetype
        cls.user = User.objects.create_user("voc", is_superuser=True)
        Placetype.objects.create(aat_id=300387178, term="historical region",
                                 term_full="historical regions", note="")
        Placetype.objects.create(aat_id=300008347, term="inhabited place",
                                 term_full="inhabited places", note="")

    def setUp(self):
        self.client.force_login(self.user)

    def test_project_create_seeds_starter_vocab(self):
        self.client.post("/project_create/",
                         {"title": "Galicia", "label": "gal", "owner": self.user.id})
        proj = Project.objects.get(label="gal")
        pts = list(proj.placetypes.values_list("source_label", flat=True))
        self.assertEqual(len(pts), 5)
        self.assertIn("cultural group", pts)
        hr = proj.placetypes.get(source_label="historical region")
        self.assertEqual(hr.aattype_id, 300387178)      # mapped where the AAT row exists
        cg = proj.placetypes.get(source_label="cultural group")
        self.assertIsNone(cg.aattype_id)                 # unmapped (no Placetype row)

    def test_add_and_remove_type(self):
        proj = Project.objects.create(owner=self.user, title="P", label="p")
        r = self.client.post(f"/project/{proj.id}/types/",
                             {"source_label": "peoples"}, follow=True)
        self.assertContains(r, "peoples")
        pt = proj.placetypes.get(source_label="peoples")
        self.assertIsNone(pt.aattype_id)

        self.client.post(f"/project/{proj.id}/types/",
                         {"source_label": "region", "aattype": "300387178"})
        self.assertEqual(proj.placetypes.get(source_label="region").aattype_id, 300387178)

        self.client.post(f"/project/{proj.id}/types/", {"delete": pt.id})
        self.assertFalse(proj.placetypes.filter(source_label="peoples").exists())


class DrawViewTests(ProjectPageTests):
    def test_draw_page_renders_with_iiif_info_url_and_header(self):
        resp = self.client.get(f"/draw/{self.recto.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["iiif_info_url"], "https://x/iiif/a/info.json")
        self.assertContains(resp, 'id="cpdraw-draw-root"')
        self.assertContains(resp, 'data-iiif="https://x/iiif/a/info.json"')
        self.assertContains(resp, "galicia-map")             # header (Source __str__)
        self.assertContains(resp, "[1r]")
        self.assertContains(resp, "15919&times;12357")
        self.assertContains(resp, 'href="/project_update/{}"'.format(self.project.id))

    def test_draw_info_url_strips_trailing_slash(self):
        self.recto.image_service_uri = "https://x/iiif/a/"
        self.recto.save(update_fields=["image_service_uri"])
        resp = self.client.get(f"/draw/{self.recto.id}/")
        self.assertEqual(resp.context["iiif_info_url"], "https://x/iiif/a/info.json")

    def test_draw_page_404_for_unknown_image(self):
        self.assertEqual(self.client.get("/draw/999999/").status_code, 404)

    def test_draw_page_requires_login(self):
        self.client.logout()
        resp = self.client.get(f"/draw/{self.recto.id}/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])

    def test_bare_draw_redirects_to_dashboard(self):
        resp = self.client.get("/draw/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/dashboard/")
