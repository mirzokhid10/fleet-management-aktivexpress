from django.urls import path

from . import views

app_name = "tracking"

urlpatterns = [
    path("map/", views.live_map, name="map"),
]
