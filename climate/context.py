from .roles import is_admin, role_of


def nav(request):
    user = request.user
    return {'role': role_of(user), 'is_admin': is_admin(user)} if user.is_authenticated else {}
