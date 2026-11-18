from django.urls import path

from . import views

app_name = "bot"

urlpatterns = [
    path("users/requests/", views.request_list, name="requests"),
    path("users/requests/<int:pk>/approve/", views.approve, name="approve"),
    path("users/requests/<int:pk>/reject/", views.reject, name="reject"),
]
