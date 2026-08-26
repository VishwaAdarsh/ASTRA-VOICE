"""
Unit tests for URLPolicy and SSRF Security Prevention.
"""

import pytest
from src.core.exceptions import SSRFSecurityError
from src.web.retrieval.url_policy import URLPolicy


def test_url_policy_valid_urls():
    assert URLPolicy.validate_url("https://python.org") == "https://python.org"
    assert URLPolicy.validate_url("http://docs.python.org/3/") == "http://docs.python.org/3/"


def test_url_policy_prohibited_schemes():
    with pytest.raises(SSRFSecurityError) as exc:
        URLPolicy.validate_url("file:///C:/Windows/System32/cmd.exe")
    assert "scheme 'file' is prohibited" in str(exc.value)

    with pytest.raises(SSRFSecurityError):
        URLPolicy.validate_url("javascript:alert(1)")


def test_url_policy_private_ip_blocking():
    # Block loopback / localhost
    with pytest.raises(SSRFSecurityError) as exc1:
        URLPolicy.validate_url("http://localhost:8080")
    assert "blocked for security" in str(exc1.value)

    with pytest.raises(SSRFSecurityError):
        URLPolicy.validate_url("http://127.0.0.1:5000")

    with pytest.raises(SSRFSecurityError):
        URLPolicy.validate_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(SSRFSecurityError):
        URLPolicy.validate_url("http://10.0.0.1/admin")
