"""Unit tests for the shared SSRF guard (`target_is_local`).

This guard gates both pipeline.py's HTTP proxy and k6.py's CLI trigger
against a caller-supplied base_url/target. It used to do substring
containment on the raw URL, which a hostname like
"evil-backend.attacker.com" could defeat; it now parses the hostname and
compares it exactly (or as a genuine subdomain) against the allow-list.
These tests pin that behavior down.
"""

from __future__ import annotations

from orchestrator_mcp.tools._localguard import target_is_local


def test_rejects_substring_bypass_host():
    # "backend" is an allowed host, but "evil-backend.attacker.com" only
    # contains it as a substring -- must not be treated as local.
    assert target_is_local("http://evil-backend.attacker.com") is False


def test_rejects_userinfo_smuggling():
    # The hostname is "evil.com"; "backend@" is userinfo, not the host.
    assert target_is_local("http://backend@evil.com") is False


def test_accepts_exact_allowed_host():
    assert target_is_local("http://localhost:8000") is True


def test_accepts_genuine_subdomain_of_allowed_host():
    # ".suffix" matching intentionally allows genuine subdomains of an
    # allowed host, e.g. "foo.localhost".
    assert target_is_local("http://foo.localhost") is True


def test_rejects_near_miss_suffix_without_dot():
    # "notlocalhost" ends with "localhost" as a raw string suffix, but
    # there's no separating "." so it's not "<something>.localhost" -- must
    # be rejected.
    assert target_is_local("http://notlocalhost") is False


def test_rejects_evil_host_containing_allowed_host_as_prefix_run():
    # Belt-and-suspenders on the original substring-containment bypass:
    # any allowed host appearing anywhere in an attacker-controlled
    # hostname must not grant access.
    assert target_is_local("http://localhost.attacker.com") is False
