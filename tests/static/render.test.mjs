import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { JSDOM } from 'jsdom';

test('renderTurn inserts an article element with expected class', async () => {
  const html = await readFile('agent_data/web/static/index.html', 'utf8');
  const dom = new JSDOM(html, { url: 'http://localhost:8000/' });

  // Import BEFORE exposing jsdom globals so the module-level init() guard
  // (typeof window === 'undefined') skips wiring in the test sandbox.
  // Node >=25 injects a broken `localStorage` global that makes guard fire falsely.
  const { renderTurn, EMPTY_CHIPS } = await import('../../agent_data/web/static/app.js');

  global.document = dom.window.document;
  global.window = dom.window;
  global.localStorage = dom.window.localStorage;

  const host = dom.window.document.getElementById('chat-list');
  const turn = {
    role: 'assistant',
    content: 'ok',
    sql: 'SELECT 1',
    rows: [{ '1': 1 }],
    columns: ['1'],
    ms: 5,
  };
  renderTurn(turn, host);
  const article = host.querySelector('article.turn.turn-assistant');
  assert.ok(article, 'expected an article.turn.turn-assistant');
  assert.equal(article.querySelector('.turn-bubble > p').textContent.trim(), 'ok');
  assert.ok(article.querySelector('details summary'), 'expected fold summary');
  assert.equal(EMPTY_CHIPS.length, 4);
});
