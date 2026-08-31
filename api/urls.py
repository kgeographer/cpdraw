# api.urls (WO-0.4)

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("annotations", views.AnnotationViewSet, basename="annotation")
router.register("project-placetypes", views.ProjectPlacetypeViewSet,
                basename="projectplacetype")

urlpatterns = [
    path("api-auth/", include("rest_framework.urls")),
    path("placetypes/search/", views.placetype_search, name="placetype-search"),
    *router.urls,
]
