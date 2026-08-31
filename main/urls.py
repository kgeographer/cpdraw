from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = 'main'
urlpatterns = [
    # bare /draw/ has no map to show — send it to the dashboard so the navbar
    # link still resolves.
    path(r'', login_required(RedirectView.as_view(
        pattern_name='dashboard', permanent=False)), name='draw'),
    path('fetch_projects/', views.fetchProjects, name='fetch-projects'),
    path('<int:image_id>/', views.DrawView.as_view(), name='draw-image'),
]
