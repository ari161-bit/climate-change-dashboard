ADMIN_GROUP = 'Administrators'
ANALYST_GROUP = 'Analysts'


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists())


def is_analyst(user):
    return user.is_authenticated and user.groups.filter(name=ANALYST_GROUP).exists()


def role_of(user):
    if not user.is_authenticated:
        return ''
    if is_admin(user):
        return 'Administrator'
    if is_analyst(user):
        return 'Analyst'
    return 'Viewer'
