import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {translate} from './i18n.mjs';
test('preview defaults to English and supports Chinese labels and live counters',()=>{
 assert.equal(translate('聆听'),'Listening');
 assert.equal(translate('Listening','zh-CN'),'聆听');
 assert.equal(translate('本机 C++ 画面正常 · 12 帧 · RGB565 · 20fps 目标'),'Local C++ renderer · 12 frames · RGB565 · 20 fps target');
 assert.equal(translate('Local C++ renderer · 12 frames · RGB565 · 20 fps target','zh-CN'),'本机 C++ 画面正常 · 12 帧 · RGB565 · 20fps 目标');
 const html=readFileSync(new URL('./dualeye.html',import.meta.url),'utf8');
 assert.match(html,/<html lang="en">/);assert.match(html,/src="\/i18n.mjs"/);
});
