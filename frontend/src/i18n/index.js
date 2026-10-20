import { createI18n } from 'vue-i18n';
import zhCN from './zh-CN.js';
import enUS from './en-US.js';

export const DEFAULT_LOCALE = 'zh-CN';
export const LOCALE_STORAGE_KEY = 'arl_locale';
export const SUPPORTED_LOCALES = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
];

export const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: { 'zh-CN': zhCN, 'en-US': enUS },
});

export function setLocale(locale) {
  if (!SUPPORTED_LOCALES.some(option => option.value === locale)) return false;
  i18n.global.locale.value = locale;
  if (typeof document !== 'undefined') document.documentElement.lang = locale;
  try {
    globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // 浏览器禁用存储时，当前页面仍可切换语言。
  }
  return true;
}

export function initializeLocale() {
  let saved;
  try {
    saved = globalThis.localStorage?.getItem(LOCALE_STORAGE_KEY);
  } catch {
    // 无法读取偏好时使用默认中文。
  }
  setLocale(SUPPORTED_LOCALES.some(option => option.value === saved) ? saved : DEFAULT_LOCALE);
}
