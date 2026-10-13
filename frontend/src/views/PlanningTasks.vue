<template>
  <div class="arl-page-container">
    <div ref="actionBarRef" class="arl-hero-card">
      <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" style="margin-bottom: 12px;" @change="onTabChange">
        <a-tab-pane key="planning" tab="扫描计划任务"></a-tab-pane>
        <a-tab-pane key="monitor" tab="资产持续监控"></a-tab-pane>
      </a-tabs>

      <!-- 扫描计划任务 操作栏 -->
      <template v-if="activeTab === 'planning'">
        <div class="arl-toolbar-row">
          <!-- 左侧：紧凑搜索条件 -->
          <div class="arl-filter-group">
            <div class="arl-filter-item">
              <span class="arl-filter-label">任务名称：</span>
              <a-input v-model:value="searchForm.name" placeholder="请输入任务名称" style="width: 140px;" allowClear size="small" @pressEnter="onPlanSearch">
                <template #suffix><search-outlined @click="onPlanSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">目标：</span>
              <a-input v-model:value="searchForm.target" placeholder="请输入目标" style="width: 140px;" allowClear size="small" @pressEnter="onPlanSearch">
                <template #suffix><search-outlined @click="onPlanSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">策略：</span>
              <a-input v-model:value="searchForm.policy_name" placeholder="请输入策略" style="width: 130px;" allowClear size="small" @pressEnter="onPlanSearch">
                <template #suffix><search-outlined @click="onPlanSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">计划类型：</span>
              <a-select v-model:value="searchForm.schedule_type" placeholder="全部类型" style="width: 110px;" allowClear size="small" @change="onPlanSearch">
                <a-select-option value="future_scan">定时任务</a-select-option>
                <a-select-option value="recurrent_scan">周期任务</a-select-option>
              </a-select>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">状态：</span>
              <a-select v-model:value="searchForm.schedule_status" placeholder="全部状态" style="width: 110px;" allowClear size="small" @change="onPlanSearch">
                <a-select-option value="done">done</a-select-option>
                <a-select-option value="scheduled">scheduled</a-select-option>
                <a-select-option value="stop">stop</a-select-option>
                <a-select-option value="error">error</a-select-option>
              </a-select>
            </div>

            <a-button size="small" @click="resetPlanSearch">
              <template #icon><undo-outlined /></template>
              重置
            </a-button>
          </div>

          <!-- 右侧：单一主要操作 + 批量动作 -->
          <div class="arl-actions-group">
            <a-button type="primary" size="small" @click="openAddModal">
              <template #icon><plus-outlined /></template>
              添加计划任务
            </a-button>

            <a-popconfirm title="确认停止所选计划任务吗？" ok-text="确认" cancel-text="取消" @confirm="handleBatchStop">
              <a-button size="small" :disabled="!hasPlanSelected">
                <template #icon><pause-circle-outlined /></template>
                批量停止
              </a-button>
            </a-popconfirm>

            <a-popconfirm title="确认删除所选计划任务吗？" ok-text="确认" cancel-text="取消" @confirm="handleBatchDelete">
              <a-button danger size="small" :disabled="!hasPlanSelected">
                <template #icon><delete-outlined /></template>
                批量删除
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </template>

      <!-- 资产持续监控 操作栏 -->
      <template v-else-if="activeTab === 'monitor'">
        <div class="arl-toolbar-row">
          <!-- 左侧：检索条件 -->
          <div class="arl-filter-group">
            <div class="arl-filter-item">
              <span class="arl-filter-label">名称：</span>
              <a-input v-model:value="monitorSearchForm.name" placeholder="请输入名称" style="width: 160px;" allowClear size="small" @pressEnter="onMonitorSearch">
                <template #suffix><search-outlined @click="onMonitorSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">域名：</span>
              <a-input v-model:value="monitorSearchForm.domain" placeholder="请输入域名" style="width: 160px;" allowClear size="small" @pressEnter="onMonitorSearch">
                <template #suffix><search-outlined @click="onMonitorSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">资产范围ID：</span>
              <a-input v-model:value="monitorSearchForm.scope_id" placeholder="请输入范围ID" style="width: 160px;" allowClear size="small" @pressEnter="onMonitorSearch">
                <template #suffix><search-outlined @click="onMonitorSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>

            <a-button size="small" @click="resetMonitorSearch">
              <template #icon><undo-outlined /></template>
              重置
            </a-button>
          </div>

          <!-- 右侧：批量动作 -->
          <div class="arl-actions-group">
            <a-button size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('run')">
              <template #icon><send-outlined /></template>
              批量下发
            </a-button>
            <a-button size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('recover')">
              <template #icon><play-circle-outlined /></template>
              批量恢复
            </a-button>
            <a-button size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('stop')">
              <template #icon><pause-circle-outlined /></template>
              批量停止
            </a-button>
            <a-button danger size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('delete')">
              <template #icon><delete-outlined /></template>
              批量删除
            </a-button>
          </div>
        </div>
      </template>

    </div>

    <!-- 扫描计划任务 表格 -->
    <template v-if="activeTab === 'planning'">
      <a-table :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: planSelectedRowKeys, onChange: onPlanSelectChange, preserveSelectedRowKeys: true }"
          :loading="loading"
          :dataSource="dataSource"
          :columns="columns"
          :pagination="false"
          size="small"
          :rowKey="(record) => record._id"
      >
        <template #emptyText>
          <div style="padding: 40px 0;">
            <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
            <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无数据</div>
          </div>
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'schedule_type'">
            {{ record.schedule_type === 'future_scan' ? '定时任务' : '周期任务' }}
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag
                :color="
                record.status === 'scheduled' ? 'blue' :
                record.status === 'stop' ? 'warning' :
                record.status === 'error' ? 'error' :
                'success'
              "
            >
              {{ record.status }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'time_config'">
            {{ record.schedule_type === 'future_scan' ? record.start_date : record.cron }}
          </template>

          <template v-else-if="column.key === 'action'">
            <div style="display: flex; gap: 6px;">
              <a-button
                  size="small"
                  :disabled="record.status === 'stop'"
                  @click="handleSingleAction('stop', record._id)"
              >停止</a-button>

              <a-popconfirm title="确认删除？" @confirm="handleSingleAction('delete', record._id)">
                <a-button size="small" danger>删除</a-button>
              </a-popconfirm>

              <a-button
                  size="small"
                  :disabled="record.status === 'scheduled'"
                  @click="handleSingleAction('recover', record._id)"
              >恢复</a-button>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="pagination.current"
          v-model:pageSize="pagination.pageSize"
          :total="pagination.total"
          show-size-changer
          size="small"
          @change="handlePlanTableChange"
          @showSizeChange="handlePlanTableChange"
        />
      </div>
    </template>

    <!-- 资产持续监控 表格 -->
    <template v-else-if="activeTab === 'monitor'">
      <a-table :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: monitorSelectedRowKeys, onChange: onMonitorSelectChange, preserveSelectedRowKeys: true }"
          :loading="monitorLoading"
          :dataSource="monitorDataSource"
          :columns="monitorColumns"
          :pagination="false"
          size="small"
          :rowKey="(record) => record._id"
      >
        <template #emptyText>
          <div style="padding: 40px 0;">
            <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
            <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无数据</div>
          </div>
        </template>

        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            {{ (monitorPagination.current - 1) * monitorPagination.pageSize + index + 1 }}
          </template>

          <template v-if="column.key === 'scope_id'">
            <a
                style="cursor: pointer;"
                @click="goToAssetScope(record.scope_id)"
            >
              {{ record.scope_id }}
            </a>
          </template>

          <template v-else-if="column.key === 'interval'">
            <span>{{ formatInterval(record.interval) }}</span>
          </template>

          <template v-else-if="column.key === 'run_number'">
            <a style="cursor: pointer;">{{ record.run_number }}</a>
          </template>

          <template v-else-if="column.key === 'action'">
            <div style="display: flex; gap: 6px;">
              <a-button size="small" :disabled="record.status === 'stop'" @click="handleMonitorSingleAction('stop', record)">暂停</a-button>
              <a-button size="small" :disabled="record.status !== 'stop'" @click="handleMonitorSingleAction('resume', record)">恢复</a-button>
              <a-button size="small" @click="handleMonitorSingleAction('run', record)">立即下发任务</a-button>
              <a-button size="small" danger @click="handleMonitorSingleAction('delete', record)">删除</a-button>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">共 {{ Math.ceil(monitorPagination.total / monitorPagination.pageSize) || 1 }} 页 / {{ monitorPagination.total }} 条数据</div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="monitorPagination.current"
          v-model:pageSize="monitorPagination.pageSize"
          :total="monitorPagination.total"
          show-size-changer
          size="small"
          @change="handleMonitorTableChange"
          @showSizeChange="handleMonitorTableChange"
        />
      </div>
    </template>

    <a-modal
        v-model:open="addModalVisible"
        title="添加计划任务"
        @ok="submitAdd"
        :confirmLoading="addLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="addForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="名称" required>
          <a-input v-model:value="addForm.name" placeholder="请输入名称" />
        </a-form-item>
        <a-form-item label="目标" required>
          <a-textarea v-model:value="addForm.target" :rows="3" placeholder="请输入目标" />
        </a-form-item>

        <a-form-item label="计划类型" required>
          <a-select v-model:value="addForm.schedule_type" @change="onScheduleTypeChange">
            <a-select-option value="future_scan">定时任务</a-select-option>
            <a-select-option value="recurrent_scan">周期任务</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="策略" required>
          <a-select v-model:value="addForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policyList" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item v-if="addForm.schedule_type === 'future_scan'" label="开始时间" required>
          <a-date-picker
              v-model:value="addForm.start_date"
              show-time
              valueFormat="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
              placeholder="请选择开始日期"
          />
        </a-form-item>

        <a-form-item v-if="addForm.schedule_type === 'recurrent_scan'" label="Cron" required>
          <a-input v-model:value="addForm.cron" placeholder="请输入Cron，如 0 0 */1 * *" />
        </a-form-item>

        <a-form-item label="任务类别" required>
          <a-select v-model:value="addForm.task_tag" placeholder="请选择任务类别">
            <a-select-option value="task">资产侦查任务</a-select-option>
            <a-select-option value="risk_cruising">风险巡航任务</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
defineOptions({ name: 'PlanningTasks' });

import { ref, reactive, onMounted, onDeactivated, computed, watch, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSticky } from '../utils/useSticky';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined, ExclamationCircleOutlined, PlusOutlined, DeleteOutlined, UndoOutlined, PauseCircleOutlined, PlayCircleOutlined, SendOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const route = useRoute();
const router = useRouter();

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

const activeTab = ref(route.query.tab === 'monitor' ? 'monitor' : 'planning');

const onTabChange = (key) => {
  router.replace({
    query: { ...route.query, tab: key }
  });
  if (key === 'monitor' && monitorDataSource.value.length === 0) {
    fetchMonitorData();
  } else if (key === 'planning' && dataSource.value.length === 0) {
    fetchPlanData();
  }
};

watch(() => route.query.tab, (newTab) => {
  if (newTab === 'monitor' && activeTab.value !== 'monitor') {
    activeTab.value = 'monitor';
    if (monitorDataSource.value.length === 0) {
      fetchMonitorData();
    }
  } else if (newTab === 'planning' && activeTab.value !== 'planning') {
    activeTab.value = 'planning';
    if (dataSource.value.length === 0) {
      fetchPlanData();
    }
  }
});

// ================= 全局分页共享 =================
const globalPageSize = useGlobalPageSize(10);

// ==========================================
// 1. 扫描计划任务逻辑
// ==========================================
const loading = ref(false);
const dataSource = ref([]);
const policyList = ref([]);
const searchForm = reactive({ name: '', target: '', policy_name: '', schedule_type: undefined, schedule_status: undefined });
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const planSelectedRowKeys = ref([]);
const hasPlanSelected = computed(() => planSelectedRowKeys.value.length > 0);
const onPlanSelectChange = (keys) => { planSelectedRowKeys.value = keys; };

const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 150 },
  { title: '目标', dataIndex: 'target', key: 'target', width: 150 },
  { title: '类型', dataIndex: 'schedule_type', key: 'schedule_type', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '策略', dataIndex: 'policy_name', key: 'policy_name', width: 120 },
  { title: '时间配置', key: 'time_config', width: 180 },
  { title: '上次运行时间', dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { title: '下次运行时间', dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { title: '运行次数', dataIndex: 'run_number', key: 'run_number', width: 100 },
  { title: '操作', key: 'action', width: 200 }
];

const fetchPlanData = async () => {
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    if (searchForm.name) params.name = searchForm.name;
    if (searchForm.target) params.target = searchForm.target;
    if (searchForm.policy_name) params.policy_name = searchForm.policy_name;
    if (searchForm.schedule_type) params.schedule_type = searchForm.schedule_type;
    if (searchForm.schedule_status) params.schedule_status = searchForm.schedule_status;

    const res = await request.get('/task_schedule/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      planSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载计划任务失败');
  } finally {
    loading.value = false;
  }
};

const fetchPolicyList = async () => {
  const res = await request.get('/policy/', { params: { size: 1000, order: '-update_date' } });
  if (res.code === 200) policyList.value = res.items || [];
};

const resetPlanSearch = () => {
  Object.assign(searchForm, { name: '', target: '', policy_name: '', schedule_type: undefined, schedule_status: undefined });
  pagination.current = 1;
  onPlanSearch();
};

const onPlanSearch = () => { pagination.current = 1; fetchPlanData(); };
const handlePlanTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchPlanData(); };

// 添加计划任务弹窗
const addModalVisible = ref(false);
const addLoading = ref(false);
const addForm = reactive({
  name: '', target: '', schedule_type: 'future_scan',
  policy_id: undefined, task_tag: undefined,
  start_date: '', cron: ''
});

const openAddModal = () => {
  Object.assign(addForm, {
    name: '', target: '', schedule_type: 'future_scan',
    policy_id: undefined, task_tag: undefined, start_date: '', cron: ''
  });
  addModalVisible.value = true;
};

const onScheduleTypeChange = () => {
  addForm.start_date = '';
  addForm.cron = '';
};

const submitAdd = async () => {
  if (!addForm.name || !addForm.target || !addForm.policy_id || !addForm.task_tag) {
    return message.warning('请填写所有必填项！');
  }

  const payload = {
    name: addForm.name,
    target: addForm.target,
    schedule_type: addForm.schedule_type,
    policy_id: addForm.policy_id,
    task_tag: addForm.task_tag
  };

  if (addForm.schedule_type === 'future_scan') {
    if (!addForm.start_date) return message.warning('请选择开始时间！');
    payload.start_date = addForm.start_date;
  } else {
    if (!addForm.cron) return message.warning('请输入Cron表达式！');
    payload.cron = addForm.cron;
  }

  addLoading.value = true;
  try {
    const res = await request.post('/task_schedule/', payload);
    if (res.code === 200) {
      message.success('计划任务创建成功！');
      addModalVisible.value = false;
      onPlanSearch();
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    message.error('请求异常，创建失败');
  } finally {
    addLoading.value = false;
  }
};

const performPlanAction = async (actionType, idArray) => {
  try {
    const url = `/task_schedule/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success('操作成功！');
      fetchPlanData();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (e) {
    message.error('请求异常');
  }
};

const handleSingleAction = (type, id) => performPlanAction(type, [id]);
const handleBatchStop = () => performPlanAction('stop', planSelectedRowKeys.value);
const handleBatchDelete = () => performPlanAction('delete', planSelectedRowKeys.value);


// ==========================================
// 2. 资产持续监控逻辑
// ==========================================
const monitorLoading = ref(false);
const monitorDataSource = ref([]);
const monitorSearchForm = ref({});
const monitorPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const monitorSelectedRowKeys = ref([]);
const hasMonitorSelected = computed(() => monitorSelectedRowKeys.value.length > 0);
const onMonitorSelectChange = (keys) => { monitorSelectedRowKeys.value = keys; };

const monitorColumns = [
  { title: '序号', key: 'index', width: 80, align: 'center' },
  { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
  { title: '域名', dataIndex: 'domain', key: 'domain', width: 180 },
  { title: '资产范围ID', key: 'scope_id', width: 220 },
  { title: '运行间隔', key: 'interval', width: 120 },
  { title: '上一次运行日期', dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { title: '下一次运行日期', dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { title: '运行次数', key: 'run_number', width: 100, align: 'center' },
  { title: '操作', key: 'action', width: 260 }
];

const goToAssetScope = (id) => {
  if (!id) return;
  router.push({
    path: '/group',
    query: { scope_id: id }
  });
};

const formatInterval = (seconds) => {
  if (!seconds) return '-';
  if (seconds >= 3600 && seconds % 3600 === 0) return `${seconds / 3600} 小时`;
  if (seconds >= 60 && seconds % 60 === 0) return `${seconds / 60} 分钟`;
  return `${seconds} 秒`;
};

const fetchMonitorData = async () => {
  monitorLoading.value = true;
  try {
    const params = { page: monitorPagination.current, size: monitorPagination.pageSize };
    for (const key in monitorSearchForm.value) {
      if (monitorSearchForm.value[key]) params[key] = monitorSearchForm.value[key];
    }
    const res = await request.get('/scheduler/', { params });
    if (res.code === 200) {
      monitorDataSource.value = res.items || [];
      monitorPagination.total = res.total || 0;
      monitorSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载资产监控数据失败');
  } finally {
    monitorLoading.value = false;
  }
};

const resetMonitorSearch = () => {
  monitorSearchForm.value = {};
  monitorPagination.current = 1;
  onMonitorSearch();
};

const onMonitorSearch = () => { monitorPagination.current = 1; fetchMonitorData(); };
const handleMonitorTableChange = (page, pageSize) => { monitorPagination.current = page; monitorPagination.pageSize = pageSize; fetchMonitorData(); };

const monitorApiMap = {
  delete: '/scheduler/delete/',
  stop: '/scheduler/stop/',
  resume: '/scheduler/recover/',
  run: '/scheduler/run/'
};

const executeMonitorAction = async (actionType, ids) => {
  const url = monitorApiMap[actionType];
  if (!url) return;

  try {
    let payload = {};
    if (actionType === 'delete') {
      payload = { scheduler_id: ids };
    } else {
      payload = { scheduler_id: ids[0] };
    }
    const res = await request.post(url, payload);
    if (res.code === 200) {
      message.success('操作成功！');
      fetchMonitorData();
    } else {
      message.error('操作失败: ' + res.message);
    }
  } catch (error) {
    message.error('网络请求异常');
  }
};

const handleMonitorSingleAction = (actionType, record) => {
  const actionName = actionType === 'delete' ? '删除' : actionType === 'stop' ? '暂停' : actionType === 'resume' ? '恢复' : '下发';
  if (actionType === 'delete' || actionType === 'run') {
    Modal.confirm({
      title: actionType === 'delete' ? '删除监控任务确认' : '下发监控任务确认',
      icon: createVNode(ExclamationCircleOutlined, actionType === 'delete' ? { style: 'color: #ff4d4f;' } : undefined),
      content: actionType === 'delete'
        ? `确认删除监控任务 [${record.name}] 吗？删除后该任务的调度配置将一并移除，不可恢复。`
        : `确认立即下发监控任务 [${record.name}] 吗？任务将进入调度队列，由执行引擎按序取用。`,
      okText: actionType === 'delete' ? '确认删除' : '确 定',
      okButtonProps: actionType === 'delete' ? { danger: true } : undefined,
      cancelText: '取 消',
      onOk: () => executeMonitorAction(actionType, [record._id])
    });
  } else {
    executeMonitorAction(actionType, [record._id]);
  }
};

const handleMonitorBatchAction = (action) => {
  const actionMap = {
    delete:  { title: '批量删除', text: '删除', url: '/scheduler/delete/', type: 'danger' },
    stop:    { title: '批量停止', text: '停止', url: '/scheduler/stop/batch', type: 'danger' },
    recover: { title: '批量恢复', text: '恢复', url: '/scheduler/recover/batch', type: 'primary' },
    run:     { title: '批量下发', text: '下发', url: '/scheduler/run/batch', type: 'primary' }
  };

  const current = actionMap[action];
  if (!current) return;

  Modal.confirm({
    title: `${current.title}确认`,
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要对选中的 ${monitorSelectedRowKeys.value.length} 个任务执行【${current.text}】操作吗？`,
    okText: '确 定',
    okType: current.type,
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.post(current.url, {
          scheduler_id: monitorSelectedRowKeys.value
        });

        if (res.code === 200) {
          message.success(`批量${current.text}成功！`);
          if (action === 'delete' && monitorDataSource.value.length === monitorSelectedRowKeys.value.length && monitorPagination.current > 1) {
            monitorPagination.current -= 1;
          }
          monitorSelectedRowKeys.value = [];
          fetchMonitorData();
        } else {
          message.error(`${current.text}失败: ` + res.message);
        }
      } catch (error) {
        message.error(`请求异常，${current.text}失败`);
      }
    }
  });
};

// ================= 监听与生命周期 =================
watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});
watch(() => monitorPagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});
watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
  monitorPagination.pageSize = newSize;
});

onMounted(() => {
  if (activeTab.value === 'monitor') {
    fetchMonitorData();
  } else {
    fetchPlanData();
  }
  fetchPolicyList();
});

onDeactivated(() => {
  addModalVisible.value = false;
});
</script>