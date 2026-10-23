import { createI18n } from 'vue-i18n';
import zhCN from './zh-CN.js';

export const DEFAULT_LOCALE = 'zh-CN';
export const LOCALE_STORAGE_KEY = 'arl_locale';
export const SUPPORTED_LOCALES = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ru-RU', label: 'Русский' },
];

const LOCALE_LOADERS = {
  'en-US': () => import('./en-US.js'),
  'ru-RU': () => import('./ru-RU.js'),
};

const loadedLocales = new Set([DEFAULT_LOCALE]);
const pendingLoads = new Map();

export const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: { 'zh-CN': zhCN },
});

function applyLocaleState(locale) {
  i18n.global.locale.value = locale;
  if (typeof document !== 'undefined') document.documentElement.lang = locale;
  try {
    globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // 浏览器禁用存储时，当前页面仍可切换语言。
  }
}

export function loadLocaleMessages(locale) {
  if (loadedLocales.has(locale) || !LOCALE_LOADERS[locale]) {
    return Promise.resolve(true);
  }
  if (pendingLoads.has(locale)) {
    return pendingLoads.get(locale);
  }
  const loaderPromise = LOCALE_LOADERS[locale]()
    .then(mod => {
      const messages = mod?.default || mod;
      if (messages) {
        i18n.global.setLocaleMessage(locale, messages);
        loadedLocales.add(locale);
      }
      pendingLoads.delete(locale);
      return true;
    })
    .catch(() => {
      pendingLoads.delete(locale);
      return false;
    });
  pendingLoads.set(locale, loaderPromise);
  return loaderPromise;
}

export function setLocale(locale) {
  if (!SUPPORTED_LOCALES.some(option => option.value === locale)) return false;
  if (loadedLocales.has(locale)) {
    applyLocaleState(locale);
    return true;
  }
  try {
    globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // 忽略存储异常
  }
  loadLocaleMessages(locale).then(ok => {
    if (ok) {
      applyLocaleState(locale);
    }
  });
  return true;
}

export function initializeLocale() {
  let saved;
  try {
    saved = globalThis.localStorage?.getItem(LOCALE_STORAGE_KEY);
  } catch {
    // 无法读取偏好时使用默认中文。
  }
  const target = SUPPORTED_LOCALES.some(option => option.value === saved) ? saved : DEFAULT_LOCALE;
  setLocale(target);
}
