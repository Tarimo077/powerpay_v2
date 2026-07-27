from django.shortcuts import redirect

class OTPRequiredMiddleware:
    """
    Middleware to ensure that users who logged in must verify OTP before accessing any page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            otp_verified = request.session.get("otp_verified", False)

            allowed_paths = [
                "/accounts/login/",
                "/accounts/verify-otp/",
                "/accounts/resend-otp/",
                "/accounts/logout/",
                "/accounts/password-reset/",
                "/accounts/password-reset/done/",
                "/accounts/reset/",
                "/accounts/terms-of-service/",
                "/accounts/accept-terms/",
            ]

            if not otp_verified and request.path not in allowed_paths:
                return redirect("verify_otp")

            if otp_verified and not request.user.terms_accepted:
                if request.path not in allowed_paths:
                    return redirect("accept-terms")

        response = self.get_response(request)
        return response
