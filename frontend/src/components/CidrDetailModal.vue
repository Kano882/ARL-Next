<template>
  <a-modal :open="open" @update:open="$emit('update:open', $event)" :title="`C段详情：${currentCidrIp}`" :footer="null" width="700px">
    <a-table 
      :dataSource="cipDetailData" 
      :columns="cipDetailColumns" 
      :pagination="false" 
      size="small"
      :scroll="{ y: 400 }"
      :loading="cipDetailLoading"
      rowKey="ip"
    >
      <template #emptyText>
        <a-empty v-if="loadFailed"
                 description="C段详情加载失败，请关闭后重试">
          <a-button size="small" type="primary" @click="fetchDetail">重新加载</a-button>
        </a-empty>
        <a-empty v-else description="该 C 段暂无关联域名记录" />
      </template>
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'">
          {{ index + 1 }}
        </template>
        <template v-else-if="column.key === 'domains'">
          <div v-if="record.domains && record.domains.length > 0">
            <div v-for="(domain, idx) in record.domains" :key="idx" style="font-family: monospace;">
              {{ domain }}
            </div>
          </div>
          <span v-else style="color: #ccc;">-</span>
        </template>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup>
import { ref, watch } from 'vue';
import request from '../utils/request';
import { message } from 'ant-design-vue';

const props = defineProps({
  open: { type: Boolean, required: true },
  record: { type: Object, default: () => ({}) }
});

const emit = defineEmits(['update:open']);

const cipDetailLoading = ref(false);
const cipDetailData = ref([]);
const currentCidrIp = ref('');
const loadFailed = ref(false);

const cipDetailColumns = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 150 },
  { title: 'IP对应的域名', key: 'domains', width: 300 }
];

const fetchDetail = async () => {
  if (!props.record) return;
  cipDetailLoading.value = true;
  loadFailed.value = false;
  cipDetailData.value = [];
  try {
    const res = await request.get('/asset_cip/ip_domain_detail/', { params: { cidr_id: props.record._id || props.record.id } });
    if (res.code === 200) {
      cipDetailData.value = res.data?.items || res.items || [];
    } else {
      loadFailed.value = true;
      message.error(res.message || '获取C段详情失败');
    }
  } catch (error) {
    loadFailed.value = true;
    message.error('获取C段详情失败，请重试');
  } finally {
    cipDetailLoading.value = false;
  }
};

watch(() => props.open, (newVal) => {
  if (newVal && props.record) {
    currentCidrIp.value = props.record.cidr_ip || '-';
    fetchDetail();
  }
});
</script>
