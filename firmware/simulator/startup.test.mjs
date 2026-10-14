import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

const server = new URL('./server.mjs', import.meta.url);
function start(settings) {
  return spawnSync(process.execPath, [server.pathname], {
    env: {...process.env, PIKOO_SIM_CONFIG: '', PIKOO_WAKE_PYTHON: '', PIKOO_WAKE_MODEL: '', ...settings},
    encoding: 'utf8', timeout: 5000,
  });
}
test('wake startup requires both explicit runtime and model, without default weights', () => {
  for (const settings of [{PIKOO_WAKE_PYTHON: '/optional/python'}, {PIKOO_WAKE_MODEL: '/private/model.tflite'}]) {
    const result = start(settings);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Local wake requires PIKOO_WAKE_PYTHON and PIKOO_WAKE_MODEL/);
    assert.doesNotMatch(result.stderr, /ENOENT/);
  }
});
test('unreadable wake weights fail with a safe actionable message', () => {
  const result = start({PIKOO_WAKE_PYTHON: '/optional/python', PIKOO_WAKE_MODEL: '/missing/private-model.tflite'});
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Local wake model is missing or unreadable/);
  assert.doesNotMatch(result.stderr, /\/missing\/private-model/);
});
