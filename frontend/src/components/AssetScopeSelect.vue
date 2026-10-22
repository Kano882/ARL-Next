<template>
  <a-select
    :value="value"
    :options="options"
    :loading="state.loading"
    :filter-option="false"
    :placeholder="taskText('tasks.selectAnAssetGroupOrSearchByName')"
    show-search
    allow-clear
    @change="onChange"
    @search="onSearch"
    @dropdownVisibleChange="onOpen"
    @popupScroll="onScroll"
  >
    <template #notFoundContent>
      <span class="asset-scope-empty">{{ state.loading ? taskText('tasks.loadingAssetGroups') : taskText('tasks.noAssetGroupsFound') }}</span>
    </template>
  </a-select>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { computed, reactive, ref, watch, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import request from '../utils/request';
import { createAssetScopeLoader } from '../utils/taskAssetGroups';

const { t: taskText } = useI18n({ useScope: 'global' });

const props = defineProps({ value: { type: String, default: undefined } });
const emit = defineEmits(['update:value']);
const selectedOption = ref(null);
const state = reactive({ search: '', page: 1, options: [], loading: false, hasMore: true });
const loader = createAssetScopeLoader(request, state, error => message.error(taskText('tasks.failedToLoadAssetGroupsReason', { reason: error.message })));
const options = computed(() => selectedOption.value && !state.options.some(item => item.value === selectedOption.value.value)
  ? [selectedOption.value, ...state.options] : state.options);
let searchTimer;
const onSearch = value => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loader.load(true, value), 250);
};
const onOpen = open => {
  if (open) {
    clearTimeout(searchTimer);
    loader.load(true, '');
  }
};
const onScroll = event => {
  const element = event.target;
  if (element.scrollTop + element.clientHeight >= element.scrollHeight - 24) loader.load();
};
const onChange = value => {
  selectedOption.value = state.options.find(item => item.value === value) || null;
  emit('update:value', value || undefined);
};
watch(() => props.value, async value => {
  if (!value) { selectedOption.value = null; return; }
  if (selectedOption.value?.value === value) return;
  const existing = state.options.find(item => item.value === value);
  if (existing) { selectedOption.value = existing; return; }
  try {
    const response = await request.get('/asset_scope/', { params: { _id: value, size: 1 } });
    if (props.value !== value) return;
    const item = response.items?.[0];
    selectedOption.value = { value, label: item?.name || value };
  } catch (error) {
    if (props.value === value) selectedOption.value = { value, label: value };
  }
}, { immediate: true });
onUnmounted(() => { clearTimeout(searchTimer); loader.dispose(); });
</script>

<style scoped>
.asset-scope-empty {
  color: var(--arl-text-secondary);
}
</style>
