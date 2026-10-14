/**
 * 任务目标解析工具（与后端 app/helpers/task.py 的 target2list / get_ip_domain_list 保持一致）
 *
 * 后端下发规则：
 *   - 所有目标按「逗号或任意空白符」切分、去空、去重；
 *   - 同一批目标中，所有 IP / IP 掩码段会被合并为【1 个】任务；
 *   - 其余每个域名【各自建立 1 个独立任务】。
 * 因此「探测目标」文本框的输入行数与实际创建的任务数并非一一对应，
 * 本模块用于在提交前向用户如实预告将创建的任务数量与构成。
 */

// IPv4 及 CIDR 掩码段（与后端 is_vaild_ip_target 的判定范围对齐）
const IP_OR_CIDR_RE = /^(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?$/;

/**
 * 将原始目标字符串切分为去重后的目标列表。
 * @param {string} target 用户输入的原始目标
 * @returns {string[]} 清洗后的目标列表
 */
export function splitTargets(target) {
  if (!target || typeof target !== 'string') return [];
  const parts = target.trim().toLowerCase().split(/[,\s]+/).filter(Boolean);
  return Array.from(new Set(parts));
}

/**
 * 预估该目标串将创建的任务数量与构成，不发起任何请求。
 * @param {string} target 用户输入的原始目标
 * @returns {{ipCount: number, domainCount: number, taskCount: number, total: number}}
 *   ipCount: 归并进同一个任务的 IP / CIDR 目标数
 *   domainCount: 将各自建任务的域名数
 *   taskCount: 实际将创建的任务总数（IP 段非空时 +1）
 *   total: 去重后的目标总数
 */
export function estimateTaskFanout(target) {
  const targets = splitTargets(target);
  let ipCount = 0;
  let domainCount = 0;

  targets.forEach((item) => {
    // 对齐后端分流顺序：先判 IP / CIDR，其余归入域名筐
    if (IP_OR_CIDR_RE.test(item)) {
      ipCount += 1;
    } else {
      domainCount += 1;
    }
  });

  return {
    ipCount,
    domainCount,
    taskCount: (ipCount > 0 ? 1 : 0) + domainCount,
    total: targets.length
  };
}

/**
 * 生成面向用户的中文构成说明，用于提交前预告。
 * @param {string} target 用户输入的原始目标
 * @returns {{taskCount: number, total: number, text: string}} text 为可直接展示的说明文案
 */
export function describeTaskFanout(target) {
  const { ipCount, domainCount, taskCount, total } = estimateTaskFanout(target);
  if (total === 0) {
    return { taskCount: 0, total: 0, text: '' };
  }

  const segments = [];
  if (ipCount > 0) {
    segments.push(`${ipCount} 个 IP/CIDR 目标将合并为 1 个任务`);
  }
  if (domainCount > 0) {
    segments.push(`${domainCount} 个域名将各自创建一个任务`);
  }

  return {
    taskCount,
    total,
    text: `共识别 ${total} 个去重目标：${segments.join('；')}，合计创建 ${taskCount} 个任务。`
  };
}
