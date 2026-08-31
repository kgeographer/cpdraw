from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import TemplateView

from main import views

urlpatterns = [
    path(r'', TemplateView.as_view(template_name="main/index.html"), name="index"),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('draw/', include('main.urls')),

    path('project_create/', views.ProjectCreateView.as_view(), name='project-create'),
    path('project_delete/<int:id>', views.ProjectDeleteView.as_view(), name='project-delete'),
    path('project_update/<int:pk>', views.ProjectUpdateView.as_view(), name='project-update'),
    path('project/<int:pk>/add_source/', views.add_source, name='source-add'),

    path('api/', include('api.urls')),
    path('accounts/', include('accounts.urls')),
    path('admin/', admin.site.urls),
]

# WO-0.2: map_* CRUD, project_download, and the names/ endpoint were removed
# with the Map/Feature/Name models. Source ingest routes arrive later in WO-0.2;
# the tile-serving block below goes with the full Leaflet teardown.
if settings.DEBUG:
    urlpatterns += static(settings.TILES_URL, document_root=settings.TILES_ROOT)
