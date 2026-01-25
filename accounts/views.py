from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib import messages
from django.contrib.auth import login
from .models import EmailOTP, User, UserInvite
from .forms import LoginForm, InviteUserForm
import random
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.views import PasswordResetView
from django.utils.html import strip_tags
from django.urls import reverse_lazy
import datetime
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone


MAX_ATTEMPTS = 5

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            user = authenticate(request, email=email, password=password)

            if user:
                # 🔐 OTP REQUIRED
                EmailOTP.objects.filter(user=user).delete()

                otp = str(random.randint(100000, 999999))
                EmailOTP.objects.create(user=user, otp=otp)

                send_otp_email(user, otp)
                messages.success(request, "An OTP has been sent to your email.")

                request.session["otp_user_id"] = user.id
                return redirect("verify_otp")

            else:
                messages.error(request, "Invalid username or password")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})

def resend_otp(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    user = User.objects.get(id=user_id)

    # Delete old OTPs
    EmailOTP.objects.filter(user=user).delete()

    # Generate new OTP
    otp = str(random.randint(100000, 999999))
    EmailOTP.objects.create(user=user, otp=otp)

    send_otp_email(user, otp)
    messages.success(request, "A new OTP has been sent to your email.")
    return redirect("verify_otp")

def verify_otp(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    otp_obj = EmailOTP.objects.filter(user_id=user_id).order_by('-created_at').first()
    if not otp_obj:
        messages.error(request, "No OTP found. Please resend OTP.")
        return redirect("resend_otp")

    if request.method == "POST":
        otp_input = request.POST.get("otp")
        if otp_obj.is_expired():
            messages.error(request, "OTP expired. Please resend OTP.")
            return redirect("resend_otp")

        if otp_obj.attempts >= MAX_ATTEMPTS:
            messages.error(request, "Maximum attempts reached. OTP locked. Resend OTP.")
            return redirect("resend_otp")

        if otp_input == otp_obj.otp:
            # Successful login
            user = otp_obj.user
            login(request, user)
            request.session['otp_verified'] = True

            # Clear session and OTP
            request.session.pop("otp_user_id")
            otp_obj.delete()
            messages.success(request, "Login successful!")
            return redirect("index")  # Default landing page

        else:
            otp_obj.attempts += 1
            otp_obj.save()
            messages.error(request, f"Invalid OTP. Attempts left: {MAX_ATTEMPTS - otp_obj.attempts}")

    context = {
        "email": otp_obj.user.email
    }
    return render(request, "accounts/verify_otp.html", context)


def send_otp_email(user, otp):
    subject = "Your PowerPayAfrica OTP"
    from_email = None  # will use DEFAULT_FROM_EMAIL
    to_email = [user.email]

    # Render HTML content
    html_content = render_to_string("accounts/otp_email.html", {"user": user, "otp": otp})

    msg = EmailMultiAlternatives(subject, otp, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

class CustomPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    html_email_template_name = "accounts/password_reset_email.html"  # HTML template
    success_url = reverse_lazy("password_reset_done")
    from_email = None

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        html_body = render_to_string(email_template_name, {**context, "year": datetime.date.today()})
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject="Reset Your PowerPay Password",
            body=text_body,
            from_email=self.from_email,
            to=[to_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()


def send_invite_email(invite):
    invite_url = f"{settings.SITE_URL}/accounts/accept-invite/{invite.token}/"

    subject = "You're invited to PowerPay Africa"
    html_content = render_to_string("accounts/user_invite.html", {
        "invite_url": invite_url,
        "organization": invite.organization.name,
    })

    msg = EmailMultiAlternatives(
        subject,
        strip_tags(html_content),
        settings.DEFAULT_FROM_EMAIL,
        [invite.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


@login_required
def invite_user(request):
    if not (request.user.is_superuser or request.user.role == "admin"):
        messages.error(request, "You are not allowed to invite users.")
        return redirect("index")

    if request.method == "POST":
        form = InviteUserForm(request.POST, user=request.user)
        if form.is_valid():
            invite = form.save(commit=False)
            invite.invited_by = request.user

            if not request.user.is_superuser:
                invite.organization = request.user.organization

            invite.save()

            send_invite_email(invite)
            messages.success(request, "Invitation sent successfully.")
            return redirect("invite_user")
    else:
        form = InviteUserForm(user=request.user)

    return render(request, "accounts/invite_user.html", {
        "form": form,
        "title": "Invite User",
    })


def accept_invite(request, token):
    invite = get_object_or_404(UserInvite, token=token)

    if not invite.is_valid():
        messages.error(request, "Invite link expired or already used.")
        return redirect("login")

    if request.method == "POST":
        password = request.POST.get("password")

        user = User.objects.create_user(
            email=invite.email,
            password=password,
            organization=invite.organization,
            role=invite.role,
            is_staff=invite.role in ["admin", "staff"],
        )

        invite.is_used = True
        invite.save()

        login(request, user)
        return redirect("index")

    return render(request, "accounts/accept_invite.html")
