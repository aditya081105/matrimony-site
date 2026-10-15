import ipaddress


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


def get_ip_network_key(ip_str: str) -> str:
    """
    Normalizes an IP address into a rate-limiting key.
    For IPv4: returns the single IP string (e.g. 203.0.113.195).
    For IPv6: masks to the /64 subnet prefix (e.g. 2001:db8:1234:5678::/64)
    because end users and mobile carriers are delegated at least a /64,
    preventing attackers from rotating through addresses in the same prefix.
    """
    if not ip_str or ip_str == 'unknown':
        return 'unknown'
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.version == 6:
            net = ipaddress.ip_network(f"{ip}/64", strict=False)
            return str(net)
        return str(ip)
    except ValueError:
        return ip_str

