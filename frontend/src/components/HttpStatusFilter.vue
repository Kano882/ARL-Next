<template>
  <a-select
    :value="selectedCodes"
    mode="multiple"
    :options="options"
    :max-tag-count="2"
    placeholder="请选择状态码，可多选"
    show-search
    option-filter-prop="label"
    allow-clear
    style="width: 100%; min-width: 200px;"
    @change="onChange"
  />
</template>

<script setup>
import { computed } from 'vue';
import { normalizeHttpStatuses } from '../utils/assetFilters';

const props = defineProps({ value: { type: [Array, String, Number], default: undefined } });
const emit = defineEmits(['update:value', 'change']);
const selectedCodes = computed(() => normalizeHttpStatuses(props.value));
const descriptions = {
  200: '成功', 201: '已创建', 204: '无内容', 301: '永久重定向',
  302: '临时重定向', 304: '未修改', 400: '请求错误', 401: '未认证',
  403: '禁止访问', 404: '未找到', 405: '方法不允许', 429: '请求过多',
  500: '服务器错误', 502: '网关错误', 503: '服务不可用', 504: '网关超时'
};
const options = Array.from({ length: 500 }, (_, index) => {
  const code = String(index + 100);
  return { value: code, label: descriptions[code] ? `${code} ${descriptions[code]}` : code };
});
const onChange = value => {
  const codes = normalizeHttpStatuses(value);
  emit('update:value', codes);
  emit('change', codes);
};
</script>
