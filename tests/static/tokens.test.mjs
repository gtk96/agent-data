import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const CSS = await readFile('agent_data/web/static/style.css', 'utf8');

test('design tokens present', () => {
  for (const v of ['--bg', '--text', '--accent', '--radius-bubble', '--radius-input', '--fs-body']) {
    assert.match(CSS, new RegExp(v + '\\s*:'));
  }
});

test('colors match spec values', () => {
  assert.match(CSS, /--bg\s*:\s*#F7F7F8/);
  assert.match(CSS, /--text\s*:\s*#111827/);
  assert.match(CSS, /--accent\s*:\s*#4F46E5/);
});
