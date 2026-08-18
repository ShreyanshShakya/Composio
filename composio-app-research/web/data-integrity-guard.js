document.addEventListener('DOMContentLoaded', () => {
    // app.js uses top-level lexical bindings, so inspect the rendered output
    // rather than relying on window.researchData/window.analysisData.
    const hero = document.getElementById('hero-stats');
    const matrix = document.querySelectorAll('#matrix-table tbody tr');
    const renderedText = document.body.innerText || '';

    const looksLikeDemo = matrix.length === 5 &&
        renderedText.includes('78%') &&
        renderedText.includes('60%') &&
        renderedText.includes('57%') &&
        renderedText.includes('45%');

    if (!hero || !looksLikeDemo) return;

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
                The generated research dataset could not be loaded. The case study has blocked its placeholder/demo view so demo statistics cannot be mistaken for real research results.
            </p>
            <a href="https://github.com/ShreyanshShakya/Composio" target="_blank" rel="noopener" style="color:#93c5fd">Open the research repository</a>
        </div>`;
    document.body.appendChild(banner);
});
