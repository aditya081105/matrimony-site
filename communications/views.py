from django.shortcuts import render

# Create your views here.

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import ContactRequest

User = get_user_model()

@login_required
def send_request(request, user_id):
    receiver = get_object_or_404(User, id=user_id)

    if receiver == request.user:
        return redirect('profile_list')

    ContactRequest.objects.get_or_create(
        sender=request.user,
        receiver=receiver
    )

    messages.success(request, "Contact request sent.")
    return redirect('profile_list')

@login_required
def update_request(request, request_id, action):
    contact_request = get_object_or_404(
        ContactRequest,
        id=request_id,
        receiver=request.user
    )

    if action == 'accept':
        contact_request.status = 'accepted'
    elif action == 'reject':
        contact_request.status = 'rejected'

    contact_request.save()
    return redirect('received_requests')

@login_required
def received_requests(request):
    requests = request.user.received_requests.select_related('sender')
    return render(request, 'communications/received_requests.html', {
        'requests': requests
    })