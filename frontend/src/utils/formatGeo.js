/**
 * 格式化三级 Geo 归属信息 (国家 / 省份 / 城市)
 * 1. 严格过滤 null, undefined, 'null', 'None', '0' 等无效占位符
 * 2. 智能去重：自动剔除相邻或跨级同名节点（如 Singapore / Singapore 或 Beijing / Beijing）
 * 3. 若无有效信息则安全保底返回 '-'
 *
 * @param {Object} geo - 后端返回的 geo_city 对象
 * @returns {string} 格式化后的地理位置字符串，如 "China / Jiangsu / Nanjing" 或 "-"
 */
export const formatGeo = (geo) => {
  if (!geo || typeof geo !== 'object') return '-';

  const rawParts = [geo.country_name, geo.region_name, geo.city];
  const cleanParts = [];

  const INVALID_PLACEHOLDERS = ['null', 'none', 'undefined', '-', '0'];

  for (const part of rawParts) {
    // 仅接受字符串；数值型占位（如 0）与 null 一律跳过
    if (typeof part !== 'string') continue;
    const trimmed = part.trim();
    if (!trimmed) continue;
    if (INVALID_PLACEHOLDERS.includes(trimmed.toLowerCase())) continue;
    // 仅剔除相邻层级的重复（如国家与城市同名），避免误删省份/城市等同名的不同层级
    if (cleanParts[cleanParts.length - 1] === trimmed) continue;
    cleanParts.push(trimmed);
  }

  return cleanParts.length > 0 ? cleanParts.join(' / ') : '-';
};
