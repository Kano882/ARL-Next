import { i18n } from '../i18n/index.js';

const taskText = (key, params) => i18n.global.t(key, params);

// 兼容历史单值、路由参数和缓存中的数组；保留无效值以便明确报错。
export function normalizeHttpStatuses(value) {
  if (value == null || value === '') return [];
  const values = Array.isArray(value) ? value : [value];
  return [...new Set(values.flatMap(item => String(item).split(','))
    .map(item => item.trim()))];
}

// 列表、导出和结果集共用参数转换，避免筛选条件不一致。
export function buildAssetFilterParams(form, searchFields = []) {
  const params = {};
  for (const field of searchFields) {
    const value = form[field.key];
    if (value == null || value === '') continue;
    if (field.type === 'httpStatus') {
      const codes = normalizeHttpStatuses(value);
      if (!codes.length) continue;
      if (codes.length > 500 || codes.some(code => !/^[1-5][0-9]{2}$/.test(code))) {
        throw new Error(taskText('tasks.invalidHttpStatus'));
      }
      params[`${field.key}__in`] = codes.sort().join(',');
    } else if (field.type === 'dateRange' && Array.isArray(value)) {
      if (value.length !== 2 || !value[0] || !value[1]) continue;
      params[`${field.key}__dgt`] = value[0].format('YYYY-MM-DD HH:mm:ss');
      params[`${field.key}__dlt`] = value[1].format('YYYY-MM-DD HH:mm:ss');
    } else {
      const suffix = field.hasOperatorSelect ? {
        '大于': '__gt', '小于': '__lt', '不等于': '__neq',
        '不包含': '__not', '精确匹配': '__eq'
      }[field.operator] || '' : '';
      params[field.key + suffix] = value;
    }
  }
  return params;
}

const OPERATOR_LABEL_KEYS = {
  等于: 'tasks.operatorEquals',
  大于: 'tasks.operatorGreaterThan',
  小于: 'tasks.operatorLessThan',
  不等于: 'tasks.operatorNotEqual',
  不包含: 'tasks.operatorNotContains',
  模糊匹配: 'tasks.operatorContains',
  精确匹配: 'tasks.operatorExactMatch',
};

// 运算符仍使用历史缓存和请求参数所需的原值，仅翻译展示名称。
export function formatAssetFilterOperator(operator) {
  return OPERATOR_LABEL_KEYS[operator] ? taskText(OPERATOR_LABEL_KEYS[operator]) : operator;
}
