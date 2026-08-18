let researchData = [];
let analysisData = {};
let chartsLoaded = false;

document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    initNavigation();
    renderAll();
});

async function loadData() {
    try {
        const [researchRes, analysisRes] = await Promise.all([
            fetch('research.json'),
            fetch('analysis.json')
        ]);
        researchData = await researchRes.json();
        analysisData = await analysisRes.json();
    } catch (e) {
        console.warn('Could not load data files, using demo data');
        loadDemoData();
    }
}

function loadDemoData() {
    researchData = [
        {app: "Slack", category: "Communications and Messaging", description: "Team communication platform", auth: ["oauth2"], credential_access: "self_serve", api_types: ["rest", "webhooks"], api_breadth: "broad", mcp_public: "no", composio_supported: "yes", buildability: "ready", blocker: null, confidence: 0.95, verification_status: "verified_correct"},
        {app: "Salesforce", category: "CRM and Sales", description: "Enterprise CRM platform", auth: ["oauth2"], credential_access: "paid_plan_required", api_types: ["rest", "soap"], api_breadth: "broad", mcp_public: "no", composio_supported: "yes", buildability: "buildable_with_caveat", blocker: "Requires paid developer edition", confidence: 0.9, verification_status: "verified_correct"},
        {app: "Notion", category: "Productivity and Project Management", description: "All-in-one workspace", auth: ["oauth2", "api_key"], credential_access: "self_serve", api_types: ["rest"], api_breadth: "limited", mcp_public: "no", composio_supported: "yes", buildability: "ready", blocker: null, confidence: 0.92, verification_status: "verified_correct"},
        {app: "Stripe", category: "Finance and Fintech", description: "Payment processing platform", auth: ["api_key", "bearer_token"], credential_access: "self_serve", api_types: ["rest"], api_breadth: "broad", mcp_public: "no", composio_supported: "yes", buildability: "ready", blocker: null, confidence: 0.96, verification_status: "verified_correct"},
        {app: "GitHub", category: "Developer, Infra and Data platforms", description: "Code hosting platform", auth: ["oauth2", "pat"], credential_access: "self_serve", api_types: ["rest", "graphql"], api_breadth: "broad", mcp_public: "no", composio_supported: "yes", buildability: "ready", blocker: null, confidence: 0.94, verification_status: "verified_correct"},
    ];
    
    analysisData = {
        total_apps: 100,
        auth_distribution: {"oauth2": 45, "api_key": 38, "bearer_token": 12, "pat": 8, "multiple": 25, "unknown": 5},
        credential_access: {"self_serve": 42, "self_serve_with_trial": 15, "paid_plan_required": 18, "admin_approval": 8, "partner_required": 5, "contact_sales": 7, "unknown": 5},
        api_types: {"rest": 85, "graphql": 12, "webhooks": 35, "soap": 8, "mcp": 3, "other": 5},
        api_breadth: {"broad": 52, "limited": 38, "unknown": 10},
        mcp_public: {"yes": 4, "no": 72, "unknown": 24},
        composio_supported: {"yes": 38, "no": 25, "unknown": 37},
        buildability: {"ready": 28, "buildable_with_caveat": 32, "human_outreach_required": 15, "blocked": 12, "unknown": 13},
        by_category: {},
        top_blockers: [["Requires paid plan", 15], ["Admin approval needed", 12], ["Partner program only", 8], ["Contact sales required", 7], ["No public API", 5]],
        confidence_distribution: {"0.9": 25, "0.8": 30, "0.7": 20, "0.6": 15, "0.5": 10},
        opportunities: [],
        summary: {
            total_apps: 100,
            buildable_pct: 60.0,
            self_serve_pct: 57.0,
            oauth_pct: 45.0,
            mcp_public_pct: 4.0,
            composio_pct: 38.0,
            top_blocker: "Requires paid plan",
            avg_confidence: 0.78
        }
    };
}

function initNavigation() {
    const navBtns = document.querySelectorAll('.nav-btn');
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.getElementById(btn.dataset.section).classList.add('active');
        });
    });
}

function renderAll() {
    renderHero();
    renderCharts();
    renderInsights();
    renderVerification();
    renderMatrix();
    populateFilters();
}

function renderHero() {
    const summary = analysisData.summary || {};
    const statsHtml = `
        <div class="stat-item">
            <div class="stat-value">${summary.buildable_pct || 0}%</div>
            <div class="stat-label">Buildable Today</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${summary.self_serve_pct || 0}%</div>
            <div class="stat-label">Self-Serve Access</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${summary.oauth_pct || 0}%</div>
            <div class="stat-label">OAuth-Based</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${summary.avg_confidence ? (summary.avg_confidence * 100).toFixed(0) : 0}%</div>
            <div class="stat-label">Avg Confidence</div>
        </div>
    `;
    document.getElementById('hero-stats').innerHTML = statsHtml;
    
    const insightsHtml = `
        <div class="insight-item">
            <div class="insight-label">Top Blocker</div>
            <div class="insight-value">${summary.top_blocker || 'N/A'}</div>
        </div>
        <div class="insight-item">
            <div class="insight-label">MCP Public</div>
            <div class="insight-value">${summary.mcp_public_pct || 0}%</div>
        </div>
        <div class="insight-item">
            <div class="insight-label">Composio Ready</div>
            <div class="insight-value">${summary.composio_pct || 0}%</div>
        </div>
    `;
    document.getElementById('hero-insights').innerHTML = insightsHtml;
}

function renderCharts() {
    if (chartsLoaded) return;
    
    loadChart('auth', 'chart-auth', analysisData.auth_distribution, 'bar');
    loadChart('credential', 'chart-credential', analysisData.credential_access, 'pie');
    loadChart('buildability', 'chart-buildability', analysisData.buildability, 'funnel');
    loadChart('mcp', 'chart-mcp', {public: analysisData.mcp_public, composio: analysisData.composio_supported}, 'grouped-bar');
    loadCategoryHeatmap();
    loadOpportunityChart();
    loadConfidenceChart();
    
    chartsLoaded = true;
}

function loadChart(name, elementId, data, type) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    let fig;
    switch(type) {
        case 'bar':
            fig = createBarChart(data, 'Authentication Methods');
            break;
        case 'pie':
            fig = createPieChart(data, 'Credential Access');
            break;
        case 'funnel':
            fig = createFunnelChart(data, 'Buildability');
            break;
        case 'grouped-bar':
            fig = createGroupedBarChart(data, 'MCP Availability');
            break;
    }
    
    if (fig) {
        Plotly.newPlot(el, fig.data, fig.layout, {responsive: true, displayModeBar: false});
    }
}

function createBarChart(data, title) {
    const order = ['oauth2', 'api_key', 'bearer_token', 'pat', 'service_account', 'basic', 'multiple', 'other', 'unknown'];
    const labels = order.filter(k => data[k]);
    const values = labels.map(k => data[k]);
    
    return {
        data: [{type: 'bar', x: labels, y: values, marker: {color: '#4F46E5'}, text: values, textposition: 'auto'}],
        layout: {title, xaxis: {title: 'Auth Method'}, yaxis: {title: 'Count'}, template: 'plotly_white', height: 350, margin: {t: 50, b: 60, l: 50, r: 20}}
    };
}

function createPieChart(data, title) {
    const order = ['self_serve', 'self_serve_with_trial', 'paid_plan_required', 'admin_approval', 'partner_required', 'contact_sales', 'unknown'];
    const colors = ['#10B981', '#34D399', '#F59E0B', '#F97316', '#EF4444', '#DC2626', '#9CA3AF'];
    const labels = [];
    const values = [];
    const usedColors = [];
    
    order.forEach((k, i) => {
        if (data[k]) {
            labels.push(k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()));
            values.push(data[k]);
            usedColors.push(colors[i]);
        }
    });
    
    return {
        data: [{type: 'pie', labels, values, marker: {colors: usedColors}, hole: 0.4, textinfo: 'label+percent'}],
        layout: {title, template: 'plotly_white', height: 350, margin: {t: 50, b: 20, l: 20, r: 20}}
    };
}

function createFunnelChart(data, title) {
    const order = ['ready', 'buildable_with_caveat', 'human_outreach_required', 'blocked', 'unknown'];
    const colors = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#9CA3AF'];
    const labels = [];
    const values = [];
    const usedColors = [];
    
    order.forEach((k, i) => {
        if (data[k]) {
            labels.push(k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()));
            values.push(data[k]);
            usedColors.push(colors[i]);
        }
    });
    
    return {
        data: [{type: 'funnel', y: labels, x: values, marker: {color: usedColors}, textinfo: 'value+percent initial'}],
        layout: {title, template: 'plotly_white', height: 350, margin: {t: 50, b: 20, l: 100, r: 20}}
    };
}

function createGroupedBarChart(data, title) {
    const categories = ['yes', 'no', 'unknown'];
    
    return {
        data: [
            {type: 'bar', name: 'Public MCP', x: categories, y: categories.map(c => data.public?.[c] || 0), marker: {color: '#4F46E5'}},
            {type: 'bar', name: 'Composio', x: categories, y: categories.map(c => data.composio?.[c] || 0), marker: {color: '#06B6D4'}}
        ],
        layout: {title, barmode: 'group', xaxis: {title: 'Status'}, yaxis: {title: 'Count'}, template: 'plotly_white', height: 350, margin: {t: 50, b: 60, l: 50, r: 20}}
    };
}

function loadCategoryHeatmap() {
    const byCat = analysisData.by_category || {};
    const categories = Object.keys(byCat);
    if (categories.length === 0) return;
    
    const buildStates = ['ready', 'buildable_with_caveat', 'human_outreach_required', 'blocked', 'unknown'];
    const z = buildStates.map(state => 
        categories.map(cat => byCat[cat]?.buildability?.[state] || 0)
    );
    
    const fig = {
        data: [{type: 'heatmap', z, x: categories, y: buildStates.map(s => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())), colorscale: 'RdYlGn', reversescale: true, text: z, texttemplate: '%{text}', textfont: {size: 12}}],
        layout: {title: 'Buildability by Category', template: 'plotly_white', height: 450, margin: {t: 50, b: 100, l: 100, r: 20}, xaxis: {tickangle: -45}}
    };
    
    const el = document.getElementById('chart-category-heatmap');
    if (el) Plotly.newPlot(el, fig.data, fig.layout, {responsive: true, displayModeBar: false});
}

function loadOpportunityChart() {
    const opportunities = analysisData.opportunities || [];
    if (opportunities.length === 0) return;
    
    const segments = ['quick_win', 'high_value_gated', 'high_effort', 'needs_partnership', 'blocked'];
    const colors = {'quick_win': '#10B981', 'high_value_gated': '#3B82F6', 'high_effort': '#F59E0B', 'needs_partnership': '#8B5CF6', 'blocked': '#EF4444'};
    
    const data = segments.map(seg => {
        const segData = opportunities.filter(o => o.segment === seg);
        return {
            type: 'box',
            y: segData.map(o => o.score),
            name: seg.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
            marker: {color: colors[seg]},
            boxpoints: 'all',
            jitter: 0.3,
            pointpos: -1.8
        };
    });
    
    const fig = {data, layout: {title: 'Opportunity Score by Segment', yaxis: {title: 'Score (0-100)'}, template: 'plotly_white', height: 350, showlegend: false, margin: {t: 50, b: 60, l: 50, r: 20}}};
    
    const el = document.getElementById('chart-opportunity');
    if (el) Plotly.newPlot(el, fig.data, fig.layout, {responsive: true, displayModeBar: false});
}

function loadConfidenceChart() {
    const data = analysisData.confidence_distribution || {};
    const buckets = Object.keys(data).sort();
    const values = buckets.map(b => data[b]);
    
    const fig = {
        data: [{type: 'bar', x: buckets, y: values, marker: {color: '#6366F1'}, text: values, textposition: 'auto'}],
        layout: {title: 'Research Confidence Distribution', xaxis: {title: 'Confidence'}, yaxis: {title: 'Count'}, template: 'plotly_white', height: 300, margin: {t: 50, b: 60, l: 50, r: 20}}
    };
    
    const el = document.getElementById('chart-confidence');
    if (el) Plotly.newPlot(el, fig.data, fig.layout, {responsive: true, displayModeBar: false});
}

function renderInsights() {
    const insights = [];
    
    const auth = analysisData.auth_distribution || {};
    const topAuth = Object.entries(auth).sort((a,b) => b[1]-a[1])[0];
    if (topAuth) insights.push(`<strong>${topAuth[0].toUpperCase()}</strong> is the most common auth method (${topAuth[1]} apps)`);
    
    const cred = analysisData.credential_access || {};
    const selfServe = (cred.self_serve || 0) + (cred.self_serve_with_trial || 0);
    const gated = (cred.paid_plan_required || 0) + (cred.admin_approval || 0) + (cred.partner_required || 0) + (cred.contact_sales || 0);
    insights.push(`<strong>${selfServe} apps</strong> offer self-serve credentials vs <strong>${gated}</strong> that require approval/sales`);
    
    const build = analysisData.buildability || {};
    const ready = build.ready || 0;
    const caveat = build.buildable_with_caveat || 0;
    insights.push(`<strong>${ready + caveat} apps</strong> are buildable (${ready} ready, ${caveat} with caveats)`);
    
    const mcp = analysisData.mcp_public || {};
    insights.push(`Only <strong>${mcp.yes || 0} apps</strong> have public MCP servers`);
    
    const blockers = analysisData.top_blockers || [];
    if (blockers.length > 0) {
        insights.push(`Top blocker: <strong>"${blockers[0][0]}"</strong> affects ${blockers[0][1]} apps`);
    }
    
    const summary = analysisData.summary || {};
    insights.push(`Average research confidence: <strong>${(summary.avg_confidence * 100).toFixed(0)}%</strong>`);
    
    document.getElementById('key-insights').innerHTML = insights.map(i => `<li>${i}</li>`).join('');
}

function renderVerification() {
    // This would be populated from verification.csv after human review
    const statsHtml = `
        <div class="verification-stat">
            <div class="stat-value">—</div>
            <div class="stat-label">Overall Accuracy</div>
        </div>
        <div class="verification-stat">
            <div class="stat-value">—</div>
            <div class="stat-label">Auth Accuracy</div>
        </div>
        <div class="verification-stat">
            <div class="stat-value">—</div>
            <div class="stat-label">Credential Accuracy</div>
        </div>
        <div class="verification-stat">
            <div class="stat-value">—</div>
            <div class="stat-label">Buildability Accuracy</div>
        </div>
    `;
    document.getElementById('verification-stats').innerHTML = statsHtml;
    
    const errorTypes = [
        ['AUTH_MISCLASSIFICATION', 0, 'Auth method incorrectly identified'],
        ['SELF_SERVE_CONFUSION', 0, 'Confused API access with credential access'],
        ['PAID_PLAN_CONFUSION', 0, 'Missed paid plan requirement for credentials'],
        ['ENTERPRISE_GATE', 0, 'Enterprise-only access not detected'],
        ['PARTNER_GATE', 0, 'Partner-only access not detected'],
        ['API_SCOPE_ERROR', 0, 'API breadth misclassified'],
        ['MCP_FALSE_POSITIVE', 0, 'Claimed MCP exists when it does not'],
        ['OUTDATED_DOC', 0, 'Used deprecated documentation'],
        ['INSUFFICIENT_EVIDENCE', 0, 'Classification without adequate sources'],
    ];
    
    const tbody = document.querySelector('#error-table tbody');
    tbody.innerHTML = errorTypes.map(([type, count, desc]) => `
        <tr><td><code>${type}</code></td><td>${count}</td><td>${desc}</td></tr>
    `).join('');
    
    document.getElementById('improvement-text').textContent = 
        'Run verification sample (20 apps) and fill verification.csv, then run: python scripts/verify_sample.py --calculate';
}

function populateFilters() {
    const categories = [...new Set(researchData.map(r => r.category))].sort();
    const buildabilities = [...new Set(researchData.map(r => r.buildability))].sort();
    const authMethods = [...new Set(researchData.flatMap(r => r.auth))].sort();
    const gating = [...new Set(researchData.map(r => r.credential_access))].sort();
    
    const catSelect = document.getElementById('filter-category');
    catSelect.innerHTML = '<option value="">All Categories</option>' + categories.map(c => `<option value="${c}">${c}</option>`).join('');
    
    const buildSelect = document.getElementById('filter-buildability');
    buildSelect.innerHTML = '<option value="">All Buildability</option>' + buildabilities.map(b => `<option value="${b}">${b.replace(/_/g, ' ')}</option>`).join('');
    
    const authSelect = document.getElementById('filter-auth');
    authSelect.innerHTML = '<option value="">All Auth</option>' + authMethods.map(a => `<option value="${a}">${a}</option>`).join('');
    
    const gateSelect = document.getElementById('filter-gating');
    gateSelect.innerHTML = '<option value="">All Credential Access</option>' + gating.map(g => `<option value="${g}">${g.replace(/_/g, ' ')}</option>`).join('');
    
    const confSelect = document.getElementById('filter-confidence');
    confSelect.innerHTML = '<option value="">All Confidence</option><option value="high">High (≥0.8)</option><option value="medium">Medium (0.5-0.8)</option><option value="low">Low (<0.5)</option>';
    
    document.getElementById('search-input').addEventListener('input', renderMatrix);
    catSelect.addEventListener('change', renderMatrix);
    buildSelect.addEventListener('change', renderMatrix);
    authSelect.addEventListener('change', renderMatrix);
    gateSelect.addEventListener('change', renderMatrix);
    confSelect.addEventListener('change', renderMatrix);
}

function renderMatrix() {
    const search = document.getElementById('search-input').value.toLowerCase();
    const catFilter = document.getElementById('filter-category').value;
    const buildFilter = document.getElementById('filter-buildability').value;
    const authFilter = document.getElementById('filter-auth').value;
    const gateFilter = document.getElementById('filter-gating').value;
    const confFilter = document.getElementById('filter-confidence').value;
    
    let filtered = researchData.filter(r => {
        if (search && !r.app.toLowerCase().includes(search) && !r.category.toLowerCase().includes(search)) return false;
        if (catFilter && r.category !== catFilter) return false;
        if (buildFilter && r.buildability !== buildFilter) return false;
        if (authFilter && !r.auth.includes(authFilter)) return false;
        if (gateFilter && r.credential_access !== gateFilter) return false;
        if (confFilter) {
            if (confFilter === 'high' && r.confidence < 0.8) return false;
            if (confFilter === 'medium' && (r.confidence < 0.5 || r.confidence >= 0.8)) return false;
            if (confFilter === 'low' && r.confidence >= 0.5) return false;
        }
        return true;
    });
    
    const tbody = document.querySelector('#matrix-table tbody');
    tbody.innerHTML = filtered.map(r => `
        <tr>
            <td><strong>${r.app}</strong></td>
            <td>${r.category}</td>
            <td>${r.auth.join(', ')}</td>
            <td>${r.credential_access.replace(/_/g, ' ')}</td>
            <td>${r.api_types.join(', ')}</td>
            <td>${r.mcp_public}</td>
            <td>${r.composio_supported}</td>
            <td><span class="buildability-badge build-${r.buildability.replace(/_/g, '-')}">${r.buildability.replace(/_/g, ' ')}</span></td>
            <td>${r.blocker || '—'}</td>
            <td><span class="confidence-badge confidence-${r.confidence >= 0.8 ? 'high' : r.confidence >= 0.5 ? 'medium' : 'low'}">${(r.confidence * 100).toFixed(0)}%</span></td>
            <td>${r.evidence ? r.evidence.length : 0} sources</td>
        </tr>
    `).join('');
    
    document.getElementById('showing-count').textContent = filtered.length;
    document.getElementById('total-count').textContent = researchData.length;
}