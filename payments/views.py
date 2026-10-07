import re
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from urllib.parse import quote_plus
from .models import Plan, PaymentOrder


def ensure_default_plans():
    """Seeds default membership plans if they do not exist yet."""
    if not Plan.objects.exists():
        Plan.objects.create(
            code='silver',
            name='Silver Plan',
            price=199.00,
            duration_days=30,
            badge_label='',
            features="Send up to 10 requests per day\nVerified Silver badge on profile\nHighlighted profile visibility\nStandard customer support",
        )
        Plan.objects.create(
            code='gold',
            name='Gold Plan',
            price=399.00,
            duration_days=90,
            badge_label='Popular',
            features="Unlimited contact requests\nVerified Gold badge on profile\nBoosted search & matchmaking visibility\nPriority customer support",
        )
        Plan.objects.create(
            code='diamond',
            name='Diamond VIP',
            price=699.00,
            duration_days=180,
            badge_label='Best Value',
            features="All Gold features included\nTop-of-the-list profile placement\nElite Diamond badge on profile\nRelationship manager profile review",
        )


from core.caching import get_active_plans

def plans_view(request):
    ensure_default_plans()
    plans = get_active_plans()

    user_sub = None
    if request.user.is_authenticated:
        user_sub = getattr(request.user, 'subscription', None)

    return render(request, 'payments/plans.html', {
        'plans': plans,
        'user_sub': user_sub,
    })


@login_required
def checkout_view(request, plan_code):
    ensure_default_plans()
    plan = get_object_or_404(Plan, code=plan_code, is_active=True)

    upi_id = getattr(settings, 'UPI_ID', 'payments@siwanmatrimony')
    upi_name = getattr(settings, 'UPI_NAME', 'Siwan Matrimony')
    transaction_note = f"SiwanMatrimony_{plan.code}_{request.user.id}"

    # Check if a custom uploaded QR code exists in static/images
    custom_qr_image = None
    if (settings.BASE_DIR / 'static' / 'images' / 'upi_qr.png').exists():
        custom_qr_image = 'images/upi_qr.png'
    elif (settings.BASE_DIR / 'static' / 'images' / 'upi_qr.jpg').exists():
        custom_qr_image = 'images/upi_qr.jpg'

    # UPI URI format according to NPCI specifications
    upi_uri = f"upi://pay?pa={upi_id}&pn={quote_plus(upi_name)}&am={plan.price:.2f}&cu=INR&tn={quote_plus(transaction_note)}"
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&margin=10&data={quote_plus(upi_uri)}"

    if request.method == 'POST':
        action = request.POST.get('action', 'submit_utr')
        utr_number = request.POST.get('utr_number', '').strip()

        # Standard 12-character alphanumeric UPI UTR validation
        if not utr_number or not re.fullmatch(r'^[A-Za-z0-9]{12}$', utr_number):
            messages.error(request, "Please enter a valid 12-character alphanumeric UPI reference (UTR) number.")
            return render(request, 'payments/checkout.html', {
                'plan': plan,
                'upi_id': upi_id,
                'upi_name': upi_name,
                'upi_uri': upi_uri,
                'qr_code_url': qr_code_url,
                'custom_qr_image': custom_qr_image,
            })

        try:
            with transaction.atomic():
                # Prevent duplicate UTR submission across active/pending orders
                if PaymentOrder.objects.filter(utr_number=utr_number).exclude(status='rejected').exists():
                    messages.error(request, "This UPI reference (UTR) number has already been submitted for verification.")
                    return render(request, 'payments/checkout.html', {
                        'plan': plan,
                        'upi_id': upi_id,
                        'upi_name': upi_name,
                        'upi_uri': upi_uri,
                        'qr_code_url': qr_code_url,
                        'custom_qr_image': custom_qr_image,
                    })

                order = PaymentOrder.objects.create(
                    user=request.user,
                    plan=plan,
                    amount=plan.price,
                    utr_number=utr_number,
                    payment_method="UPI QR Payment",
                )
        except IntegrityError:
            messages.error(request, "This UPI reference (UTR) number has already been submitted for verification.")
            return render(request, 'payments/checkout.html', {
                'plan': plan,
                'upi_id': upi_id,
                'upi_name': upi_name,
                'upi_uri': upi_uri,
                'qr_code_url': qr_code_url,
                'custom_qr_image': custom_qr_image,
            })

        messages.success(
            request,
            f"Payment submitted successfully (Order #{order.id})! Your transaction is under verification. "
            f"Once verified, your {plan.name} will be active."
        )
        return redirect('payment_history')

    return render(request, 'payments/checkout.html', {
        'plan': plan,
        'upi_id': upi_id,
        'upi_name': upi_name,
        'upi_uri': upi_uri,
        'qr_code_url': qr_code_url,
        'custom_qr_image': custom_qr_image,
    })


@login_required
def payment_history_view(request):
    orders = PaymentOrder.objects.filter(user=request.user).select_related('plan').order_by('-created_at')
    user_sub = getattr(request.user, 'subscription', None)

    return render(request, 'payments/history.html', {
        'orders': orders,
        'user_sub': user_sub,
    })
