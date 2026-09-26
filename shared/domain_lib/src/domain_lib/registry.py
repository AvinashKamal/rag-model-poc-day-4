"""Domain registry: loads config/domains.yaml and exposes typed lookups.

This is the single source of truth for which literature domains exist, their
keyword sets (used by tagging.py), which corpus sources are valid for each
domain (enforced by corpus.py), and where each domain's eval gold set lives.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# shared/domain_lib/src/domain_lib/registry.py -> repo root is 4 parents up.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "domains.yaml"


class DomainNotFoundError(KeyError):
    """Raised when an unknown domain id is requested from the registry."""

    def __init__(self, domain_id: str, known_ids: list[str]):
        self.domain_id = domain_id
        self.known_ids = known_ids
        super().__init__(
            f"unknown domain '{domain_id}'; known domains are: {sorted(known_ids)}"
        )


class DomainEntry(BaseModel):
    id: str
    display_name: str
    enabled: bool = True
    keywords: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    default_query: str = ""
    gold_questions: str = ""


class DomainRegistry(BaseModel):
    domains: list[DomainEntry]

    def by_id(self) -> dict[str, DomainEntry]:
        return {d.id: d for d in self.domains}


def _load_registry(config_path: Path) -> DomainRegistry:
    if not config_path.exists():
        raise FileNotFoundError(f"domain registry config not found at {config_path}")
    raw = yaml.safe_load(config_path.read_text()) or {}
    return DomainRegistry.model_validate(raw)


@lru_cache(maxsize=1)
def _cached_registry() -> DomainRegistry:
    return _load_registry(_DEFAULT_CONFIG_PATH)


def load_registry(config_path: Path | None = None) -> DomainRegistry:
    """Load the domain registry. Uses the cached repo-root config unless an
    explicit path is given (mainly for tests)."""
    if config_path is None:
        return _cached_registry()
    return _load_registry(config_path)


def list_domains(*, enabled_only: bool = False) -> list[DomainEntry]:
    domains = load_registry().domains
    if enabled_only:
        domains = [d for d in domains if d.enabled]
    return domains


def get_domain(domain_id: str) -> DomainEntry:
    registry = load_registry()
    entry = registry.by_id().get(domain_id)
    if entry is None:
        raise DomainNotFoundError(domain_id, list(registry.by_id().keys()))
    return entry


def get_keywords(domain_id: str) -> list[str]:
    return get_domain(domain_id).keywords


def get_sources(domain_id: str) -> list[str]:
    return get_domain(domain_id).sources
