from .menu import MENU, active_key


def navigation(request):
    return {"menu": MENU, "menu_active": active_key(request.path)}
