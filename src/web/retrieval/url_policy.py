"""
URL Security Policy and SSRF Prevention.
Validates URL schemes and blocks private network / loopback access.
"""

import ipaddress
import urllib.parse
from src.core.exceptions import SSRFSecurityError
from src.core.logger import get_logger

logger = get_logger()


class URLPolicy:
    """Validates target URLs before HTTP fetch operations to prevent SSRF and unsafe schemes."""

    ALLOWED_SCHEMES = {"http", "https"}
    BLOCKED_HOSTNAMES = {"localhost", "loopback", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"}

    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate URL scheme and host security. Raises SSRFSecurityError if unsafe."""
        if not url or not isinstance(url, str):
            raise SSRFSecurityError("URL string is empty or invalid.")

        parsed = urllib.parse.urlparse(url.strip())

        # 1. Scheme Validation
        if parsed.scheme.lower() not in cls.ALLOWED_SCHEMES:
            raise SSRFSecurityError(
                f"URL scheme '{parsed.scheme}' is prohibited. Only http:// and https:// are allowed."
            )

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise SSRFSecurityError("URL hostname is missing or invalid.")

        # 2. Hostname Blocklist Validation
        if hostname in cls.BLOCKED_HOSTNAMES:
            raise SSRFSecurityError(f"Access to private/loopback host '{hostname}' is blocked for security (SSRF prevention).")

        # 3. IP Range Security Check (10.x, 192.168.x, 172.16.x)
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                raise SSRFSecurityError(f"Access to private IP address '{hostname}' is blocked for security.")
        except ValueError:
            # Hostname is a domain name (not a raw IP), which is valid
            pass

        return url.strip()
