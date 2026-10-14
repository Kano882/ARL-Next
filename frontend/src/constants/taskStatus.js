/**
 * 任务状态术语唯一事实源（全项目唯一口径）
 *
 * 基准词表（新增状态须先在此登记再使用）：
 *   running 进行中 / waiting 排队中 / done 已完成 / stop 已停止 / error 异常失败
 *
 * 注意：
 *   - 状态文案字典（TASK_STATUS_LABEL）与插件名/阶段字典（PLUGIN_NAME_MAP）必须分表维护；
 *   - 后端插件名/阶段标识严禁直接当作任务状态展示，须经 formatTaskStatus 标注为「进行中 · <阶段名>」。
 */

/** 任务状态 → 唯一中文文案 */
export const TASK_STATUS_LABEL = {
  running: '进行中',
  waiting: '排队中',
  done: '已完成',
  stop: '已停止',
  error: '异常失败'
};

/** 任务状态 → Ant Design Tag 配色 */
export const TASK_STATUS_COLOR = {
  running: 'processing',
  waiting: 'warning',
  done: 'success',
  stop: 'default',
  error: 'error'
};

/** 插件名/阶段标识 → 中文名（与状态字典分表，严禁混用） */
export const PLUGIN_NAME_MAP = {
  domain_brute: '域名爆破',
  dns_query_plugin: '域名查询',
  arl_search: '历史查询',
  alt_dns: 'DNS智能生成',
  recursive_domain_brute: '递归爆破',
  port_scan: '端口扫描',
  ssl_cert: 'SSL证书获取',
  service_detection: '服务识别',
  os_detection: '系统识别',
  find_site: '站点发现',
  site_identify: '指纹识别',
  search_engines: '搜索引擎',
  site_spider: '站点爬虫',
  file_leak: '文件泄露',
  find_vhost: 'Host碰撞',
  findvhost: 'Host碰撞',
  npoc_service_detection: 'Python服务识别',
  poc_run: 'PoC验证',
  nuclei_scan: 'Nuclei扫描',
  weak_brute: '弱口令爆破',
  wih_domain_update: 'WIH更新',
  web_info_hunter: 'WIH探测'
};

/**
 * 是否为已知的任务状态值。
 * @param {string} status 后端返回的状态值
 * @returns {boolean}
 */
export const isKnownTaskStatus = (status) => !!status && status in TASK_STATUS_LABEL;

/**
 * 是否为阶段状态（后端返回插件/阶段标识，表示任务正在该阶段执行）。
 * @param {string} status 后端返回的状态值
 * @returns {boolean}
 */
export const isStageStatus = (status) => !!status && !isKnownTaskStatus(status);

/**
 * 状态值 → 展示文案。阶段状态显式标注为「进行中 · <阶段名>」，
 * 避免用户把插件名误读为任务状态。
 * @param {string} status 后端返回的状态值
 * @returns {string} 展示文案
 */
export const formatTaskStatus = (status) => {
  if (TASK_STATUS_LABEL[status]) return TASK_STATUS_LABEL[status];
  const stageName = PLUGIN_NAME_MAP[status] || status;
  return stageName ? `进行中 · ${stageName}` : '进行中';
};

/**
 * 状态值 → Tag 配色，未知状态回落 default。
 * @param {string} status 后端返回的状态值
 * @returns {string}
 */
export const formatTaskStatusColor = (status) => TASK_STATUS_COLOR[status] || 'default';
