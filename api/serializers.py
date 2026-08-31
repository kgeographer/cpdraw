# api.serializers (WO-0.4)

from rest_framework import serializers

from main.models import Annotation, Placetype, ProjectPlacetype


def _bbox_from_w3c(w3c):
    """Best-effort [x0, y0, x1, y1] from an Annotorious annotation, else None."""
    try:
        geom = w3c["target"]["selector"]["geometry"]
    except (KeyError, TypeError):
        return None
    b = geom.get("bounds") if isinstance(geom, dict) else None
    if isinstance(b, dict) and {"minX", "minY", "maxX", "maxY"} <= b.keys():
        return [float(b["minX"]), float(b["minY"]), float(b["maxX"]), float(b["maxY"])]
    pts = geom.get("points") if isinstance(geom, dict) else None
    if isinstance(pts, list) and pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
    return None


class AnnotationSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.username")
    modified_by = serializers.ReadOnlyField(source="modified_by.username")

    class Meta:
        model = Annotation
        fields = ("id", "image", "geometry_type", "feature_role",
                  "name", "name_normalized", "placetype", "certainty", "when",
                  "w3c", "bbox", "created_by", "modified_by", "created", "modified")
        read_only_fields = ("bbox", "created", "modified")

    def validate(self, data):
        pt = data.get("placetype") or getattr(self.instance, "placetype", None)
        image = data.get("image") or getattr(self.instance, "image", None)
        if pt and image and pt.project_id != image.source.project_id:
            raise serializers.ValidationError(
                {"placetype": "not in this image’s project vocabulary"})
        return data

    def create(self, validated):
        validated["bbox"] = _bbox_from_w3c(validated.get("w3c"))
        return super().create(validated)

    def update(self, instance, validated):
        if "w3c" in validated:
            validated["bbox"] = _bbox_from_w3c(validated["w3c"])
        return super().update(instance, validated)


class ProjectPlacetypeSerializer(serializers.ModelSerializer):
    aattype = serializers.SlugRelatedField(
        slug_field="aat_id", queryset=Placetype.objects.all(),
        required=False, allow_null=True)
    aat_term = serializers.ReadOnlyField()

    class Meta:
        model = ProjectPlacetype
        fields = ("id", "project", "source_label", "aattype", "aat_term")
