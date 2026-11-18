from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("language/", views.switch_language, name="language"),
    path("login/telegram/start/", views.telegram_start, name="telegram_start"),
    path("login/telegram/", views.telegram_wait, name="telegram"),
    path("login/telegram/status/", views.telegram_status, name="telegram_status"),
]
