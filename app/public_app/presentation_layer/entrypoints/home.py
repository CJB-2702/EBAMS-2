from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

SESSION_NOTE_KEY = "public_app_note"
NOTE_MAX_LEN = 2000


def _style_login_form(form: AuthenticationForm) -> AuthenticationForm:
    form.fields["username"].widget.attrs.setdefault("class", "input")
    form.fields["password"].widget.attrs.setdefault("class", "input")
    return form


@login_not_required
def public_home(request: HttpRequest) -> HttpResponse:
    """Homepage: login for guests; signed-in users see a short session note area."""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "login":
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                next_url = request.POST.get("next")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}
                ):
                    return redirect(next_url)
                return redirect("public_home")
            _style_login_form(form)
            return render(
                request,
                "pub_home.html",
                {
                    "form": form,
                    "session_note": request.session.get(SESSION_NOTE_KEY, ""),
                },
            )
        if action == "save_note" and request.user.is_authenticated:
            raw = request.POST.get("note", "")
            request.session[SESSION_NOTE_KEY] = raw[:NOTE_MAX_LEN]
            return redirect("public_home")
        return redirect("public_home")

    if request.user.is_authenticated:
        return render(
            request,
            "pub_home.html",
            {"session_note": request.session.get(SESSION_NOTE_KEY, "")},
        )
    form = _style_login_form(AuthenticationForm())
    return render(request, "pub_home.html", {"form": form})
