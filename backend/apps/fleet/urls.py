from django.urls import path

from . import views

app_name = "fleet"

urlpatterns = [
    path("vehicles/", views.vehicle_list, name="vehicles"),
    path("vehicles/import/", views.import_upload, name="import"),
    path("vehicles/import/confirm/", views.import_confirm, name="import_confirm"),
    path("vehicles/import/template.xlsx", views.import_template, name="import_template"),
    path("drivers/", views.driver_list, name="drivers"),
    path("shifts/", views.shift_list, name="shifts"),
    path("shifts/<int:pk>/end/", views.shift_end, name="shift_end"),
]
