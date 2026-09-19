<template>
  <a-modal
    :open="open"
    @update:open="val => $emit('update:open', val)"
    title="新建 ICP 查询"
    @ok="handleOk"
    :confirmLoading="submitLoading"
    width="540px"
    wrapClassName="arl-theme-modal"
    okText="确 定"
    cancelText="取 消"
    destroyOnClose
  >
    <a-form
      ref="formRef"
      :model="formState"
      :label-col="{ style: { width: '90px' } }"
      :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
    >
      <a-alert
        v-if="isDomainTarget && hasMobileQueryType"
        message="工信部移动端资产（APP、小程序、快应用）仅支持以企业主体名称检索。目标为域名时将只执行网站备案查询。"
        type="info"
        show-icon
        style="margin-bottom: 16px;"
      />
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="formState.name" placeholder="请输入任务名称" />
      </a-form-item>
      <a-form-item label="查询目标" name="target" :rules="[{ required: true, message: '请输入企业名称或根域名' }]">
        <a-input v-model:value="formState.target" placeholder="企业全称（如：腾讯科技）或 根域名（如：qq.com）" />
      </a-form-item>
      <a-form-item label="查询类型" name="query_type">
        <a-checkbox-group v-model:value="formState.query_type">
          <a-checkbox value="web">网站备案</a-checkbox>
          <a-checkbox value="app" :disabled="isDomainTarget">APP</a-checkbox>
          <a-checkbox value="mapp" :disabled="isDomainTarget">小程序</a-checkbox>
          <a-checkbox value="kapp" :disabled="isDomainTarget">快应用</a-checkbox>
        </a-checkbox-group>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { message } from 'ant-design-vue';
import request from '../utils/request';

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:open', 'success']);

const formRef = ref();
const submitLoading = ref(false);
const formState = reactive({
  name: '',
  target: '',
  query_type: ['web']
});

const isDomainTarget = computed(() => {
  let t = (formState.target || '').trim();
  if (!t) return false;
  t = t.replace(/^https?:\/\//i, '').split('/')[0].split(':')[0];
  if (/\s/.test(t)) return false;
  return /^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$/.test(t);
});

const hasMobileQueryType = computed(() => {
  const qt = formState.query_type || [];
  return qt.includes('app') || qt.includes('mapp') || qt.includes('kapp');
});

watch(() => props.open, (val) => {
  if (val) {
    formState.name = '';
    formState.target = '';
    formState.query_type = ['web'];
  }
});

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
      message.success('ICP 测绘任务创建成功');
      emit('update:open', false);
      emit('success', res);
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    console.error(error);
  } finally {
    submitLoading.value = false;
  }
};
</script>
