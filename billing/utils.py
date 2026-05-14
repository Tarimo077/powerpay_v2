from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from xhtml2pdf import pisa
from io import BytesIO
from django.conf import settings
import os
from notifications.utils import notify


def generate_pdf(invoice):
    html = render_to_string("billing/invoice_pdf.html", {
        "invoice": invoice,
        "STATIC_ROOT": os.path.join(settings.BASE_DIR, "static")
    })

    result = BytesIO()

    pdf = pisa.CreatePDF(
        src=html,
        dest=result
    )

    if pdf.err:
        return None

    return result.getvalue()

def generate_receipt_pdf(receipt):
    html = render_to_string(
        "billing/receipt_pdf.html",
        {
            "receipt": receipt,
            "STATIC_ROOT": os.path.join(
                settings.BASE_DIR,
                "static"
            )
        }
    )

    result = BytesIO()

    pdf = pisa.CreatePDF(
        src=html,
        dest=result
    )

    if pdf.err:
        return None

    return result.getvalue()


def send_invoice(invoice, user):
    # ✅ Safety check
    if not invoice.organization or not invoice.organization.email:
        if user:
            notify(user, "EMAIL FAILURE", f"An email for the organization: { invoice.organization.name } could not be found", "error")
        return False

    # ✅ Generate PDF
    pdf = generate_pdf(invoice)

    # ✅ Email content (HTML)
    html_body = render_to_string("billing/invoice_email.html", {
        "invoice": invoice
    })

    # ✅ Plain text fallback
    text_body = strip_tags(html_body)

    # ✅ Email setup (same pattern as your working code)
    msg = EmailMultiAlternatives(
        subject=f"Invoice {invoice.invoice_number}",
        body=text_body,
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        to=[invoice.organization.email],
    )

    # ✅ Attach HTML version
    msg.attach_alternative(html_body, "text/html")

    # ✅ Attach PDF
    if pdf:
        msg.attach(
            f"{invoice.invoice_number}.pdf",
            pdf,
            "application/pdf"
        )
    else:
        print("⚠️ PDF generation failed")

    # ✅ Send
    try:
        msg.send()
        if user:
            notify(user, "EMAIL SUCCESS", f"Invoice { invoice.invoice_number } was sent successfully to the organization: { invoice.organization.name } via {invoice.organization.email}.", "success")
        return True
    except Exception as e:
        print("❌ Email failed:", str(e))
        return False

def send_invoice_to_org(invoice, user):
    send_invoice(invoice, user)


def send_pdf_email(subject, html_body, text_body, recipients, attachment_name, pdf_bytes):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=None,
        to=recipients,
    )
    msg.attach_alternative(html_body, "text/html")

    if pdf_bytes:
        msg.attach(attachment_name, pdf_bytes, "application/pdf")

    msg.send()
