<template>
  <a-select
    :value="selectedCodes"
    mode="multiple"
    :options="options"
    :max-tag-count="2"
    :placeholder="taskText('tasks.selectOneOrMoreStatusCodes')"
    show-search
    option-filter-prop="label"
    allow-clear
    style="width: 100%; min-width: 200px;"
    @change="onChange"
  />
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { computed } from 'vue';
import { normalizeHttpStatuses } from '../utils/assetFilters';

const { t: taskText } = useI18n({ useScope: 'global' });

const props = defineProps({ value: { type: [Array, String, Number], default: undefined } });
const emit = defineEmits(['update:value', 'change']);
const selectedCodes = computed(() => normalizeHttpStatuses(props.value));
const descriptionKeys = {
  200: 'tasks.ok', 201: 'tasks.created', 204: 'tasks.noContent', 301: 'tasks.movedPermanently',
  302: 'tasks.temporaryRedirect', 304: 'tasks.notModified', 400: 'tasks.badRequest', 401: 'tasks.unauthorized',
  403: 'tasks.forbidden', 404: 'tasks.notFound', 405: 'tasks.methodNotAllowed', 429: 'tasks.tooManyRequests',
  500: 'tasks.internalServerError', 502: 'tasks.badGateway', 503: 'tasks.serviceUnavailable', 504: 'tasks.gatewayTimeout'
};
const options = computed(() => Array.from({ length: 500 }, (_, index) => {
  const code = String(index + 100);
  return { value: code, label: descriptionKeys[code] ? `${code} ${taskText(descriptionKeys[code])}` : code };
}));
const onChange = value => {
  const codes = normalizeHttpStatuses(value);
  emit('update:value', codes);
  emit('change', codes);
};
</script>
