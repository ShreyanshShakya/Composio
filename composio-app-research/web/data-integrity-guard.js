document.addEventListener('DOMContentLoaded', () => {
    // app.js must finish loading before this guard runs.
    // If its demo fallback is ever used, make that state explicit instead of
    // allowing placeholder statistics to look like real research results.
    const looksLikeDemo = Array.isArray(window.researchData) &&
        window.researchData.length === 5 &&
        window.analysisData &&
        window.analysisData.total_apps === 100 &&
        window.analysisData.summary &&
        Number(window.analysisData.summary.avg_confidence) === 0.78;

    if (!looksLikeDemo) return;

    const banner = document.createElement('div');
    banner.style.cssText = [
        'position:fixed', 'inset:0', 'z-index:99999', 'display:flex',
        'align-items:center', 'justify-content:center', 'padding:24px',
        'background:rgba(15,23,42,.96)', 'color:#fff',
        'font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
    ].join(';');
    banner.innerHTML = `
        <div style="max-width:620px;text-align:center;padding:32px;border:1px solid #475569;border-radius:16px;background:#111827">
            <h2 style="margin:0 0 12px">Research dataset unavailable</h2>
            <p style="line-height:1.6;color:#cbd5e1;margin:0 0 20px">
                The case study is showing placeholder/demo data because the generated research dataset could not be loaded.
                This view is intentionally blocked so demo statistics cannot be mistaken for research results.
            </p>
            <a href="https://github.com/ShreyanshShakya/Composio" target="_blank" rel="noopener"
               style="color:#93c5fd">Open the research repository</a>
        </div>`;
    document.body.appendChild(banner);
});
