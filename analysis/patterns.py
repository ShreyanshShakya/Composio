import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from agent.models import AppResearch, AuthMethod, CredentialAccess, APIType, Buildability, MCPStatus


def load_research(filepath: str) -> list[AppResearch]:
    results = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            try:
                results.append(AppResearch.model_validate_json(line))
            except Exception:
                pass
    return results


def analyze_patterns(research: list[AppResearch]) -> dict:
    """Generate comprehensive pattern analysis."""
    
    total = len(research)
    if total == 0:
        return {}
    
    # Auth distribution
    auth_counts = Counter()
    for r in research:
        for a in r.auth_methods:
            auth_counts[a.value] += 1
    
    # Credential access distribution
    cred_counts = Counter(r.credential_access.value for r in research)
    
    # API type distribution
    api_counts = Counter()
    for r in research:
        for a in r.api_types:
            api_counts[a.value] += 1
    
    # API breadth
    breadth_counts = Counter(r.api_breadth.value for r in research)
    
    # MCP status
    mcp_public_counts = Counter(r.mcp_public.value for r in research)
    composio_counts = Counter(r.composio_supported.value for r in research)
    
    # Buildability
    build_counts = Counter(r.buildability.value for r in research)
    
    # By category
    by_category = defaultdict(lambda: {
        "count": 0,
        "auth": Counter(),
        "credential": Counter(),
        "api": Counter(),
        "buildability": Counter(),
        "mcp_public": Counter(),
        "composio": Counter(),
        "avg_confidence": 0.0,
    })
    
    for r in research:
        cat = by_category[r.category]
        cat["count"] += 1
        for a in r.auth_methods:
            cat["auth"][a.value] += 1
        cat["credential"][r.credential_access.value] += 1
        for a in r.api_types:
            cat["api"][a.value] += 1
        cat["buildability"][r.buildability.value] += 1
        cat["mcp_public"][r.mcp_public.value] += 1
        cat["composio"][r.composio_supported.value] += 1
        cat["avg_confidence"] += r.confidence
    
    for cat in by_category.values():
        if cat["count"] > 0:
            cat["avg_confidence"] /= cat["count"]
        # Convert Counters to dicts for JSON serialization
        for key in ["auth", "credential", "api", "buildability", "mcp_public", "composio"]:
            cat[key] = dict(cat[key])
    
    # Top blockers
    blockers = [r.blocker for r in research if r.blocker]
    blocker_counts = Counter(blockers).most_common(10)
    
    # Confidence distribution
    confidence_buckets = Counter()
    for r in research:
        bucket = int(r.confidence * 10) / 10
        confidence_buckets[bucket] += 1
    
    # Opportunity scoring
    opportunities = calculate_opportunity_scores(research)
    
    return {
        "total_apps": total,
        "auth_distribution": dict(auth_counts),
        "credential_access": dict(cred_counts),
        "api_types": dict(api_counts),
        "api_breadth": dict(breadth_counts),
        "mcp_public": dict(mcp_public_counts),
        "composio_supported": dict(composio_counts),
        "buildability": dict(build_counts),
        "by_category": dict(by_category),
        "top_blockers": blocker_counts,
        "confidence_distribution": dict(sorted(confidence_buckets.items())),
        "opportunities": opportunities,
        "summary": generate_summary(research),
    }


def calculate_opportunity_scores(research: list[AppResearch]) -> list[dict]:
    """Calculate opportunity score for each app."""
    
    results = []
    
    for r in research:
        score = 0
        factors = {}
        
        # Self-serve accessibility (0-30)
        cred_scores = {
            "self_serve": 30,
            "self_serve_with_trial": 25,
            "paid_plan_required": 15,
            "admin_approval": 10,
            "partner_required": 5,
            "contact_sales": 0,
            "unknown": 10,
        }
        cred_score = cred_scores.get(r.credential_access.value, 0)
        score += cred_score
        factors["credential_access"] = cred_score
        
        # API breadth (0-25)
        breadth_scores = {
            "broad": 25,
            "limited": 15,
            "unknown": 5,
        }
        breadth_score = breadth_scores.get(r.api_breadth.value, 0)
        score += breadth_score
        factors["api_breadth"] = breadth_score
        
        # Agent suitability (0-25) - based on auth + API type
        auth_modern = any(a.value in ["oauth2", "api_key", "bearer_token", "pat"] for a in r.auth_methods)
        api_modern = any(a.value in ["rest", "graphql", "webhooks", "mcp"] for a in r.api_types)
        
        agent_score = 0
        if auth_modern:
            agent_score += 12
        if api_modern:
            agent_score += 13
        score += agent_score
        factors["agent_suitability"] = agent_score
        
        # Documentation quality proxy (0-20) - based on evidence count
        ev_score = min(len(r.evidence) * 3, 20)
        score += ev_score
        factors["doc_quality"] = ev_score
        
        # Blocker penalty (0-30)
        blocker_penalty = 0
        if r.buildability.value == "blocked":
            blocker_penalty = 30
        elif r.buildability.value == "human_outreach_required":
            blocker_penalty = 20
        elif r.buildability.value == "buildable_with_caveat":
            blocker_penalty = 10
        score -= blocker_penalty
        factors["blocker_penalty"] = -blocker_penalty
        
        score = max(0, min(100, score))
        
        # Segment classification
        if score >= 75:
            segment = "quick_win"
        elif score >= 55:
            segment = "high_value_gated"
        elif score >= 35:
            segment = "high_effort"
        elif score >= 20:
            segment = "needs_partnership"
        else:
            segment = "blocked"
        
        results.append({
            "app": r.app,
            "category": r.category,
            "score": score,
            "segment": segment,
            "factors": factors,
            "buildability": r.buildability.value,
            "credential_access": r.credential_access.value,
        })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def generate_summary(research: list[AppResearch]) -> dict:
    """Generate executive summary."""
    total = len(research)
    
    buildable = sum(1 for r in research if r.buildability.value in ["ready", "buildable_with_caveat"])
    self_serve = sum(1 for r in research if r.credential_access.value in ["self_serve", "self_serve_with_trial"])
    oauth = sum(1 for r in research if any(a.value == "oauth2" for a in r.auth_methods))
    mcp_public = sum(1 for r in research if r.mcp_public.value == "yes")
    composio = sum(1 for r in research if r.composio_supported.value == "yes")
    
    # Top blocker
    blockers = [r.blocker for r in research if r.blocker]
    top_blocker = Counter(blockers).most_common(1)
    
    return {
        "total_apps": total,
        "buildable_pct": round(100 * buildable / total, 1) if total else 0,
        "self_serve_pct": round(100 * self_serve / total, 1) if total else 0,
        "oauth_pct": round(100 * oauth / total, 1) if total else 0,
        "mcp_public_pct": round(100 * mcp_public / total, 1) if total else 0,
        "composio_pct": round(100 * composio / total, 1) if total else 0,
        "top_blocker": top_blocker[0][0] if top_blocker else "N/A",
        "avg_confidence": round(sum(r.confidence for r in research) / total, 2) if total else 0,
    }


def export_for_web(analysis: dict, filepath: str):
    """Export analysis as JSON for web consumption."""
    with open(filepath, "w") as f:
        json.dump(analysis, f, indent=2)


if __name__ == "__main__":
    research = load_research("data/research_final.jsonl")
    analysis = analyze_patterns(research)
    export_for_web(analysis, "web/analysis.json")
    print("Analysis exported to web/analysis.json")