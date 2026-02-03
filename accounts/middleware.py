from django.shortcuts import redirect

class OTPRequiredMiddleware:
    """
    Middleware to ensure that users who logged in must verify OTP before accessing any page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip if user is not logged in
        if request.user.is_authenticated:
            otp_verified = request.session.get("otp_verified", False)

            # Paths to ignore (login, OTP page, logout, password reset)
            allowed_paths = [
                "/accounts/login/",
                "/accounts/otp/",
                "/accounts/logout/",
                "/accounts/password-reset/",
                "/accounts/password-reset/done/",
                "/accounts/reset/",
            ]

            if not otp_verified and request.path not in allowed_paths:
                return redirect("verify_otp")

        response = self.get_response(request)
        return response
