from communications.models import ContactRequest

def pending_request_count(request):
    if request.user.is_authenticated:
        count = ContactRequest.objects.filter(
            receiver=request.user,
            status='pending'
        ).count()
        return {'pending_request_count': count}
    return {}