import test from 'node:test';
import assert from 'node:assert/strict';
import { parseErrorMessage } from '../../agent_data/web/static/app.js';

test('parseErrorMessage — 8 categories', () => {
  assert.equal(parseErrorMessage(null), '运行失败：未知错误');
  assert.equal(parseErrorMessage('boom'), '运行失败：boom');
  assert.equal(parseErrorMessage('运行失败：x'), '运行失败：x');
  assert.equal(parseErrorMessage(new Error('NetworkError when attempting to fetch resource')), '运行失败：网络异常，请检查连接');
  assert.equal(parseErrorMessage(new Error('Request timeout exceeded (30000ms)')), '运行失败：查询超时（30s）');
  assert.equal(parseErrorMessage(new Error('LLM connect failed')), '运行失败：LLM 连接失败');
  assert.equal(parseErrorMessage({ message: '' }), '运行失败：未知错误');
  assert.equal(parseErrorMessage({ message: 'weird' }), '运行失败：weird');
});
