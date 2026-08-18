# App Research Agent

Researches 100 apps for integration buildability: auth methods, credential accessibility, API capabilities, MCP availability, and Composio support.

## What It Does

1. **Researches 100 apps** across 10 categories using Firecrawl via Composio
2. **Extracts structured evidence** for every claim (auth, credentials, API, MCP, buildability)
3. **Validates with Pydantic** + automated repair retry
4. **Runs verification pass** to detect contradictions and gaps
5. **Human verification sample** (20 apps, stratified by category)
6. **Generates interactive HTML case study** with patterns, accuracy metrics, and full matrix

## Architecture

```
100 Apps CSV
     │
     ▼
Research Orchestrator (5 concurrent workers)
     │
     ├─► Firecrawl (Composio) ──► Web Evidence
     ├─► Composio Registry ──────► Toolkit Evidence
     └─► Public MCP Registry ────► MCP Evidence
                │
                ▼
         Nemotron 3 Ultra
                │
                ▼
        Pydantic Validation
                │
                ▼
         Confidence Scoring
                │
       ┌────────┴────────┐
       ▼                 ▼
    High              Low/Conflict
       │                 │
       │           Verification Agent
       └────────┬────────┘
                ▼
          Final Dataset
                │
       ┌────────┴────────┐
       ▼                 ▼
  Pattern Analysis   HTML Case Study
```

## Quick Start

### Prerequisites
- Python 3.11+
- Composio API key (for Firecrawl)
- NVIDIA API key (for Nemotron)

### Setup

```bash
git clone <repo-url>
cd composio-app-research
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Run Research

```bash
# Full 100 apps (resumes automatically if interrupted)
python scripts/run_research.py

# With custom concurrency
python scripts/run_research.py --concurrent 3
```

### Verification

```bash
# Create 20-app stratified sample for manual review
python scripts/verify_sample.py

# After filling data/verification.csv manually:
python scripts/verify_sample.py --calculate
```

### Build Case Study

```bash
python scripts/build_case_study.py

# View locally
cd web && python -m http.server 8000
# Open http://localhost:8000
```

## Output Files

| File | Description |
|------|-------------|
| `data/research_raw.jsonl` | Raw agent output (one JSON per line) |
| `data/research_final.jsonl` | Post-verification final dataset |
| `data/verification.csv` | Human verification log |
| `web/analysis.json` | Pattern analysis for frontend |
| `web/research.json` | Full dataset for matrix table |
| `web/charts/*.json` | Plotly chart specs |

## Data Schema

Each app research record contains:

```json
{
  "app": "Slack",
  "category": "Communications and Messaging",
  "description": "Team communication platform",
  "auth_methods": ["oauth2"],
  "credential_access": "self_serve",
  "api_types": ["rest", "webhooks"],
  "api_breadth": "broad",
  "mcp_public": "no",
  "composio_supported": "yes",
  "buildability": "ready",
  "blocker": null,
  "evidence": [...],
  "confidence": 0.95,
  "verification_status": "verified_correct"
}
```

## Classification Vocabulary

Fixed enums prevent hallucination:

- **Auth**: oauth2, api_key, basic, bearer_token, pat, service_account, other, multiple, unknown
- **Credential Access**: self_serve, self_serve_with_trial, paid_plan_required, admin_approval, partner_required, contact_sales, unknown
- **API**: rest, graphql, soap, grpc, webhooks, mcp, other
- **Buildability**: ready, buildable_with_caveat, human_outreach_required, blocked, unknown
- **MCP**: yes, no, unknown (separate: public vs Composio)

## Verification Protocol

1. **Automated checks**: Evidence completeness, consistency, contradiction detection
2. **Stratified sample**: 2 apps × 10 categories = 20 apps
3. **Manual review**: Cross-check against official documentation
4. **Error taxonomy**: AUTH_MISCLASSIFICATION, SELF_SERVE_CONFUSION, PAID_PLAN_CONFUSION, ENTERPRISE_GATE, PARTNER_GATE, API_SCOPE_ERROR, MCP_FALSE_POSITIVE, OUTDATED_DOC, INSUFFICIENT_EVIDENCE
5. **Report**: Field-level accuracy + overall improvement delta

## Opportunity Scoring

Each app gets a 0-100 score:

```
Self-serve accessibility (0-30)
+ API breadth (0-25)
+ Agent suitability (0-25)
+ Documentation quality (0-20)
- Integration blockers (0-30)
```

Segments: Quick Wins (≥75), High-Value Gated (55-74), High Effort (35-54), Needs Partnership (20-34), Blocked (<20)

## Case Study Sections

1. **Hero**: 100 apps, key percentages, top blocker, biggest insight
2. **Patterns**: 7 interactive charts (auth, gating, buildability, MCP, category heatmap, opportunity, confidence)
3. **The Agent**: Architecture, methodology, prompt philosophy, tech stack
4. **Verification**: Accuracy stats, error taxonomy, improvement delta
5. **Full Matrix**: Searchable, filterable table (11 columns)
6. **Run/GitHub**: Repo link, local execution instructions, env vars

## Customization

- Edit `data/apps.csv` to change the app list
- Modify `PipelineConfig` in `scripts/run_research.py` for concurrency/retries
- Adjust `calculate_opportunity_scores` in `analysis/patterns.py` for scoring weights
- Update `web/styles.css` and `web/index.html` for presentation

## License

MIT