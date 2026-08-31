from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from main.models import (Annotation, MapImage, Placetype, Project,
                         ProjectPlacetype, Source, WorkState)

User = get_user_model()

W3C_POLYGON = {
    "id": "anno-1",
    "target": {"selector": {"type": "SvgSelector", "value": "<svg><polygon/></svg>",
                            "geometry": {"bounds": {"minX": 10, "minY": 20,
                                                    "maxX": 110, "maxY": 220}}}},
}


class ApiBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("anno_user")
        cls.other = User.objects.create_user("other_user")
        cls.project = Project.objects.create(owner=cls.user, title="P", label="p")
        cls.src = Source.objects.create(
            project=cls.project, owner=cls.user, ingest_uri="https://x/m",
            ingest_kind=Source.IngestKind.MANIFEST, iiif_version="3")
        cls.image = MapImage.objects.create(
            source=cls.src, seq=0, image_service_uri="https://x/iiif/a",
            width=1000, height=800)
        WorkState.objects.create(image=cls.image)
        cls.aat = Placetype.objects.create(
            aat_id=300387178, term="historical region", term_full="historical regions",
            note="")
        cls.ptype = ProjectPlacetype.objects.create(
            project=cls.project, source_label="region", aattype=cls.aat)

    def setUp(self):
        self.client.force_authenticate(self.user)


class AnnotationApiTests(ApiBase):
    def _create(self, **over):
        payload = {"image": self.image.id, "geometry_type": "polygon",
                   "feature_role": "region", "name": "Teke",
                   "placetype": self.ptype.id, "w3c": W3C_POLYGON}
        payload.update(over)
        return self.client.post("/api/annotations/", payload, format="json")

    def test_create_sets_provenance_bbox_and_advances_workstate(self):
        r = self._create()
        self.assertEqual(r.status_code, 201, r.content)
        anno = Annotation.objects.get(pk=r.data["id"])
        self.assertEqual(anno.created_by, self.user)
        self.assertEqual(anno.bbox, [10.0, 20.0, 110.0, 220.0])
        self.image.workstate.refresh_from_db()
        self.assertEqual(self.image.workstate.status, WorkState.Status.IN_PROGRESS)

    def test_list_requires_image_param(self):
        self._create()
        self.assertEqual(self.client.get("/api/annotations/").data, [])
        scoped = self.client.get(f"/api/annotations/?image={self.image.id}")
        self.assertEqual(len(scoped.data), 1)

    def test_list_scoped_to_image(self):
        self._create()
        img2 = MapImage.objects.create(source=self.src, seq=1,
                                       image_service_uri="https://x/iiif/b")
        self.assertEqual(
            self.client.get(f"/api/annotations/?image={img2.id}").data, [])

    def test_update_sets_modified_by(self):
        anno_id = self._create().data["id"]
        self.client.force_authenticate(self.other)
        r = self.client.patch(f"/api/annotations/{anno_id}/",
                              {"name": "Teke tribe"}, format="json")
        self.assertEqual(r.status_code, 200)
        anno = Annotation.objects.get(pk=anno_id)
        self.assertEqual(anno.name, "Teke tribe")
        self.assertEqual(anno.modified_by, self.other)

    def test_delete(self):
        anno_id = self._create().data["id"]
        self.assertEqual(
            self.client.delete(f"/api/annotations/{anno_id}/").status_code, 204)
        self.assertFalse(Annotation.objects.filter(pk=anno_id).exists())

    def test_placetype_must_belong_to_project(self):
        other_proj = Project.objects.create(owner=self.user, title="Q", label="q")
        alien = ProjectPlacetype.objects.create(project=other_proj, source_label="x")
        r = self._create(placetype=alien.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("placetype", r.data)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(f"/api/annotations/?image={self.image.id}").status_code, 403)


class ProjectPlacetypeApiTests(ApiBase):
    def test_create_with_and_without_aat(self):
        r = self.client.post("/api/project-placetypes/",
                             {"project": self.project.id, "source_label": "peoples"},
                             format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.data["aattype"])

        r = self.client.post("/api/project-placetypes/",
                             {"project": self.project.id, "source_label": "region",
                              "aattype": 300387178}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["aattype"], 300387178)
        self.assertEqual(r.data["aat_term"], "historical region")

    def test_list_requires_project_param(self):
        self.assertEqual(self.client.get("/api/project-placetypes/").data, [])
        scoped = self.client.get(f"/api/project-placetypes/?project={self.project.id}")
        self.assertEqual(len(scoped.data), 1)


class PlacetypeSearchTests(ApiBase):
    def test_short_query_returns_empty(self):
        self.assertEqual(self.client.get("/api/placetypes/search/?q=h").data, [])

    def test_matches_term_substring(self):
        r = self.client.get("/api/placetypes/search/?q=histor")
        self.assertEqual(r.data[0]["aat_id"], 300387178)
