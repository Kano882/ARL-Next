<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">

    <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
      <a-button type="primary" @click="showTycModal">新建企业资产查询</a-button>
      <a-button type="primary" @click="showModal">新建 ICP 查询</a-button>
    </div>

    <div class="search-row" style="margin-bottom: 16px; ">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
        <a-form-item label="任务名:">
          <a-input v-model:value="searchForm.name" placeholder="请输入任务名" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="查询目标:">
          <a-input v-model:value="searchForm.target" placeholder="请输入查询目标" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="状态:">
          <a-input v-model:value="searchForm.status" placeholder="请输入状态" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="结束时间:">
          <a-range-picker
            v-model:value="searchForm.dateRange"
            :presets="rangePresets"
            :placeholder="['开始日期', '结束日期']"
            format="YYYY-MM-DD"
            style="width: 250px;"
            allowClear
            @change="onSearch"
            @openChange="onOpenChange"
          />
        </a-form-item>
      </a-form>
    </div>

    <div style="margin-bottom: 16px;">
      <a-button style="margin-right: 16px;" @click="resetSearch">清 除</a-button>
      <a-popconfirm title="确定要批量重启选中的任务吗？" ok-text="确定" cancel-text="取消" @confirm="handleBatchRestart">
        <a-button :disabled="selectedRowKeys.length === 0" style="margin-right: 16px;">批量重启</a-button>
      </a-popconfirm>
      <a-popconfirm title="确定要批量删除选中的任务吗？" @confirm="handleBatchDelete">
        <a-button danger :disabled="selectedRowKeys.length === 0" style="margin-right: 16px;">批量删除</a-button>
      </a-popconfirm>
      <a-button type="primary" :disabled="selectedRowKeys.length === 0" @click="handleBatchExport">批量导出</a-button>
    </div>

    
    </div>
<a-table :sticky="stickyConfig"
        :dataSource="taskList"
        :columns="columns"
        :loading="loading"
        :pagination="false"
        :scroll="{ x: 'max-content' }"
        :rowSelection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :rowKey="(record) => record._id"
        bordered
        style="margin-bottom: 16px;"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a style="color: var(--arl-theme-color); font-weight: 500;" @click="viewTask(record)">{{ record.name }}</a>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'statistic'">
          <div v-if="record.statistic" style="display: flex; gap: 8px; flex-wrap: wrap;">
            <a-badge :count="(record.statistic.asset_cnt || 0) - (record.statistic.invest_cnt || 0)" title="核心资产" />
            <a-badge v-if="record.statistic.invest_cnt !== undefined" :count="record.statistic.invest_cnt" title="对外投资" :number-style="{ backgroundColor: '#52c41a' }" />
          </div>
        </template>
        <template v-else-if="column.key === 'sync_status'">
          <!-- 1. 无网站资产 -->
          <span v-if="record.sync_badge_status === 'no_web'" style="color: var(--arl-text-color); opacity: 0.35; font-size: 12px;">
            无网站资产
          </span>
          <!-- 2. 已同步 (可附带有增量标签) -->
          <div v-else-if="record.synced_scope_id" style="display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap;">
            <a-tag
              color="blue"
              style="cursor: pointer; display: inline-flex; align-items: center; gap: 4px; margin-right: 0;"
              @click="goToScope(record.synced_scope_id)"
              title="点击前往该资产分组"
            >
              <export-outlined />
              <span>{{ record.synced_scope_name || '已同步' }}</span>
            </a-tag>
            <a-badge v-if="record.has_increment" count="有增量" :number-style="{ backgroundColor: '#52c41a', fontSize: '10px' }" />
          </div>
          <!-- 3. 未同步 -->
          <span v-else style="color: #faad14; font-size: 12px; font-weight: 500;">
            ● 未同步
          </span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space size="small">
            <a-tooltip v-if="record.sync_badge_status === 'no_web'" title="当前任务无网站资产可同步">
              <a-button type="link" size="small" disabled>同步</a-button>
            </a-tooltip>
            <a-button
              v-else
              type="link"
              size="small"
              @click="handleSync(record)"
              :disabled="record.status !== 'done' && record.status !== 'stop'"
            >
              {{ record.synced_scope_id ? (record.has_increment ? '同步增量' : '再次同步') : '同步' }}
            </a-button>
            <a-button type="link" size="small" @click="handleExport(record)">导出</a-button>
            <a-button type="link" size="small" @click="handleStop(record)" :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'">停止</a-button>
            <a-button type="link" size="small" @click="handleRestart(record)" :disabled="record.status === 'running' || record.status === 'waiting'">重启</a-button>
            <a-popconfirm title="确定要删除该任务吗？" ok-text="确定" cancel-text="取消" @confirm="handleDelete(record)">
              <a-button type="link" danger size="small">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>
  </div>

  <a-modal
      v-model:open="visible"
      title="新建 ICP 查询"
      @ok="handleOk"
      :confirmLoading="submitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
  >
    <a-form
        ref="formRef"
        :model="formState"
        :label-col="{ style: { width: '90px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
    >
      <a-alert
        v-if="isDomainTarget && hasMobileQueryType"
        type="warning"
        show-icon
        style="margin-bottom: 16px;"
      >
        <template #message>
          <span>提示：工信部系统要求按<b>主办单位全称</b>（企业名称）检索 APP/小程序/快应用。当前目标为域名，将无法检索到移动端应用，建议输入企业全称（如：深圳市腾讯计算机系统有限公司）。</span>
        </template>
      </a-alert>

      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="formState.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="查询目标" name="target" :rules="[{ required: true, message: '请输入查询目标' }]">
        <a-input v-model:value="formState.target" placeholder="企业全称（如：深圳市腾讯计算机系统有限公司）或网站域名" />
      </a-form-item>

      <a-form-item label="查询类型" name="query_type" :rules="[{ required: true, message: '请至少选择一种查询类型' }]">
        <a-checkbox-group v-model:value="formState.query_type">
          <a-checkbox value="web">网站查询</a-checkbox>
          <a-checkbox value="app">APP查询</a-checkbox>
          <a-checkbox value="mapp">小程序查询</a-checkbox>
          <a-checkbox value="kapp">快应用查询</a-checkbox>
        </a-checkbox-group>
      </a-form-item>
    </a-form>
  </a-modal>

  <a-modal
      v-model:open="tycVisible"
      title="新建企业资产查询"
      @ok="handleTycOk"
      :confirmLoading="tycSubmitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
  >
    <a-form
        ref="tycFormRef"
        :model="tycFormState"
        :label-col="{ style: { width: '110px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 110px)' } }"
    >
      <a-alert
          v-if="!tycConfigCheck.valid && !tycConfigCheck.loading"
          type="warning"
          show-icon
          style="margin-bottom: 16px;"
      >
        <template #message>
          {{ tycConfigCheck.message || '未配置天眼查 ID 或 Token，请先完成配置。' }}
          <a @click="router.push({ path: '/systemSettings', query: { tab: 'api_config' } })" style="margin-left: 8px; font-weight: 500;">
            去配置 &rarr;
          </a>
        </template>
      </a-alert>
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="tycFormState.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item
        label="公司 ID"
        name="gid"
        :rules="[
          { required: true, message: '请输入天眼查公司 ID' },
          { pattern: /^[a-zA-Z0-9]+$/, message: '公司 ID 格式不正确，请输入纯数字/字母 ID' }
        ]"
        tooltip="可在天眼查详情页URL中获取，例如 https://www.tianyancha.com/company/25174642 中的 25174642"
      >
        <a-input v-model:value="tycFormState.gid" placeholder="请输入天眼查公司 ID（纯数字/字母，例如：25174642）" />
      </a-form-item>

      <a-form-item label="查询层数" name="depth" tooltip="1 表示查询当前目标企业自身资产，2 表示穿透其对外投资子公司，以此类推">
        <a-input-number v-model:value="tycFormState.depth" :min="1" :max="20" style="width: 100%;" />
      </a-form-item>

      <a-form-item label="最低投资比例" name="invest_ratio" tooltip="仅对对外投资生效，大于等于该比例才入库并递归。0或为空表示不限制；设置比例后，无持股比例数据的公司将自动丢弃">
        <a-input-number v-model:value="tycFormState.invest_ratio" addon-after="%" :min="0" :max="100" style="width: 100%;" placeholder="0 表示不限制" />
      </a-form-item>

      <a-form-item label="查询类型" name="query_type" :rules="[{ required: true, message: '请至少选择一种查询类型' }]">
        <a-checkbox-group v-model:value="tycFormState.query_type">
          <a-checkbox value="invest">对外投资</a-checkbox>
          <a-checkbox value="trademark">商标信息</a-checkbox>
          <a-checkbox value="web">备案网站</a-checkbox>
          <a-checkbox value="app">APP</a-checkbox>
          <a-checkbox value="mapp">小程序</a-checkbox>
          <a-checkbox value="wechat">微信公众号</a-checkbox>
          <a-checkbox value="weibo">微博</a-checkbox>
        </a-checkbox-group>
      </a-form-item>
    </a-form>
  </a-modal>

  <SyncToScopeModal
    v-model:open="syncModalVisible"
    :task="currentSyncTask"
    @success="handleSyncSuccess"
  />
</template>

<script setup>
defineOptions({ name: 'AssetRecon' });

import { ref, reactive, computed, onMounted, watch, onActivated } from 'vue';
import dayjs from 'dayjs';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { message, Modal } from 'ant-design-vue';
import { useRouter } from 'vue-router';
import { SearchOutlined, ExportOutlined } from '@ant-design/icons-vue';
import SyncToScopeModal from '../components/SyncToScopeModal.vue';
import request from '../utils/request';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const router = useRouter();
const taskList = ref([]);
const loading = ref(false);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const selectedRowKeys = ref([]);
const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};

const syncModalVisible = ref(false);
const currentSyncTask = ref(null);

const handleSync = (record) => {
  currentSyncTask.value = record;
  syncModalVisible.value = true;
};

const handleSyncSuccess = (result) => {
  if (currentSyncTask.value) {
    currentSyncTask.value.synced_scope_id = result.scope_id;
    currentSyncTask.value.synced_scope_name = result.target_name;
  }
  fetchTasks(pagination.current, pagination.pageSize, true);
};

const goToScope = (scopeId) => {
  if (scopeId) {
    router.push({ path: '/group', query: { scope_id: scopeId } });
  }
};

const rangePresets = ref([
  { label: '今天', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
  { label: '近 7 天', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: '近 30 天', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: '本月', value: [dayjs().startOf('month'), dayjs().endOf('month')] },
]);

const onOpenChange = (open) => {
  if (open) {
    rangePresets.value = [
      { label: '今天', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
      { label: '近 7 天', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
      { label: '近 30 天', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
      { label: '本月', value: [dayjs().startOf('month'), dayjs().endOf('month')] },
    ];
  }
};

const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 180 },
  { title: '查询目标', dataIndex: 'target', key: 'target', width: 220 },
  { title: '查询类型', dataIndex: 'query_type', key: 'query_type', width: 180 },
  { title: '资产数量', dataIndex: 'statistic', key: 'statistic', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '同步分组', key: 'sync_status', width: 150 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 160 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: '任务 ID', dataIndex: '_id', key: '_id', width: 220 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
];

const getStatusColor = (status) => {
  if (status === 'done') return 'success';
  if (status === 'error') return 'error';
  if (status === 'stop') return 'warning';
  if (status === 'waiting') return 'default';
  return 'processing';
};

const searchForm = reactive({ name: '', target: '', status: '', dateRange: null });

const fetchTasks = async (page = 1, size = 10, silent = false) => {
  if (!silent) {
    loading.value = true;
  }
  try {
    const queryParams = { page, size };
    if (searchForm.name) queryParams.name = searchForm.name;
    if (searchForm.target) queryParams.target = searchForm.target;
    if (searchForm.status) queryParams.status = searchForm.status;
    if (searchForm.dateRange && searchForm.dateRange.length === 2 && searchForm.dateRange[0] && searchForm.dateRange[1]) {
      queryParams.end_time__gte = dayjs(searchForm.dateRange[0]).startOf('day').format('YYYY-MM-DD HH:mm:ss');
      queryParams.end_time__lte = dayjs(searchForm.dateRange[1]).endOf('day').format('YYYY-MM-DD HH:mm:ss');
    }

    const res = await request.get('/icp/task', { params: queryParams });
    if (res.code === 200) {
      taskList.value = res.items || [];
      // 将返回的列表格式化展示，若是数组则逗号拼接
      taskList.value.forEach(item => {
        if (Array.isArray(item.query_type)) {
          item.query_type = item.query_type.join(', ');
        }
      });
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
    } else {
      console.error('获取列表失败:', res);
    }
  } catch (error) {
    console.error('API 请求失败:', error);
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
};

const onSearch = () => fetchTasks(1, pagination.pageSize);
const resetSearch = () => {
  searchForm.name = '';
  searchForm.target = '';
  searchForm.status = '';
  searchForm.dateRange = null;
  onSearch();
};
const handleTableChange = (page, pageSize) => fetchTasks(page, pageSize);

onMounted(() => fetchTasks(pagination.current, pagination.pageSize));

const visible = ref(false);
const submitLoading = ref(false);
const formRef = ref();

const formState = reactive({
  name: "",
  target: "",
  query_type: ["web"]
});

const isDomainTarget = computed(() => {
  let t = (formState.target || '').trim();
  if (!t) return false;
  // 清洗可能粘贴的协议前缀、端口与路径后缀
  t = t.replace(/^https?:\/\//i, '').split('/')[0].split(':')[0];
  if (/\s/.test(t)) return false; // 排除含有空格的英文公司名缩写（如 Apple Inc.）
  return /^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$/.test(t);
});

const hasMobileQueryType = computed(() => {
  const qt = formState.query_type || [];
  return qt.includes('app') || qt.includes('mapp') || qt.includes('kapp');
});

const showModal = () => { visible.value = true; };

const handleOk = async () => {
  try {
    await formRef.value.validate();
    if (isDomainTarget.value && hasMobileQueryType.value && !formState.query_type.includes('web')) {
      message.warning('检测到查询目标为域名，工信部移动端查询需输入企业全称');
      return;
    }
    submitLoading.value = true;
    const res = await request.post('/icp/task', formState);
    if (res.code === 200) {
      message.success('任务创建成功');
      visible.value = false;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    console.error(error);
  } finally {
    submitLoading.value = false;
  }
};

const tycVisible = ref(false);
const tycSubmitLoading = ref(false);
const tycFormRef = ref();

const tycFormState = reactive({
  name: "",
  gid: "",
  depth: 1,
  invest_ratio: 50,
  query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo']
});

const tycConfigCheck = reactive({
  loading: false,
  valid: true,
  message: ''
});

const showTycModal = async () => {
  tycVisible.value = true;
  // 重置表单状态，确保每次打开时恢复默认配置
  tycFormState.depth = 1;
  tycFormState.query_type = ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'];
  
  tycConfigCheck.loading = true;
  tycConfigCheck.valid = true;
  tycConfigCheck.message = '';
  try {
    const res = await request.get('/icp/tyc_check');
    if (res.code === 200) {
      tycConfigCheck.valid = res.data.valid;
      tycConfigCheck.message = res.data.message;
    }
  } catch (error) {
    console.error(error);
  } finally {
    tycConfigCheck.loading = false;
  }
};

const handleTycOk = async () => {
  try {
    await tycFormRef.value.validate();

    if (!tycConfigCheck.valid) {
      Modal.confirm({
        title: '天眼查配置无效',
        content: tycConfigCheck.message || '未配置天眼查 ID 或 Token，请先完成配置后再创建任务。',
        okText: '去配置',
        cancelText: '取消',
        onOk() {
          router.push({ path: '/systemSettings', query: { tab: 'api_config' } });
        }
      });
      return;
    }

    tycSubmitLoading.value = true;
    const res = await request.post('/icp/tyc_task', tycFormState);
    if (res.code === 200) {
      message.success('企业资产查询任务创建成功');
      tycVisible.value = false;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    console.error(error);
  } finally {
    tycSubmitLoading.value = false;
  }
};

const viewTask = (record) => {
  const stats = record.statistic || {};
  router.push({
    path: '/assetRecon/assetDetail',
    query: {
      task_id: record._id,
      name: record.name,
      target: record.target,
      task_type: record.task_type || 'icp',
      web_cnt: stats.web_cnt || 0,
      app_cnt: stats.app_cnt || 0,
      mapp_cnt: stats.mapp_cnt || 0,
      kapp_cnt: stats.kapp_cnt || 0,
      invest_cnt: stats.invest_cnt || 0,
      trademark_cnt: stats.trademark_cnt || 0,
      wechat_cnt: stats.wechat_cnt || 0,
      weibo_cnt: stats.weibo_cnt || 0,
    }
  });
};

const handleExport = async (record) => {
  try {
    message.loading({ content: '正在导出...', key: 'export', duration: 0 });
    const res = await request.get(`/icp/export/${record._id}`, { responseType: 'blob' });

    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${record.name || 'icp_export'}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success({ content: '导出成功', key: 'export', duration: 2 });
  } catch (error) {
    console.error('导出失败', error);
    message.error({ content: '导出失败', key: 'export', duration: 2 });
  }
};

const handleBatchExport = async () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先勾选需要导出的任务');
    return;
  }
  try {
    message.loading({ content: '正在批量导出...', key: 'batch_export', duration: 0 });
    const res = await request.post('/icp/batch_export', {
      task_id: selectedRowKeys.value
    }, { responseType: 'blob' });

    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `batch_icp_export.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success({ content: '批量导出成功', key: 'batch_export', duration: 2 });
  } catch (error) {
    console.error('批量导出失败', error);
    message.error({ content: '批量导出失败', key: 'batch_export', duration: 2 });
  }
};


const handleBatchDelete = async () => {
  if (!selectedRowKeys.value.length) return;
  try {
    message.loading({ content: '正在批量删除...', key: 'batchDelete', duration: 0 });
    const res = await request.post('/icp/delete/', { task_ids: selectedRowKeys.value });
    if (res.code === 200) {
      message.success({ content: '批量删除成功', key: 'batchDelete', duration: 2 });
      selectedRowKeys.value = [];
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error({ content: res.message || '批量删除失败', key: 'batchDelete', duration: 2 });
    }
  } catch (error) {
    console.error('批量删除失败', error);
    message.error({ content: '网络错误，批量删除失败', key: 'batchDelete', duration: 2 });
  }
};

const handleBatchRestart = async () => {
  if (!selectedRowKeys.value.length) return;
  try {
    message.loading({ content: '正在批量重启...', key: 'batchRestart', duration: 0 });
    const res = await request.post('/icp/restart/', { task_ids: selectedRowKeys.value });
    if (res.code === 200) {
      const data = res.data || {};
      const restarted = data.restarted_count ?? selectedRowKeys.value.length;
      const skipped = data.skipped_count || 0;

      let msg = `成功重启 ${restarted} 个任务`;
      if (skipped > 0) {
        msg += `（已自动跳过 ${skipped} 个运行中/等待中任务）`;
      }

      message.success({ content: msg, key: 'batchRestart', duration: 3 });
      selectedRowKeys.value = [];
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error({ content: res.message || '批量重启失败', key: 'batchRestart', duration: 3 });
    }
  } catch (error) {
    console.error('批量重启失败', error);
    message.error({ content: '网络错误，批量重启失败', key: 'batchRestart', duration: 3 });
  }
};

const handleStop = async (record) => {
  try {
    const res = await request.get(`/icp/stop/${record._id}`);
    if (res.code === 200) {
      message.success('已停止任务');
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(res.message || '停止失败');
    }
  } catch (error) {
    console.error('停止任务失败', error);
  }
};

const handleRestart = async (record) => {
  try {
    const res = await request.get(`/icp/restart/${record._id}`);
    if (res.code === 200) {
      message.success('已重启任务');
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(res.message || '重启失败');
    }
  } catch (error) {
    console.error('重启任务失败', error);
  }
};

const handleDelete = async (record) => {
  try {
    const res = await request.get(`/icp/delete/${record._id}`);
    if (res.code === 200) {
      message.success('删除成功');
      // 如果当前页只有一条且非第一页，删除后回到上一页
      if (taskList.value.length === 1 && pagination.current > 1) {
        pagination.current -= 1;
      }
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(res.message || '删除失败');
    }
  } catch (error) {
    console.error('删除任务失败', error);
  }
};

onActivated(() => {
  fetchTasks(pagination.current, pagination.pageSize, true);
});
</script>
