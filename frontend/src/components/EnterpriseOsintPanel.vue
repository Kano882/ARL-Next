<template>
  <div class="enterprise-osint-panel">
    <!-- 顶部摘要与操作栏 (仅当有任务时渲染) -->
    <div v-if="taskId" style="margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-weight: 600; font-size: 15px; color: var(--arl-text-color);">{{ taskTarget || taskName || '企业资产画像' }}</span>
          <a-tag v-if="taskTypeLabel" color="blue">{{ taskTypeLabel }}</a-tag>
          <a-tag v-if="taskStatusLabel" :color="taskStatusColor">{{ taskStatusLabel }}</a-tag>
          <a-badge v-if="hasIncrement" count="有增量" :number-style="{ backgroundColor: '#52c41a', fontSize: '10px' }" />
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <a-button type="primary" size="small" :loading="refreshLoading" @click="handleRefreshTask">
            <template #icon><sync-outlined /></template>
            增量更新测绘
          </a-button>
          <a-button v-if="activeTab === 'web' && selectedWebRowKeys.length > 0" type="dashed" size="small" @click="openSyncModalWithSelected">
            <template #icon><cloud-sync-outlined /></template>
            同步勾选域名 ({{ selectedWebRowKeys.length }})
          </a-button>
        </div>
      </div>

      <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" :style="activeTab === 'log' ? 'margin-bottom: 0;' : 'margin-bottom: 16px;'" @change="onTabChange">
        <a-tab-pane key="web" :tab="`网站备案 (${queryCounts.web})`"></a-tab-pane>
        <a-tab-pane key="app" :tab="`移动 APP (${queryCounts.app})`"></a-tab-pane>
        <a-tab-pane key="mapp" :tab="`微信小程序 (${queryCounts.mapp})`"></a-tab-pane>
        <a-tab-pane key="wechat" :tab="`微信公众号 (${queryCounts.wechat})`"></a-tab-pane>
        <a-tab-pane key="weibo" :tab="`企业微博 (${queryCounts.weibo})`"></a-tab-pane>
        <a-tab-pane key="kapp" :tab="`快应用 (${queryCounts.kapp})`"></a-tab-pane>
        <a-tab-pane key="trademark" :tab="`商标信息 (${queryCounts.trademark})`"></a-tab-pane>
        <a-tab-pane key="invest" :tab="`对外投资 (${queryCounts.invest})`"></a-tab-pane>
        <a-tab-pane key="log" tab="测绘日志"></a-tab-pane>
      </a-tabs>

      <!-- 搜索与导出栏 -->
      <div v-show="activeTab !== 'log'">
        <div style="margin-bottom: 12px;">
          <a-form :model="searchForm" layout="inline" style="row-gap: 12px;">
            <template v-for="col in dynamicColumns" :key="col.key">
              <a-form-item v-if="col.key !== 'index' && col.key !== 'raw' && col.key !== 'icon' && col.key !== 'examineDate' && col.key !== 'updateRecordTime'" :label="col.title + ':'">
                <a-input-group compact v-if="['amount', 'percent'].includes(col.dataIndex)">
                  <a-select v-model:value="searchFormOp[col.dataIndex]" style="width: 65px" :options="[{value:'eq',label:'='},{value:'gt',label:'>'},{value:'lt',label:'<'}]" />
                  <a-input v-model:value="searchForm[col.dataIndex]" style="width: 120px" :placeholder="'输入' + col.title" @pressEnter="onSearch">
                    <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
                  </a-input>
                </a-input-group>
                <a-input v-else v-model:value="searchForm[col.dataIndex]" :placeholder="'请输入' + col.title" style="width: 160px;" allowClear @pressEnter="onSearch">
                  <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
                </a-input>
              </a-form-item>
            </template>
          </a-form>
        </div>
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <a-button size="small" @click="resetSearch">重 置</a-button>
          <a-button size="small" type="primary" :loading="exportLoading" @click="handleExport">
            <template #icon><download-outlined /></template>
            导出表格
          </a-button>
        </div>
      </div>
    </div>

    <!-- 资产表格 -->
    <div v-if="taskId && activeTab !== 'log'">
      <a-table
        :dataSource="assetList"
        :columns="dynamicColumns"
        :loading="loading"
        :pagination="false"
        :row-selection="activeTab === 'web' ? { selectedRowKeys: selectedWebRowKeys, onChange: onWebSelectChange } : null"
        :scroll="{ x: 'max-content' }"
        :rowKey="(record) => record._id || record.id || record.domain || record.ym || Math.random()"
        size="small"
        bordered
        style="margin-bottom: 16px;"
      >
        <template #bodyCell="{ column, record, text, index }">
          <template v-if="column.key === 'index'">
            {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
          </template>
          <template v-else-if="column.key === 'icon'">
            <img v-if="text" :src="text" style="width:28px;height:28px;border-radius:4px;" />
          </template>
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="text">
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
                  <pre style="font-size: 11px;">{{ JSON.stringify(record, null, 2) }}</pre>
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

      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 8px;">
        <div style="color: var(--arl-text-color); opacity: 0.65; font-size: 12px;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
        <a-pagination
          :pageSizeOptions="['10', '20', '50', '100']"
          v-model:current="pagination.current"
          v-model:pageSize="pagination.pageSize"
          :total="pagination.total"
          size="small"
          show-size-changer
          @change="handlePaginationChange"
          @showSizeChange="handlePaginationChange"
        />
      </div>
    </div>

    <!-- 运行日志 Tab -->
    <div v-if="taskId && activeTab === 'log'">
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
        <div ref="terminalContainer" style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, monospace; padding: 14px; border-radius: 4px; height: 480px; overflow-y: auto; font-size: 12px; line-height: 1.6;">
          <div v-for="(log, idx) in syslogList" :key="idx" style="margin-bottom: 4px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 2px;">
            <span style="opacity: 0.7; margin-right: 8px;">[{{ log.create_time }}]</span>
            <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <span style="margin-right: 8px; color: #40a9ff;">[{{ log.title }}]</span>
            <span>{{ log.message }}</span>
          </div>
          <div v-if="syslogList.length === 0" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录... (历史任务或日志正在生成中)</div>
        </div>
      </div>
    </div>

    <!-- 同步至资产分组弹窗 -->
    <SyncToScopeModal
      v-model:open="syncModalVisible"
      :task="taskRecord"
      :preSelectedDomains="selectedWebDomains"
      @success="handleSyncSuccess"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import { SearchOutlined, DownloadOutlined, CloudSyncOutlined, SyncOutlined } from '@ant-design/icons-vue';
import request from '../utils/request';
import SyncToScopeModal from './SyncToScopeModal.vue';

const props = defineProps({
  taskId: {
    type: String,
    default: ''
  },
  scopeId: {
    type: String,
    default: ''
  },
  enterpriseName: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['synced', 'refreshed']);

const activeTab = ref('web');
const loading = ref(false);
const exportLoading = ref(false);
const refreshLoading = ref(false);
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const taskRecord = ref({});
const taskName = ref('');
const taskTarget = ref('');
const taskType = ref('icp');
const taskStatus = ref('');
const hasIncrement = ref(false);

const queryCounts = reactive({
  web: 0,
  app: 0,
  mapp: 0,
  wechat: 0,
  weibo: 0,
  kapp: 0,
  trademark: 0,
  invest: 0,
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
    stop: '已停止',
    error: '执行失败'
  };
  return map[taskStatus.value] || taskStatus.value;
});

const taskStatusColor = computed(() => {
  const map = {
    waiting: 'warning',
    running: 'processing',
    done: 'success',
    stop: 'default',
    error: 'error'
  };
  return map[taskStatus.value] || 'default';
});

const syncModalVisible = ref(false);
const selectedWebRowKeys = ref([]);
const selectedWebDomains = ref([]);

const onWebSelectChange = (keys, rows) => {
  selectedWebRowKeys.value = keys;
  const domains = [];
  rows.forEach(r => {
    const d = r.domain || r.ym;
    if (d && typeof d === 'string') domains.push(d.trim());
  });
  selectedWebDomains.value = domains;
};

const openSyncModalWithSelected = () => {
  syncModalVisible.value = true;
};

const handleSyncSuccess = (res) => {
  fetchTaskStatistic();
  emit('synced', res);
};

const handleRefreshTask = async () => {
  if (!props.taskId) return;
  refreshLoading.value = true;
  try {
    const res = await request.get(`/icp/restart/${props.taskId}`);
    if (res.code === 200) {
      message.success('已触发增量测绘任务');
      fetchTaskDetail();
      emit('refreshed');
    } else {
      message.error(res.message || '触发失败');
    }
  } catch (err) {
    message.error('网络请求失败');
  } finally {
    refreshLoading.value = false;
  }
};

const searchForm = reactive({});
const searchFormOp = reactive({});

const columnConfigs = {
  web: [
    { title: '序号', key: 'index', width: 60 },
    { title: '域名', dataIndex: 'domain', key: 'domain' },
    { title: '网站名称', dataIndex: 'serviceName', key: 'serviceName' },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName' },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence' },
    { title: '首页网址', dataIndex: 'homeUrl', key: 'homeUrl' },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 }
  ],
  app: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: 'APP名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    { title: '简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '当前版本', dataIndex: 'version', key: 'version' },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 }
  ],
  mapp: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '小程序名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' },
    { title: '描述', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 }
  ],
  wechat: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '公众号名称', dataIndex: 'name', key: 'name' },
    { title: '微信号', dataIndex: 'wechatId', key: 'wechatId' },
    { title: '功能介绍', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '认证主体', dataIndex: 'unitName', key: 'unitName' }
  ],
  weibo: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '微博昵称', dataIndex: 'name', key: 'name' },
    { title: '认证信息', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '粉丝数', dataIndex: 'fans', key: 'fans' }
  ],
  kapp: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '快应用名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'category' }
  ],
  trademark: [
    { title: '序号', key: 'index', width: 60 },
    { title: '商标图', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '商标名称', dataIndex: 'name', key: 'name' },
    { title: '注册号', dataIndex: 'regNo', key: 'regNo' },
    { title: '国际分类', dataIndex: 'category', key: 'category' },
    { title: '状态', dataIndex: 'status', key: 'status' },
    { title: '申请日期', dataIndex: 'appDate', key: 'appDate' }
  ],
  invest: [
    { title: '序号', key: 'index', width: 60 },
    { title: '被投资企业', dataIndex: 'name', key: 'name' },
    { title: '法定代表人', dataIndex: 'legalPerson', key: 'legalPerson' },
    { title: '投资比例', dataIndex: 'percent', key: 'percent' },
    { title: '投资数额', dataIndex: 'amount', key: 'amount' },
    { title: '企业状态', dataIndex: 'status', key: 'status' }
  ]
};

const dynamicColumns = computed(() => {
  return columnConfigs[activeTab.value] || columnConfigs.web;
});

const assetList = ref([]);
const syslogList = ref([]);

const fetchTaskDetail = async () => {
  if (!props.taskId) return;
  try {
    const res = await request.get(`/icp/task`, { params: { _id: props.taskId } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      const task = res.items[0];
      taskRecord.value = task;
      taskName.value = task.name || '';
      taskTarget.value = task.target || '';
      taskType.value = task.task_type || 'icp';
      taskStatus.value = task.status || '';
      hasIncrement.value = !!task.has_increment;
      const stats = task.statistic || {};
      queryCounts.web = stats.web_cnt || 0;
      queryCounts.app = stats.app_cnt || 0;
      queryCounts.mapp = stats.mapp_cnt || 0;
      queryCounts.wechat = stats.wechat_cnt || 0;
      queryCounts.weibo = stats.weibo_cnt || 0;
      queryCounts.kapp = stats.kapp_cnt || 0;
      queryCounts.trademark = stats.trademark_cnt || 0;
      queryCounts.invest = stats.invest_cnt || 0;
    }
  } catch (err) {
    console.error('获取任务详情失败', err);
  }
};

const fetchTaskStatistic = async () => {
  fetchTaskDetail();
};

const fetchAssets = async (page = 1, size = 10) => {
  if (!props.taskId || activeTab.value === 'log') return;
  loading.value = true;
  try {
    const params = {
      task_id: props.taskId,
      query_type: activeTab.value,
      page,
      size
    };
    for (const k in searchForm) {
      if (searchForm[k] !== undefined && searchForm[k] !== '') {
        params[k] = searchForm[k];
      }
    }
    const res = await request.get('/icp/asset', { params });
    if (res.code === 200) {
      assetList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
    }
  } catch (err) {
    console.error('获取资产列表失败', err);
  } finally {
    loading.value = false;
  }
};

const fetchLogs = async () => {
  if (!props.taskId) return;
  try {
    const res = await request.get(`/icp/task/log/${props.taskId}`);
    if (res.code === 200) {
      syslogList.value = res.items || [];
    }
  } catch (err) {
    console.error('获取日志失败', err);
  }
};

const onTabChange = (key) => {
  pagination.current = 1;
  selectedWebRowKeys.value = [];
  selectedWebDomains.value = [];
  if (key === 'log') {
    fetchLogs();
  } else {
    fetchAssets(1, pagination.pageSize);
  }
};

const onSearch = () => fetchAssets(1, pagination.pageSize);
const resetSearch = () => {
  for (const k in searchForm) {
    searchForm[k] = undefined;
  }
  onSearch();
};

const handlePaginationChange = (page, pageSize) => {
  fetchAssets(page, pageSize);
};

const handleExport = async () => {
  if (!props.taskId) return;
  exportLoading.value = true;
  try {
    const res = await request.get(`/icp/export/${props.taskId}`, {
      params: { query_type: activeTab.value },
      responseType: 'blob'
    });
    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${taskTarget.value || 'osint'}_${activeTab.value}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success('导出成功');
  } catch (err) {
    message.error('导出失败');
  } finally {
    exportLoading.value = false;
  }
};

watch(() => props.taskId, (newVal) => {
  if (newVal) {
    fetchTaskDetail();
    if (activeTab.value === 'log') {
      fetchLogs();
    } else {
      fetchAssets(pagination.current, pagination.pageSize);
    }
  }
}, { immediate: true });
</script>

<style scoped>
.enterprise-osint-panel :deep(.ant-tabs-nav) {
  margin-bottom: 12px;
}
</style>
