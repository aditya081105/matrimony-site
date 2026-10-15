def get_client_ip(request):
    """
    Extracts the trusted client IP address.
    In production behind Nginx, Nginx sets X-Real-IP from $remote_addr (which is
    safely restored via ngx_http_realip_module only when connecting from trusted
    Cloudflare CIDRs).
    We do NOT read raw client-supplied CF-Connecting-IP or X-Forwarded-For headers
    to prevent origin header injection or rate-limit bypasses.
    Falls back to REMOTE_ADDR (standard WSGI / local test runner).
    """
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()
