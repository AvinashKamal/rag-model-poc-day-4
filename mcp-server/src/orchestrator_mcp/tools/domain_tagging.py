# Thin re-export shim. The real classifier now lives in
# shared/domain_lib/src/domain_lib/tagging.py, reading keywords from the
# domain registry (config/domains.yaml) instead of a hardcoded dict. Kept here
# so server.py's import (orchestrator_mcp.tools.domain_tagging.tag_domain)
# doesn't need to change.

from domain_lib.tagging import tag_domain

__all__ = ["tag_domain"]
