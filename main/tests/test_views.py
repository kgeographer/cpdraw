from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from main.iiif.exceptions import FetchError
from main.models import MapImage, Project, Source, WorkState

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
            image_service_uri="https://x/iiif/b", width=50, height=40)
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
        # "Open" is present but inert until WO-0.3
        self.assertContains(resp, 'title="opens in the viewer')
        self.assertNotContains(resp, "/draw/{}/".format(self.recto.id))

    def test_add_source_rejects_empty_uri(self):
        resp = self.client.post(f"/project/{self.project.id}/add_source/", {"uri": ""}, follow=True)
        self.assertRedirects(resp, f"/project_update/{self.project.id}")
        msgs = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("Enter a IIIF" in m for m in msgs))

    @mock.patch("main.views.ingest_source", side_effect=FetchError("nope: HTTP 404"))
    def test_add_source_reports_ingest_failure(self, _ingest):
        resp = self.client.post(
            f"/project/{self.project.id}/add_source/",
            {"uri": "https://polona.pl/bad/manifest"}, follow=True)
        msgs = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("Ingest failed" in m for m in msgs))

    def test_add_source_success_message(self):
        new = Source.objects.create(
            project=self.project, owner=self.user, ingest_uri="https://y/manifest",
            ingest_kind=Source.IngestKind.MANIFEST, iiif_version="3")
        MapImage.objects.create(source=new, seq=0, image_service_uri="https://y/iiif/a")
        with mock.patch("main.views.ingest_source", return_value=new) as ing:
            resp = self.client.post(
                f"/project/{self.project.id}/add_source/",
                {"uri": "https://y/manifest"}, follow=True)
        ing.assert_called_once()
        _, kwargs = ing.call_args
        self.assertEqual(kwargs["project"], self.project)
        self.assertEqual(kwargs["owner"], self.user)
        msgs = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("Added source" in m and "1 image" in m for m in msgs))

    def test_add_source_requires_login(self):
        self.client.logout()
        resp = self.client.post(f"/project/{self.project.id}/add_source/", {"uri": "x"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])
