import json
import random
from pathlib import Path
from typing import Any
from collections import defaultdict
from agent.models import AppResearch, VerificationRecord, ErrorType, VerificationStatus
from agent.evidence import calculate_confidence


class Verifier:
    """Second-pass verification agent to detect issues in research."""
    
    def __init__(self, llm_client: Any):
        self.llm = llm_client
    
    def verify_research(self, research: AppResearch) -> list[str]:
        """Automated verification checks. Returns list of issues found."""
        issues = []
        
        # Check 1: Evidence supports auth classification
        auth_evidence = [e for e in research.evidence if "auth" in e.claim.lower() or "oauth" in e.supporting_text.lower()]
        if research.auth_methods != [research.auth_methods[0]] if research.auth_methods else [] and research.auth_methods[0].value != "unknown":
            if not auth_evidence:
                issues.append("auth_evidence_missing")
        
        # Check 2: Credential access has pricing/plan evidence
        cred_evidence = [e for e in research.evidence if e.source_type.value in ["pricing_docs", "official_docs"]]
        if research.credential_access.value not in ["unknown", "self_serve"]:
            if not cred_evidence:
                issues.append("credential_access_evidence_weak")
        
        # Check 3: MCP claim needs specific evidence
        if research.mcp_public.value == "yes":
            mcp_evidence = [e for e in research.evidence if "mcp" in e.supporting_text.lower()]
            if not mcp_evidence:
                issues.append("mcp_claim_unsupported")
        
        # Check 4: Composio supported claim
        if research.composio_supported.value == "yes":
            composio_evidence = [e for e in research.evidence if e.source_type.value == "composio_registry"]
            if not composio_evidence:
                issues.append("composio_claim_unsupported")
        
        # Check 5: Buildability consistency
        if research.buildability.value == "ready":
            if research.credential_access.value in ["contact_sales", "partner_required", "unknown"]:
                issues.append("buildability_ready_but_gated")
            if research.auth_methods == [research.auth_methods[0]] if research.auth_methods else [] and research.auth_methods[0].value == "unknown":
                issues.append("buildability_ready_but_auth_unknown")
        
        if research.buildability.value == "blocked" and not research.blocker:
            issues.append("blocked_without_blocker")
        
        # Check 6: Contradictory evidence
        # (Would need more sophisticated NLP - placeholder)
        
        # Check 7: Low confidence with high-stakes claims
        if research.confidence < 0.6 and research.buildability.value in ["ready", "buildable_with_caveat"]:
            issues.append("low_confidence_high_buildability")
        
        return issues
    
    async def verify_with_llm(self, research: AppResearch) -> list[str]:
        """LLM-based verification pass."""
        
        evidence_text = "\n\n---\n\n".join([
            f"SOURCE: {e.url}\nTYPE: {e.source_type.value}\nCONTENT: {e.supporting_text[:2000]}"
            for e in research.evidence[:8]
        ])
        
        prompt = f"""You are a verification analyst. Review this research for {research.app} and identify issues.

RESEARCH:
- App: {research.app}
- Category: {research.category}
- Auth: {[a.value for a in research.auth_methods]}
- Credential Access: {research.credential_access.value}
- API Types: {[a.value for a in research.api_types]}
- API Breadth: {research.api_breadth.value}
- MCP Public: {research.mcp_public.value}
- Composio Supported: {research.composio_supported.value}
- Buildability: {research.buildability.value}
- Blocker: {research.blocker}
- Confidence: {research.confidence:.2f}
- Uncertainty: {research.uncertainty}

EVIDENCE:
{evidence_text}

Identify specific issues. Return JSON array of issue codes:
[
  "AUTH_MISCLASSIFICATION",
  "SELF_SERVE_CONFUSION", 
  "PAID_PLAN_CONFUSION",
  "ENTERPRISE_GATE",
  "PARTNER_GATE",
  "API_SCOPE_ERROR",
  "MCP_FALSE_POSITIVE",
  "OUTDATED_DOC",
  "INSUFFICIENT_EVIDENCE",
  "CONTRADICTORY_SOURCES",
  "BUILDABILITY_MISMATCH"
]

Only return the JSON array. No explanation."""

        # TODO: Call LLM
        return []


def create_stratified_sample(research_list: list[AppResearch], sample_size: int = 20) -> list[AppResearch]:
    """Create stratified sample across categories for human verification."""
    
    by_category = defaultdict(list)
    for r in research_list:
        by_category[r.category].append(r)
    
    sample = []
    per_category = max(1, sample_size // len(by_category))
    
    for category, items in by_category.items():
        # Stratify by confidence within category
        items_sorted = sorted(items, key=lambda x: x.confidence)
        
        # Pick from low, medium, high confidence
        n = min(per_category, len(items_sorted))
        if n == 1:
            sample.append(items_sorted[len(items_sorted) // 2])
        elif n == 2:
            sample.append(items_sorted[len(items_sorted) // 4])
            sample.append(items_sorted[3 * len(items_sorted) // 4])
        else:
            step = len(items_sorted) // n
            for i in range(n):
                idx = min(i * step + step // 2, len(items_sorted) - 1)
                sample.append(items_sorted[idx])
    
    # If we need more, add random
    if len(sample) < sample_size:
        remaining = [r for r in research_list if r not in sample]
        sample.extend(random.sample(remaining, min(sample_size - len(sample), len(remaining))))
    
    return sample[:sample_size]


def load_research_results(filepath: str) -> list[AppResearch]:
    """Load research results from JSONL."""
    results = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            try:
                results.append(AppResearch.model_validate_json(line))
            except Exception:
                pass
    return results


def save_verification_records(records: list[VerificationRecord], filepath: str):
    """Save verification records to CSV."""
    import csv
    
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "app", "field", "agent_answer", "verified_answer", 
            "correct", "error_type", "evidence"
        ])
        writer.writeheader()
        for r in records:
            writer.writerow(r.model_dump())


def calculate_accuracy(records: list[VerificationRecord]) -> dict:
    """Calculate field-level and overall accuracy."""
    if not records:
        return {}
    
    total = len(records)
    correct = sum(1 for r in records if r.correct)
    
    by_field = defaultdict(lambda: {"total": 0, "correct": 0})
    by_error = defaultdict(int)
    
    for r in records:
        by_field[r.field]["total"] += 1
        if r.correct:
            by_field[r.field]["correct"] += 1
        if r.error_type:
            by_error[r.error_type.value] += 1
    
    field_accuracy = {
        field: f"{stats['correct']}/{stats['total']} ({100*stats['correct']/stats['total']:.0f}%)"
        for field, stats in by_field.items()
    }
    
    return {
        "overall": f"{correct}/{total} ({100*correct/total:.1f}%)",
        "by_field": field_accuracy,
        "error_distribution": dict(by_error),
    }


async def run_verification(research_file: str, output_file: str, sample_size: int = 20):
    """Run automated + human verification workflow."""
    
    research = load_research_results(research_file)
    print(f"Loaded {len(research)} research records")
    
    # Automated verification
    verifier = Verifier(None)  # LLM client would go here
    
    flagged = []
    for r in research:
        issues = verifier.verify_research(r)
        if issues:
            r.uncertainty.extend(issues)
            flagged.append((r.app, issues))
    
    print(f"Automated checks flagged {len(flagged)} apps")
    
    # Create stratified sample for human verification
    sample = create_stratified_sample(research, sample_size)
    print(f"Created verification sample of {len(sample)} apps")
    
    # Save sample for human review
    sample_file = Path(output_file).with_suffix(".verification_sample.json")
    with open(sample_file, "w") as f:
        json.dump([r.model_dump() for r in sample], f, indent=2, default=str)
    
    print(f"Sample saved to {sample_file}")
    print("Human verification needed - fill in verification.csv")
    
    return sample


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_verification("data/research_raw.jsonl", "data/verification.csv"))