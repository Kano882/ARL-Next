<template>
  <div class="policy-detail-container">
    <div class="policy-detail-header">
      <a-button type="link" @click="goBack" class="back-link-btn">&lt; 返回列表</a-button>
      <h2 class="page-title">{{ isEdit ? '编辑策略配置' : '新建扫描策略' }}</h2>
    </div>

    <a-form :model="policyForm" layout="vertical" class="policy-form-layout">
      <!-- 基础信息卡片 -->
      <a-card :bordered="false" class="policy-section-card basic-info-card">
        <div class="section-card-title">
          <span class="indicator-bar"></span>基础信息
        </div>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="策略名称" required>
              <a-input v-model:value="policyForm.name" placeholder="请输入策略名称，如：全面综合侦查策略" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="策略描述">
              <a-input v-model:value="policyForm.desc" placeholder="请输入策略的适用场景与描述" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <!-- 四维功能折叠配置面板 -->
      <a-collapse v-model:activeKey="activePanels" :bordered="false" class="policy-collapse-box">
        
        <!-- 1. 域名与资产发现 -->
        <a-collapse-panel key="1" header="🌐 域名与资产发现">
          <div class="panel-action-bar">
            <a-checkbox :checked="isAllDomainSelected" @change="toggleAllDomain">全选本组</a-checkbox>
            <a-input v-model:value="domainSearch" placeholder="搜索域名探测项" class="search-input" allowClear>
              <template #suffix><search-outlined class="search-icon" /></template>
            </a-input>
          </div>

          <div class="feature-item-list">
            <!-- 域名查询插件 -->
            <div v-show="matchSearch('域名查询插件', domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.dns_query_plugin">域名查询插件</a-checkbox>
                <span class="feature-hint">调用 crt.sh、AlienVault、VirusTotal 等外部公开被动 DNS 平台提取子域名</span>
              </div>
            </div>

            <!-- 域名爆破 + 内联字典 -->
            <div v-show="matchSearch('域名爆破', domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.domain_brute">域名爆破</a-checkbox>
                <span class="feature-hint">基于字典进行 DNS 高速子域名暴力解析探测</span>
              </div>
              <div v-if="policyForm.domain_config.domain_brute" class="sub-config-box">
                <a-form-item label="爆破字典" required class="inline-form-item">
                  <a-select v-model:value="policyForm.domain_config.domain_brute_type" placeholder="请选择爆破字典" style="width: 280px;">
                    <a-select-option v-for="item in domainDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
            </div>

            <!-- DNS字典智能生成 + 内联字典 -->
            <div v-show="matchSearch('DNS字典智能生成', domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.alt_dns">DNS字典智能生成 (AltDNS)</a-checkbox>
                <span class="feature-hint">依据已发现子域名自动置换前缀/数字后缀并排列变异词进行二次探测</span>
              </div>
              <div v-if="policyForm.domain_config.alt_dns" class="sub-config-box">
                <a-form-item label="智能子域爆破字典" required class="inline-form-item">
                  <a-select v-model:value="policyForm.domain_config.alt_dns_dict" placeholder="请选择智能变异字典" style="width: 280px;">
                    <a-select-option v-for="item in altDnsDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
            </div>

            <!-- ARL 历史查询 -->
            <div v-show="matchSearch('ARL 历史查询', domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.arl_search">ARL 历史资产查询</a-checkbox>
                <span class="feature-hint">自动从本系统历史资产数据库中关联提取目标子域记录</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>

        <!-- 2. 端口与服务发现 -->
        <a-collapse-panel key="2" header="⚡️ 端口与服务发现">
          <div class="panel-action-bar">
            <a-checkbox :checked="isAllIpSelected" @change="toggleAllIp">全选本组</a-checkbox>
            <a-input v-model:value="ipSearch" placeholder="搜索端口与服务探测项" class="search-input" allowClear>
              <template #suffix><search-outlined class="search-icon" /></template>
            </a-input>
          </div>

          <div class="feature-item-list">
            <!-- 跳过 CDN -->
            <div v-show="matchSearch('跳过CDN', ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.skip_scan_cdn_ip">跳过 CDN IP 扫描</a-checkbox>
                <span class="feature-hint">识别到 CDN 节点 IP 时自动略过全端口探测，避免无效开销</span>
              </div>
            </div>

            <!-- 端口扫描 + 策略/自定义/高级配置内联 -->
            <div v-show="matchSearch('端口扫描', ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.port_scan">端口扫描</a-checkbox>
                <span class="feature-hint">对目标 IP 资产执行 TCP 端口存活状态探测</span>
              </div>
              <div v-if="policyForm.ip_config.port_scan" class="sub-config-box">
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item label="端口扫描策略" required class="inline-form-item">
                      <a-select v-model:value="policyForm.ip_config.port_scan_type" placeholder="请选择端口策略">
                        <a-select-option value="custom">自定义端口</a-select-option>
                        <a-select-option v-for="item in portDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="12" v-if="policyForm.ip_config.port_scan_type === 'custom'">
                    <a-form-item label="自定义端口范围" required class="inline-form-item">
                      <a-input v-model:value="policyForm.ip_config.port_custom" placeholder="例如: 80,443,8000-8080" />
                    </a-form-item>
                  </a-col>
                </a-row>

                <!-- 高级发包配置收展 -->
                <div class="advanced-toggle-row">
                  <a-button type="link" size="small" @click="showAdvancedPortConfig = !showAdvancedPortConfig" style="padding: 0;">
                    {{ showAdvancedPortConfig ? '收起高级发包参数 ▲' : '展开高级发包参数 (速率/并发/排除端口) ▼' }}
                  </a-button>
                </div>

                <div v-if="showAdvancedPortConfig" class="advanced-params-grid">
                  <a-row :gutter="16">
                    <a-col :span="8">
                      <a-form-item label="主机超时时间" class="inline-form-item">
                        <a-select v-model:value="policyForm.ip_config.host_timeout_type">
                          <a-select-option value="default">默认 (900s)</a-select-option>
                          <a-select-option value="custom">自定义超时</a-select-option>
                        </a-select>
                      </a-form-item>
                    </a-col>
                    <a-col :span="8" v-if="policyForm.ip_config.host_timeout_type === 'custom'">
                      <a-form-item label="超时秒数" required class="inline-form-item">
                        <a-input-number v-model:value="policyForm.ip_config.host_timeout" :min="1" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item label="探测并行度" class="inline-form-item">
                        <a-input-number v-model:value="policyForm.ip_config.port_parallelism" :min="1" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item label="最少发包速率" class="inline-form-item">
                        <a-input-number v-model:value="policyForm.ip_config.port_min_rate" :min="1" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="16">
                      <a-form-item label="排除扫描端口" class="inline-form-item">
                        <a-input v-model:value="policyForm.ip_config.exclude_ports" placeholder="排除指定端口，如：9100,9102,1-100" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </div>
              </div>
            </div>

            <!-- 服务识别 (双轨合并为单一选项) -->
            <div v-show="matchSearch('服务识别', ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.service_detection">
                  <span style="font-weight: 500;">服务识别</span>
                  <a-tag color="blue" style="margin-left: 8px;">双轨协同</a-tag>
                </a-checkbox>
                <span class="feature-hint">系统自动并行协同执行精准指纹分析与高危端口纯协议探测，无需手动区分底层引擎</span>
              </div>
            </div>

            <!-- 操作系统识别 -->
            <div v-show="matchSearch('操作系统识别', ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.os_detection">操作系统识别</a-checkbox>
                <span class="feature-hint">基于 TCP/IP 协议栈指纹探针智能推断目标主机操作系统类型</span>
              </div>
            </div>

            <!-- SSL 证书获取 -->
            <div v-show="matchSearch('SSL 证书获取', ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.ssl_cert">SSL 证书获取</a-checkbox>
                <span class="feature-hint">拉取 HTTPS 与 TLS 端口证书信息，解析域名主体与颁发机构</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>

        <!-- 3. Web 深度探测 -->
        <a-collapse-panel key="3" header="🕷️ Web 深度探测">
          <div class="panel-action-bar">
            <a-checkbox :checked="isAllSiteSelected" @change="toggleAllSite">全选本组</a-checkbox>
            <a-input v-model:value="siteSearch" placeholder="搜索 Web 探测项" class="search-input" allowClear>
              <template #suffix><search-outlined class="search-icon" /></template>
            </a-input>
          </div>

          <div class="feature-item-list">
            <!-- 站点与指纹识别 -->
            <div v-show="matchSearch('站点与指纹识别', siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.site_identify">站点与指纹识别</a-checkbox>
                <span class="feature-hint">提取 HTTP 响应头、网页标题、Server Banner 及开源 CMS/组件框架指纹</span>
              </div>
            </div>

            <!-- 文件泄露 + 内联字典 -->
            <div v-show="matchSearch('文件泄露', siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.file_leak">目录文件泄露检测</a-checkbox>
                <span class="feature-hint">探测目标 Web 站点的备份文件、源码泄露、敏感配置及未授权后台路径</span>
              </div>
              <div v-if="policyForm.file_leak" class="sub-config-box">
                <a-form-item label="目录文件泄露字典" required class="inline-form-item">
                  <a-select v-model:value="policyForm.file_leak_dict" placeholder="请选择泄露字典" style="width: 280px;">
                    <a-select-option v-for="item in fileLeakDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
            </div>

            <!-- 搜索引擎调用 -->
            <div v-show="matchSearch('搜索引擎调用', siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.search_engines">搜索引擎调用 (360 / Bing)</a-checkbox>
                <span class="feature-hint">调用公共搜索引擎检索目标域名的收录页面与入口 URL</span>
              </div>
            </div>

            <!-- 站点静态爬虫 -->
            <div v-show="matchSearch('站点爬虫', siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.site_spider">站点静态爬虫</a-checkbox>
                <span class="feature-hint">深入爬取页面 a/form/src 等超链接标签，拓扑收敛全站资产</span>
              </div>
            </div>

            <!-- WIH 调用 -->
            <div v-show="matchSearch('WIH 调用', siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.web_info_hunter">WIH 前端 JS 深度提取</a-checkbox>
                <span class="feature-hint">深度静态解析前端 JavaScript 脚本，提取 API 路由、隐藏子域与敏感凭据</span>
              </div>
            </div>

            <!-- Host 碰撞 -->
            <div v-show="matchSearch('Host 碰撞', siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.findvhost">Host 碰撞检测</a-checkbox>
                <span class="feature-hint">遍历内网域名与外网 IP 组合，探测未做访问隔离的虚拟主机 Host 漏洞</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>

        <!-- 4. 漏洞与风险巡航 -->
        <a-collapse-panel key="4" header="🛡️ 漏洞与风险巡航">
          <!-- Nuclei 独立开关与细粒度策略配置 -->
          <div class="feature-item-block" style="padding-bottom: 16px; border-bottom: 1px solid var(--arl-border-color); margin-bottom: 16px;">
            <div class="feature-switch-row">
              <a-checkbox v-model:checked="policyForm.site_config.nuclei_scan">
                <span style="font-weight: 500;">Nuclei 自动化扫描</span>
                <a-tag color="purple" style="margin-left: 8px;">社区模板 + 自建模板</a-tag>
              </a-checkbox>
              <span class="feature-hint">调用 Nuclei 引擎针对已发现 Web 站点执行模板化漏洞探测</span>
            </div>

            <!-- Nuclei 细粒度过滤与自建模板配置 (纯开关矩阵，极简交互) -->
            <div v-if="policyForm.site_config.nuclei_scan" class="sub-config-box" style="margin-top: 12px;">
              <a-row :gutter="16">
                <a-col :span="13">
                  <a-form-item label="探测危害级别 (Severity)" class="inline-form-item">
                    <a-checkbox-group v-model:value="policyForm.site_config.nuclei_config.severity" :options="nucleiSeverityOptions" />
                  </a-form-item>
                </a-col>
                <a-col :span="11">
                  <a-form-item label="防御与自建模板联动" class="inline-form-item">
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                      <a-checkbox v-model:checked="policyForm.site_config.nuclei_config.exclude_blacklist">
                        自动排除全局误报黑名单 (推荐)
                      </a-checkbox>
                      <a-checkbox
                        :checked="policyForm.site_config.nuclei_config.custom_template_mode === 'all_enabled'"
                        @change="(e) => policyForm.site_config.nuclei_config.custom_template_mode = e.target.checked ? 'all_enabled' : 'none'"
                      >
                        自动加载所有已启用的自建模板 (推荐)
                      </a-checkbox>
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>
            </div>
          </div>

          <!-- PoC 插件配置子区域 -->
          <div class="plugin-sub-section">
            <div class="sub-section-header">
              <div class="sub-section-title">
                <span>PoC 漏洞验证插件</span>
                <span class="count-tag">已选 {{ selectedPocCount }} / {{ pocList.length }}</span>
              </div>
              <div class="sub-section-actions">
                <a-checkbox :checked="isAllPocSelected" @change="toggleAllPoc">全选 PoC</a-checkbox>
                <a-input v-model:value="pocSearch" placeholder="搜索 PoC 插件名称" class="search-input" allowClear>
                  <template #suffix><search-outlined class="search-icon" /></template>
                </a-input>
              </div>
            </div>
            <a-row :gutter="[12, 12]" class="plugin-checkbox-grid">
              <a-col :span="12" v-for="(item, index) in filteredPocList" :key="item.plugin_name">
                <div class="plugin-item-checkbox" :class="{ 'is-checked': item.enable }">
                  <a-checkbox v-model:checked="item.enable">
                    <span class="index-num">{{ index + 1 }}.</span>
                    <span class="plugin-name-text">{{ item.vul_name || item.plugin_name }}</span>
                  </a-checkbox>
                </div>
              </a-col>
            </a-row>
          </div>

          <a-divider style="margin: 20px 0;" />

          <!-- 弱口令爆破子区域 -->
          <div class="plugin-sub-section">
            <div class="sub-section-header">
              <div class="sub-section-title">
                <span>弱口令爆破插件</span>
                <span class="count-tag">已选 {{ selectedBruteCount }} / {{ bruteList.length }}</span>
              </div>
              <div class="sub-section-actions">
                <a-checkbox :checked="isAllBruteSelected" @change="toggleAllBrute">全选爆破</a-checkbox>
                <a-input v-model:value="bruteSearch" placeholder="搜索弱口令插件" class="search-input" allowClear>
                  <template #suffix><search-outlined class="search-icon" /></template>
                </a-input>
              </div>
            </div>
            <a-row :gutter="[12, 12]" class="plugin-checkbox-grid">
              <a-col :span="12" v-for="(item, index) in filteredBruteList" :key="item.plugin_name">
                <div class="plugin-item-checkbox" :class="{ 'is-checked': item.enable }">
                  <a-checkbox v-model:checked="item.enable">
                    <span class="index-num">{{ index + 1 }}.</span>
                    <span class="plugin-name-text">{{ item.vul_name || item.plugin_name }}</span>
                  </a-checkbox>
                </div>
              </a-col>
            </a-row>
          </div>
        </a-collapse-panel>

      </a-collapse>

      <!-- 底部保存/取消操作条 -->
      <div class="policy-footer-actions">
        <a-button type="primary" size="large" class="submit-btn" @click="submitPolicy" :loading="submitLoading">保 存 策 略</a-button>
        <a-button size="large" class="cancel-btn" @click="goBack">取 消</a-button>
      </div>
    </a-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined } from '@ant-design/icons-vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();
const policyId = route.query._id;
const isEdit = !!policyId;

const goBack = () => router.push('/policy');

// 默认展开所有核心探测面板
const activePanels = ref(['1', '2', '3', '4']);
const submitLoading = ref(false);
const showAdvancedPortConfig = ref(false);

const initPolicyForm = () => ({
  name: '',
  desc: '',
  domain_config: {
    domain_brute: false,
    alt_dns: false,
    arl_search: false,
    dns_query_plugin: false,
    domain_brute_type: undefined,
    alt_dns_dict: undefined
  },
  ip_config: {
    port_scan: false,
    service_detection: false,
    os_detection: false,
    ssl_cert: false,
    skip_scan_cdn_ip: false,
    port_scan_type: undefined,
    port_custom: '',
    host_timeout_type: 'default',
    host_timeout: 900,
    port_parallelism: 32,
    port_min_rate: 60,
    exclude_ports: ''
  },
  site_config: {
    site_identify: false,
    search_engines: false,
    site_spider: false,
    findvhost: false,
    nuclei_scan: false,
    nuclei_config: {
      severity: ['critical', 'high', 'medium', 'low'],
      custom_template_mode: 'all_enabled',
      exclude_blacklist: true
    },
    web_info_hunter: false
  },
  file_leak: false,
  file_leak_dict: undefined
});

const nucleiSeverityOptions = [
  { label: '严重 (Critical)', value: 'critical' },
  { label: '高危 (High)', value: 'high' },
  { label: '中危 (Medium)', value: 'medium' },
  { label: '低危 (Low)', value: 'low' },
  { label: '信息 (Info)', value: 'info' }
];

const policyForm = reactive(initPolicyForm());

const pocList = ref([]);
const bruteList = ref([]);
const domainDicts = ref([]);
const altDnsDicts = ref([]);
const fileLeakDicts = ref([]);
const portDicts = ref([]);
const hasPocLoaded = ref(false);

const domainSearch = ref('');
const ipSearch = ref('');
const siteSearch = ref('');
const pocSearch = ref('');
const bruteSearch = ref('');

const matchSearch = (text, keyword) => {
  if (!keyword) return true;
  return text.toLowerCase().includes(keyword.toLowerCase().trim());
};

const normalizeDomainDict = (val) => {
  if (!val) return val;
  const map = {
    'big': 'domain_2w.txt',
    'test': 'domain_top300.txt',
    'domain_2w': 'domain_2w.txt',
    'domain_top300': 'domain_top300.txt'
  };
  return map[val] || val;
};

const normalizePortDict = (val) => {
  if (!val) return val;
  const map = {
    'top100': 'port_top100.txt',
    'top1000': 'port_top1000.txt',
    'bughunter': 'port_bughunter.txt',
    'port_top100': 'port_top100.txt',
    'port_top1000': 'port_top1000.txt',
    'port_bughunter': 'port_bughunter.txt'
  };
  return map[val] || val;
};

// ================= 面板 1：域名探测全选联动 =================
const isAllDomainSelected = computed(() => {
  const dc = policyForm.domain_config;
  return dc.domain_brute && dc.alt_dns && dc.arl_search && dc.dns_query_plugin;
});
const toggleAllDomain = (e) => {
  const val = e.target.checked;
  const dc = policyForm.domain_config;
  dc.domain_brute = dc.alt_dns = dc.arl_search = dc.dns_query_plugin = val;
};

// ================= 面板 2：端口与服务全选联动 =================
const isAllIpSelected = computed(() => {
  const ic = policyForm.ip_config;
  return ic.port_scan && ic.service_detection && ic.os_detection && ic.ssl_cert && ic.skip_scan_cdn_ip;
});
const toggleAllIp = (e) => {
  const val = e.target.checked;
  const ic = policyForm.ip_config;
  ic.port_scan = ic.service_detection = ic.os_detection = ic.ssl_cert = ic.skip_scan_cdn_ip = val;
};

// ================= 面板 3：Web 探测全选联动 =================
const isAllSiteSelected = computed(() => {
  const sc = policyForm.site_config;
  return sc.site_identify && sc.search_engines && sc.site_spider &&
      sc.findvhost && sc.web_info_hunter && policyForm.file_leak;
});
const toggleAllSite = (e) => {
  const val = e.target.checked;
  const sc = policyForm.site_config;
  sc.site_identify = sc.search_engines = sc.site_spider = sc.findvhost = sc.web_info_hunter = val;
  policyForm.file_leak = val;
};

// ================= 面板 4：漏洞插件过滤与全选联动 =================
const filteredPocList = computed(() => {
  const kw = (pocSearch.value || '').toLowerCase().trim();
  if (!kw) return pocList.value;
  return pocList.value.filter(p =>
      (p.vul_name && p.vul_name.toLowerCase().includes(kw)) ||
      (p.plugin_name && p.plugin_name.toLowerCase().includes(kw))
  );
});

const filteredBruteList = computed(() => {
  const kw = (bruteSearch.value || '').toLowerCase().trim();
  if (!kw) return bruteList.value;
  return bruteList.value.filter(p =>
      (p.vul_name && p.vul_name.toLowerCase().includes(kw)) ||
      (p.plugin_name && p.plugin_name.toLowerCase().includes(kw))
  );
});

const selectedPocCount = computed(() => pocList.value.filter(p => p.enable).length);
const selectedBruteCount = computed(() => bruteList.value.filter(p => p.enable).length);

const isAllPocSelected = computed(() => filteredPocList.value.length > 0 && filteredPocList.value.every(p => p.enable));
const isAllBruteSelected = computed(() => filteredBruteList.value.length > 0 && filteredBruteList.value.every(p => p.enable));

const toggleAllPoc = (e) => {
  const checked = e.target.checked;
  filteredPocList.value.forEach(p => p.enable = checked);
};
const toggleAllBrute = (e) => {
  const checked = e.target.checked;
  filteredBruteList.value.forEach(p => p.enable = checked);
};

// ================= 生命周期：数据加载与编辑回填 =================
onMounted(async () => {
  try {
    const [pocRes, bruteRes, dictRes] = await Promise.all([
      request.get('/poc/', { params: { plugin_type: 'poc', size: 10000 } }),
      request.get('/poc/', { params: { plugin_type: 'brute', size: 10000 } }),
      request.get('/dictionary/list')
    ]);

    if (dictRes.code === 200 && dictRes.data) {
      domainDicts.value = dictRes.data.filter(item => item.category && item.category.includes('子域名爆破') && !item.category.includes('智能'));
      altDnsDicts.value = dictRes.data.filter(item => item.category && item.category.includes('智能子域爆破'));
      fileLeakDicts.value = dictRes.data.filter(item => item.category && (item.category.includes('目录文件泄露') || item.category.includes('目录与文件泄露')));
      portDicts.value = dictRes.data.filter(item => item.category && item.category.includes('端口扫描策略') && item.name !== 'port_custom.txt');

      if (!isEdit) {
        if (domainDicts.value.length > 0) policyForm.domain_config.domain_brute_type = domainDicts.value[0].name;
        if (altDnsDicts.value.length > 0) policyForm.domain_config.alt_dns_dict = altDnsDicts.value[0].name;
        if (fileLeakDicts.value.length > 0) policyForm.file_leak_dict = fileLeakDicts.value[0].name;
        if (portDicts.value.length > 0) policyForm.ip_config.port_scan_type = portDicts.value[0].name;
      }
    }

    if (pocRes.code === 200) {
      const uniquePoc = new Map();
      (pocRes.items || []).forEach(p => {
        if (!uniquePoc.has(p.plugin_name)) uniquePoc.set(p.plugin_name, { ...p, enable: false });
      });
      pocList.value = Array.from(uniquePoc.values());
    }

    if (bruteRes.code === 200) {
      const uniqueBrute = new Map();
      (bruteRes.items || []).forEach(p => {
        if (!uniqueBrute.has(p.plugin_name)) uniqueBrute.set(p.plugin_name, { ...p, enable: false });
      });
      bruteList.value = Array.from(uniqueBrute.values());
    }

    if (pocRes.code === 200 && bruteRes.code === 200) {
      hasPocLoaded.value = true;
    }

    // 编辑模式回填
    if (isEdit) {
      const detailRes = await request.get('/policy/', { params: { _id: policyId } });
      if (detailRes.code === 200 && detailRes.items && detailRes.items.length > 0) {
        const data = detailRes.items[0];

        policyForm.name = data.name || '';
        policyForm.desc = data.desc || '';
        Object.assign(policyForm.domain_config, data.policy?.domain_config || {});
        Object.assign(policyForm.ip_config, data.policy?.ip_config || {});
        Object.assign(policyForm.site_config, data.policy?.site_config || {});
        if (!policyForm.site_config.nuclei_config) {
          policyForm.site_config.nuclei_config = {
            severity: ['critical', 'high', 'medium', 'low'],
            custom_template_mode: 'all_enabled',
            exclude_blacklist: true
          };
        } else {
          if (policyForm.site_config.nuclei_config.exclude_blacklist === undefined) {
            policyForm.site_config.nuclei_config.exclude_blacklist = true;
          }
          if (!policyForm.site_config.nuclei_config.custom_template_mode) {
            policyForm.site_config.nuclei_config.custom_template_mode = 'all_enabled';
          }
        }

        // 字典历史别名归一化回填
        if (policyForm.domain_config.domain_brute_type) {
          policyForm.domain_config.domain_brute_type = normalizeDomainDict(policyForm.domain_config.domain_brute_type);
        }
        if (policyForm.ip_config.port_scan_type) {
          policyForm.ip_config.port_scan_type = normalizePortDict(policyForm.ip_config.port_scan_type);
        }

        // 统一双轨服务识别回填：若历史开启了 npoc_service_detection 或 service_detection，均视为开启
        const isSvcDetect = !!(data.policy?.ip_config?.service_detection || data.policy?.npoc_service_detection);
        policyForm.ip_config.service_detection = isSvcDetect;

        // 文件泄露回填
        policyForm.file_leak = !!(data.policy?.file_leak || data.policy?.site_config?.file_leak);
        if (data.policy?.file_leak_dict || data.policy?.site_config?.file_leak_dict) {
          policyForm.file_leak_dict = data.policy.file_leak_dict || data.policy.site_config?.file_leak_dict;
        }

        // 若配置了自定义高级发包参数，自动展开高级参数面板
        if (policyForm.ip_config.host_timeout_type === 'custom' || policyForm.ip_config.exclude_ports) {
          showAdvancedPortConfig.value = true;
        }

        // PoC 插件勾选回填
        const pocMap = {};
        data.policy?.poc_config?.forEach(p => pocMap[p.plugin_name] = p.enable);
        pocList.value.forEach(p => { if (pocMap[p.plugin_name] !== undefined) p.enable = pocMap[p.plugin_name]; });

        // 弱口令插件勾选回填
        const bruteMap = {};
        data.policy?.brute_config?.forEach(p => bruteMap[p.plugin_name] = p.enable);
        bruteList.value.forEach(p => { if (bruteMap[p.plugin_name] !== undefined) p.enable = bruteMap[p.plugin_name]; });
      } else {
        message.error('未找到对应策略或该策略已被删除');
        router.push('/policy');
        return;
      }
    }
  } catch (e) {
    message.error('加载策略数据失败');
  }
});

// ================= 提交表单 =================
const submitPolicy = async () => {
  if (isEdit && !hasPocLoaded.value) {
    return message.error('插件数据尚未加载完毕，禁止保存！');
  }
  if (!policyForm.name?.trim()) return message.warning('策略名称不能为空！');

  // 条件校验：仅在勾选对应功能时，校验字典必选项
  if (policyForm.domain_config.domain_brute && !policyForm.domain_config.domain_brute_type) {
    return message.warning('开启域名爆破后，必须选择爆破字典！');
  }
  if (policyForm.domain_config.alt_dns && !policyForm.domain_config.alt_dns_dict) {
    return message.warning('开启智能子域爆破后，必须选择智能字典！');
  }
  if (policyForm.ip_config.port_scan) {
    if (!policyForm.ip_config.port_scan_type) {
      return message.warning('开启端口扫描后，必须选择扫描策略！');
    }
    if (policyForm.ip_config.port_scan_type === 'custom' && !policyForm.ip_config.port_custom?.trim()) {
      return message.warning('自定义端口策略下，必须输入自定义端口范围！');
    }
    if (policyForm.ip_config.host_timeout_type === 'custom') {
      if (!policyForm.ip_config.host_timeout || policyForm.ip_config.host_timeout < 1) {
        return message.warning('自定义主机超时时间必须大于等于 1 秒！');
      }
    }
  }
  if (policyForm.file_leak && !policyForm.file_leak_dict) {
    return message.warning('开启文件泄露检测后，必须选择文件泄露字典！');
  }

  submitLoading.value = true;
  try {
    const poc_config = pocList.value.filter(p => p.enable).map(p => ({ plugin_name: p.plugin_name, vul_name: p.vul_name, enable: p.enable }));
    const brute_config = bruteList.value.filter(p => p.enable).map(p => ({ plugin_name: p.plugin_name, vul_name: p.vul_name, enable: p.enable }));

    const policyData = {
      name: policyForm.name.trim(),
      desc: policyForm.desc || '',
      policy: {
        domain_config: { ...policyForm.domain_config },
        ip_config: { ...policyForm.ip_config },
        npoc_service_detection: policyForm.ip_config.service_detection,
        site_config: { ...policyForm.site_config },
        file_leak: policyForm.file_leak,
        file_leak_dict: policyForm.file_leak_dict || 'file_top_2000.txt',
        poc_config,
        brute_config
      }
    };

    let res;
    if (isEdit) {
      res = await request.post('/policy/edit/', {
        policy_id: policyId,
        policy_data: policyData
      });
    } else {
      res = await request.post('/policy/add/', policyData);
    }

    if (res.code === 200) {
      message.success(isEdit ? '修改策略成功！' : '创建策略成功！');
      router.push('/policy');
    } else {
      message.error((isEdit ? '修改' : '创建') + '失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('请求异常，保存失败');
  } finally {
    submitLoading.value = false;
  }
};
</script>

<style scoped>
.policy-detail-container {
  background-color: var(--arl-bg-layout);
  padding: 24px;
  min-height: calc(100vh - 64px);
  position: relative;
}

.policy-detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--arl-border-color);
  padding-bottom: 16px;
}

.back-link-btn {
  padding: 0;
  margin-right: 16px;
  font-size: 14px;
  color: var(--arl-theme-color);
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.policy-form-layout {
  max-width: 1040px;
  margin: 0 auto;
}

.policy-section-card {
  background: var(--arl-bg-card, #ffffff);
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.section-card-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
  margin-bottom: 16px;
}

.indicator-bar {
  display: inline-block;
  width: 4px;
  height: 16px;
  background-color: var(--arl-theme-color, #1890ff);
  border-radius: 2px;
  margin-right: 8px;
}

.policy-collapse-box {
  background: transparent;
  margin-bottom: 24px;
}

:deep(.ant-collapse-item) {
  background: var(--arl-bg-card, #ffffff);
  border-radius: 8px !important;
  margin-bottom: 16px;
  border: 1px solid var(--arl-border-color) !important;
  overflow: hidden;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

:deep(.ant-collapse-item.ant-collapse-item-active) {
  border-color: color-mix(in srgb, var(--arl-theme-color) 45%, var(--arl-border-color)) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

:deep(.ant-collapse-header) {
  font-weight: 600;
  font-size: 15px;
  background-color: var(--arl-bg-card, #ffffff) !important;
  padding: 14px 20px !important;
  color: var(--arl-text-color) !important;
  border-bottom: 1px solid transparent;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

:deep(.ant-collapse-item.ant-collapse-item-active > .ant-collapse-header) {
  border-bottom: 1px solid var(--arl-border-color);
}

:deep(.ant-collapse-content) {
  background-color: var(--arl-bg-card, #ffffff) !important;
  color: var(--arl-text-color) !important;
  border-top: none !important;
}

:deep(.ant-collapse-content-box) {
  padding: 16px 20px !important;
}

.panel-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--arl-border-color);
}

.search-input {
  width: 240px;
}

.search-icon {
  color: var(--arl-text-color);
  opacity: 0.35;
}

.feature-item-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item-block {
  display: flex;
  flex-direction: column;
}

.feature-switch-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.feature-hint {
  color: var(--arl-text-color);
  opacity: 0.55;
  font-size: 13px;
  margin-left: 8px;
}

.sub-config-box {
  background-color: var(--arl-bg-subcard, #f8f9fa);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 14px 18px;
  margin-top: 10px;
  margin-left: 24px;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
}

.inline-form-item {
  margin-bottom: 0 !important;
}

.advanced-toggle-row {
  margin-top: 12px;
  margin-bottom: 6px;
}

.advanced-params-grid {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--arl-border-color);
}

.plugin-sub-section {
  display: flex;
  flex-direction: column;
}

.sub-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sub-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
}

.count-tag {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  background: color-mix(in srgb, var(--arl-theme-color) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--arl-theme-color) 32%, transparent);
  border-radius: 12px;
  color: var(--arl-theme-color);
  letter-spacing: 0.3px;
}

.sub-section-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.plugin-checkbox-grid {
  max-height: 380px;
  overflow-y: auto;
  padding-right: 6px;
}

.plugin-item-checkbox {
  padding: 6px 10px;
  border-radius: 6px;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.plugin-item-checkbox:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

:not(body.dark-mode) .plugin-item-checkbox:hover {
  background-color: rgba(0, 0, 0, 0.035);
}

.plugin-item-checkbox.is-checked {
  background-color: color-mix(in srgb, var(--arl-theme-color) 8%, transparent);
  border-color: color-mix(in srgb, var(--arl-theme-color) 22%, transparent);
}

.plugin-item-checkbox.is-checked .plugin-name-text {
  color: var(--arl-text-color);
  font-weight: 500;
}

.index-num {
  opacity: 0.45;
  margin-right: 4px;
  font-size: 12px;
}

.plugin-name-text {
  font-size: 13px;
}

.policy-footer-actions {
  position: sticky;
  bottom: 16px;
  z-index: 99;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  margin: 32px auto 16px auto;
  width: fit-content;
  background: color-mix(in srgb, var(--arl-bg-card, #141414) 85%, transparent);
  border: 1px solid var(--arl-border-color);
  border-radius: 28px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.submit-btn {
  width: 140px;
  height: 38px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 20px;
}

.cancel-btn {
  width: 100px;
  height: 38px;
  font-size: 14px;
  border-radius: 20px;
}
</style>