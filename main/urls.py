from django.conf import settings
#from django.conf.urls.static import static
#from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path#, include
from django.views.generic.base import TemplateView

from . import views

app_name='main'
urlpatterns = [
    path(r'', login_required(TemplateView.as_view(
        template_name="main/draw.html")), name="draw"),
    # WO-0.1 scaffolding: smoke-tests the Vite/Svelte/Allmaps build pipeline at
    # /draw/_wo01/. No auth, not in any nav. Removed when WO-0.3 puts the real
    # OpenSeadragon viewer on the Draw page.
    path('_wo01/', TemplateView.as_view(
        template_name="main/wo01_pipeline_check.html"), name="wo01-pipeline-check"),
    path('<int:projid>/', views.DrawView.as_view(), name='draw'),
    path('fetch_projects/', views.fetchProjects, name='fetch-projects'),
    
    path('feature_create/', views.createFeature, name='feature-create'),
    path('feature_delete/', views.deleteFeature, name='feature-delete'),
    path('feature_update/', views.updateFeature, name='feature-update'),
    
    path('dl_project/<str:prj>/<str:format>', views.download_project, name="dl-project"), # 
    #path('dl_map/<int:id>/<str:format>', views.download_map, name="dl-map"), # 
    
]
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
