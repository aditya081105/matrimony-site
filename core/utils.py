def get_client_ip(request):
    """
    Extracts the client IP address from HTTP headers.
    Prioritizes HTTP_CF_CONNECTING_IP and HTTP_X_FORWARDED_FOR when behind Cloudflare or reverse proxies,
    falling back to REMOTE_ADDR.
    """
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip.strip()
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()
