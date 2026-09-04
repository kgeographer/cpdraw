from django.contrib.auth import get_user_model
from django.test import TestCase

from main.models import (MapImage, MapImagePlacetype, Placetype, Project,
                         ProjectPlacetype, ProjectUser, Source)

User = get_user_model()


def _project(owner, label="p"):
    return Project.objects.create(owner=owner, title=label.title(), label=label)


class ProjectRoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner")
        cls.editor = User.objects.create_user("editor")
        cls.annot = User.objects.create_user("annot")
        cls.stranger = User.objects.create_user("stranger")
        cls.super = User.objects.create_user("root", is_superuser=True)
        cls.p = _project(cls.owner)
        ProjectUser.objects.create(project=cls.p, user=cls.editor, role="editor")
        ProjectUser.objects.create(project=cls.p, user=cls.annot, role="annotator")

    def test_role_of(self):
        self.assertEqual(self.p.role_of(self.owner), "owner")       # FK owner
        self.assertEqual(self.p.role_of(self.editor), "editor")
        self.assertEqual(self.p.role_of(self.annot), "annotator")
        self.assertEqual(self.p.role_of(self.super), "owner")       # superuser
        self.assertIsNone(self.p.role_of(self.stranger))

    def test_can_edit_metadata_is_owner_only(self):
        self.assertTrue(self.p.can_edit_metadata(self.owner))
        self.assertTrue(self.p.can_edit_metadata(self.super))
        self.assertFalse(self.p.can_edit_metadata(self.editor))
        self.assertFalse(self.p.can_edit_metadata(self.annot))

    def test_can_add_sources_and_manage_vocab_are_editor_plus(self):
        for u, ok in [(self.owner, True), (self.editor, True),
                      (self.annot, False), (self.stranger, False)]:
            self.assertEqual(self.p.can_add_sources(u), ok)
            self.assertEqual(self.p.can_manage_vocabulary(u), ok)


class VisibleToTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("a")
        cls.b = User.objects.create_user("b")
        cls.root = User.objects.create_user("root", is_superuser=True)
        cls.pa = _project(cls.a, "pa")
        cls.pb = _project(cls.b, "pb")
        ProjectUser.objects.create(project=cls.pb, user=cls.a, role="annotator")

    def test_owner_and_membership_visible_superuser_sees_all_stranger_none(self):
        self.assertCountEqual(
            Project.objects.visible_to(self.a).values_list("label", flat=True),
            ["pa", "pb"])                       # owns pa, annotator on pb
        self.assertCountEqual(
            Project.objects.visible_to(self.b).values_list("label", flat=True),
            ["pb"])
        self.assertCountEqual(
            Project.objects.visible_to(self.root).values_list("label", flat=True),
            ["pa", "pb"])
        stranger = User.objects.create_user("stranger")
        self.assertEqual(Project.objects.visible_to(stranger).count(), 0)


class MapImagePlacetypeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("u")
        cls.p = _project(cls.user)
        cls.src = Source.objects.create(
            project=cls.p, owner=cls.user, ingest_uri="https://x/m",
            ingest_kind=Source.IngestKind.MANIFEST, iiif_version="3")
        cls.img = MapImage.objects.create(
            source=cls.src, seq=0, image_service_uri="https://x/iiif/a")
        cls.t1 = ProjectPlacetype.objects.create(project=cls.p, source_label="region")
        cls.t2 = ProjectPlacetype.objects.create(project=cls.p, source_label="river")
        cls.t3 = ProjectPlacetype.objects.create(project=cls.p, source_label="mountain")

    def test_no_rows_yields_full_project_vocab(self):
        self.assertCountEqual(self.img.available_placetypes,
                              [self.t1, self.t2, self.t3])

    def test_rows_restrict_to_linked_subset(self):
        MapImagePlacetype.objects.create(image=self.img, placetype=self.t1)
        MapImagePlacetype.objects.create(image=self.img, placetype=self.t2)
        self.assertCountEqual(self.img.available_placetypes, [self.t1, self.t2])

    def test_deleting_projectplacetype_cascades_join_rows(self):
        MapImagePlacetype.objects.create(image=self.img, placetype=self.t1)
        self.t1.delete()
        self.assertFalse(
            MapImagePlacetype.objects.filter(image=self.img).exists())
        # back to "no rows = inherit" -> full remaining vocab
        self.assertCountEqual(self.img.available_placetypes, [self.t2, self.t3])

    def test_image_placetype_pair_is_unique(self):
        from django.db import IntegrityError, transaction
        MapImagePlacetype.objects.create(image=self.img, placetype=self.t1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MapImagePlacetype.objects.create(image=self.img, placetype=self.t1)
