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
    path('project/<int:pk>/types/', views.project_placetypes, name='project-types'),

    path('api/', include('api.urls')),
    path('accounts/', include('accounts.urls')),
    path('admin/', admin.site.urls),
]

# WO-0.2: map_* CRUD, project_download, the names/ endpoint, and the DEBUG-only
# tile-pyramid route were all removed with the Leaflet-era stack. Source ingest
# routes live in main/urls.py; the OpenSeadragon Draw page arrives in WO-0.3.
