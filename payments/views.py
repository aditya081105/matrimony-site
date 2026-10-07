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
            features="Send up to 10 requests per day\nDirect profile contact unlock (5/month)\nVerified Silver badge on profile\nStandard customer support",
        )
        Plan.objects.create(
            code='gold',
            name='Gold Plan',
            price=399.00,
            duration_days=90,
            badge_label='Most Popular',
            features="Unlimited contact requests\nDirectly unlock phone & email on all profiles\nGold VIP badge on profile ⭐\nBoosted search & matchmaking visibility\nPriority customer support",
        )
        Plan.objects.create(
            code='diamond',
            name='Diamond VIP',
            price=699.00,
            duration_days=180,
            badge_label='Best Value',
            features="All Gold features included\nTop-of-the-list profile placement\nDiamond VIP badge 💎\nUnlimited contact views\nRelationship manager profile review",
        )


def plans_view(request):
    ensure_default_plans()
    plans = Plan.objects.filter(is_active=True).order_by('price')

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

    # UPI URI format according to NPCI specifications
    upi_uri = f"upi://pay?pa={upi_id}&pn={quote_plus(upi_name)}&am={plan.price:.2f}&cu=INR&tn={quote_plus(transaction_note)}"
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&margin=10&data={quote_plus(upi_uri)}"

    if request.method == 'POST':
        action = request.POST.get('action', 'submit_utr')
        utr_number = request.POST.get('utr_number', '').strip()

        if action == 'instant_demo':
            # Instant Demo Sandbox Activation for Recruiters & Testers
            order = PaymentOrder.objects.create(
                user=request.user,
                plan=plan,
                amount=plan.price,
                utr_number=f"DEMO_{request.user.id}_{plan.code.upper()}",
                payment_method="Demo Sandbox Instant",
                admin_notes="Instant activation via Demo Sandbox mode.",
            )
            order.activate_subscription()
            messages.success(
                request,
                f"🎉 Congratulations! Your {plan.name} has been activated instantly via Demo Sandbox!"
            )
            return redirect('payment_history')

        # Regular UPI UTR submission
        if not utr_number or len(utr_number) < 6:
            messages.error(request, "Please enter a valid 12-digit UPI reference (UTR) number.")
            return render(request, 'payments/checkout.html', {
                'plan': plan,
                'upi_id': upi_id,
                'upi_name': upi_name,
                'upi_uri': upi_uri,
                'qr_code_url': qr_code_url,
            })

        order = PaymentOrder.objects.create(
            user=request.user,
            plan=plan,
            amount=plan.price,
            utr_number=utr_number,
            payment_method="UPI QR Payment",
        )

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
    })


@login_required
def payment_history_view(request):
    orders = PaymentOrder.objects.filter(user=request.user).select_related('plan').order_by('-created_at')
    user_sub = getattr(request.user, 'subscription', None)

    return render(request, 'payments/history.html', {
        'orders': orders,
        'user_sub': user_sub,
    })


@login_required
def simulate_instant_activation(request, order_id):
    """Allows one-click test activation for a pending order (convenient for testing & portfolio demonstrations)."""
    order = get_object_or_404(PaymentOrder, id=order_id, user=request.user)
    if order.status != 'completed':
        order.activate_subscription()
        messages.success(request, f"Order #{order.id} verified and subscription activated successfully!")
    else:
        messages.info(request, "This order is already active.")
    return redirect('payment_history')
