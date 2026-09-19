<template>
  <a-modal
    :open="open"
    @update:open="val => $emit('update:open', val)"
    title="新建企业资产查询 (天眼查)"
    @ok="handleTycOk"
    :confirmLoading="tycSubmitLoading"
    width="560px"
    wrapClassName="arl-theme-modal"
    okText="确 定"
    cancelText="取 消"
    destroyOnClose
  >
    <a-spin :spinning="tycConfigCheck.loading" tip="正在校验天眼查配置...">
      <a-alert
        v-if="!tycConfigCheck.valid && !tycConfigCheck.loading"
        type="error"
        show-icon
        style="margin-bottom: 16px;"
        :message="tycConfigCheck.message || '系统未检测到天眼查配置，请先在系统设置中配置后再发起任务。'"
      />
      <a-form
        ref="tycFormRef"
        :model="tycFormState"
        :label-col="{ style: { width: '90px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
      >
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
        <a-form-item label="投资层级" name="depth">
          <a-input-number v-model:value="tycFormState.depth" :min="1" :max="3" style="width: 120px;" addon-after="层" />
        </a-form-item>
        <a-form-item label="投资比例" name="invest_ratio">
          <a-input-number v-model:value="tycFormState.invest_ratio" :min="1" :max="100" style="width: 120px;" addon-after="%" />
        </a-form-item>
        <a-form-item label="查询类型" name="query_type">
          <a-checkbox-group v-model:value="tycFormState.query_type">
            <a-checkbox value="invest">对外投资</a-checkbox>
            <a-checkbox value="web">网站备案</a-checkbox>
            <a-checkbox value="app">移动APP</a-checkbox>
            <a-checkbox value="mapp">微信小程序</a-checkbox>
            <a-checkbox value="wechat">微信公众号</a-checkbox>
            <a-checkbox value="weibo">企业微博</a-checkbox>
            <a-checkbox value="trademark">企业商标</a-checkbox>
          </a-checkbox-group>
        </a-form-item>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import { useRouter } from 'vue-router';
import { message, Modal } from 'ant-design-vue';
import request from '../utils/request';

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:open', 'success']);
const router = useRouter();

const tycFormRef = ref();
const tycSubmitLoading = ref(false);
const tycFormState = reactive({
  name: '',
  gid: '',
  depth: 1,
  invest_ratio: 50,
  query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
  enable_icp: true
});

const tycConfigCheck = reactive({
  loading: false,
  valid: true,
  message: ''
});

const checkTycConfig = async () => {
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
    console.error('校验天眼查配置异常:', error);
  } finally {
    tycConfigCheck.loading = false;
  }
};

watch(() => props.open, (val) => {
  if (val) {
    tycFormState.name = '';
    tycFormState.gid = '';
    tycFormState.depth = 1;
    tycFormState.invest_ratio = 50;
    tycFormState.query_type = ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'];
    tycFormState.enable_icp = true;
    checkTycConfig();
  }
});

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
          emit('update:open', false);
          router.push({ path: '/systemSettings', query: { tab: 'api_config' } });
        }
      });
      return;
    }

    tycSubmitLoading.value = true;
    const res = await request.post('/icp/tyc_task', tycFormState);
    if (res.code === 200) {
      message.success('企业资产查询任务创建成功');
      emit('update:open', false);
      emit('success', res);
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    console.error(error);
  } finally {
    tycSubmitLoading.value = false;
  }
};
</script>
