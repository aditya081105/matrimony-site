import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner
from django.urls import reverse
import resend

logger = logging.getLogger(__name__)

# Decoupled thread executor for non-blocking background I/O
_email_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="email_worker")


def _is_testing():
    return 'test' in sys.argv or getattr(settings, 'TESTING', False)


import time

MAX_RETRIES = 3


def _dispatch_email_job(user_email, user_name, verify_link):
    subject = "Verify your email - Siwan Matrimony"
    message = f"""Welcome to Siwan Matrimony, {user_name}!

Please verify your email address to unlock matchmaking and contact requests:

{verify_link}

If you did not register for Siwan Matrimony, please ignore this email.
"""

    for attempt in range(1, MAX_RETRIES + 1):
        # 1. Try standard Django send_mail (Gmail SMTP / Brevo) if configured
        if getattr(settings, 'EMAIL_HOST_USER', None):
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user_email],
                    fail_silently=False,
                )
                logger.info(f"Verification email sent via SMTP to {user_email}")
                print(f"==> Verification email sent via SMTP to {user_email}")
                return True
            except Exception as e:
                logger.warning(f"SMTP send_mail attempt {attempt}/{MAX_RETRIES} failed for {user_email}: {e}")
                if attempt < MAX_RETRIES and not _is_testing():
                    time.sleep(1.5 * attempt)
                continue

        # 2. Try Resend if configured
        if getattr(settings, 'RESEND_API_KEY', None):
            try:
                resend.api_key = settings.RESEND_API_KEY
                from_email = getattr(settings, 'RESEND_FROM_EMAIL', 'onboarding@resend.dev')
                resend.Emails.send({
                    "from": from_email,
                    "to": user_email,
                    "subject": subject,
                    "text": message
                })
                logger.info(f"Verification email sent via Resend to {user_email}")
                print(f"==> Verification email sent via Resend to {user_email}")
                return True
            except Exception as e:
                logger.warning(f"Resend attempt {attempt}/{MAX_RETRIES} failed for {user_email}: {e}")
                if attempt < MAX_RETRIES and not _is_testing():
                    time.sleep(1.5 * attempt)
                continue

        # If neither provider is configured, break out to dev fallback
        break

    # 3. Development / Server log fallback
    print(f"==> VERIFICATION LINK for {user_email}: {verify_link}")
    return False


def send_verification_email(request, user):
    """
    Dispatches email verification.
    In testing: executes synchronously for deterministic assertions.
    In production: executes asynchronously via ThreadPoolExecutor so HTTP workers are never blocked.
    """
    signer = TimestampSigner()
    token = signer.sign(user.id)
    verify_link = request.build_absolute_uri(
        reverse("verify_email", args=[token])
    )
    user_email = user.email
    user_name = user.full_name or user.username

    if _is_testing():
        return _dispatch_email_job(user_email, user_name, verify_link)
    else:
        _email_executor.submit(_dispatch_email_job, user_email, user_name, verify_link)
        return True


def _dispatch_contact_email_job(name, sender_email, message_content):
    subject = f"Contact Form Inquiry - {name}"
    body = f"Name: {name}\nEmail: {sender_email}\n\nMessage:\n{message_content}"
    admin_email = getattr(settings, 'CONTACT_ADMIN_EMAIL', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@siwan-matrimony.com')

    for attempt in range(1, MAX_RETRIES + 1):
        if getattr(settings, 'EMAIL_HOST_USER', None):
            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=False,
                )
                logger.info(f"Contact email sent via SMTP to {admin_email}")
                return True
            except Exception as e:
                logger.warning(f"SMTP contact attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES and not _is_testing():
                    time.sleep(1.5 * attempt)
                continue

        if getattr(settings, 'RESEND_API_KEY', None):
            try:
                resend.api_key = settings.RESEND_API_KEY
                from_email = getattr(settings, 'RESEND_FROM_EMAIL', 'onboarding@resend.dev')
                resend.Emails.send({
                    "from": from_email,
                    "to": admin_email,
                    "subject": subject,
                    "text": body,
                })
                logger.info(f"Contact email sent via Resend to {admin_email}")
                return True
            except Exception as e:
                logger.warning(f"Resend contact attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES and not _is_testing():
                    time.sleep(1.5 * attempt)
                continue

        break

    logger.info(f"==> CONTACT INQUIRY logged: From {sender_email} ({name}): {message_content}")
    return True


def send_contact_email(name, sender_email, message_content):
    """
    Dispatches contact form inquiries.
    Runs asynchronously via ThreadPoolExecutor in production, synchronously in tests.
    """
    if _is_testing():
        return _dispatch_contact_email_job(name, sender_email, message_content)
    else:
        _email_executor.submit(_dispatch_contact_email_job, name, sender_email, message_content)
        return True

