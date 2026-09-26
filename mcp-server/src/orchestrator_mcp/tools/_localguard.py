# Shared SSRF guard: both pipeline.py (backend HTTP proxy) and k6.py (k6 CLI
# trigger) accept a caller-supplied base_url/target and must refuse to act
# against anything that isn't the local dev stack. Previously duplicated
# verbatim in both files; kept here as the single source of truth so the
# allow-list only has to be updated in one place.

from urllib.parse import urlparse

_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "backend", "host.docker.internal")


def target_is_local(base_url: str) -> bool:
    # Must compare the *parsed* hostname, not do substring containment on
    # the raw URL: `"backend" in base_url` also matches
    # "http://evil-backend.attacker.com/x" (an attacker-controlled host that
    # merely contains an allowed host as a substring), which defeats the
    # whole point of this guard. `endswith("." + host)` still allows genuine
    # subdomains (e.g. "foo.localhost") without allowing "evilhostlocalhost"
    # or "notlocalhost".
    hostname = urlparse(base_url).hostname or ""
    return any(
        hostname == host or hostname.endswith(f".{host}") for host in _ALLOWED_HOSTS
    )
