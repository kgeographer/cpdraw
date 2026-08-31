# api.urls

from django.urls import path, include

# WO-0.2: feature/geom routes removed with the Feature model. The browsable-API
# login stays; annotation endpoints arrive in WO-0.4.
urlpatterns = [
    path('api-auth/', include('rest_framework.urls')),
]
