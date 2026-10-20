<template>
  <a-drawer
    :open="open"
    :title="assetText('assets.rawDataJson')"
    placement="right"
    :width="drawerWidth"
    destroyOnClose
    @close="handleClose"
  >
    <template #extra>
      <a-button type="primary" size="small" @click="handleCopy">
        <template #icon><copy-outlined /></template>
        {{ assetText('assets.copyJson') }}
      </a-button>
    </template>

    <div class="raw-drawer-container">
      <div class="raw-meta-bar">
        <span class="raw-tip">{{ assetText('assets.formattedJsonPreviewBrowseDataFields') }}</span>
        <a-tag color="blue">{{ assetText('assets.jsonPropertyCount', { count: Object.keys(data || {}).length }) }}</a-tag>
      </div>
      <div class="json-code-block">
        <pre><code>{{ formattedJson }}</code></pre>
      </div>
    </div>
  </a-drawer>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { computed } from 'vue';
import { message } from 'ant-design-vue';
import { CopyOutlined } from '@ant-design/icons-vue';
import { copyText } from '../utils/clipboard';

const { t: assetText } = useI18n({ useScope: 'global' });

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  data: {
    type: Object,
    default: () => ({})
  }
});

const emit = defineEmits(['update:open']);

const drawerWidth = computed(() => {
  return window.innerWidth > 900 ? '580px' : '90vw';
});

const formattedJson = computed(() => {
  try {
    return JSON.stringify(props.data || {}, null, 2);
  } catch (e) {
    return String(props.data);
  }
});

const handleCopy = async () => {
  const ok = await copyText(formattedJson.value);
  if (ok) message.success(assetText('assets.rawJsonCopiedToClipboard'));
};

const handleClose = () => {
  emit('update:open', false);
};
</script>

<style scoped>
.raw-drawer-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.raw-meta-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.json-code-block {
  flex: 1;
  background-color: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  padding: 16px;
  overflow: auto;
  font-family: 'Fira Code', Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.2);
}

.json-code-block pre {
  margin: 0;
}
</style>
