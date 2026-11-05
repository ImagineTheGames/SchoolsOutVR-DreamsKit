"""Dream validation report writer (ClickUp 17tm466wd3f).

Writes Saved/DreamReports/<Name>/validate.html and validate.json for a dream_validate_core.ValidationResult.
Same section shape as the uap report (a verdict banner, then one section per level, FAIL first). Plain Python,
no engine calls, so the Kit panel can open the HTML as is.
"""
import html
import json
import os

ORDER = ('FAIL', 'WARN', 'INFO', 'PASS')
COLORS = {'FAIL': '#b3261e', 'WARN': '#b26a00', 'INFO': '#44546a', 'PASS': '#1b6e3c'}


def _rows_html(rows):
    out = ['<table><tr><th>Check</th><th>Asset</th><th>Message</th></tr>']
    for r in rows:
        out.append('<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>' % (
            html.escape(r.check), html.escape(r.asset_path), html.escape(r.message)))
    out.append('</table>')
    return ''.join(out)


def render_html(result):
    verdict = 'PASS' if result.passed else 'FAIL'
    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8"><title>Dream validation - %s</title>' % html.escape(result.plugin_name),
             '<style>body{font-family:sans-serif;margin:24px;max-width:1000px}table{border-collapse:collapse;width:100%}'
             'td,th{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}h2{margin-top:24px}'
             '.v{font-size:22px;font-weight:bold}</style></head><body>',
             '<h1>Dream validation: %s</h1>' % html.escape(result.plugin_name),
             '<p class="v" style="color:%s">%s</p>' % (COLORS[verdict], verdict),
             '<p>Mode: %s. %d FAIL, %d WARN, %d INFO, %d PASS.</p>' % (
                 html.escape(result.mode), result.count('FAIL'), result.count('WARN'), result.count('INFO'), result.count('PASS'))]
    for level in ORDER:
        rows = [r for r in result.rows if r.level == level]
        if rows:
            parts.append('<h2 style="color:%s">%s (%d)</h2>' % (COLORS[level], level, len(rows)))
            parts.append(_rows_html(rows))
    if result.facts:
        parts.append('<h2>Measured</h2><table>')
        for k, v in result.facts.items():
            parts.append('<tr><td>%s</td><td>%s</td></tr>' % (html.escape(str(k)), html.escape(str(v))))
        parts.append('</table>')
    parts.append('</body></html>')
    return ''.join(parts)


def to_dict(result):
    return {
        'plugin': result.plugin_name,
        'mode': result.mode,
        'passed': result.passed,
        'counts': {lv: result.count(lv) for lv in ORDER},
        'facts': dict(result.facts),
        'rows': [{'check': r.check, 'level': r.level, 'asset_path': r.asset_path, 'message': r.message} for r in result.rows],
    }


def write_report(result, out_dir):
    """Write validate.html and validate.json into out_dir. Returns (html_path, json_path)."""
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, 'validate.html')
    json_path = os.path.join(out_dir, 'validate.json')
    with open(html_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(render_html(result))
    with open(json_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(to_dict(result), f, indent=1)
    return html_path, json_path
