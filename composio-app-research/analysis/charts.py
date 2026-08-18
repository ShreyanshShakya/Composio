import json
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
from analysis.patterns import load_research, analyze_patterns


def create_auth_chart(analysis: dict) -> dict:
    """Authentication method distribution."""
    data = analysis.get("auth_distribution", {})
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(data.keys()),
            y=list(data.values()),
            marker_color="#4F46E5",
            text=list(data.values()),
            textposition="auto",
        )
    ])
    fig.update_layout(
        title="Authentication Methods Across 100 Apps",
        xaxis_title="Auth Method",
        yaxis_title="Count",
        template="plotly_white",
        height=400,
    )
    return fig.to_dict()


def create_credential_access_chart(analysis: dict) -> dict:
    """Credential access gating distribution."""
    data = analysis.get("credential_access", {})
    
    order = ["self_serve", "self_serve_with_trial", "paid_plan_required", 
             "admin_approval", "partner_required", "contact_sales", "unknown"]
    
    labels = [k for k in order if k in data]
    values = [data[k] for k in labels]
    
    colors = ["#10B981", "#34D399", "#F59E0B", "#F97316", "#EF4444", "#DC2626", "#9CA3AF"]
    colors = colors[:len(labels)]
    
    fig = go.Figure(data=[
        go.Pie(
            labels=labels,
            values=values,
            marker_colors=colors,
            hole=0.4,
            textinfo="label+percent",
        )
    ])
    fig.update_layout(
        title="Credential Accessibility",
        template="plotly_white",
        height=400,
    )
    return fig.to_dict()


def create_buildability_chart(analysis: dict) -> dict:
    """Buildability funnel."""
    data = analysis.get("buildability", {})
    
    order = ["ready", "buildable_with_caveat", "human_outreach_required", "blocked", "unknown"]
    
    labels = [k for k in order if k in data]
    values = [data[k] for k in labels]
    
    colors = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#9CA3AF"]
    colors = colors[:len(labels)]
    
    fig = go.Figure(data=[
        go.Funnel(
            y=labels,
            x=values,
            marker_color=colors,
            textinfo="value+percent initial",
        )
    ])
    fig.update_layout(
        title="Buildability Funnel",
        template="plotly_white",
        height=400,
    )
    return fig.to_dict()


def create_mcp_chart(analysis: dict) -> dict:
    """MCP availability comparison."""
    public = analysis.get("mcp_public", {})
    composio = analysis.get("composio_supported", {})
    
    categories = ["yes", "no", "unknown"]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Public MCP",
        x=categories,
        y=[public.get(c, 0) for c in categories],
        marker_color="#4F46E5",
    ))
    fig.add_trace(go.Bar(
        name="Composio Supported",
        x=categories,
        y=[composio.get(c, 0) for c in categories],
        marker_color="#06B6D4",
    ))
    fig.update_layout(
        title="MCP Availability: Public vs Composio",
        barmode="group",
        xaxis_title="Status",
        yaxis_title="Count",
        template="plotly_white",
        height=400,
    )
    return fig.to_dict()


def create_category_heatmap(analysis: dict) -> dict:
    """Buildability by category heatmap."""
    by_cat = analysis.get("by_category", {})
    
    categories = list(by_cat.keys())
    build_states = ["ready", "buildable_with_caveat", "human_outreach_required", "blocked", "unknown"]
    
    z = []
    for state in build_states:
        row = []
        for cat in categories:
            row.append(by_cat[cat].get("buildability", {}).get(state, 0))
        z.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=categories,
        y=build_states,
        colorscale="RdYlGn",
        reversescale=True,
        text=z,
        texttemplate="%{text}",
        textfont={"size": 12},
    ))
    fig.update_layout(
        title="Buildability by Category",
        template="plotly_white",
        height=500,
        xaxis_tickangle=-45,
    )
    return fig.to_dict()


def create_opportunity_chart(analysis: dict) -> dict:
    """Opportunity score distribution by segment."""
    opportunities = analysis.get("opportunities", [])
    
    segments = ["quick_win", "high_value_gated", "high_effort", "needs_partnership", "blocked"]
    segment_colors = {
        "quick_win": "#10B981",
        "high_value_gated": "#3B82F6",
        "high_effort": "#F59E0B",
        "needs_partnership": "#8B5CF6",
        "blocked": "#EF4444",
    }
    
    fig = go.Figure()
    
    for segment in segments:
        seg_data = [o for o in opportunities if o["segment"] == segment]
        if not seg_data:
            continue
        
        fig.add_trace(go.Box(
            y=[o["score"] for o in seg_data],
            name=segment.replace("_", " ").title(),
            marker_color=segment_colors.get(segment, "#9CA3AF"),
            boxpoints="all",
            jitter=0.3,
            pointpos=-1.8,
        ))
    
    fig.update_layout(
        title="Opportunity Score by Segment",
        yaxis_title="Score (0-100)",
        template="plotly_white",
        height=400,
        showlegend=False,
    )
    return fig.to_dict()


def create_confidence_chart(analysis: dict) -> dict:
    """Confidence distribution."""
    data = analysis.get("confidence_distribution", {})
    
    buckets = sorted(data.keys())
    values = [data[b] for b in buckets]
    
    fig = go.Figure(data=[
        go.Bar(
            x=[f"{b:.1f}" for b in buckets],
            y=values,
            marker_color="#6366F1",
            text=values,
            textposition="auto",
        )
    ])
    fig.update_layout(
        title="Research Confidence Distribution",
        xaxis_title="Confidence",
        yaxis_title="Count",
        template="plotly_white",
        height=350,
    )
    return fig.to_dict()


def generate_all_charts(research_file: str = "data/research_final.jsonl", output_dir: str = "web/charts"):
    """Generate all charts and save as JSON."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    research = load_research(research_file)
    analysis = analyze_patterns(research)
    
    charts = {
        "auth": create_auth_chart(analysis),
        "credential_access": create_credential_access_chart(analysis),
        "buildability": create_buildability_chart(analysis),
        "mcp": create_mcp_chart(analysis),
        "category_heatmap": create_category_heatmap(analysis),
        "opportunity": create_opportunity_chart(analysis),
        "confidence": create_confidence_chart(analysis),
    }
    
    for name, chart in charts.items():
        with open(f"{output_dir}/{name}.json", "w") as f:
            json.dump(chart, f)
    
    # Also save combined
    with open(f"{output_dir}/all.json", "w") as f:
        json.dump(charts, f)
    
    print(f"Charts saved to {output_dir}/")
    return charts


if __name__ == "__main__":
    generate_all_charts()