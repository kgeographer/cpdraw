from django.test import SimpleTestCase

from main.iiif.quality import assess


def codes(notes):
    return {n["code"] for n in notes}


class AssessResolutionTests(SimpleTestCase):
    def test_high_res_is_clean(self):
        self.assertEqual(assess(15919, 12357), [])

    def test_moderate_res_over_10k_is_clean(self):
        self.assertEqual(assess(10388, 8163), [])

    def test_mid_band_is_advisory_only(self):
        notes = assess(6762, 5888)
        self.assertEqual(codes(notes), {"low_res"})
        self.assertEqual(notes[0]["level"], "info")   # shows a ⚠ but does not gate

    def test_very_low_res_gates(self):
        notes = assess(3000, 2400)
        self.assertIn("very_low_res", codes(notes))
        self.assertEqual([n for n in notes if n["code"] == "very_low_res"][0]["level"],
                         "warning")

    def test_missing_dims_no_resolution_note(self):
        self.assertEqual(assess(None, None), [])


class AssessServiceTests(SimpleTestCase):
    LEVEL2_TILED = {
        "protocol": "http://iiif.io/api/image",
        "tiles": [{"width": 256, "scaleFactors": [1, 2, 4, 8]}],
        "profile": ["http://iiif.io/api/image/2/level2.json"],
    }

    def test_tiled_level2_small_tiles_is_clean(self):
        self.assertEqual(assess(15919, 12357, self.LEVEL2_TILED), [])

    def test_not_tiled_warns(self):
        info = {"protocol": "http://iiif.io/api/image", "sizes": [{"width": 1024}]}
        self.assertIn("not_tiled", codes(assess(15919, 12357, info)))

    def test_big_tiles_info_note(self):
        info = dict(self.LEVEL2_TILED, tiles=[{"width": 1536, "scaleFactors": [1, 2, 4]}])
        notes = assess(12000, 9000, info)
        self.assertIn("large_tiles", codes(notes))
        self.assertEqual([n for n in notes if n["code"] == "large_tiles"][0]["level"], "info")

    def test_level0_info_note(self):
        info = dict(self.LEVEL2_TILED, profile=["http://iiif.io/api/image/2/level0.json"])
        self.assertIn("level0", codes(assess(12000, 9000, info)))

    def test_resolution_and_service_notes_combine(self):
        info = dict(self.LEVEL2_TILED, tiles=[{"width": 1536}])
        self.assertEqual(codes(assess(6762, 5888, info)), {"low_res", "large_tiles"})
