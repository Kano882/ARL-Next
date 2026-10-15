<template>
  <a-modal
    :open="open"
    @update:open="val => $emit('update:open', val)"
    title="🏢 新建企业全景测绘任务"
    @ok="handleSubmit"
    :confirmLoading="submitLoading"
    width="580px"
    wrapClassName="arl-theme-modal"
    okText="🚀 开始全景测绘"
    cancelText="取 消"
    destroyOnClose
  >
    <a-spin :spinning="configChecking" tip="正在检测测绘环境配置...">
      <!-- 引擎能力状态动态提示 -->
      <a-alert
        v-if="!configChecking"
        :type="tycConfigValid ? 'info' : 'warning'"
        show-icon
        style="margin-bottom: 16px; border-radius: 6px; font-size: 12px;"
      >
        <template #message>
          <span v-if="tycConfigValid" style="color: var(--arl-text-color); line-height: 1.5;">
            已就绪：支持<b>天眼查股权穿透</b>与<b>工信部官方 ICP</b> 双轨测绘。输入天眼查链接、ID 或企业全称即可发起。
          </span>
          <span v-else style="color: var(--arl-text-color); line-height: 1.5;">
            未配置天眼查 API：系统将自动通过<b>工信部 ICP 备案数据</b>归集资产；若需投资穿透，请先完善凭据
            <a @click="goToApiConfig" style="margin-left: 4px;">前往配置 →</a>
          </span>
        </template>
      </a-alert>

      <a-form
        ref="formRef"
        :model="formState"
        :rules="rules"
        :label-col="{ style: { width: '100px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 100px)' } }"
      >
        <!-- 核心企业目标输入框 -->
        <a-form-item
          label="企业目标"
          name="rawTarget"
          tooltip="支持天眼查企业主页链接（如 https://www.tianyancha.com/company/25174642）、纯数字 GID 或企业工商注册全称"
        >
          <a-input
            v-model:value="formState.rawTarget"
            placeholder="粘贴天眼查链接 / GID 或输入企业工商全称"
            allowClear
            @pressEnter="handleSubmit"
          >
            <template #prefix>
              <component :is="parsedGid ? 'LinkOutlined' : 'BankOutlined'" style="color: #bfbfbf;" />
            </template>
          </a-input>

          <!-- 智能识别反馈状态 -->
          <div v-if="parsedGid" style="margin-top: 5px; font-size: 12px; color: var(--ant-primary-color); display: flex; align-items: center; gap: 4px;">
            <check-circle-outlined />
            <span>按天眼查 GID 解析: <b>{{ parsedGid }}</b> (将在提交后校验并执行全景双轨穿透)</span>
          </div>
          <div v-else-if="isCompanyName" style="margin-top: 5px; font-size: 12px; color: #722ed1; display: flex; align-items: center; gap: 4px;">
            <safety-certificate-outlined />
            <span>已识别企业主体: <b>{{ formState.rawTarget.trim() }}</b> (来源：工信部 ICP 备案)</span>
          </div>
        </a-form-item>

        <!-- 任务名称 (选填，自动补齐) -->
        <a-form-item
          label="任务名称"
          name="name"
          tooltip="选填，留空将根据企业官方名称或目标 ID 自动命名"
        >
          <a-input
            v-model:value="formState.name"
            placeholder="选填，留空将自动生成标准全景测绘任务名"
            allowClear
            @pressEnter="handleSubmit"
          />
        </a-form-item>

        <!-- 高级测绘参数（常驻平铺展示） -->
        <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px 14px; margin-top: 10px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
            <span style="font-weight: 500; font-size: 13px;">⚙️ 高级测绘参数</span>
          </div>

          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item
                label="投资层级"
                :label-col="{ style: { width: '80px' } }"
                :wrapper-col="{ style: { width: 'calc(100% - 80px)' } }"
                style="margin-bottom: 8px;"
                tooltip="穿透控股子公司与参股公司的递归深度 (1~20)。层级越高，天眼查 API 调用量与执行耗时增长越明显，且会消耗付费查询额度，请按需设置"
              >
                <a-input-number
                  v-model:value="formState.depth"
                  :min="1"
                  :max="20"
                  size="small"
                  style="width: 100px;"
                  addon-after="层"
                />
                <div v-if="formState.depth > 1" class="depth-cost-hint">
                  已设置为 {{ formState.depth }} 层，将递归查询下属企业，API 调用量与付费额度消耗相应增加
                </div>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item
                label="控股比例"
                :label-col="{ style: { width: '80px' } }"
                :wrapper-col="{ style: { width: 'calc(100% - 80px)' } }"
                style="margin-bottom: 8px;"
                tooltip="对外投资的最小持股比例 (1~100%)"
              >
                <a-input-number
                  v-model:value="formState.invest_ratio"
                  :min="1"
                  :max="100"
                  size="small"
                  style="width: 100px;"
                  addon-after="%"
                />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item
            label="ICP 双轨查重"
            :label-col="{ style: { width: '85px' } }"
            :wrapper-col="{ style: { width: 'calc(100% - 85px)' } }"
            style="margin-bottom: 8px;"
            tooltip="调用工信部 ICP 备案数据接口进行双轨校对与兜底补全"
          >
            <a-switch v-model:checked="formState.enable_icp" size="small" />
            <span style="font-size: 12px; margin-left: 8px; color: var(--arl-text-color); opacity: 0.7;">
              {{ formState.enable_icp ? '已启用（推荐）' : '已关闭' }}
            </span>
          </a-form-item>

          <a-form-item
            label="资产维度"
            :label-col="{ style: { width: '80px' } }"
            :wrapper-col="{ style: { width: 'calc(100% - 80px)' } }"
            style="margin-bottom: 0;"
          >
            <a-checkbox-group v-model:value="formState.query_type" style="display: flex; flex-wrap: wrap; gap: 6px;">
              <a-checkbox value="invest">对外投资</a-checkbox>
              <a-checkbox value="web">网站备案</a-checkbox>
              <a-checkbox value="app">移动APP</a-checkbox>
              <a-checkbox value="mapp">微信小程序</a-checkbox>
              <a-checkbox value="wechat">微信公众号</a-checkbox>
              <a-checkbox value="weibo">企业微博</a-checkbox>
            </a-checkbox-group>
          </a-form-item>
        </div>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Modal, message } from 'ant-design-vue';
import {
  LinkOutlined,
  BankOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:open', 'success']);
const router = useRouter();

const formRef = ref();
const submitLoading = ref(false);
const configChecking = ref(false);
const tycConfigValid = ref(false);

const formState = reactive({
  name: '',
  rawTarget: '',
  depth: 1,
  invest_ratio: 50,
  query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
  enable_icp: true
});

const rules = {
  rawTarget: [{ required: true, message: '请输入天眼查链接、GID 或企业工商全称', trigger: 'blur' }]
};

// 正则解析企业输入
const parseTargetInput = (input) => {
  if (!input) return { gid: '', isUrl: false, isName: false };
  const str = input.trim();
  const urlMatch = str.match(/(?:tianyancha\.com\/company\/|^company\/)([a-zA-Z0-9]+)/i);
  if (urlMatch && urlMatch[1]) {
    return { gid: urlMatch[1], isUrl: true, isName: false };
  }
  // 仅纯数字串视为 GID（天眼查 GID 为数字）；其余字母数字混排按企业名称处理，
  // 交由后端检索匹配，避免误把普通输入当成 GID。
  if (/^\d+$/.test(str)) {
    return { gid: str, isUrl: false, isName: false };
  }
  if (str.length >= 2) {
    return { gid: '', isUrl: false, isName: true };
  }
  return { gid: '', isUrl: false, isName: false };
};

const parsedGid = computed(() => {
  const parsed = parseTargetInput(formState.rawTarget);
  return parsed.gid;
});

const isCompanyName = computed(() => {
  const parsed = parseTargetInput(formState.rawTarget);
  return parsed.isName;
});

const checkTycConfig = async () => {
  configChecking.value = true;
  try {
    const res = await request.get('/icp/tyc_check');
    if (res.code === 200 && res.data) {
      tycConfigValid.value = !!res.data.valid;
    } else {
      tycConfigValid.value = false;
    }
  } catch (error) {
    console.error('检测天眼查配置异常:', error);
    tycConfigValid.value = false;
  } finally {
    configChecking.value = false;
  }
};

// 跳转系统设置前暂存输入，返回时恢复，避免用户已填写的目标被清空后需重新输入
let pendingDraft = null;

const goToApiConfig = () => {
  pendingDraft = { rawTarget: formState.rawTarget, name: formState.name };
  emit('update:open', false);
  // focus 参数让系统设置页直接定位并高亮天眼查凭据卡片
  router.push({ path: '/systemSettings', query: { tab: 'api_config', focus: 'tyc' } });
};

watch(() => props.open, (val) => {
  if (val) {
    const draft = pendingDraft;
    pendingDraft = null;
    formState.name = draft ? draft.name : '';
    formState.rawTarget = draft ? draft.rawTarget : '';
    formState.depth = 1;
    formState.invest_ratio = 50;
    formState.query_type = ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'];
    formState.enable_icp = true;
    checkTycConfig();
  }
});

const handleSubmit = async () => {
  try {
    await formRef.value.validate();
    const targetStr = (formState.rawTarget || '').trim();
    const customName = (formState.name || '').trim();
    const parsed = parseTargetInput(targetStr);

    if (!parsed.gid && !parsed.isName) {
      message.error('未能识别有效目标，请输入天眼查链接、ID 或企业工商注册全称');
      return;
    }

    // 分流场景 1: 输入了天眼查 GID / 链接
    if (parsed.gid) {
      if (!tycConfigValid.value) {
        Modal.confirm({
          title: '未配置天眼查商业凭据',
          content: '当前输入的天眼查 GID 需要商业凭据才能执行股权穿透。您可以先去系统设置配置凭据，或改用企业工商全称通过工信部官方备案检索。',
          okText: '前往配置凭据',
          cancelText: '留在本页',
          onOk() {
            goToApiConfig();
          }
        });
        return;
      }

      submitLoading.value = true;
      const taskName = customName || ('TYC_' + parsed.gid);
      const payload = {
        name: taskName,
        gid: parsed.gid,
        depth: formState.depth || 1,
        invest_ratio: formState.invest_ratio || 50,
        enable_icp: formState.enable_icp !== false,
        query_type: formState.query_type
      };
      if (customName) {
        payload.company_name = customName;
      }
      const res = await request.post('/icp/tyc_task', payload);
      if (res.code === 200) {
        message.success(`企业全景测绘任务【${taskName}】创建成功`);
        emit('update:open', false);
        emit('success', res);
      } else {
        message.error(res.message || '创建任务失败');
      }
      return;
    }

    // 分流场景 2: 输入了企业工商全称
    submitLoading.value = true;
    const taskName = customName || targetStr;
    const payload = {
      name: taskName,
      target: targetStr,
      depth: formState.depth || 1,
      invest_ratio: formState.invest_ratio || 50,
      enable_icp: formState.enable_icp !== false,
      query_type: formState.query_type
    };
    const res = await request.post('/icp/task', payload);
    if (res.code === 200) {
      const modeTip = res.data?.matched_tyc ? ' (已自动识别并升级为全景双轨测绘)' : '';
      message.success(`企业全景测绘任务【${taskName}】创建成功${modeTip}`);
      emit('update:open', false);
      emit('success', res);
    } else {
      message.error(res.message || '创建任务失败');
    }

  } catch (error) {
    console.error('提交企业全景测绘任务失败', error);
  } finally {
    submitLoading.value = false;
  }
};
</script>

<style scoped>
/* 投资层级成本提示：层级越高，天眼查付费额度消耗越大 */
.depth-cost-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-warning-color, #faad14);
}
</style>
