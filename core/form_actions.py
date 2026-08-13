"""Helpers for the multi-action save buttons used on data-entry forms.

Forms submit a `_action` field with one of:

* ``save``              -> default behaviour (back to list/detail page)
* ``save_add_another``  -> save, then reopen a blank create form
* ``save_continue``     -> save, then stay on the edit form for the record
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

ACTION_FIELD = "_action"
ACTION_SAVE = "save"
ACTION_ADD_ANOTHER = "save_add_another"
ACTION_CONTINUE = "save_continue"


def get_form_action(request):
    return (request.POST.get(ACTION_FIELD) or ACTION_SAVE).strip()


def _resolve(url, *args, **kwargs):
    """Accept either an absolute path or a URL name."""
    if not url:
        return None

    if url.startswith("/"):
        return url

    try:
        return reverse(url, args=args or None, kwargs=kwargs or None)
    except NoReverseMatch:
        return None


def resolve_post_save_redirect(
    request,
    obj=None,
    *,
    default_url,
    default_kwargs=None,
    create_url=None,
    edit_url_name=None,
    edit_kwargs=None,
    label="Record",
):
    """Return the redirect response matching the clicked save button."""

    action = get_form_action(request)

    if action == ACTION_ADD_ANOTHER:
        target = _resolve(create_url) or request.path
        messages.success(request, f"{label} saved. You can add another one.")
        return redirect(target)

    if action == ACTION_CONTINUE:
        kwargs = edit_kwargs
        if kwargs is None and obj is not None and getattr(obj, "pk", None):
            kwargs = {"pk": obj.pk}

        target = _resolve(edit_url_name, **(kwargs or {})) if edit_url_name else None

        if target:
            messages.success(request, f"{label} saved. You are still editing it.")
            return redirect(target)

    return redirect(_resolve(default_url, **(default_kwargs or {})) or default_url)
