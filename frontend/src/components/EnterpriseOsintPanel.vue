<template>
  <div class="enterprise-osint-panel">
    <!-- 顶部摘要与操作栏 (仅当有任务且未隐藏 Header 时渲染) -->
    <div v-if="taskId && !hideHeader" style="margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span style="font-weight: 600; font-size: 15px; color: var(--arl-text-color);">{{ displayName }}</span>
          <a-tag v-if="taskTarget && taskTarget.startsWith('TYC_')" color="cyan">{{ taskTarget }}</a-tag>
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
    </div>

    <!-- 维度 Tabs 导航与搜索操作栏 (吸附在 Hero 顶栏正下方) -->
    <div
      v-if="taskId"
      ref="osintControlRef"
      class="osint-sticky-control-box"
      :style="{ top: (props.stickyTopOffset || 0) + 'px' }"
    >
      <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs osint-tabs-nav" :style="activeTab === 'log' ? 'margin-bottom: 0;' : 'margin-bottom: 12px;'" @change="onTabChange">
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
              <a-form-item
                v-if="col.key !== 'index' && col.key !== 'raw' && col.key !== 'icon' && col.key !== 'qrcode' && col.key !== 'examineDate' && col.key !== 'updateRecordTime' && col.key !== 'estiblishTime' && col.key !== 'href'"
                :label="col.title + ':'"
              >
                <a-input-group compact v-if="['amount', 'percent'].includes(col.dataIndex)">
                  <a-select v-model:value="searchFormOp[col.dataIndex]" style="width: 65px" :options="[{value:'eq',label:'='},{value:'gt',label:'>'},{value:'lt',label:'<'}]" />
                  <a-input v-model:value="searchForm[col.dataIndex]" style="width: 140px" :placeholder="'输入' + col.title" @pressEnter="onSearch">
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
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <a-button size="small" @click="resetSearch">重 置</a-button>
          <a-button size="small" type="primary" :loading="exportLoading" @click="handleExport">
            <template #icon><download-outlined /></template>
            导出当前维度表格
          </a-button>
          <a-button v-if="activeTab === 'web' && selectedWebRowKeys.length > 0" type="primary" ghost size="small" @click="openSyncModalWithSelected">
            <template #icon><cloud-sync-outlined /></template>
            同步勾选域名 ({{ selectedWebRowKeys.length }})
          </a-button>
        </div>
      </div>
    </div>

    <!-- 资产表格 -->
    <div v-if="taskId && activeTab !== 'log'">
      <a-table
        :sticky="osintStickyConfig"
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

          <!-- 图标/头像渲染 -->
          <template v-else-if="column.key === 'icon'">
            <a-avatar v-if="getAssetIcon(record)" :src="getAssetIcon(record)" shape="square" :size="32" style="background: #fafafa; border: 1px solid var(--arl-border-color);" />
            <span v-else style="color: #bfbfbf;">-</span>
          </template>

          <!-- 域名可点击外链与快捷复制 -->
          <template v-else-if="column.key === 'domain'">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
              <a v-if="record.domain || record.ym" :href="(record.domain || record.ym).startsWith('http') ? (record.domain || record.ym) : ('http://' + (record.domain || record.ym))" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
                {{ record.domain || record.ym }} <export-outlined style="font-size: 11px;" />
              </a>
              <span v-else>-</span>
              <a-tooltip title="复制域名" v-if="record.domain || record.ym">
                <a-button type="text" size="small" style="padding: 0 4px; height: 22px;" @click.stop="handleCopyText(record.domain || record.ym)">
                  <copy-outlined style="font-size: 12px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
          </template>

          <!-- 首页网址外链与快捷复制 -->
          <template v-else-if="column.key === 'homeUrl'">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
              <a v-if="getAssetHomeUrl(record)" :href="getAssetHomeUrl(record)" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
                {{ getAssetHomeUrl(record) }} <export-outlined style="font-size: 11px;" />
              </a>
              <span v-else>-</span>
              <a-tooltip title="复制网址" v-if="getAssetHomeUrl(record)">
                <a-button type="text" size="small" style="padding: 0 4px; height: 22px;" @click.stop="handleCopyText(getAssetHomeUrl(record))">
                  <copy-outlined style="font-size: 12px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
          </template>

          <!-- 微博主页外链 -->
          <template v-else-if="column.key === 'href'">
            <a v-if="record.href" :href="record.href" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color);">
              访问微博 <export-outlined style="font-size: 11px;" />
            </a>
            <span v-else>-</span>
          </template>

          <!-- 公众号二维码浮层预览 -->
          <template v-else-if="column.key === 'qrcode'">
            <a-popover v-if="record.codeImg" placement="right" trigger="hover">
              <template #content>
                <div style="text-align: center; padding: 4px;">
                  <img :src="record.codeImg" style="width: 150px; height: 150px; display: block;" />
                  <span style="font-size: 12px; color: #8c8c8c; margin-top: 4px; display: block;">微信扫码关注</span>
                </div>
              </template>
              <a-tag color="blue" style="cursor: pointer;"><qrcode-outlined /> 查看二维码</a-tag>
            </a-popover>
            <span v-else style="color: #bfbfbf;">-</span>
          </template>

          <!-- 企业状态 Tag 渲染 -->
          <template v-else-if="column.key === 'status'">
            <a-tag v-if="['存续', '在业', '正常'].includes(record.status || record.regStatus)" color="success">
              {{ record.status || record.regStatus }}
            </a-tag>
            <a-tag v-else-if="['注销', '吊销', '撤销', '迁出'].includes(record.status || record.regStatus)" color="error">
              {{ record.status || record.regStatus }}
            </a-tag>
            <a-tag v-else-if="record.status || record.regStatus">
              {{ record.status || record.regStatus }}
            </a-tag>
            <span v-else style="color: #bfbfbf;">-</span>
          </template>

          <!-- 地区展示 -->
          <template v-else-if="column.key === 'region'">
            {{ record.region || [record.province, record.city].filter(Boolean).join(' ') || '-' }}
          </template>

          <!-- 成立时间 -->
          <template v-else-if="column.key === 'estiblishTime'">
            {{ formatDate(record.estiblishTime) }}
          </template>

          <!-- 单位性质 -->
          <template v-else-if="column.key === 'companyType'">
            {{ record.companyType || record.natureName || '-' }}
          </template>

          <!-- 服务备案号/服务许可 -->
          <template v-else-if="column.key === 'serviceLicence'">
            {{ record.serviceLicence || record.liscense || record.serviceFilingNumber || record.mainLicence || '-' }}
          </template>

          <!-- 主办单位 -->
          <template v-else-if="column.key === 'unitName'">
            {{ record.unitName || record.companyName || record.miniProgramIcpRecordDetail?.icpFilingSubjectInformation?.organizingName || '-' }}
          </template>

          <!-- 名称字段多字段兼顾 -->
          <template v-else-if="column.key === 'serviceName' || column.key === 'name'">
            {{ record.serviceName || record.name || record.webName || record.title || record.tmName || '-' }}
          </template>

          <!-- 法定代表人 -->
          <template v-else-if="column.key === 'legalPerson'">
            {{ record.legalPerson || record.legalPersonName || '-' }}
          </template>

          <!-- 分类字段 -->
          <template v-else-if="column.key === 'category'">
            {{ record.category || record.classes || record.intCls || record.type || '-' }}
          </template>

          <!-- 微信号 -->
          <template v-else-if="column.key === 'wechatId'">
            {{ record.wechatId || record.publicNum || '-' }}
          </template>

          <!-- 更新/审核时间 -->
          <template v-else-if="column.key === 'updateRecordTime'">
            {{ record.updateRecordTime || record.examineDate || '-' }}
          </template>

          <!-- 简介/描述 -->
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="record.brief || record.recommend || record.info || text">
              {{ record.brief || record.recommend || record.info || text || '-' }}
            </div>
          </template>

          <!-- 原始 JSON 抽屉 -->
          <template v-else-if="column.key === 'raw'">
            <a-button type="link" size="small" style="padding: 0;" @click="openRawDrawer(record)">查看JSON</a-button>
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
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 12px; background-color: var(--arl-bg-light);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-weight: bold; font-size: 13px;">任务执行过程日志</span>
            <a-tag :color="taskRecord.status === 'running' ? 'processing' : taskRecord.status === 'done' ? 'success' : taskRecord.status === 'error' ? 'error' : 'default'">
              {{ taskRecord.status === 'running' ? '实时采集监控中...' : taskRecord.status === 'done' ? '测绘已完成' : taskRecord.status === 'error' ? '任务异常终止' : (taskRecord.status || '就绪') }}
            </a-tag>
            <span style="color: rgba(255,255,255,0.45); font-size: 12px;" v-if="taskRecord.status === 'running'">(每 3 秒自动轮询增量)</span>
          </div>
          <a-button size="small" :loading="logLoading" @click="() => fetchLogs(true)">
            <template #icon><SyncOutlined :spin="logLoading" /></template>
            刷新日志
          </a-button>
        </div>
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

    <!-- 原始数据 JSON 抽屉 -->
    <RawDataDrawer
      v-model:open="rawDrawerVisible"
      :data="currentRawRecord"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import {
  SearchOutlined,
  DownloadOutlined,
  CloudSyncOutlined,
  SyncOutlined,
  ExportOutlined,
  QrcodeOutlined,
  CopyOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';
import { copyText } from '../utils/clipboard';
import SyncToScopeModal from './SyncToScopeModal.vue';
import RawDataDrawer from './RawDataDrawer.vue';

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
  },
  hideHeader: {
    type: Boolean,
    default: false
  },
  stickyTopOffset: {
    type: Number,
    default: 120
  }
});

const osintControlRef = ref(null);
const osintControlHeight = ref(120);
const scrollContainer = ref(null);
let osintResizeObserver = null;

const updateOsintHeight = () => {
  if (osintControlRef.value && typeof osintControlRef.value.getBoundingClientRect === 'function') {
    const rect = osintControlRef.value.getBoundingClientRect();
    if (rect.height > 0) {
      osintControlHeight.value = Math.round(rect.height);
    }
  }
};

const totalOsintOffsetHeader = computed(() => {
  return (props.stickyTopOffset || 0) + osintControlHeight.value;
});

const osintStickyConfig = computed(() => {
  if (!scrollContainer.value) return false;
  return {
    offsetHeader: totalOsintOffsetHeader.value,
    offsetScroll: 0,
    getContainer: () => scrollContainer.value
  };
});

onMounted(() => {
  scrollContainer.value = document.querySelector('.ant-layout-content');
  osintResizeObserver = new ResizeObserver(updateOsintHeight);
  if (osintControlRef.value) {
    osintResizeObserver.observe(osintControlRef.value);
  }
  updateOsintHeight();
});

const emit = defineEmits(['synced', 'refreshed', 'taskLoaded']);

const rawDrawerVisible = ref(false);
const currentRawRecord = ref({});

const openRawDrawer = (record) => {
  currentRawRecord.value = record;
  rawDrawerVisible.value = true;
};

const handleCopyText = async (text) => {
  const ok = await copyText(text);
  if (ok) message.success('已复制: ' + text);
};

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

const displayName = computed(() => {
  return props.enterpriseName || (taskName.value && !taskName.value.includes('TYC_') ? taskName.value : '') || (taskTarget.value && !taskTarget.value.startsWith('TYC_') ? taskTarget.value : '') || taskName.value || '企业资产画像';
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
    { title: '域名', dataIndex: 'domain', key: 'domain', width: 160 },
    { title: '网站名称', dataIndex: 'serviceName', key: 'serviceName', ellipsis: true },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '单位性质', dataIndex: 'companyType', key: 'companyType', width: 100 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { title: '首页网址', dataIndex: 'homeUrl', key: 'homeUrl', ellipsis: true },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 130 },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  app: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: 'APP名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 160 },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '版本', dataIndex: 'version', key: 'version', width: 90 },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 130 },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  mapp: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '小程序名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
    { title: '描述', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 130 },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  wechat: [
    { title: '序号', key: 'index', width: 60 },
    { title: '头像', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '公众号名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '微信号', dataIndex: 'wechatId', key: 'wechatId', width: 140 },
    { title: '二维码', key: 'qrcode', width: 100 },
    { title: '功能介绍', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '认证主体', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  weibo: [
    { title: '序号', key: 'index', width: 60 },
    { title: '头像', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '微博昵称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '认证信息/简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '微博主页', key: 'href', width: 160 },
    { title: '粉丝数', dataIndex: 'fans', key: 'fans', width: 100 },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  kapp: [
    { title: '序号', key: 'index', width: 60 },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '快应用名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 130 },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  trademark: [
    { title: '序号', key: 'index', width: 60 },
    { title: '商标图', dataIndex: 'icon', key: 'icon', width: 70 },
    { title: '商标名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '注册号', dataIndex: 'regNo', key: 'regNo', width: 140 },
    { title: '国际分类', dataIndex: 'category', key: 'category', width: 110 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
    { title: '申请日期', dataIndex: 'appDate', key: 'appDate', width: 130 },
    { title: '原始数据', key: 'raw', width: 90 }
  ],
  invest: [
    { title: '序号', key: 'index', width: 60 },
    { title: '被投资企业', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '法定代表人', dataIndex: 'legalPerson', key: 'legalPerson', width: 110 },
    { title: '投资比例', dataIndex: 'percent', key: 'percent', width: 100 },
    { title: '投资数额', dataIndex: 'amount', key: 'amount', width: 140 },
    { title: '企业状态', dataIndex: 'status', key: 'status', width: 100 },
    { title: '地区', key: 'region', width: 130 },
    { title: '成立日期', key: 'estiblishTime', width: 120 },
    { title: '原始数据', key: 'raw', width: 90 }
  ]
};

const dynamicColumns = computed(() => {
  return columnConfigs[activeTab.value] || columnConfigs.web;
});

const assetList = ref([]);
const syslogList = ref([]);
const terminalContainer = ref(null);
const logLoading = ref(false);
let logTimer = null;

const getAssetIcon = (record) => {
  return record.icon || record.titleImgURL || record.codeImg || record.ico || record.productLogo || record.tmPic || '';
};

const getAssetHomeUrl = (record) => {
  if (record.homeUrl) return record.homeUrl;
  if (record.webSite) {
    if (Array.isArray(record.webSite) && record.webSite.length > 0) return record.webSite[0];
    if (typeof record.webSite === 'string') return record.webSite;
  }
  return '';
};

const formatDate = (val) => {
  if (!val) return '-';
  if (typeof val === 'number') {
    const d = new Date(val);
    if (!isNaN(d.getTime())) {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
  }
  return String(val);
};

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

      if (task.status === 'done' || task.status === 'error') {
        stopLogPolling();
      }

      emit('taskLoaded', {
        task,
        taskName: taskName.value,
        taskTarget: taskTarget.value,
        taskType: taskType.value,
        taskTypeLabel: taskTypeLabel.value,
        taskStatus: taskStatus.value,
        taskStatusLabel: taskStatusLabel.value,
        taskStatusColor: taskStatusColor.value,
        hasIncrement: hasIncrement.value,
        queryCounts: { ...queryCounts },
        totalCount: Object.values(queryCounts).reduce((a, b) => a + (Number(b) || 0), 0)
      });
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
        if (searchFormOp[k]) {
          params[`${k}_op`] = searchFormOp[k];
        }
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

const fetchLogs = async (isManual = false) => {
  if (!props.taskId) return;
  if (isManual) logLoading.value = true;
  try {
    let items = [];
    try {
      const res = await request.get(`/icp/task/log/${props.taskId}`);
      if (res && res.code === 200 && Array.isArray(res.items)) {
        items = res.items;
      }
    } catch (e) {
      console.warn('Fallback to /syslog for task logs', e);
      const res = await request.get('/syslog/', {
        params: { task_id: props.taskId, size: 500, order: 'create_time' }
      });
      if (res && res.code === 200 && Array.isArray(res.items)) {
        items = res.items;
      }
    }

    items.sort((a, b) => (a.create_time || '').localeCompare(b.create_time || ''));
    syslogList.value = items;

    await nextTick();
    if (terminalContainer.value) {
      terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
    }
  } catch (err) {
    console.error('获取日志失败', err);
  } finally {
    if (isManual) logLoading.value = false;
  }
};

const startLogPolling = () => {
  stopLogPolling();
  if (activeTab.value === 'log' && (taskRecord.value.status === 'running' || taskRecord.value.status === 'waiting')) {
    logTimer = setInterval(() => {
      fetchLogs(false);
      fetchTaskDetail();
    }, 3000);
  }
};

const stopLogPolling = () => {
  if (logTimer) {
    clearInterval(logTimer);
    logTimer = null;
  }
};

onUnmounted(() => {
  stopLogPolling();
  if (osintResizeObserver) osintResizeObserver.disconnect();
});

const onTabChange = (key) => {
  pagination.current = 1;
  selectedWebRowKeys.value = [];
  selectedWebDomains.value = [];
  nextTick(() => { updateOsintHeight(); });
  if (key === 'log') {
    fetchLogs(true);
    startLogPolling();
  } else {
    stopLogPolling();
    fetchAssets(1, pagination.pageSize);
  }
};

const onSearch = () => fetchAssets(1, pagination.pageSize);
const resetSearch = () => {
  for (const k in searchForm) {
    searchForm[k] = undefined;
  }
  for (const k in searchFormOp) {
    searchFormOp[k] = undefined;
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
    link.setAttribute('download', `${displayName.value || taskTarget.value || 'osint'}_${activeTab.value}.xlsx`);
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
      fetchLogs(true);
      startLogPolling();
    } else {
      stopLogPolling();
      fetchAssets(pagination.current, pagination.pageSize);
    }
  }
}, { immediate: true });

defineExpose({
  handleRefreshTask,
  refreshLoading,
  queryCounts,
  taskRecord,
  fetchTaskDetail
});
</script>

<style scoped>
.osint-sticky-control-box {
  position: sticky;
  z-index: 11;
  background: var(--arl-bg-white);
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  padding: 14px 16px 12px 16px;
  margin-bottom: 16px;
  transition: box-shadow 0.2s ease;
}

.osint-tabs-nav :deep(.ant-tabs-nav) {
  margin-bottom: 0 !important;
}

.enterprise-osint-panel :deep(.ant-tabs-nav) {
  margin-bottom: 12px;
}
</style>
