"""Friendly CSRF failure: an old/expired form token sends the user back to the page with a fresh one."""
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views.csrf import csrf_failure as django_csrf_failure


def csrf_failure(request, reason=""):
    path = request.path
    is_api = "/api/" in path or request.headers.get("Accept", "").startswith("application/json")
    if request.method == "POST" and not is_api:
        messages.warning(request, "Your page was out of date, so we refreshed it. Please try again.")
        return HttpResponseRedirect(path)
    return django_csrf_failure(request, reason)
