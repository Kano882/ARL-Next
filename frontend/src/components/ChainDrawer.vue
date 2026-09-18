<template>
  <a-drawer
    :open="open"
    :title="null"
    :closable="false"
    :width="drawerWidth"
    placement="right"
    destroyOnClose
    class="chain-drawer-root"
    @close="handleClose"
  >
    <!-- 头部自定义导航与控制栏 -->
    <div class="chain-drawer-header">
      <div class="drawer-header-left">
        <div class="drawer-header-badge">
          <compass-outlined class="drawer-compass-icon" />
        </div>
        <div>
          <div class="drawer-title-text">
            <span>全链路资产画像</span>
            <a-tag color="blue" class="drawer-target-tag">{{ target }}</a-tag>
          </div>
          <div class="drawer-subtitle-text">
            已聚合透视 DNS 解析、关联 IP、C 段、SSL 证书、开放服务与风险脆弱性
          </div>
        </div>
      </div>
      <div class="drawer-header-right">
        <a-tooltip title="复制目标">
          <a-button size="small" @click="handleCopyTarget">
            <template #icon><copy-outlined /></template>
          </a-button>
        </a-tooltip>
        <a-button type="primary" ghost size="small" @click="handleOpenDedicated">
          <template #icon><fullscreen-outlined /></template>
          独立画板
        </a-button>
        <a-button type="text" size="small" @click="handleClose">
          <template #icon><close-outlined /></template>
        </a-button>
      </div>
    </div>

    <!-- 抽屉主体内容区 -->
    <div class="chain-drawer-body">
      <a-spin :spinning="loading" tip="正在聚合多维全链路资产画像...">
        <div v-if="!loading && (!chainData || totalAssetCount === 0)" class="drawer-empty-box">
          <a-empty description="暂未检索到该资产的全链路关联记录">
            <template #image>
              <compass-outlined style="font-size: 56px; color: var(--arl-theme-color); opacity: 0.6;" />
            </template>
            <div style="margin-top: 12px; color: var(--arl-text-secondary); font-size: 13px;">
              目标暂未完成深度资产测绘，或未在当前资产组范围中命中关联数据
            </div>
          </a-empty>
        </div>

        <div v-else-if="chainData" class="chain-sections-container">
          <!-- 统计指标胶囊行 -->
          <div class="chain-metric-row">
            <div class="chain-metric-chip" v-if="chainData.site?.length">
              <global-outlined style="color: #1890ff;" /> 站点 <b>{{ chainData.site.length }}</b>
            </div>
            <div class="chain-metric-chip" v-if="chainData.domain_records?.length">
              <link-outlined style="color: #52c41a;" /> 解析 <b>{{ chainData.domain_records.length }}</b>
            </div>
            <div class="chain-metric-chip" v-if="chainData.ip?.length">
              <cloud-server-outlined style="color: #722ed1;" /> 关联IP <b>{{ chainData.ip.length }}</b>
            </div>
            <div class="chain-metric-chip" v-if="chainData.cip?.length">
              <cluster-outlined style="color: #eb2f96;" /> C段 <b>{{ chainData.cip.length }}</b>
            </div>
            <div class="chain-metric-chip" v-if="chainData.cert?.length">
              <safety-certificate-outlined style="color: #13c2c2;" /> 证书 <b>{{ chainData.cert.length }}</b>
            </div>
            <div class="chain-metric-chip" v-if="(chainData.service?.length || 0) + (chainData.npoc_service?.length || 0)">
              <api-outlined style="color: #fa8c16;" /> 服务 <b>{{ (chainData.service?.length || 0) + (chainData.npoc_service?.length || 0) }}</b>
            </div>
            <div class="chain-metric-chip" v-if="(chainData.vuln?.length || 0) + (chainData.nuclei_result?.length || 0)">
              <bug-outlined style="color: #f5222d;" /> 风险 <b>{{ (chainData.vuln?.length || 0) + (chainData.nuclei_result?.length || 0) }}</b>
            </div>
          </div>

          <!-- 1. 站点基础信息与截图 -->
          <a-card v-if="chainData.site && chainData.site.length > 0" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <global-outlined style="color: #1890ff;" />
                <span>站点基础信息</span>
                <a-badge :count="chainData.site.length" :number-style="{ backgroundColor: '#1890ff' }" />
              </div>
            </template>
            <div class="drawer-site-list">
              <div v-for="(siteItem, idx) in chainData.site" :key="idx" class="drawer-site-item">
                <div class="drawer-site-meta">
                  <div class="site-title-row">
                    <img v-if="siteItem.favicon && siteItem.favicon.data" :src="`data:image/png;base64,${siteItem.favicon.data}`" class="drawer-favicon" />
                    <a :href="siteItem.site" target="_blank" class="site-link">{{ siteItem.site }}</a>
                    <a-tag :color="siteItem.status === 200 ? 'success' : (siteItem.status >= 400 ? 'error' : 'default')">
                      HTTP {{ siteItem.status || '-' }}
                    </a-tag>
                  </div>
                  <div class="site-kv-grid">
                    <div class="kv-item"><span class="kv-label">标题：</span><span class="kv-value">{{ siteItem.title || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">Server：</span><span class="kv-value">{{ siteItem.http_server || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">IP：</span><span class="kv-value font-mono">{{ siteItem.ip || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">更新：</span><span class="kv-value">{{ siteItem.update_date || siteItem.save_date || '-' }}</span></div>
                  </div>
                  <div v-if="siteItem.finger && siteItem.finger.length" class="site-finger-row">
                    <span class="kv-label">指纹：</span>
                    <a-tag v-for="f in siteItem.finger" :key="f.name" color="blue" size="small">{{ f.name }}</a-tag>
                  </div>
                </div>
                <div v-if="siteItem.screenshot" class="drawer-site-shot">
                  <img :src="`/api${siteItem.screenshot}`" alt="截图" />
                </div>
              </div>
            </div>
          </a-card>

          <!-- 2. 子域名与解析记录 -->
          <a-card v-if="chainData.domain_records && chainData.domain_records.length > 0" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <link-outlined style="color: #52c41a;" />
                <span>子域名解析记录</span>
                <a-badge :count="chainData.domain_records.length" :number-style="{ backgroundColor: '#52c41a' }" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.domain_records"
              :columns="domainCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'domain'">
                  <span class="font-mono font-bold">{{ record.domain }}</span>
                </template>
                <template v-else-if="column.key === 'ips'">
                  <div v-if="Array.isArray(record.ips)">
                    <span v-for="(ip, idx) in record.ips" :key="idx" class="font-mono font-tag">{{ ip }}</span>
                  </div>
                  <span v-else class="font-mono">{{ record.ips || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 3. IP 与网络归属 -->
          <a-card v-if="chainData.ip && chainData.ip.length > 0" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <cloud-server-outlined style="color: #722ed1;" />
                <span>IP 与网络归属</span>
                <a-badge :count="chainData.ip.length" :number-style="{ backgroundColor: '#722ed1' }" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.ip"
              :columns="ipCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'ip'">
                  <span class="font-mono font-bold">{{ record.ip }}</span>
                </template>
                <template v-else-if="column.key === 'port_info'">
                  <span>{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
                </template>
                <template v-else-if="column.key === 'geo'">
                  <span>{{ formatGeo(record.geo_city) }}</span>
                </template>
                <template v-else-if="column.key === 'asn'">
                  <span>{{ record.geo_asn?.organization || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 4. SSL 证书 -->
          <a-card v-if="chainData.cert && chainData.cert.length > 0" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <safety-certificate-outlined style="color: #13c2c2;" />
                <span>SSL 证书</span>
                <a-badge :count="chainData.cert.length" :number-style="{ backgroundColor: '#13c2c2' }" />
              </div>
            </template>
            <div v-for="(certItem, idx) in chainData.cert" :key="idx" class="drawer-cert-item">
              <div class="cert-host-tag">{{ certItem.ip || certItem.host }}{{ certItem.port ? ':' + certItem.port : '' }}</div>
              <div v-if="certItem.cert" class="cert-fields">
                <div><b>主题名称：</b>{{ certItem.cert.subject_dn || '-' }}</div>
                <div><b>签发机构：</b>{{ certItem.cert.issuer_dn || '-' }}</div>
                <div v-if="certItem.cert.extensions?.subjectAltName"><b>备用名称 (SAN)：</b>{{ certItem.cert.extensions.subjectAltName }}</div>
                <div><b>有效期限：</b>{{ certItem.cert.validity?.start || '-' }} 至 {{ certItem.cert.validity?.end || '-' }}</div>
              </div>
            </div>
          </a-card>

          <!-- 5. 开放服务 -->
          <a-card v-if="chainData.service && chainData.service.length > 0" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <api-outlined style="color: #fa8c16;" />
                <span>开放系统服务</span>
                <a-badge :count="chainData.service.length" :number-style="{ backgroundColor: '#fa8c16' }" />
              </div>
            </template>
            <div class="drawer-services-grid">
              <div v-for="(srv, idx) in chainData.service" :key="idx" class="service-pill">
                <div class="service-name-tag">{{ srv.service_name || 'service' }}</div>
                <div v-for="(inf, i) in (srv.service_info || [])" :key="i" class="service-endpoint">
                  <span class="font-mono">{{ inf.ip }}:{{ inf.port_id }}</span>
                  <span v-if="inf.product" class="service-product">{{ inf.product }}</span>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 6. 风险与缺陷 (Vuln & Nuclei) -->
          <a-card v-if="(chainData.vuln?.length || 0) + (chainData.nuclei_result?.length || 0) > 0" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <bug-outlined style="color: #f5222d;" />
                <span>安全风险与漏洞</span>
                <a-badge :count="(chainData.vuln?.length || 0) + (chainData.nuclei_result?.length || 0)" :number-style="{ backgroundColor: '#f5222d' }" />
              </div>
            </template>
            <div class="drawer-vuln-list">
              <div v-for="(v, idx) in (chainData.vuln || [])" :key="'v-'+idx" class="vuln-item-card">
                <div class="vuln-header">
                  <a-tag color="error">风险</a-tag>
                  <span class="vuln-name">{{ v.vul_name || v.title || '未知风险' }}</span>
                </div>
                <div class="vuln-target font-mono">{{ v.target }}</div>
              </div>
              <div v-for="(n, idx) in (chainData.nuclei_result || [])" :key="'n-'+idx" class="vuln-item-card">
                <div class="vuln-header">
                  <a-tag color="volcano">Nuclei</a-tag>
                  <span class="vuln-name">{{ n.vuln_name || n.template_id }}</span>
                  <a-tag size="small" color="red">{{ n.vuln_severity || 'HIGH' }}</a-tag>
                </div>
                <div class="vuln-target font-mono">{{ n.vuln_url || n.target }}</div>
              </div>
            </div>
          </a-card>

        </div>
      </a-spin>
    </div>
  </a-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { message } from 'ant-design-vue';
import {
  CompassOutlined,
  GlobalOutlined,
  LinkOutlined,
  CloudServerOutlined,
  ClusterOutlined,
  SafetyCertificateOutlined,
  ApiOutlined,
  BugOutlined,
  CopyOutlined,
  FullscreenOutlined,
  CloseOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';
import { formatGeo } from '../utils/formatGeo';
import { copyText } from '../utils/clipboard';

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  target: {
    type: String,
    default: ''
  },
  scopeId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:open', 'openDedicated']);

const loading = ref(false);
const chainData = ref(null);

const drawerWidth = computed(() => {
  return window.innerWidth > 1200 ? '780px' : '90vw';
});

const domainCols = [
  { title: '子域名', dataIndex: 'domain', key: 'domain' },
  { title: '类型', dataIndex: 'type', key: 'type', width: 90 },
  { title: '解析IP', key: 'ips' }
];

const ipCols = [
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 140 },
  { title: '开放端口', key: 'port_info' },
  { title: '地理位置', key: 'geo', width: 140 },
  { title: 'AS机构', key: 'asn' }
];

const totalAssetCount = computed(() => {
  if (!chainData.value) return 0;
  const d = chainData.value;
  return (
    (d.site?.length || 0) +
    (d.domain_records?.length || 0) +
    (d.ip?.length || 0) +
    (d.cip?.length || 0) +
    (d.cert?.length || 0) +
    (d.service?.length || 0) +
    (d.npoc_service?.length || 0) +
    (d.fileleak?.length || 0) +
    (d.url?.length || 0) +
    (d.wih?.length || 0) +
    (d.vuln?.length || 0) +
    (d.nuclei_result?.length || 0)
  );
});

const fetchChainData = async () => {
  if (!props.target || !props.scopeId) return;
  loading.value = true;
  chainData.value = null;
  try {
    const res = await request.get('/asset_site/subdomain_chain/', {
      params: {
        scope_id: props.scopeId,
        domain: props.target.trim()
      }
    });
    if (res.code === 200) {
      chainData.value = res.data || {};
    } else {
      message.error(res.message || '获取画像失败');
    }
  } catch (e) {
    message.error('网络请求异常');
  } finally {
    loading.value = false;
  }
};

watch(() => props.open, (isOpen) => {
  if (isOpen && props.target) {
    fetchChainData();
  }
});

const handleClose = () => {
  emit('update:open', false);
};

const handleCopyTarget = async () => {
  const ok = await copyText(props.target);
  if (ok) message.success('已复制目标: ' + props.target);
};

const handleOpenDedicated = () => {
  emit('openDedicated', props.target);
  handleClose();
};
</script>

<style scoped>
.chain-drawer-root :deep(.ant-drawer-body) {
  padding: 0;
  background: var(--arl-bg-layout);
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chain-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--arl-bg-white);
  border-bottom: 1px solid var(--arl-border-color);
  position: sticky;
  top: 0;
  z-index: 10;
}

.drawer-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.drawer-header-badge {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(250, 84, 28, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-compass-icon {
  font-size: 20px;
  color: var(--arl-theme-color);
}

.drawer-title-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--arl-text-color);
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-target-tag {
  font-family: monospace;
  font-size: 13px;
  border-radius: 4px;
}

.drawer-subtitle-text {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-top: 2px;
}

.drawer-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chain-drawer-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.drawer-empty-box {
  background: var(--arl-bg-white);
  border-radius: 8px;
  padding: 80px 24px;
  text-align: center;
  border: 1px dashed var(--arl-border-color);
}

.chain-sections-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chain-metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}

.chain-metric-chip {
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--arl-text-color);
}

.chain-metric-chip b {
  color: var(--arl-primary-color);
}

.drawer-chain-card {
  border-radius: 8px;
  background: var(--arl-bg-white);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.drawer-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.drawer-site-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-site-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
}

.drawer-site-meta {
  flex: 1;
}

.site-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.drawer-favicon {
  width: 16px;
  height: 16px;
}

.site-link {
  font-weight: 600;
  font-size: 14px;
  color: var(--arl-theme-color);
  word-break: break-all;
}

.site-kv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 12px;
  font-size: 12px;
}

.kv-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.kv-label {
  color: var(--arl-text-secondary);
}

.kv-value {
  color: var(--arl-text-color);
}

.site-finger-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.drawer-site-shot img {
  width: 140px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--arl-border-color);
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: 600;
}

.font-tag {
  display: inline-block;
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 4px;
  margin-bottom: 2px;
}

.drawer-cert-item {
  padding: 10px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
  margin-bottom: 8px;
}

.cert-host-tag {
  font-weight: 600;
  font-family: monospace;
  color: var(--arl-primary-color);
  margin-bottom: 6px;
}

.cert-fields {
  font-size: 12px;
  line-height: 1.6;
  color: var(--arl-text-color);
}

.drawer-services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.service-pill {
  padding: 8px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.service-name-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-primary-color);
  margin-bottom: 4px;
}

.service-endpoint {
  font-size: 11px;
  display: flex;
  justify-content: space-between;
  gap: 4px;
}

.service-product {
  color: var(--arl-text-secondary);
}

.drawer-vuln-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vuln-item-card {
  padding: 8px 12px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border-left: 3px solid #f5222d;
}

.vuln-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.vuln-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--arl-text-color);
}

.vuln-target {
  font-size: 12px;
  color: var(--arl-text-secondary);
}
</style>
