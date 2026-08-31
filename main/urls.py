from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.generic.base import TemplateView

from . import views

app_name = 'main'
urlpatterns = [
    path(r'', login_required(TemplateView.as_view(
        template_name="main/draw.html")), name="draw"),
    # WO-0.1 scaffolding — removed when WO-0.3 lands the OpenSeadragon viewer.
    path('_wo01/', TemplateView.as_view(
        template_name="main/wo01_pipeline_check.html"), name="wo01-pipeline-check"),
    path('fetch_projects/', views.fetchProjects, name='fetch-projects'),
]

# WO-0.2: the <int:projid> Draw view, feature_* endpoints, and dl_project
# export were removed with the Map/Feature models.
