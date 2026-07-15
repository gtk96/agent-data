// agent_data/web/static/app.js
// Browser-side state + render + fetch for the NL2SQL web UI.
// ESM module loaded with `defer`. No build step.

export const EMPTY_CHIPS = Object.freeze([
  '有多少用户？',
  '订单总额多少？',
  '最受欢迎的产品？',
  '上周有几笔订单？',
]);

const HEALTH_INTERVAL_MS = 30_000;

/**
 * Classify a thrown/network error into one of 8 UI message keys.
 * Pure function — no DOM access, easy to unit test.
 * @param {unknown} err
 * @returns {string} UI message prefix (no emoji)
 */
export function parseErrorMessage(err) {
  if (err == null) return '运行失败：未知错误';
  if (typeof err === 'string') return err.startsWith('运行失败') ? err : `运行失败：${err}`;
  if (typeof Response !== 'undefined' && err instanceof Response) {
    return `运行失败：HTTP ${err.status}`;
  }
  const msg = (err && err.message) ? String(err.message) : '';
  if (/timeout|timed out|TimeoutError/i.test(msg)) return '运行失败：查询超时（30s）';
  if (/NetworkError|fetch failed|Failed to fetch/i.test(msg)) return '运行失败：网络异常，请检查连接';
  if (/LLM.*connect|api.*unreachable|503|502|504/i.test(msg)) return '运行失败：LLM 连接失败';
  return `运行失败：${msg || '未知错误'}`;
}

/**
 * Render a single conversation turn into the given host element.
 * @param {{role:'user'|'assistant', content:string, sql?:string, rows?:Array<Record<string, unknown>>, columns?:string[], ms?:number, error?:string, retry?:boolean}} turn
 * @param {HTMLElement} host
 */
export function renderTurn(turn, host) {
  const article = document.createElement('article');
  article.className = `turn turn-${turn.role}`;

  const meta = document.createElement('div');
  meta.className = 'turn-meta';
  meta.textContent = turn.role === 'user' ? '你' : '助手';
  article.appendChild(meta);

  const bubble = document.createElement('div');
  bubble.className = 'turn-bubble';
  if (turn.content) {
    const p = document.createElement('p');
    p.textContent = turn.content;
    bubble.appendChild(p);
  }
  article.appendChild(bubble);

  if (turn.role === 'assistant' && (turn.sql || turn.rows || turn.ms != null)) {
    const fold = document.createElement('div');
    fold.className = 'fold';
    if (turn.rows && turn.columns) {
      fold.appendChild(makeFold('▸ 表格 (' + (turn.rows.length || 0) + ' 行)', renderTable(turn.rows, turn.columns)));
    }
    if (turn.sql) {
      fold.appendChild(makeFold('▸ SQL (' + (turn.ms != null ? turn.ms : '?') + 'ms)', renderSql(turn.sql)));
    }
    bubble.appendChild(fold);
  }

  if (turn.role === 'assistant' && turn.error && turn.retry) {
    const row = document.createElement('div');
    row.className = 'error-row';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'retry-btn';
    btn.textContent = '↻ 重试';
    btn.dataset.action = 'retry';
    row.appendChild(btn);
    bubble.appendChild(row);
  }

  host.appendChild(article);
}

function makeFold(summaryText, bodyNode) {
  const det = document.createElement('details');
  const sum = document.createElement('summary');
  sum.textContent = summaryText;
  det.appendChild(sum);
  det.appendChild(bodyNode);
  return det;
}

function renderTable(rows, columns) {
  const card = document.createElement('div');
  card.className = 'table-card';
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  for (const col of columns) {
    const th = document.createElement('th');
    th.textContent = col;
    trh.appendChild(th);
  }
  thead.appendChild(trh);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for (const row of rows) {
    const tr = document.createElement('tr');
    for (const col of columns) {
      const td = document.createElement('td');
      td.textContent = row[col] == null ? '' : String(row[col]);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  card.appendChild(table);
  return card;
}

function renderSql(sql) {
  const pre = document.createElement('pre');
  pre.className = 'sql-block';
  pre.textContent = sql;
  return pre;
}

// ---------- State + DOM wiring (runs only in browser) ----------
function init() {
  const state = { turns: [], sessionId: localStorage.getItem('agentdata.session') || null };
  const host = document.getElementById('chat-list');
  const empty = document.getElementById('chat-empty');
  const chipList = document.getElementById('chip-list');
  const composer = document.getElementById('composer');
  const input = document.getElementById('chat-input');
  const spinner = document.getElementById('spinner');
  const statusDot = document.getElementById('header-status-dot');
  const statusText = document.getElementById('header-status-text');

  // populate chips
  if (chipList) {
    for (const q of EMPTY_CHIPS) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip';
      b.textContent = q;
      b.addEventListener('click', () => { input.value = q; input.focus(); submit(); });
      chipList.appendChild(b);
    }
  }

  async function submit() {
    const question = (input.value || '').trim();
    if (!question) return;
    input.value = '';
    input.disabled = true;
    spinner.hidden = false;
    empty?.remove();

    state.turns.push({ role: 'user', content: question, ts: new Date().toISOString() });
    renderTurn(state.turns.at(-1), host);

    try {
      const resp = await fetch('/api/v1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: state.sessionId }),
      });
      if (!resp.ok) {
        const body = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status} ${body.slice(0, 200)}`);
      }
      const json = await resp.json();
      state.sessionId = json.session_id || state.sessionId;
      if (state.sessionId) localStorage.setItem('agentdata.session', state.sessionId);
      const turn = {
        role: 'assistant',
        content: json.answer || '',
        sql: json.sql || '',
        rows: json.data || [],
        columns: json.columns || [],
        ms: Math.round(json.query_time_ms || 0),
      };
      state.turns.push(turn);
      renderTurn(turn, host);
      healthTick();
    } catch (err) {
      const ui = parseErrorMessage(err);
      const turn = { role: 'assistant', content: ui, error: ui, retry: true, ts: new Date().toISOString() };
      state.turns.push(turn);
      renderTurn(turn, host);
    } finally {
      input.disabled = false;
      spinner.hidden = true;
      input.focus();
    }
  }

  host.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.matches('button[data-action="retry"]')) {
      // find the user question preceding this assistant turn
      const assistantTurn = t.closest('.turn');
      if (!assistantTurn) return;
      const turns = Array.from(host.querySelectorAll('.turn'));
      const idx = turns.indexOf(assistantTurn);
      const prev = turns[idx - 1];
      if (prev && prev.classList.contains('turn-user')) {
        const q = prev.querySelector('.turn-bubble p')?.textContent || '';
        if (q) { input.value = q; submit(); }
      }
    }
  });

  composer.addEventListener('submit', (e) => { e.preventDefault(); submit(); });

  async function healthTick() {
    try {
      const r = await fetch('/api/v1/health');
      const j = await r.json();
      const ok = j && (j.status === 'healthy' || j.status === 'no_engine') && j.database;
      statusDot.className = 'status-dot ' + (ok ? 'status-dot--ok' : 'status-dot--err');
      let label;
      if (!j) label = '● 引擎未就绪';
      else if (j.status === 'healthy') label = '● 引擎 ready';
      else if (j.status === 'no_engine') label = '● 引擎未就绪（无 LLM）';
      else label = '● 引擎 ' + j.status;
      statusText.textContent = label;
      statusDot.setAttribute('aria-label', label.replace(/^●\s*/, ''));
    } catch {
      statusDot.className = 'status-dot status-dot--err';
      statusText.textContent = '● 引擎未就绪';
      statusDot.setAttribute('aria-label', '引擎未就绪');
    }
  }

  healthTick();
  setInterval(healthTick, HEALTH_INTERVAL_MS);
}

if (typeof window !== 'undefined' && document.getElementById('composer')) init();
