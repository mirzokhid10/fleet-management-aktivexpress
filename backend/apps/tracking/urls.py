from django.urls import path

from . import views

app_name = "tracking"

urlpatterns = [
    path("map/", views.live_map, name="map"),
    path("map/data/", views.live_map_data, name="map_data"),
    path("trips/", views.trip_list, name="trips"),
]
