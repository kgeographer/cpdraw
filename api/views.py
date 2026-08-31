# api.views (WO-0.4)

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from main.models import Annotation, Placetype, ProjectPlacetype, WorkState
from .serializers import AnnotationSerializer, ProjectPlacetypeSerializer


class AnnotationViewSet(viewsets.ModelViewSet):
    """CRUD for image-space annotations. `list` requires ?image=<id>."""
    serializer_class = AnnotationSerializer

    def get_queryset(self):
        qs = (Annotation.objects
              .select_related("image", "image__source", "placetype",
                              "created_by", "modified_by")
              .order_by("created"))
        image = self.request.query_params.get("image")
        if image:
            return qs.filter(image_id=image)
        if self.action == "list":
            return qs.none()
        return qs

    def perform_create(self, serializer):
        anno = serializer.save(created_by=self.request.user)
        ws, _ = WorkState.objects.get_or_create(image=anno.image)
        if ws.status == WorkState.Status.UNSTARTED:
            ws.status = WorkState.Status.IN_PROGRESS
            ws.save(update_fields=["status", "modified"])

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)


class ProjectPlacetypeViewSet(viewsets.ModelViewSet):
    """A project's own place-type vocabulary. `list` requires ?project=<id>."""
    serializer_class = ProjectPlacetypeSerializer

    def get_queryset(self):
        qs = ProjectPlacetype.objects.select_related("aattype").order_by("source_label")
        project = self.request.query_params.get("project")
        return qs.filter(project_id=project) if project else qs.none()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def placetype_search(request):
    """AAT autocomplete for the project-vocab 'add type' form."""
    q = (request.query_params.get("q") or "").strip()
    hits = []
    if len(q) >= 2:
        hits = list(Placetype.objects
                    .filter(term__icontains=q)
                    .order_by("term")
                    .values("aat_id", "term", "term_full")[:20])
    return Response(hits)
