import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, nextTick, ref, watch } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import dayjs from 'dayjs';
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, SUPPORTED_LOCALES, i18n, initializeLocale, setLocale } from '../src/i18n/index.js';
import zh from '../src/i18n/zh-CN.js';
import en from '../src/i18n/en-US.js';
import ru from '../src/i18n/ru-RU.js';
import { formatTaskStatus, formatTaskStatusColor } from '../src/constants/taskStatus.js';
import { buildAssetFilterParams, formatAssetFilterOperator } from '../src/utils/assetFilters.js';

const require = createRequire(import.meta.url);
const t = (...args) => i18n.global.t(...args);
const descriptors = Object.fromEntries(['localStorage', 'document'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
const stops = [];
afterEach(() => {
  stops.splice(0).forEach(stop => stop());
  i18n.global.locale.value = DEFAULT_LOCALE;
  dayjs.locale('en');
  for (const [key, descriptor] of Object.entries(descriptors)) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
});

function preferences(values = {}) {
  const data = new Map(Object.entries(values));
  const store = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, String(value)) };
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: store });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { documentElement: { lang: '' } } });
  return { data, store };
}

function flatten(messages, prefix = '') {
  return Object.entries(messages).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === 'string' ? [[path, value]] : flatten(value, path);
  });
}

test('俄语覆盖全部中英文消息，具名参数一致且每条消息均可渲染', () => {
  const russian = Object.fromEntries(flatten(ru));
  for (const messages of [zh, en]) {
    const source = Object.fromEntries(flatten(messages));
    assert.deepEqual(Object.keys(russian).sort(), Object.keys(source).sort());
    for (const key of Object.keys(source)) {
      assert.deepEqual(russian[key].match(/\{\w+\}/g)?.sort(), source[key].match(/\{\w+\}/g)?.sort(), key);
    }
  }
  setLocale('ru-RU');
  for (const [key, message] of Object.entries(russian)) {
    assert.ok(message.trim(), key);
    assert.doesNotMatch(message, /\p{Script=Han}/u, key);
    const params = Object.fromEntries([...message.matchAll(/\{(\w+)\}/g)].map(([, name]) => [name, `fixture_${name}`]));
    const rendered = t(key, params);
    assert.notEqual(rendered, key, key);
    for (const value of Object.values(params)) assert.ok(rendered.includes(value), key);
  }
});

test('三种语言切换后可恢复偏好，保留登录资料、分页、菜单和原始资产数据', () => {
  const saved = { token: 'fixture-token', userInfo: '{"username":"fixture"}', global_pageSize: '20',
    arl_sidebar_menu_order_fixture: '["/policy","/dashboard"]', cachedAsset: '{"name":"用户资产","status":"running"}' };
  const { data } = preferences(saved);
  assert.deepEqual(SUPPORTED_LOCALES.map(option => option.value), ['zh-CN', 'en-US', 'ru-RU']);
  assert.equal(SUPPORTED_LOCALES.find(option => option.value === 'ru-RU').label, 'Русский');
  for (const [locale, signIn] of [['ru-RU', 'Войти'], ['en-US', 'Sign in'], ['zh-CN', '登录']]) {
    assert.equal(setLocale(locale), true);
    assert.equal(data.get(LOCALE_STORAGE_KEY), locale);
    assert.equal(document.documentElement.lang, locale);
    i18n.global.locale.value = 'fixture-invalid-locale';
    initializeLocale();
    assert.equal(t('login.signIn'), signIn);
    for (const [key, value] of Object.entries(saved)) assert.equal(data.get(key), value);
  }
  assert.equal(data.size, Object.keys(saved).length + 1);
});

test('俄语在浏览器禁用存储时仍可切换，后端原始错误不被翻译', () => {
  preferences();
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, get() { throw new Error('storage unavailable'); } });
  assert.doesNotThrow(() => setLocale('ru-RU'));
  assert.equal(document.documentElement.lang, 'ru-RU');
  assert.equal(t('login.failed', { reason: '服务原始提示 {value}' }), 'Ошибка входа: 服务原始提示 {value}');
});

test('App 为三种语言同步 Ant Design 和 Day.js，俄语月份与星期正确显示', async () => {
  const file = fs.readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(file);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'russian-app' });
  const context = vm.createContext({ computed, locale: i18n.global.locale, dayjs,
    watch: (...args) => { const stop = watch(...args); stops.push(stop); return stop; } });
  const names = ['localeOptions', 'activeLocale', 'componentLocale'];
  for (const node of scriptSetupAst) {
    if (node.type === 'ImportDeclaration') {
      if (node.source.value.startsWith('ant-design-vue/es/locale/')) {
        context[node.specifiers[0].local.name] = require(node.source.value.replace('/es/', '/lib/') + '.js').default;
      } else if (node.source.value.startsWith('dayjs/locale/')) require(node.source.value + '.js');
    }
    if (node.type === 'VariableDeclaration') {
      for (const declaration of node.declarations) {
        if (names.includes(declaration.id.name)) {
          vm.runInContext(`globalThis.${declaration.id.name} = (${descriptor.scriptSetup.content.slice(declaration.init.start, declaration.init.end)})`, context);
        }
      }
    }
    if (node.type === 'ExpressionStatement' && node.expression.callee?.name === 'watch' && node.expression.arguments[0]?.name === 'activeLocale') {
      vm.runInContext(descriptor.scriptSetup.content.slice(node.start, node.end), context);
    }
  }
  for (const [locale, component, date] of [['ru-RU', 'ru', 'ru'], ['en-US', 'en', 'en'], ['zh-CN', 'zh-cn', 'zh-cn']]) {
    setLocale(locale);
    await nextTick();
    assert.equal(context.componentLocale.value.locale, component);
    assert.equal(dayjs.locale(), date);
    if (locale === 'ru-RU') {
      assert.equal(dayjs('2026-10-21').format('MMMM dddd'), 'октябрь среда');
      assert.equal(context.componentLocale.value.Pagination.items_per_page, '/ стр.');
      assert.equal(context.componentLocale.value.DatePicker.lang.locale, 'ru_RU');
    }
  }
});

test('俄语状态和筛选标签只改变显示文案，请求字段和后端状态保持原值', () => {
  const form = { status: ['404', '200'], title: '用户原始标题' };
  const fields = [{ key: 'status', type: 'httpStatus' }, { key: 'title', hasOperatorSelect: true, operator: '精确匹配' }];
  const expected = { status__in: '200,404', title__eq: '用户原始标题' };
  const before = JSON.stringify({ form, fields });
  setLocale('ru-RU');
  assert.equal(formatTaskStatus('running'), 'Выполняется');
  assert.equal(formatTaskStatus('nuclei_scan'), 'Выполняется · Сканирование Nuclei');
  assert.equal(formatTaskStatusColor('running'), 'processing');
  assert.equal(formatAssetFilterOperator('精确匹配'), 'Точное совпадение');
  assert.deepEqual(buildAssetFilterParams(form, fields), expected);
  assert.equal(JSON.stringify({ form, fields }), before);
  setLocale('en-US');
  assert.equal(formatTaskStatus('running'), 'In progress');
  assert.deepEqual(buildAssetFilterParams(form, fields), expected);
});

test('俄语数量提示使用中性计数格式，单数和多种复数数量均保留', () => {
  setLocale('ru-RU');
  for (const count of [0, 1, 2, 5, 11, 21, 22, 25, 101]) {
    assert.equal(t('tasks.viewAllTotal', { count }), `Посмотреть всё (всего: ${count}) >>`);
    assert.equal(t('tasks.countSeconds', { count }), `${count} с`);
    assert.equal(t('tasks.paginationSummary', { pages: count, total: count + 1 }), `Страниц: ${count} / Записей: ${count + 1}`);
  }
});

test('登录校验失败后切换语言更新错误提示，未提交时不校验，也不发送登录请求', async () => {
  const file = fs.readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(file);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'russian-login' });
  const messages = [];
  const validationFailed = ref(false);
  const context = vm.createContext({ locale: i18n.global.locale, validationFailed,
    formRef: ref({ validateFields: async () => { messages.push(t('login.passwordRequired')); throw new Error('invalid form'); } }),
    request: { post() { assert.fail('语言切换不应发送登录请求'); } },
    watch: (...args) => { const stop = watch(...args); stops.push(stop); return stop; } });
  const listener = scriptSetupAst.find(node => node.type === 'ExpressionStatement' && node.expression.callee?.name === 'watch' && node.expression.arguments[0]?.name === 'locale');
  assert.ok(listener);
  vm.runInContext(descriptor.scriptSetup.content.slice(listener.start, listener.end), context);
  setLocale('ru-RU'); await nextTick();
  assert.deepEqual(messages, []);
  validationFailed.value = true;
  for (const locale of ['en-US', 'zh-CN', 'ru-RU']) {
    setLocale(locale); await nextTick();
  }
  assert.deepEqual(messages, ['Please enter your password.', '请输入密码!', 'Введите пароль.']);
});
