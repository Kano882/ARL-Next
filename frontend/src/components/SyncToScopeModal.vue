<template>
  <a-modal
    :open="open"
    @update:open="val => $emit('update:open', val)"
    :title="step === 'form' ? '同步资产至资产分组' : '资产同步完成'"
    wrapClassName="arl-theme-modal"
    width="680px"
    :destroyOnClose="true"
    :footer="null"
  >
    <!-- 步骤 1：同步配置与域名预检表单 -->
    <a-spin :spinning="modalDataLoading || syncLoading" :tip="syncLoading ? '正在同步数据与下发任务...' : '正在加载资产组及预检数据...'">
      <div v-if="step === 'form'">
        <a-form :label-col="{ style: { width: '100px' } }" :wrapper-col="{ style: { width: 'calc(100% - 100px)' } }">
          
          <a-form-item label="所属集团">
            <a-select
              v-model:value="syncFormState.group_id"
              placeholder="请选择所属集团（可选）"
              allowClear
              show-search
              option-filter-prop="label"
              @change="onGroupChange"
            >
              <a-select-option v-for="g in groupList" :key="g._id" :value="g._id" :label="g.name">
                {{ g.name }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="同步方式">
            <a-radio-group v-model:value="syncFormState.mode" @change="onSyncScopeChange">
              <a-radio value="existing">关联已有资产组</a-radio>
              <a-radio value="new">新建资产组</a-radio>
            </a-radio-group>
          </a-form-item>

          <a-form-item v-if="syncFormState.mode === 'existing'" label="选择资产组" :rules="[{ required: true, message: '请选择资产组' }]">
            <a-select
              v-model:value="syncFormState.scope_id"
              placeholder="请选择资产组"
              show-search
              option-filter-prop="label"
              @change="onSyncScopeChange"
            >
              <a-select-option
                v-for="scope in filteredScopes"
                :key="scope._id"
                :value="scope._id"
                :label="scope.name"
              >
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ scope.name }}</span>
                  <span v-if="scope.group_name" style="font-size: 11px; color: var(--arl-text-color); opacity: 0.55; margin-left: 8px;">
                    [{{ scope.group_name }}]
                  </span>
                </div>
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item v-if="syncFormState.mode === 'new'" label="资产组名称" :rules="[{ required: true, message: '请输入资产组名称' }]">
            <a-input v-model:value="syncFormState.target_name" placeholder="请输入资产组名称" @input="onSyncScopeChange" />
          </a-form-item>

          <!-- 增量预检摘要与穿透面板 -->
          <div style="margin: 0 16px 16px 16px; border: 1px solid var(--arl-border-color); border-radius: 6px; overflow: hidden; background: var(--arl-bg-light, rgba(0,0,0,0.02));">
            <div style="padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;">
              <div style="font-size: 13px;">
                本次任务共包含 <b>{{ diffStats.totalCount }}</b> 个网站域名：
                <span style="color: #1890ff; font-weight: bold;">{{ diffStats.newCount }} 个全新</span>，
                <span style="color: #8c8c8c;">{{ diffStats.duplicateCount }} 个已存在</span>。
                <span style="margin-left: 8px; color: #52c41a;">(已勾选 {{ selectedDomainKeys.length }}/{{ diffStats.totalCount }})</span>
              </div>
              <a-button type="link" size="small" style="padding: 0;" @click="isDomainPanelExpanded = !isDomainPanelExpanded">
                {{ isDomainPanelExpanded ? '收起域名明细 ▲' : '展开挑选明细 ▼' }}
              </a-button>
            </div>

            <!-- 展开的域名明细与快速过滤面板 -->
            <div v-show="isDomainPanelExpanded" style="border-top: 1px solid var(--arl-border-color); padding: 10px 14px; background: var(--arl-bg-white);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; flex-wrap: wrap;">
                <a-radio-group v-model:value="domainFilterTab" size="small" button-style="solid">
                  <a-radio-button value="all">全部 ({{ diffStats.totalCount }})</a-radio-button>
                  <a-radio-button value="new">全新 ({{ diffStats.newCount }})</a-radio-button>
                  <a-radio-button value="duplicate">已存在 ({{ diffStats.duplicateCount }})</a-radio-button>
                </a-radio-group>
                <div style="display: flex; gap: 6px; align-items: center;">
                  <a-input
                    v-model:value="domainSearchKey"
                    placeholder="过滤域名..."
                    size="small"
                    style="width: 140px;"
                    allowClear
                  />
                  <a-button size="small" @click="selectAllDomains">全选</a-button>
                  <a-button size="small" @click="selectOnlyNewDomains">仅选全新</a-button>
                  <a-button size="small" @click="unselectAllDomains">清空</a-button>
                </div>
              </div>

              <!-- 域名勾选列表 -->
              <div style="max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; padding-right: 4px;">
                <div
                  v-for="d in displayedDomainList"
                  :key="d.domain"
                  style="display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; border-radius: 4px; background: var(--arl-bg-light, #fafafa); font-size: 12px; font-family: monospace;"
                >
                  <a-checkbox
                    :checked="selectedDomainKeys.includes(d.domain)"
                    @change="e => toggleDomainSelect(d.domain, e.target.checked)"
                  >
                    <span>{{ d.domain }}</span>
                  </a-checkbox>
                  <a-tag v-if="d.isNew" color="blue" size="small" style="margin-right: 0;">全新</a-tag>
                  <a-tag v-else color="default" size="small" style="margin-right: 0;">已存在</a-tag>
                </div>
                <div v-if="displayedDomainList.length === 0" style="text-align: center; color: #bfbfbf; padding: 16px 0; font-size: 12px;">
                  未找到匹配的域名
                </div>
              </div>
            </div>
          </div>

          <a-divider style="margin: 12px 0 16px 0;" dashed />

          <a-form-item label="任务下发">
            <a-checkbox v-model:checked="syncFormState.auto_scan">
              立即对新发现域名发起自动化探测任务
            </a-checkbox>
          </a-form-item>

          <template v-if="syncFormState.auto_scan">
            <a-form-item label="任务类型">
              <a-radio-group v-model:value="syncFormState.task_type">
                <a-radio value="oneshot">一次性扫描 (立刻深度探测并入库)</a-radio>
                <a-radio value="periodic">周期性监控 (定时自动化巡航)</a-radio>
              </a-radio-group>
            </a-form-item>

            <a-form-item label="扫描策略" :rules="[{ required: true, message: '请选择扫描策略' }]">
              <a-select
                v-model:value="syncFormState.policy_id"
                placeholder="请选择扫描策略"
                :options="policyList.map(p => ({ value: p._id, label: p.name }))"
              />
            </a-form-item>

            <a-form-item v-if="syncFormState.task_type === 'periodic'" label="运行间隔">
              <a-input-number
                v-model:value="syncFormState.interval_hours"
                :min="6"
                :max="720"
                style="width: 160px;"
                addon-after="小时"
              />
            </a-form-item>
          </template>

          <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px;">
            <a-button @click="$emit('update:open', false)">取 消</a-button>
            <a-button type="primary" :loading="syncLoading" :disabled="modalDataLoading || selectedDomainKeys.length === 0" @click="submitSync">
              同 步 ({{ selectedDomainKeys.length }}项)
            </a-button>
          </div>
        </a-form>
      </div>

      <!-- 步骤 2：同步结果看板 -->
      <div v-else-if="step === 'result'" style="padding: 12px 16px 4px 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
          <div style="font-size: 40px; margin-bottom: 8px;">🎉</div>
          <div style="font-size: 18px; font-weight: 600;">资产同步完成</div>
          <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65; margin-top: 4px;">
            企业资产查询数据已成功写入资产分组与探测调度管线
          </div>
        </div>

        <div style="background: var(--arl-bg-light, rgba(0,0,0,0.02)); border: 1px solid var(--arl-border-color); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 14px;">
            <span style="color: var(--arl-text-color); opacity: 0.75;">目标归属:</span>
            <span style="font-weight: 600;">
              <span v-if="syncResult.group_name" style="color: var(--arl-theme-color);">{{ syncResult.group_name }} / </span>
              <span>{{ syncResult.target_name }}</span>
            </span>
          </div>

          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; text-align: center;">
            <div style="padding: 12px 8px; background: var(--arl-bg-white); border-radius: 6px; border: 1px solid var(--arl-border-color);">
              <div style="font-size: 20px; font-weight: bold; color: #1890ff;">+{{ syncResult.insert_count || 0 }}</div>
              <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.65; margin-top: 4px;">新增入库域名</div>
            </div>
            <div style="padding: 12px 8px; background: var(--arl-bg-white); border-radius: 6px; border: 1px solid var(--arl-border-color);">
              <div style="font-size: 20px; font-weight: bold; color: #8c8c8c;">{{ syncResult.duplicate_count || 0 }}</div>
              <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.65; margin-top: 4px;">跳过重复域名</div>
            </div>
            <div style="padding: 12px 8px; background: var(--arl-bg-white); border-radius: 6px; border: 1px solid var(--arl-border-color);">
              <div style="font-size: 20px; font-weight: bold; color: #52c41a;">{{ syncResult.task_triggered_count || 0 }}</div>
              <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.65; margin-top: 4px;">下发探测任务</div>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px;">
          <a-button @click="handleStayHere">留在当前页</a-button>
          <a-button type="primary" @click="handleGoToScope">
            立即前往资产分组查看 &rarr;
          </a-button>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { message } from 'ant-design-vue';
import request from '../utils/request';

const props = defineProps({
  open: { type: Boolean, required: true },
  task: { type: Object, default: () => ({}) },
  preSelectedDomains: { type: Array, default: () => [] }
});

const emit = defineEmits(['update:open', 'success']);
const router = useRouter();

const step = ref('form'); // 'form' | 'result'
const modalDataLoading = ref(false);
const syncLoading = ref(false);

const groupList = ref([]);
const assetScopes = ref([]);
const policyList = ref([]);
const allTaskWebDomains = ref([]);
const selectedDomainKeys = ref([]);

const isDomainPanelExpanded = ref(false);
const domainFilterTab = ref('all'); // 'all' | 'new' | 'duplicate'
const domainSearchKey = ref('');

const syncFormState = reactive({
  group_id: undefined,
  mode: 'existing',
  scope_id: undefined,
  target_name: '',
  auto_scan: false,
  task_type: 'oneshot',
  policy_id: undefined,
  interval_hours: 24
});

const syncResult = reactive({
  scope_id: '',
  target_name: '',
  group_name: '',
  insert_count: 0,
  duplicate_count: 0,
  task_triggered_count: 0
});

// 根据选择的集团过滤资产组
const filteredScopes = computed(() => {
  if (!syncFormState.group_id) {
    return assetScopes.value;
  }
  return assetScopes.value.filter(s => s.group_id === syncFormState.group_id);
});

// 当切换集团时联动校验资产组
const onGroupChange = () => {
  if (syncFormState.mode === 'existing') {
    if (syncFormState.scope_id) {
      const match = filteredScopes.value.find(s => s._id === syncFormState.scope_id);
      if (!match) {
        syncFormState.scope_id = filteredScopes.value.length > 0 ? filteredScopes.value[0]._id : undefined;
      }
    } else if (filteredScopes.value.length > 0) {
      syncFormState.scope_id = filteredScopes.value[0]._id;
    }
  }
  calculateDiff();
};

// 当前目标资产组已有域名集合
const currentTargetScopeDomains = computed(() => {
  if (syncFormState.mode === 'existing') {
    if (!syncFormState.scope_id) return new Set();
    const scope = assetScopes.value.find(s => s._id === syncFormState.scope_id);
    const list = scope?.domain_array || scope?.scope_array || [];
    return new Set(list.map(d => String(d).trim().toLowerCase()));
  } else {
    // 新建模式，若同名则比对
    const scope = assetScopes.value.find(s => s.name === syncFormState.target_name?.trim());
    if (scope) {
      const list = scope?.domain_array || scope?.scope_array || [];
      return new Set(list.map(d => String(d).trim().toLowerCase()));
    }
    return new Set();
  }
});

// 增量差异统计
const diffStats = computed(() => {
  const existingSet = currentTargetScopeDomains.value;
  const total = allTaskWebDomains.value.length;
  let dupCount = 0;
  let newCount = 0;
  for (const d of allTaskWebDomains.value) {
    if (existingSet.has(d.toLowerCase())) {
      dupCount++;
    } else {
      newCount++;
    }
  }
  return {
    totalCount: total,
    duplicateCount: dupCount,
    newCount: newCount
  };
});

// 域名明细列表与状态标记
const processedDomainList = computed(() => {
  const existingSet = currentTargetScopeDomains.value;
  return allTaskWebDomains.value.map(domain => {
    const isNew = !existingSet.has(domain.toLowerCase());
    return {
      domain,
      isNew
    };
  });
});

// 过滤后的域名展示列表
const displayedDomainList = computed(() => {
  return processedDomainList.value.filter(item => {
    if (domainFilterTab.value === 'new' && !item.isNew) return false;
    if (domainFilterTab.value === 'duplicate' && item.isNew) return false;
    if (domainSearchKey.value.trim()) {
      return item.domain.toLowerCase().includes(domainSearchKey.value.trim().toLowerCase());
    }
    return true;
  });
});

const calculateDiff = () => {
  // 触发响应式重算
};

const onSyncScopeChange = () => {
  calculateDiff();
};

const toggleDomainSelect = (domain, checked) => {
  if (checked) {
    if (!selectedDomainKeys.value.includes(domain)) {
      selectedDomainKeys.value.push(domain);
    }
  } else {
    selectedDomainKeys.value = selectedDomainKeys.value.filter(d => d !== domain);
  }
};

const selectAllDomains = () => {
  selectedDomainKeys.value = allTaskWebDomains.value.slice();
};

const selectOnlyNewDomains = () => {
  selectedDomainKeys.value = processedDomainList.value.filter(d => d.isNew).map(d => d.domain);
};

const unselectAllDomains = () => {
  selectedDomainKeys.value = [];
};

// 监听弹窗打开状态，初始化加载数据
watch(() => props.open, async (newVal) => {
  if (newVal && props.task && props.task._id) {
    step.value = 'form';
    modalDataLoading.value = true;
    isDomainPanelExpanded.value = false;
    domainFilterTab.value = 'all';
    domainSearchKey.value = '';

    syncFormState.group_id = undefined;
    syncFormState.mode = 'existing';
    syncFormState.scope_id = props.task.synced_scope_id || undefined;
    syncFormState.target_name = props.task.name || props.task.target || '';
    syncFormState.auto_scan = false;
    syncFormState.task_type = 'oneshot';
    syncFormState.interval_hours = 24;

    try {
      const [groupRes, scopeRes, policyRes, assetRes] = await Promise.all([
        request.get('/asset_group/', { params: { size: 1000 } }),
        request.get('/asset_scope/', { params: { size: 1000 } }),
        policyList.value.length === 0 ? request.get('/policy/', { params: { size: 1000 } }) : Promise.resolve({ code: 200, items: policyList.value }),
        request.get('/icp/asset', { params: { task_id: props.task._id, query_type: 'web', size: 10000 } })
      ]);

      if (groupRes.code === 200) {
        groupList.value = groupRes.items || groupRes.data?.items || [];
      }
      if (scopeRes.code === 200) {
        assetScopes.value = scopeRes.items || scopeRes.data?.items || [];
      }
      if (policyRes.code === 200 && policyRes.items) {
        policyList.value = policyRes.items || [];
        if (!syncFormState.policy_id && policyList.value.length > 0) {
          syncFormState.policy_id = policyList.value[0]._id;
        }
      }

      // 处理任务域名
      if (assetRes.code === 200) {
        const items = assetRes.items || assetRes.data?.items || [];
        const domainSet = new Set();
        items.forEach(item => {
          const d = item.domain || item.ym;
          if (d && typeof d === 'string') {
            domainSet.add(d.trim());
          }
        });
        allTaskWebDomains.value = Array.from(domainSet);
      }

      // 如果外部传入了预选域名，优先使用
      if (props.preSelectedDomains && props.preSelectedDomains.length > 0) {
        selectedDomainKeys.value = props.preSelectedDomains.slice();
      } else {
        selectedDomainKeys.value = allTaskWebDomains.value.slice();
      }

      // 若已有同步资产组，自动反查所属集团
      if (syncFormState.scope_id) {
        const matchedScope = assetScopes.value.find(s => s._id === syncFormState.scope_id);
        if (matchedScope && matchedScope.group_id) {
          syncFormState.group_id = matchedScope.group_id;
        }
      }
    } catch (error) {
      console.error('加载同步弹窗数据失败', error);
      message.error('加载资产组数据失败');
    } finally {
      modalDataLoading.value = false;
    }
  }
});

const submitSync = async () => {
  if (syncFormState.mode === 'existing' && !syncFormState.scope_id) {
    message.error('请选择关联的资产组');
    return;
  }
  if (syncFormState.mode === 'new' && !syncFormState.target_name.trim()) {
    message.error('请输入资产组名称');
    return;
  }
  if (selectedDomainKeys.value.length === 0) {
    message.error('请至少勾选一个待同步域名');
    return;
  }
  if (syncFormState.auto_scan && !syncFormState.policy_id) {
    message.error('请选择扫描策略');
    return;
  }

  try {
    syncLoading.value = true;
    const payload = {
      mode: syncFormState.mode,
      target_name: syncFormState.target_name.trim(),
      scope_id: syncFormState.scope_id,
      group_id: syncFormState.group_id,
      selected_domains: selectedDomainKeys.value,
      auto_scan: syncFormState.auto_scan,
      task_type: syncFormState.task_type,
      policy_id: syncFormState.policy_id,
      interval_hours: syncFormState.interval_hours
    };

    const res = await request.post(`/icp/sync/${props.task._id}`, payload);
    if (res.code === 200) {
      const data = res.data || res;
      syncResult.scope_id = data.scope_id || payload.scope_id;
      syncResult.target_name = data.target_name || payload.target_name;
      syncResult.group_name = data.group_name || '';
      syncResult.insert_count = data.insert_count || 0;
      syncResult.duplicate_count = data.duplicate_count || 0;
      syncResult.task_triggered_count = data.task_triggered_count || 0;

      // 原位切换为结果看板
      step.value = 'result';
      emit('success', syncResult);
    } else {
      message.error(res.message || '同步失败');
    }
  } catch (error) {
    console.error('同步失败', error);
    message.error('网络异常，同步失败');
  } finally {
    syncLoading.value = false;
  }
};

const handleStayHere = () => {
  emit('update:open', false);
};

const handleGoToScope = () => {
  emit('update:open', false);
  if (syncResult.scope_id) {
    router.push({
      path: '/group',
      query: { scope_id: syncResult.scope_id }
    });
  } else {
    router.push('/group');
  }
};
</script>

<style scoped>
</style>
