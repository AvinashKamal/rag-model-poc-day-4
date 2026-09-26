# Shared SSRF guard: both pipeline.py (backend HTTP proxy) and k6.py (k6 CLI
# trigger) accept a caller-supplied base_url/target and must refuse to act
# against anything that isn't the local dev stack. Previously duplicated
# verbatim in both files; kept here as the single source of truth so the
# allow-list only has to be updated in one place.

_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "backend", "host.docker.internal")


def target_is_local(base_url: str) -> bool:
    return any(host in base_url for host in _ALLOWED_HOSTS)
