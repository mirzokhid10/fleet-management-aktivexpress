from .menu import active_key, menu_for


def navigation(request):
    return {"menu": menu_for(request.user), "menu_active": active_key(request.path)}
