from django.urls import path
from .views import login_view, verify_otp, resend_otp, CustomPasswordResetView, invite_user, accept_invite, profile_view, terms_of_service, accept_terms
from django.contrib.auth import views as auth_views
from .forms import StyledPasswordResetForm, StyledSetPasswordForm
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("profile/", profile_view, name="profile"),
    path("terms-of-service/", terms_of_service, name="terms"),
    path("accept-terms/", accept_terms, name="accept-terms"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/accounts/login"), name="logout"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("resend-otp/", resend_otp, name="resend_otp"),
    path(
        "password-reset/",
        CustomPasswordResetView.as_view(
            form_class=StyledPasswordResetForm
        ),
        name="password_reset"
    ),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"
    ), name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        form_class=StyledSetPasswordForm,
        success_url="/accounts/password-reset-complete/"
    ), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"
    ), name="password_reset_complete"),
    path(
        "accept-invite/<uuid:token>/",
        accept_invite,
        name="accept_invite"
    ),
    path(
        "invite/",
        invite_user,
        name="invite_user"
    ),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

]
