<template>
  <div style="background-color: var(--arl-bg-layout); min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
      <a-page-header
        @back="handleBack"
        style="padding: 0 0 24px 0;"
      >
        <template #title>
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-tooltip placement="bottomLeft">
              <template #title>
                <div style="word-break: break-all; max-height: 300px; overflow-y: auto; font-weight: normal; font-size: 14px;">
                  <div v-for="(item, index) in targetList" :key="index">
                    {{ item }}
                  </div>
                </div>
              </template>
              <span style="cursor: default;">{{ displayTitle }}</span>
            </a-tooltip>
            <a-tag v-if="taskTypeLabel" color="blue">{{ taskTypeLabel }}</a-tag>
            <a-tag v-if="taskStatusLabel" :color="taskStatusColor">{{ taskStatusLabel }}</a-tag>
            <a-tag
              v-if="taskRecord.synced_scope_id"
              color="blue"
              style="cursor: pointer; display: inline-flex; align-items: center; gap: 4px;"
              @click="goToScope(taskRecord.synced_scope_id)"
              title="点击前往该资产分组"
            >
              <export-outlined />
              <span>已同步至: {{ taskRecord.synced_scope_name || '资产分组' }}</span>
            </a-tag>
          </div>
        </template>
        <template #extra>
          <a-tooltip v-if="taskStatus === 'done' && (taskRecord.statistic?.web_cnt === 0)" title="当前任务无网站资产可同步">
            <a-button type="primary" disabled>
              <cloud-sync-outlined /> 同步至资产分组
            </a-button>
          </a-tooltip>
          <a-button
            v-else
            type="primary"
            @click="openSyncModal"
            :disabled="taskStatus !== 'done' && taskStatus !== 'stop'"
          >
            <cloud-sync-outlined /> {{ taskRecord.synced_scope_id ? (taskRecord.has_increment ? '同步增量至分组' : '再次同步至分组') : '同步至资产分组' }}
          </a-button>
        </template>
      </a-page-header>

      <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" :style="activeTab === 'log' ? 'margin-bottom: 0;' : 'margin-bottom: 16px;'" @change="onTabChange">
        <a-tab-pane key="web" :tab="`网站备案 - ${queryCounts.web}`"></a-tab-pane>
        <a-tab-pane key="app" :tab="`APP - ${queryCounts.app}`"></a-tab-pane>
        <a-tab-pane key="mapp" :tab="`小程序 - ${queryCounts.mapp}`"></a-tab-pane>
        <a-tab-pane key="wechat" :tab="`公众号 - ${queryCounts.wechat}`"></a-tab-pane>
        <a-tab-pane key="weibo" :tab="`微博 - ${queryCounts.weibo}`"></a-tab-pane>
        <a-tab-pane key="kapp" :tab="`快应用 - ${queryCounts.kapp}`"></a-tab-pane>
        <a-tab-pane key="trademark" :tab="`商标信息 - ${queryCounts.trademark}`"></a-tab-pane>
        <a-tab-pane key="invest" :tab="`对外投资 - ${queryCounts.invest}`"></a-tab-pane>
        <a-tab-pane key="log" tab="运行日志"></a-tab-pane>
      </a-tabs>

      <div v-show="activeTab !== 'log'">
        <div style="margin-bottom: 16px;">
          <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
            <template v-for="col in dynamicColumns" :key="col.key">
              <a-form-item v-if="col.key !== 'index' && col.key !== 'raw' && col.key !== 'icon' && col.key !== 'examineDate' && col.key !== 'updateRecordTime'" :label="col.title + ':'">
                <a-input-group compact v-if="['amount', 'percent'].includes(col.dataIndex)">
                  <a-select v-model:value="searchFormOp[col.dataIndex]" style="width: 70px" :options="[{value:'eq',label:'='},{value:'gt',label:'>'},{value:'lt',label:'<'}]" />
                  <a-input v-model:value="searchForm[col.dataIndex]" style="width: 130px" :placeholder="'输入' + col.title" @pressEnter="onSearch">
                    <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
                  </a-input>
                </a-input-group>
                <a-input v-else v-model:value="searchForm[col.dataIndex]" :placeholder="'请输入' + col.title" style="width: 180px;" allowClear @pressEnter="onSearch">
                  <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
                </a-input>
              </a-form-item>
            </template>
          </a-form>
        </div>
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
          <a-button @click="resetSearch">清 除</a-button>
          <a-button type="primary" :loading="exportLoading" @click="handleExport">
            <template #icon><download-outlined /></template>
            导出数据
          </a-button>
          <a-button
            v-if="activeTab === 'web' && selectedWebRowKeys.length > 0"
            type="dashed"
            @click="openSyncModalWithSelected"
          >
            <cloud-sync-outlined /> 同步勾选域名 ({{ selectedWebRowKeys.length }})
          </a-button>
        </div>
      </div>
    </div>

    <div v-show="activeTab !== 'log'">
      <a-table
        :sticky="stickyConfig"
        :dataSource="assetList"
        :columns="dynamicColumns"
        :loading="loading"
        :pagination="false"
        :row-selection="activeTab === 'web' ? { selectedRowKeys: selectedWebRowKeys, onChange: onWebSelectChange } : null"
        :scroll="pagination.pageSize >= 100 ? { y: 'calc(100vh - 380px)', x: 'max-content' } : { x: 'max-content' }"
        :virtual="pagination.pageSize >= 100"
        :rowKey="(record) => record._id || record.id || record.domain || record.ym || Math.random()"
        size="middle"
        style="margin-bottom: 16px;"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record, text, index }">
          <template v-if="column.key === 'index'">
            {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
          </template>
          <template v-else-if="column.key === 'icon'">
            <img v-if="text" :src="text" style="width:32px;height:32px;border-radius:4px;" />
          </template>
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="text">
              {{ text || '-' }}
            </div>
          </template>
          <template v-else-if="column.key === 'serviceName' || column.key === 'name'">
            {{ record.serviceName || record.name || '-' }}
          </template>
          <template v-else-if="column.key === 'raw'">
            <a-popover title="原始数据" trigger="click" placement="left">
              <template #content>
                <div style="max-width: 400px; max-height: 400px; overflow: auto;">
                  <pre style="font-size: 12px;">{{ JSON.stringify(record, null, 2) }}</pre>
                </div>
              </template>
              <a-button type="link" size="small">查看JSON</a-button>
            </a-popover>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
      </a-table>

      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
        <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
        <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handlePaginationChange" @showSizeChange="handlePaginationChange" />
      </div>
    </div>

    <div v-show="activeTab === 'log'">
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
        <div ref="terminalContainer" style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, 'Courier New', monospace; padding: 16px; border-radius: 4px; height: calc(100vh - 240px); overflow-y: auto; font-size: 13px; line-height: 1.6; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);" @mouseenter="pauseScroll = true" @mouseleave="pauseScroll = false">
          <div v-for="(log, idx) in syslogList" :key="idx" style="margin-bottom: 6px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 4px;">
            <a style="margin-right: 8px;">[{{ log.create_time }}]</a>
            <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <a style="margin-right: 8px;">[{{ log.title }}]</a>
            <span style="color: #e6f7ff;">{{ log.message }}</span>
          </div>
          <div v-if="syslogLoading && syslogList.length === 0" style="color: rgba(255,255,255,0.65); font-style: italic;">[System] 正在加载任务运行日志...</div>
          <div v-else-if="syslogList.length === 0" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录... (等待日志生成或当前为历史遗留任务)</div>
        </div>
      </div>
    </div>

    <SyncToScopeModal
      v-model:open="syncModalVisible"
      :task="taskRecord"
      :preSelectedDomains="selectedWebDomains"
      @success="handleSyncSuccess"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { SearchOutlined, DownloadOutlined, CloudSyncOutlined, ExportOutlined } from '@ant-design/icons-vue';
import SyncToScopeModal from './SyncToScopeModal.vue';
import { message } from 'ant-design-vue';
import request from '../utils/request';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { useSticky } from '../utils/useSticky';

const route = useRoute();
const router = useRouter();

const taskId = computed(() => (route.query?.task_id ? String(route.query.task_id) : ''));
const taskName = ref(route.query?.name || '');
const taskTarget = ref(route.query?.target || '');
const taskType = ref(route.query?.task_type || 'icp');
const taskStatus = ref('');
const taskRecord = ref({});

const syncModalVisible = ref(false);
const selectedWebRowKeys = ref([]);
const selectedWebDomains = ref([]);

const handleBack = () => {
  router.push({ path: '/taskList', query: { tab: 'enterprise' } });
};

const onWebSelectChange = (keys, rows) => {
  selectedWebRowKeys.value = keys;
  const domains = [];
  rows.forEach(r => {
    const d = r.domain || r.ym;
    if (d && typeof d === 'string') domains.push(d.trim());
  });
  selectedWebDomains.value = domains;
};

const openSyncModal = () => {
  selectedWebDomains.value = [];
  syncModalVisible.value = true;
};

const openSyncModalWithSelected = () => {
  syncModalVisible.value = true;
};

const handleSyncSuccess = (res) => {
  taskRecord.value.synced_scope_id = res.scope_id;
  taskRecord.value.synced_scope_name = res.target_name;
  fetchTaskStatistic();
};

const goToScope = (scopeId) => {
  if (scopeId) {
    router.push({ path: '/group', query: { scope_id: scopeId } });
  }
};

const targetList = computed(() => {
  const t = taskTarget.value || taskName.value || taskId.value || '未知目标';
  return String(t).split(/[,\s]+/).filter(Boolean);
});

const displayTitle = computed(() => {
  const list = targetList.value;
  if (list.length <= 1) {
    return `${list[0] || '目标'} 相关资产`;
  }
  return `${list[0]} 等 ${list.length} 个目标相关资产`;
});

const taskTypeLabel = computed(() => {
  if (taskType.value === 'tyc') return '天眼查';
  if (taskType.value === 'icp') return 'ICP备案';
  return '';
});

const taskStatusLabel = computed(() => {
  const map = {
    waiting: '等待中',
    running: '运行中',
    done: '已完成',
    error: '失败',
    stop: '已停止'
  };
  return map[taskStatus.value] || '';
});

const taskStatusColor = computed(() => {
  const map = {
    waiting: 'blue',
    running: 'processing',
    done: 'success',
    error: 'error',
    stop: 'default'
  };
  return map[taskStatus.value] || 'default';
});

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

const validTabs = ['web', 'app', 'mapp', 'kapp', 'invest', 'trademark', 'wechat', 'weibo', 'log'];
const activeTab = ref(route.query?.tab && validTabs.includes(route.query.tab) ? route.query.tab : 'web');
const queryCounts = reactive({
  web: 0,
  app: 0,
  mapp: 0,
  kapp: 0,
  invest: 0,
  trademark: 0,
  wechat: 0,
  weibo: 0,
});

const syncEnterpriseQueryCounts = (q = route.query) => {
  queryCounts.web = Number(q?.web_cnt) || 0;
  queryCounts.app = Number(q?.app_cnt) || 0;
  queryCounts.mapp = Number(q?.mapp_cnt) || 0;
  queryCounts.kapp = Number(q?.kapp_cnt) || 0;
  queryCounts.invest = Number(q?.invest_cnt) || 0;
  queryCounts.trademark = Number(q?.trademark_cnt) || 0;
  queryCounts.wechat = Number(q?.wechat_cnt) || 0;
  queryCounts.weibo = Number(q?.weibo_cnt) || 0;
};
syncEnterpriseQueryCounts();

const assetList = ref([]);
const loading = ref(false);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const syslogList = ref([]);
let syslogTimer = null;
const terminalContainer = ref(null);
const pauseScroll = ref(false);
const syslogLoading = ref(false);

const sortState = reactive({
  field: null,
  order: null
});

const getDefaultSortForTab = (tab) => {
  const isTyc = taskType.value === 'tyc';
  if (isTyc) {
    if (tab === 'web' || tab === 'mapp') {
      return { field: 'examineDate', order: 'descend' };
    }
  } else {
    if (['web', 'app', 'mapp', 'kapp'].includes(tab)) {
      return { field: 'updateRecordTime', order: 'descend' };
    }
  }
  return { field: null, order: null };
};

const resetTabSort = (tab) => {
  const def = getDefaultSortForTab(tab);
  sortState.field = def.field;
  sortState.order = def.order;
};

const webColumns = [
  { title: '主办单位名称', dataIndex: 'companyName', key: 'companyName', width: 220 },
  { title: '单位性质', dataIndex: 'companyType', key: 'companyType', width: 120 },
  { title: '主备案号', dataIndex: 'liscense', key: 'liscense', width: 180 },
  { title: '域名', dataIndex: 'ym', key: 'ym', width: 200 },
  { title: '网站名称', dataIndex: 'webName', key: 'webName', width: 200 },
  { title: '审核日期', dataIndex: 'examineDate', key: 'examineDate', width: 120 },
  { title: '详情', key: 'raw', width: 80 }
];

const mappColumns = [
  { title: '小程序名称', dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { title: '备案号', dataIndex: 'serviceFilingNumber', key: 'serviceFilingNumber', width: 200 },
  { title: '审核日期', dataIndex: 'examineDate', key: 'examineDate', width: 120 },
  { title: '详情', key: 'raw', width: 80 }
];

const appColumns = [
  { title: '图标', dataIndex: 'icon', key: 'icon', width: 60 },
  { title: 'APP名称', dataIndex: 'name', key: 'name', width: 150 },
  { title: '分类', dataIndex: 'classes', key: 'classes', width: 100 },
  { title: '应用类型', dataIndex: 'type', key: 'type', width: 100 },
  { title: '简介', dataIndex: 'brief', key: 'brief', width: 300, ellipsis: true },
  { title: '详情', key: 'raw', width: 80 }
];

const investColumns = [
  { title: '投资公司名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '法定代表人', dataIndex: 'legalPersonName', key: 'legalPersonName', width: 120 },
  { title: '注册资本', dataIndex: 'amount', key: 'amount', width: 120 },
  { title: '投资比例', dataIndex: 'percent', key: 'percent', width: 100 },
  { title: '详情', key: 'raw', width: 80 }
];

const trademarkColumns = [
  { title: '商标名称', dataIndex: 'tmName', key: 'tmName', width: 180 },
  { title: '注册号', dataIndex: 'regNo', key: 'regNo', width: 150 },
  { title: '分类', dataIndex: 'intCls', key: 'intCls', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '详情', key: 'raw', width: 80 }
];

const wechatColumns = [
  { title: '头像', dataIndex: 'titleImgURL', key: 'icon', width: 60 },
  { title: '公众号名称', dataIndex: 'title', key: 'title', width: 200 },
  { title: '微信号', dataIndex: 'publicNum', key: 'publicNum', width: 150 },
  { title: '简介', dataIndex: 'recommend', key: 'recommend', width: 300, ellipsis: true },
  { title: '详情', key: 'raw', width: 80 }
];

const weiboColumns = [
  { title: '微博名称', dataIndex: 'name', key: 'name', width: 200 },
  { title: '微博链接', dataIndex: 'href', key: 'href', width: 250 },
  { title: '详情', key: 'raw', width: 80 }
];

const baseIcpColumns = [
  { title: '主办单位名称', dataIndex: 'unitName', key: 'unitName', width: 220 },
  { title: '单位性质', dataIndex: 'natureName', key: 'natureName', width: 120 },
  { title: '主备案号', dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { title: '域名', dataIndex: 'domain', key: 'domain', width: 200 },
  { title: '网站名称', dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { title: '审核日期', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 },
  { title: '详情', key: 'raw', width: 80 }
];

const mobileIcpColumns = [
  { title: '应用名称', dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { title: '服务备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 200 },
  { title: '主办单位名称', dataIndex: 'unitName', key: 'unitName', width: 220 },
  { title: '主备案号', dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { title: '前置审批/类型', dataIndex: 'contentTypeName', key: 'contentTypeName', width: 150 },
  { title: '审核日期', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 },
  { title: '详情', key: 'raw', width: 80 }
];

const genericColumns = [
  { title: '名称', dataIndex: 'filterName', key: 'filterName', width: 200 },
  { title: '详情', key: 'raw', width: 80 }
];

const dynamicColumns = computed(() => {
  const isTyc = taskType.value === 'tyc';
  let cols = [];
  if (activeTab.value === 'invest') cols = investColumns;
  else if (activeTab.value === 'trademark') cols = trademarkColumns;
  else if (activeTab.value === 'wechat') cols = wechatColumns;
  else if (activeTab.value === 'weibo') cols = weiboColumns;
  else if (isTyc) {
    if (activeTab.value === 'web') cols = webColumns;
    else if (activeTab.value === 'mapp') cols = mappColumns;
    else if (activeTab.value === 'app') cols = appColumns;
    else cols = genericColumns;
  } else {
    if (activeTab.value === 'web') cols = baseIcpColumns;
    else if (['app', 'mapp', 'kapp'].includes(activeTab.value)) cols = mobileIcpColumns;
    else cols = genericColumns;
  }

  const processedCols = cols.map((col) => {
    if (col.key === 'examineDate' || col.key === 'updateRecordTime') {
      return {
        ...col,
        sorter: true,
        sortOrder: sortState.field === col.key ? sortState.order : null
      };
    }
    return col;
  });

  return [
    { title: '序号', key: 'index', width: 70, align: 'center' },
    ...processedCols
  ];
});

const exportLoading = ref(false);
const handleExport = async () => {
  if (!taskId.value) return;
  try {
    exportLoading.value = true;
    message.loading({ content: '正在导出...', key: 'export', duration: 0 });
    const res = await request.get(`/icp/export/${taskId.value}`, { responseType: 'blob' });
    const resData = res.data || res;
    if (resData.type === 'application/json' || (res.headers && res.headers['content-type']?.includes('application/json'))) {
      message.error({ content: '导出失败，接口返回异常', key: 'export', duration: 2 });
      return;
    }
    const blob = new Blob([resData]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${taskName.value || taskTarget.value || 'icp_export'}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    message.success({ content: '导出成功', key: 'export', duration: 2 });
  } catch (error) {
    console.error('导出失败:', error);
    message.error({ content: '导出失败', key: 'export', duration: 2 });
  } finally {
    exportLoading.value = false;
  }
};

const searchForm = reactive({});
const searchFormOp = reactive({ amount: 'eq', percent: 'eq' });

const hasActiveSearch = () => {
  return Object.values(searchForm).some((val) => val !== undefined && val !== null && val !== '');
};

const resetSearch = () => {
  for (const key in searchForm) {
    delete searchForm[key];
  }
  searchFormOp.amount = 'eq';
  searchFormOp.percent = 'eq';
  pagination.current = 1;
  fetchAssets(1, pagination.pageSize);
};

const fetchAssets = async (page = 1, size = 10) => {
  loading.value = true;
  try {
    let orderParam = '-_id';
    if (sortState.field && sortState.order) {
      orderParam = (sortState.order === 'ascend' ? '+' : '-') + sortState.field;
    } else {
      const def = getDefaultSortForTab(activeTab.value);
      if (def.field && def.order) {
        orderParam = (def.order === 'ascend' ? '+' : '-') + def.field;
      }
    }

    const queryParams = { page, size, task_id: taskId.value, query_type: activeTab.value, order: orderParam };
    for (const [key, val] of Object.entries(searchForm)) {
      if (val !== undefined && val !== null && val !== '') {
        if (['amount', 'percent'].includes(key)) {
          const op = searchFormOp[key] || 'eq';
          const fieldName = key + '_num';
          if (op === 'gt') queryParams[`${fieldName}__ngt`] = val;
          else if (op === 'lt') queryParams[`${fieldName}__nlt`] = val;
          else queryParams[fieldName] = val;
        } else {
          queryParams[key] = val;
        }
      }
    }

    const res = await request.get('/icp/asset', { params: queryParams });
    if (res.code === 200) {
      assetList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
      if (!hasActiveSearch() && Object.prototype.hasOwnProperty.call(queryCounts, activeTab.value)) {
        queryCounts[activeTab.value] = pagination.total;
      }
    } else {
      console.error('获取资产列表失败:', res);
    }
  } catch (error) {
    console.error('API 请求失败:', error);
  } finally {
    loading.value = false;
  }
};

const onSearch = () => fetchAssets(1, pagination.pageSize);
const handleTableChange = (paginationData, filters, sorter) => {
  if (sorter && sorter.field && sorter.order) {
    sortState.field = sorter.field;
    sortState.order = sorter.order;
  } else {
    const def = getDefaultSortForTab(activeTab.value);
    sortState.field = def.field;
    sortState.order = def.order;
  }
  pagination.current = 1;
  fetchAssets(1, pagination.pageSize);
};

const handlePaginationChange = (page, pageSize) => {
  fetchAssets(page, pageSize);
};

const fetchSyslog = async (isPolling = false) => {
  if (!taskId.value) return;
  try {
    if (!isPolling) syslogLoading.value = true;
    const res = await request.get('/syslog/', {
      params: {
        task_id: taskId.value,
        size: 50000,
        order: 'create_time',
        _t: Date.now()
      }
    });
    if (res.code === 200) {
      syslogList.value = res.items || [];
      if (!pauseScroll.value) {
        nextTick(() => {
          if (terminalContainer.value) {
            terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
          }
        });
      }
    }
  } catch (error) {
    console.error('获取日志失败:', error);
  } finally {
    if (!isPolling) syslogLoading.value = false;
  }
};

const startSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
  fetchSyslog();
  const isTerminal = ['done', 'error', 'stop'].includes(taskStatus.value);
  if (!isTerminal) {
    syslogTimer = setInterval(() => {
      fetchSyslog(true);
    }, 5000);
  }
};

const stopSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
};

const onTabChange = (key) => {
  for (const k of Object.keys(searchForm)) {
    delete searchForm[k];
  }
  for (const k of Object.keys(searchFormOp)) {
    delete searchFormOp[k];
  }

  if (key === 'invest') {
    searchFormOp['amount'] = 'eq';
    searchFormOp['percent'] = 'eq';
  }

  resetTabSort(key);

  if (key === 'log') {
    startSyslogTimer();
  } else {
    stopSyslogTimer();
    assetList.value = [];
    fetchAssets(1, globalPageSize.value);
  }
};

let taskTimer = null;
let lastStatus = '';

const fetchTaskStatistic = async () => {
  if (!taskId.value) return;
  try {
    const res = await request.get('/icp/task', { params: { _id: taskId.value, _t: Date.now() } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      const taskData = res.items[0];
      taskRecord.value = taskData;
      if (taskData.name) taskName.value = taskData.name;
      if (taskData.target) taskTarget.value = taskData.target;
      if (taskData.task_type) taskType.value = taskData.task_type;
      taskStatus.value = taskData.status || '';

      const stat = taskData.statistic || {};
      queryCounts.web = stat.web_cnt !== undefined ? stat.web_cnt : queryCounts.web;
      queryCounts.app = stat.app_cnt !== undefined ? stat.app_cnt : queryCounts.app;
      queryCounts.mapp = stat.mapp_cnt !== undefined ? stat.mapp_cnt : queryCounts.mapp;
      queryCounts.kapp = stat.kapp_cnt !== undefined ? stat.kapp_cnt : queryCounts.kapp;
      queryCounts.invest = stat.invest_cnt !== undefined ? stat.invest_cnt : queryCounts.invest;
      queryCounts.trademark = stat.trademark_cnt !== undefined ? stat.trademark_cnt : queryCounts.trademark;
      queryCounts.wechat = stat.wechat_cnt !== undefined ? stat.wechat_cnt : queryCounts.wechat;
      queryCounts.weibo = stat.weibo_cnt !== undefined ? stat.weibo_cnt : queryCounts.weibo;
      
      const currentStatus = taskData.status;
      if (['done', 'error', 'stop'].includes(currentStatus)) {
        if (taskTimer) {
          clearInterval(taskTimer);
          taskTimer = null;
        }
        stopSyslogTimer();
        if (activeTab.value === 'log') {
          fetchSyslog(true);
        } else if (lastStatus && !['done', 'error', 'stop'].includes(lastStatus)) {
          fetchAssets(pagination.current, pagination.pageSize);
        }
      }
      lastStatus = currentStatus;
    }
  } catch (error) {
    console.error('获取任务统计失败:', error);
  }
};

const loadedEnterpriseTaskId = ref('');

const reloadEnterpriseTaskData = () => {
  if (taskTimer) {
    clearInterval(taskTimer);
    taskTimer = null;
  }
  stopSyslogTimer();

  loadedEnterpriseTaskId.value = taskId.value;
  taskName.value = route.query?.name || '';
  taskTarget.value = route.query?.target || '';
  taskType.value = route.query?.task_type || 'icp';
  taskStatus.value = '';
  taskRecord.value = {};
  selectedWebRowKeys.value = [];
  selectedWebDomains.value = [];
  assetList.value = [];
  syncEnterpriseQueryCounts(route.query);

  if (taskId.value) {
    if (activeTab.value === 'log') {
      startSyslogTimer();
    } else {
      resetTabSort(activeTab.value);
      fetchAssets(1, pagination.pageSize);
    }
    fetchTaskStatistic();
    taskTimer = setInterval(fetchTaskStatistic, 5000);
  }
};

watch(taskId, () => {
  if (!route.path.startsWith('/taskList/taskDetail')) return;
  const t = route.query?.task_type;
  if (t !== 'tyc' && t !== 'icp') return;
  reloadEnterpriseTaskData();
});

watch(() => route.query?.tab, (newTab) => {
  if (!route.path.startsWith('/taskList/taskDetail')) return;
  if (newTab && validTabs.includes(newTab) && newTab !== activeTab.value) {
    activeTab.value = newTab;
    onTabChange(newTab);
  }
});

onMounted(() => {
  reloadEnterpriseTaskData();
});

onUnmounted(() => {
  stopSyslogTimer();
  if (taskTimer) {
    clearInterval(taskTimer);
    taskTimer = null;
  }
});

onDeactivated(() => {
  stopSyslogTimer();
  if (taskTimer) {
    clearInterval(taskTimer);
    taskTimer = null;
  }
  syncModalVisible.value = false;
  rawDetailVisible.value = false;
});

onActivated(() => {
  const t = route.query?.task_type;
  if (t !== 'tyc' && t !== 'icp') return;
  if (loadedEnterpriseTaskId.value !== taskId.value) {
    reloadEnterpriseTaskData();
  } else if (taskId.value) {
    fetchTaskStatistic();
    const isTerminal = ['done', 'error', 'stop'].includes(taskStatus.value);
    if (!taskTimer && !isTerminal) {
      taskTimer = setInterval(fetchTaskStatistic, 5000);
    }
    if (activeTab.value === 'log') {
      if (!syslogTimer && !isTerminal) {
        startSyslogTimer();
      } else if (syslogList.value.length === 0) {
        fetchSyslog();
      }
    }
  }
});
</script>
