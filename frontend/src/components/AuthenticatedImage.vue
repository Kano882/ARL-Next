<template>
  <a-image v-if="objectUrl" v-bind="$attrs" :src="objectUrl" :preview="preview" @click="emit('preview', objectUrl)" />
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { fetchAuthenticatedBlob } from '../utils/authenticatedFiles';

defineOptions({ inheritAttrs: false });
const props = defineProps({ src: { type: String, default: '' }, preview: { type: Boolean, default: true } });
const emit = defineEmits(['preview']);
const objectUrl = ref('');
let controller;

const release = () => {
  controller?.abort();
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value);
  objectUrl.value = '';
};

watch(() => props.src, async (src) => {
  release();
  if (!src) return;
  const current = new AbortController();
  controller = current;
  try {
    const blob = await fetchAuthenticatedBlob(src, { signal: current.signal });
    if (!current.signal.aborted && blob.type.startsWith('image/')) {
      objectUrl.value = URL.createObjectURL(blob);
    }
  } catch {
    // Missing/revoked screenshots remain hidden; never retry without credentials.
  }
}, { immediate: true });

onBeforeUnmount(release);
</script>
