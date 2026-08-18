import json
import random
from pathlib import Path
from typing import Any
from collections import defaultdict
from agent.models import AppResearch, VerificationRecord


class Verifier:
    """Deterministic verification checks plus an optional LLM verification hook."""

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    def verify_research(self, research: AppResearch) -> list[str]:
        """Run deterministic consistency/evidence checks and return issue codes."""
        issues = []

        known_auth = research.auth_methods and not (
            len(research.auth_methods) == 1 and research.auth_methods[0].value == "unknown"
        )
        if known_auth:
            auth_evidence = [
                e for e in research.evidence
                if "auth" in e.claim.lower() or "oauth" in e.supporting_text.lower()
            ]
            if not auth_evidence:
                issues.append("auth_evidence_missing")

        cred_evidence = [
            e for e in research.evidence
            if e.source_type.value in ["pricing_docs", "official_docs"]
        ]
        if research.credential_access.value not in ["unknown", "self_serve"] and not cred_evidence:
            issues.append("credential_access_evidence_weak")

        if research.mcp_public.value == "yes":
            mcp_evidence = [e for e in research.evidence if "mcp" in e.supporting_text.lower()]
            if not mcp_evidence:
                issues.append("mcp_claim_unsupported")

        if research.composio_supported.value == "yes":
            composio_evidence = [
                e for e in research.evidence
                if e.source_type.value == "composio_registry"
            ]
            if not composio_evidence:
                issues.append("composio_claim_unsupported")

        auth_unknown = research.auth_methods and len(research.auth_methods) == 1 and research.auth_methods[0].value == "unknown"
        if research.buildability.value == "ready":
            if research.credential_access.value in ["contact_sales", "partner_required", "unknown"]:
                issues.append("buildability_ready_but_gated")
            if auth_unknown:
                issues.append("buildability_ready_but_auth_unknown")

        if research.buildability.value == "blocked" and not research.blocker:
            issues.append("blocked_without_blocker")

        if research.confidence < 0.6 and research.buildability.value in ["ready", "buildable_with_caveat"]:
            issues.append("low_confidence_high_buildability")

        return sorted(set(issues))

    async def verify_with_llm(self, research: AppResearch) -> list[str]:
        """Optional LLM verification; never claims verification when no client exists."""
        if self.llm is None:
            return []
        evidence_text = "\n\n---\n\n".join(
            f"SOURCE: {e.url}\nTYPE: {e.source_type.value}\nCONTENT: {e.supporting_text[:2000]}"
            for e in research.evidence[:8]
        )
        prompt = f"""You are a verification analyst. Review this research for {research.app} and return ONLY a JSON array of issue codes.
Allowed codes: AUTH_MISCLASSIFICATION, SELF_SERVE_CONFUSION, PAID_PLAN_CONFUSION, ENTERPRISE_GATE, PARTNER_GATE, API_SCOPE_ERROR, MCP_FALSE_POSITIVE, OUTDATED_DOC, INSUFFICIENT_EVIDENCE, CONTRADICTORY_SOURCES, BUILDABILITY_MISMATCH.

RESEARCH:
App: {research.app}
Auth: {[a.value for a in research.auth_methods]}
Credential Access: {research.credential_access.value}
API Types: {[a.value for a in research.api_types]}
API Breadth: {research.api_breadth.value}
MCP Public: {research.mcp_public.value}
Composio Supported: {research.composio_supported.value}
Buildability: {research.buildability.value}
Blocker: {research.blocker}
Confidence: {research.confidence:.2f}

EVIDENCE:
{evidence_text}"""
        try:
            response = await self.llm.complete_async(prompt, temperature=0.0, max_tokens=500)
            data = json.loads(response)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def create_stratified_sample(research_list: list[AppResearch], sample_size: int = 20) -> list[AppResearch]:
    """Create a deterministic stratified sample across categories and confidence."""
    if not research_list or sample_size <= 0:
        return []
    by_category = defaultdict(list)
    for r in research_list:
        by_category[r.category].append(r)

    sample = []
    per_category = max(1, sample_size // len(by_category))
    for category in sorted(by_category):
        items = sorted(by_category[category], key=lambda x: (x.confidence, x.app))
        n = min(per_category, len(items))
        if n == 1:
            sample.append(items[len(items) // 2])
        else:
            for i in range(n):
                idx = round(i * (len(items) - 1) / (n - 1))
                sample.append(items[idx])

    if len(sample) < sample_size:
        selected = {id(r) for r in sample}
        remaining = [r for r in research_list if id(r) not in selected]
        remaining.sort(key=lambda x: (x.confidence, x.category, x.app))
        sample.extend(remaining[:sample_size - len(sample)])
    return sample[:sample_size]


def load_research_results(filepath: str, *, strict: bool = True) -> list[AppResearch]:
    """Load JSONL and fail instead of silently dropping malformed records."""
    results = []
    errors = []
    with open(filepath, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                results.append(AppResearch.model_validate_json(line))
            except Exception as exc:
                errors.append((line_no, str(exc)))
    if strict and errors:
        preview = "; ".join(f"line {n}: {err}" for n, err in errors[:3])
        raise ValueError(f"Verification input contains {len(errors)} invalid record(s): {preview}")
    if not results:
        raise ValueError(f"Verification input contains no valid records: {filepath}")
    return results


def save_verification_records(records: list[VerificationRecord], filepath: str):
    import csv
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["app", "field", "agent_answer", "verified_answer", "correct", "error_type", "evidence"])
        writer.writeheader()
        for r in records:
            writer.writerow(r.model_dump())


def calculate_accuracy(records: list[VerificationRecord]) -> dict:
    """Calculate accuracy only from explicit verification records."""
    if not records:
        return {"status": "not_available", "overall": None, "by_field": {}, "error_distribution": {}}
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
    return {
        "status": "available",
        "overall": f"{correct}/{total} ({100 * correct / total:.1f}%)",
        "by_field": {field: f"{s['correct']}/{s['total']} ({100 * s['correct'] / s['total']:.0f}%)" for field, s in by_field.items()},
        "error_distribution": dict(by_error),
    }


async def run_verification(research_file: str, output_file: str, sample_size: int = 20):
    """Run deterministic checks and create a human-verification sample."""
    research = load_research_results(research_file, strict=True)
    print(f"Loaded {len(research)} validated research records")

    verifier = Verifier()
    flagged = []
    for r in research:
        issues = verifier.verify_research(r)
        if issues:
            r.uncertainty = sorted(set(r.uncertainty + issues))
            flagged.append((r.app, issues))
    print(f"Automated checks flagged {len(flagged)} apps")

    sample = create_stratified_sample(research, sample_size)
    print(f"Created verification sample of {len(sample)} apps")
    sample_file = Path(output_file).with_suffix(".verification_sample.json")
    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump([r.model_dump(mode="json") for r in sample], f, indent=2)
    print(f"Sample saved to {sample_file}")
    print("Human verification required before reporting accuracy.")
    return sample


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_verification("data/research_raw.jsonl", "data/verification.csv"))