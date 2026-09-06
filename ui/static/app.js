'use strict';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let STATE = { examples: [], library: [], predicates: [] };

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

// ------------------------------------------------------------------ startup

async function boot() {
  STATE = await (await fetch('/api/state')).json();

  STATE.examples.forEach((ex, i) => {
    const o = new Option(ex.name, String(i));
    $('examples').add(o);
  });
  STATE.library.forEach(f => {
    const label = `${f.scratch ? '✎ ' : ''}${f.path}  (${f.rules} rule${f.rules === 1 ? '' : 's'})`;
    $('library').add(new Option(label, f.path));
  });
  $('engine').textContent = `engine: ${STATE.engine}`;

  parse();
}

// -------------------------------------------------------------- parse check

let parseTimer = null;
function parseSoon() { clearTimeout(parseTimer); parseTimer = setTimeout(parse, 350); }

async function parse() {
  const text = $('rules').value;
  if (!text.trim()) {
    $('parse').innerHTML = '<span class="muted">No rules — nothing can fire.</span>';
    return;
  }
  const { rules } = await post('/api/parse', { text });
  const bad = rules.filter(r => r.errors.length);
  const parts = [
    `<span class="pill ${bad.length ? 'bad' : 'ok'}">` +
    `${rules.length} rule${rules.length === 1 ? '' : 's'}, ${bad.length} with errors</span>`,
  ];
  for (const r of rules) {
    if (!r.errors.length) continue;
    parts.push(`<div class="err small" style="margin-top:6px">@${esc(r.id)}` +
      r.errors.map(e => `<br>&nbsp;&nbsp;L${e.line}:${e.column} ${esc(e.message)}`).join(''));
  }
  if (bad.length) {
    parts.push('<p class="hint">The rule still loads — <code>Rule.from_text</code> ' +
      'installs no error listener, so bad rules fail <em>open</em>. See Help &rsaquo; ' +
      'Known grammar limits.</p>');
  }
  $('parse').innerHTML = parts.join('');
}

// ---------------------------------------------------------------- rendering

function steps() {
  const raw = $('steps').value.trim();
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

function renderWhy(explain) {
  if (!explain.length) {
    $('why').innerHTML = '<p class="muted small">No rules loaded — nothing could fire.</p>';
    return;
  }
  $('why').innerHTML = explain.map(r => {
    const fired = r.would_fire;
    let body = '';

    if (r.errors.length) {
      body += `<div class="err small">does not parse: ` +
        r.errors.map(e => `L${e.line}:${e.column} ${esc(e.message)}`).join('; ') + '</div>';
    }
    body += `<div class="small muted">trigger <code>${esc(r.trigger)}</code> vs this call: ` +
      `<span class="pill ${r.triggered === true ? 'ok' : 'mute'}">` +
      `${r.triggered === true ? 'matched' : 'no match'}</span></div>`;

    if (r.checks.length) {
      body += '<table><tr><th>check</th><th>value</th></tr>' + r.checks.map(c => {
        const v = c.error ? `<span class="err">${esc(c.error)}</span>`
          : `<span class="pill ${c.effective ? 'ok' : 'mute'}">${c.effective}</span>` +
            (c.negated ? ` <span class="muted small">(raw ${c.value}, negated)</span>` : '');
        return `<tr><td class="mono">${esc(c.raw)}</td><td>${v}</td></tr>`;
      }).join('') + '</table>';
    } else if (r.triggered === true) {
      body += '<div class="small muted">no checks parsed — nothing to evaluate</div>';
    }

    body += `<div class="small" style="margin-top:6px">enforce <code>` +
      `${esc(r.enforce.join(', ') || '—')}</code> &rarr; ` +
      `<b>${fired ? 'FIRES' : 'does not fire'}</b></div>`;

    return `<div class="rulecard ${fired ? 'fired' : 'quiet'}">` +
      `<h3>@${esc(r.id)}</h3>${body}</div>`;
  }).join('');
}

function renderOutcome(res) {
  const toolRow = res.tool_calls.length
    ? `<span class="pill bad">reached</span> <code>${esc(res.tool_calls.join(' | '))}</code>`
    : '<span class="pill ok">never reached</span>';

  let html = `<table>
    <tr><th>tool</th><td>${toolRow}</td></tr>
    <tr><th>final output</th><td class="mono">${esc(res.output).slice(0, 300) || '<span class="muted">—</span>'}</td></tr>
    <tr><th>steps</th><td>${res.steps.length}</td></tr>
  </table>`;

  if (res.steps.length) {
    html += '<table style="margin-top:8px"><tr><th>#</th><th>action</th><th>observation</th></tr>' +
      res.steps.map((s, i) =>
        `<tr><td>${i + 1}</td><td class="mono">${esc(s.tool)}(${esc(JSON.stringify(s.input))})</td>` +
        `<td class="mono">${esc(s.observation).slice(0, 220)}</td></tr>`).join('') + '</table>';
  }
  if (res.error) html += `<pre class="err" style="margin-top:8px">${esc(res.error)}</pre>`;
  $('outcome').innerHTML = html;
}

// The same call, decided by Cedar against policies/ (plan.md S1.8). Shown next
// to the legacy verdict rather than instead of it: a disagreement between the
// two is the interesting output of this bench, not an error in it.
function renderCedar(c, legacyVerdict) {
  const panel = (body, tint) =>
    `<div class="panel" style="margin-top:14px${tint ? ';background:var(--code)' : ''}">
       <h2>Cedar decision <span class="muted" style="text-transform:none">— policies/, decided independently</span></h2>
       ${body}</div>`;

  if (c.status !== 'ok') {
    $('cedar').innerHTML = panel(
      `<p class="err small" style="margin:0">${esc(c.note || 'no decision')}</p>`, true);
    return;
  }

  const deny = c.decision === 'Deny';
  const agrees = c.verdict === legacyVerdict;

  const active = `${c.sensors.length} active of ${c.registered} registered`;
  const flags = c.flags.length
    ? c.flags.map(f => `<span class="pill bad" style="margin:2px 3px 2px 0">${esc(f)}</span>`).join('')
    : `<span class="muted small">nothing fired</span>`;

  const reasons = c.reasons.length
    ? '<table style="margin-top:8px"><tr><th>policy</th><th>@advice</th><th>@source</th></tr>' +
      c.reasons.map(r =>
        `<tr><td class="mono">@${esc(r.id)}</td>` +
        `<td>${r.advice ? `<span class="pill ${r.advice === 'stop' ? 'bad' : 'warn'}">${esc(r.advice)}</span>` : '<span class="muted">—</span>'}</td>` +
        `<td class="mono small">${esc(r.source || '—')}</td></tr>`).join('') + '</table>'
    : '<p class="small muted" style="margin-top:8px">no determining policies</p>';

  const errors = c.errors.length
    ? `<p class="err small">engine errors (failing closed): ${esc(c.errors.join('; '))}</p>` : '';

  $('cedar').innerHTML = panel(`
    <div class="row" style="gap:14px;align-items:center">
      <span class="verdict ${deny ? 'STOPPED' : 'ALLOWED'}">${esc(c.decision)}</span>
      <span class="small">resolves to <b>${esc(c.verdict)}</b></span>
      <span class="pill ${agrees ? 'ok' : 'bad'}">${agrees
        ? 'agrees with the legacy verdict'
        : `differs — legacy said ${esc(legacyVerdict)}`}</span>
    </div>
    ${errors}
    <p class="small" style="margin:10px 0 4px"><b>context.flags</b>
      <span class="muted">— what the Python sensors materialised (${esc(active)})</span></p>
    <div>${flags}</div>
    <p class="small" style="margin:12px 0 0"><b>diagnostics.reasons</b>
      <span class="muted">— the policies that determined it</span></p>
    ${reasons}
    <details style="margin-top:10px"><summary>Raw request &amp; entities</summary>
      <pre>${esc(JSON.stringify({ request: c.request, entities: c.entities }, null, 2))}</pre>
    </details>`);
}

const WHY_VERDICT = {
  ALLOWED: 'the tool was reached — no rule blocked this action',
  STOPPED: 'a rule fired with enforce stop; the run ended before the tool',
  SKIPPED: 'a rule suppressed the action, but the run continued',
  'NO ACTION': 'the agent never proposed a tool call',
  ERROR: 'the run raised — see the trace',
};

async function run() {
  $('busy').textContent = 'running…';
  const res = await post('/api/run', {
    rule_text: $('rules').value,
    user_input: $('task').value,
    tool_name: $('tool').value.trim() || 'python_repl',
    tool_input: $('input').value,
    intermediate_steps: steps(),
    approve: $('approve').checked,
  });
  $('busy').textContent = '';
  $('results').hidden = false;

  $('verdict').textContent = res.verdict;
  $('verdict').className = 'verdict ' + res.verdict.replace(/\s/g, '');
  $('verdictWhy').textContent = WHY_VERDICT[res.verdict] || '';

  renderWhy(res.explain);
  renderOutcome(res);
  $('trace').textContent = res.trace || '(no trace)';

  renderCedar(res.cedar || {}, res.verdict);

  $('results').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function probe() {
  $('busy').textContent = 'probing…';
  const { predicates } = await post('/api/probe', {
    user_input: $('task').value,
    tool_input: $('input').value,
    intermediate_steps: steps(),
  });
  $('busy').textContent = '';
  $('probes').hidden = false;

  const hit = predicates.filter(p => p.value === true);
  const err = predicates.filter(p => p.error);
  const rest = predicates.filter(p => p.value === false);

  const list = (items, cls) => items.map(p =>
    `<span class="pill ${cls}" style="margin:2px 3px 2px 0" title="${esc(p.error || '')}">` +
    `${esc(p.name)}</span>`).join(' ');

  $('probeBody').innerHTML =
    `<p class="small"><b>${hit.length} fire</b> on this input:</p><div>${list(hit, 'bad') || '<span class="muted small">none</span>'}</div>` +
    (err.length ? `<p class="small" style="margin-top:12px"><b>${err.length} raised</b> (hover for the message) — most expect a different <code>intermediate_steps</code> shape:</p><div>${list(err, 'warn')}</div>` : '') +
    `<details style="margin-top:12px"><summary>${rest.length} returned false</summary><div style="margin-top:6px">${list(rest, 'mute')}</div></details>`;
  $('probes').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ------------------------------------------------------------------ wiring

$('run').onclick = run;
$('probe').onclick = probe;
$('rules').oninput = parseSoon;

$('clear').onclick = () => { $('rules').value = ''; parse(); };

$('examples').onchange = (e) => {
  const ex = STATE.examples[Number(e.target.value)];
  if (!ex) return;
  $('rules').value = ex.rule_text;
  $('task').value = ex.user_input;
  $('tool').value = ex.tool_name;
  $('input').value = ex.tool_input;
  $('steps').value = '';
  parse();
  $('busy').innerHTML = `<span class="muted">${esc(ex.why)} <b>Expect: ${esc(ex.expect)}</b></span>`;
};

$('library').onchange = async (e) => {
  if (!e.target.value) return;
  const r = await (await fetch('/api/rule?path=' + encodeURIComponent(e.target.value))).json();
  if (r.error) { $('parse').innerHTML = `<span class="err">${esc(r.error)}</span>`; return; }
  $('rules').value = r.text;
  parse();
};

$('save').onclick = async () => {
  const suggested = $('library').value.startsWith('ui/')
    ? $('library').value : 'ui/rules/my_rules.ar';
  const path = prompt('Save to (must be under ui/rules/ or src/rules/):', suggested);
  if (!path) return;
  const r = await post('/api/rule', { path, text: $('rules').value });
  $('parse').innerHTML = r.error
    ? `<span class="err">${esc(r.error)}</span>`
    : `<span class="pill ok">saved ${esc(r.saved)}</span>`;
};

// Cmd/Ctrl+Enter runs, the way a REPL would.
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); run(); }
});

boot();
