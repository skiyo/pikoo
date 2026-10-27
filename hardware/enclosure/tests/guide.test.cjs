const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = readFileSync(path.join(__dirname, '../guide.html'), 'utf8');
const dictionary = JSON.parse(html.match(/<script id="guide-translations" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const runtime = html.match(/<script id="guide-runtime">([\s\S]*?)<\/script>/)[1];
const ids = [...html.matchAll(/type="checkbox" data-id="([^"]+)"/g)].map(match => match[1]);
function fixture(options = {}) {
  const storage = new Map(Object.entries(options.storage || {}));
  const result = {storage, cookieWrites: [], download: null};
  const control = (attributes = {}) => ({
    attributes: {...attributes}, listeners: {}, value: '', checked: false, hidden: true,
    getAttribute(name) { return this.attributes[name] ?? null; },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    fire(name) { this.listeners[name]?.(); }
  });
  const inputs = ids.map(id => Object.assign(control(), {dataset: {id}}));
  const notes = control({placeholder: '记录耗材、App版本、设置、异常位置与照片说明'});
  const toggle = control();
  const status = control();
  const exportButton = control();
  const text = ['三个打印件，全机械固定', '厚锁座：保留', '横向插入'].map(nodeValue => ({nodeValue, parentElement: {tagName: 'SPAN'}}));
  // Script/style text must never become a translation binding.
  text.push({nodeValue: '三个打印件，全机械固定', parentElement: {tagName: 'SCRIPT'}});
  const root = {lang: 'zh-CN'};
  let cookie = options.cookie || '';
  const document = {
    documentElement: root,
    get cookie() { if (options.denyCookie) throw Error('Cookie denied'); return cookie; },
    set cookie(value) { if (options.denyCookie) throw Error('Cookie denied'); result.cookieWrites.push(value); cookie = value.split(';')[0]; },
    getElementById(id) { return {notes, status, export: exportButton, 'language-toggle': toggle, 'guide-translations': {textContent: JSON.stringify(dictionary)}}[id]; },
    querySelectorAll(selector) { return selector === '[data-id]' ? inputs : [notes]; },
    createTreeWalker() { let index = 0; return {nextNode: () => text[index++] || null}; },
    createElement() { return {click() { result.downloadName = this.download; }}; }
  };
  const localStorage = {
    getItem(key) { if (options.denyStorage) throw Error('Storage denied'); return storage.get(key) ?? null; },
    setItem(key, value) { if (options.denyStorage) throw Error('Storage denied'); storage.set(key, value); }
  };
  vm.runInNewContext(runtime, {
    document, localStorage, navigator: {languages: options.languages ?? ['en-US'], language: 'en-US'},
    location: {protocol: options.protocol || 'https:'}, NodeFilter: {SHOW_TEXT: 4}, Blob,
    URL: {createObjectURL(blob) { result.download = blob; return 'blob:test'; }, revokeObjectURL() {}},
    setTimeout(fn) { fn(); }
  });
  return Object.assign(result, {inputs, notes, toggle, status, exportButton, text, root});
}

test('first visit follows the first supported browser language, with Chinese fallback', () => {
  assert.equal(fixture().root.lang, 'en');
  assert.equal(fixture({languages: ['de-DE', 'zh-TW', 'en-US']}).root.lang, 'zh-CN');
  assert.equal(fixture({languages: ['fr-FR']}).root.lang, 'zh-CN');
  assert.equal(fixture().cookieWrites.length, 0, 'browser detection does not write a preference');
});
test('saved cookie then offline preference take priority over browser language', () => {
  assert.equal(fixture({cookie: 'pikoo_language=zh', storage: {'pikoo-guide-language': 'en'}}).root.lang, 'zh-CN');
  assert.equal(fixture({protocol: 'file:', storage: {'pikoo-guide-language': 'zh'}}).root.lang, 'zh-CN');
  assert.equal(fixture({cookie: 'pikoo_language=invalid', languages: ['en-GB']}).root.lang, 'en');
});
test('manual switching updates diagram labels, attributes and language without replacing controls', () => {
  const f = fixture(); const input = f.inputs[0]; const notes = f.notes;
  assert.equal(f.text[0].nodeValue, 'Three printed parts. Mechanical retention.');
  assert.equal(f.text[1].nodeValue, 'Keep the thick lock receiver');
  assert.equal(f.text[2].nodeValue, 'Insert horizontally');
  assert.equal(f.text[3].nodeValue, '三个打印件，全机械固定');
  assert.match(f.notes.getAttribute('placeholder'), /^Record material/);
  f.inputs[0].checked = true; f.notes.value = 'PLA / 设备记录';
  f.toggle.fire('click');
  assert.equal(f.root.lang, 'zh-CN');
  assert.equal(f.text[1].nodeValue, '厚锁座：保留');
  assert.equal(f.inputs[0], input); assert.equal(f.notes, notes);
  assert.equal(input.checked, true); assert.equal(notes.value, 'PLA / 设备记录');
  assert.equal(f.toggle.hidden, false);
  assert.match(f.status.textContent, /1 \/ 15/);
  assert.equal(f.storage.get('pikoo-guide-language'), 'zh');
  assert.match(f.cookieWrites[0], /Max-Age=31536000; Path=\/; SameSite=Lax; Secure$/);
});
test('offline and denied storage still allow a current-page language switch', () => {
  const f = fixture({denyCookie: true, denyStorage: true, protocol: 'file:'});
  f.toggle.fire('click'); assert.equal(f.root.lang, 'zh-CN');
  f.toggle.fire('click'); assert.equal(f.root.lang, 'en');
  const insecure = fixture({protocol: 'http:'}); insecure.toggle.fire('click');
  assert(!insecure.cookieWrites[0].includes('Secure'));
});
test('existing checklist IDs and notes survive language changes and reloads', () => {
  const record = JSON.stringify({checks: {key01: true, cover03: true}, notes: 'Keep these notes 原记录'});
  const f = fixture({storage: {'pikoo-enclosure-checks': record}});
  assert.equal(f.inputs.filter(input => input.checked).length, 2);
  f.toggle.fire('click'); f.toggle.fire('click');
  assert.equal(f.notes.value, 'Keep these notes 原记录');
  assert.equal(f.storage.get('pikoo-enclosure-checks'), record, 'a translation does not overwrite the acceptance record');
  f.inputs[1].checked = true; f.inputs[1].fire('change'); f.notes.fire('input');
  const reloaded = fixture({storage: Object.fromEntries(f.storage)});
  assert.equal(reloaded.inputs.filter(input => input.checked).length, 3);
  assert.equal(reloaded.notes.value, f.notes.value);
});
test('malformed or partial saved records do not break the guide', () => {
  assert.equal(fixture({storage: {'pikoo-enclosure-checks': '{bad'}}).root.lang, 'en');
  const partial = fixture({storage: {'pikoo-enclosure-checks': '{"notes":"partial"}'}});
  assert.equal(partial.notes.value, 'partial');
  assert.equal(partial.inputs.filter(input => input.checked).length, 0);
});
test('JSON export retains stable IDs, notes and acceptance scope in either language', async () => {
  const f = fixture(); f.inputs[0].checked = true; f.notes.value = 'My printer / 我的打印机';
  f.exportButton.fire('click');
  const exported = JSON.parse(await f.download.text());
  assert.equal(exported.language, 'en'); assert.equal(exported.checks.key01, true);
  assert.equal(exported.notes, f.notes.value); assert.equal(exported.digitalChecksAreNotPhysicalAcceptance, true);
  assert.equal(f.downloadName, 'pikoo-acceptance.json');
  f.toggle.fire('click'); f.exportButton.fire('click');
  assert.equal(JSON.parse(await f.download.text()).language, 'zh');
});
test('every Chinese text/attribute has a translation, including native diagram callouts', () => {
  const visible = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/g, '');
  for (const raw of visible.replace(/<[^>]*>/g, '\0').split('\0')) {
    const text = raw.trim();
    if (/[\u3400-\u9fff]/u.test(text)) assert(Object.hasOwn(dictionary, text), `Missing text: ${text}`);
  }
  for (const match of visible.matchAll(/(?:alt|placeholder|aria-label|title)="([^"]+)"/g)) {
    if (/[\u3400-\u9fff]/u.test(match[1])) assert(Object.hasOwn(dictionary, match[1]), `Missing attribute: ${match[1]}`);
  }
  assert.equal((html.match(/class="guide-diagram"/g) || []).length, 2);
  assert.equal((html.match(/data:image\/(?:png|jpeg|webp);base64,/g) || []).length, 10);
  assert.equal(ids.length, 15);
  assert(!/fetch\(|XMLHttpRequest|<script[^>]+src=|<link[^>]+rel="stylesheet"/.test(html));
  for (const name of ['01_main_body.stl', '02_rear_cover.stl', '03_rotary_lock.stl']) assert(html.includes(`href="stl/${name}"`));
});
