# Naive keyword-overlap classifier — a placeholder baseline until the eval harness
# (see architecture plan, section 3) shows whether a real embedding-based classifier
# is actually needed. Keywords now live in config/domains.yaml (via the registry)
# instead of a hardcoded dict, so onboarding a new domain doesn't require a code change.

from domain_lib.registry import list_domains


def tag_domain(text: str) -> dict:
    lowered = text.lower()
    scores = {}
    domain_keywords: dict[str, list[str]] = {}
    for entry in list_domains(enabled_only=True):
        keywords = entry.keywords
        domain_keywords[entry.id] = keywords
        hits = [kw for kw in keywords if kw in lowered]
        if hits:
            scores[entry.id] = len(hits)

    if not scores:
        return {"domain": "unknown", "confidence": 0.0, "matched_keywords": []}

    # Tie-break: on equal keyword-match counts, the domain declared earlier in
    # config/domains.yaml wins. This relies on two easily-missed facts: `scores`
    # is populated in registry declaration order (dicts preserve insertion
    # order), and `max()` returns the *first* item that attains the maximum
    # when there are ties — so declaration order in the YAML doubles as the
    # tie-break order. With 6 domains now sharing overlapping vocabulary
    # (e.g. "sustainability"/"emissions" showing up for both
    # environmental_science and energy/agriculture text), this tie-break
    # actually gets exercised, not just theoretical.
    best_domain = max(scores, key=scores.get)
    total_hits = sum(scores.values())
    confidence = round(scores[best_domain] / total_hits, 2)
    matched = [kw for kw in domain_keywords[best_domain] if kw in lowered]
    return {"domain": best_domain, "confidence": confidence, "matched_keywords": matched}
