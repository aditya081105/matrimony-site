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


def _dispatch_email_job(user_email, user_name, verify_link):
    subject = "Verify your email - Siwan Matrimony"
    message = f"""Welcome to Siwan Matrimony, {user_name}!

Please verify your email address to unlock matchmaking and contact requests:

{verify_link}

If you did not register for Siwan Matrimony, please ignore this email.
"""

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
            logger.error(f"SMTP send_mail error for {user_email}: {e}")
            print(f"SMTP send_mail error: {e}")

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
            logger.error(f"Resend error for {user_email}: {e}")
            print(f"Resend error: {e}")

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
