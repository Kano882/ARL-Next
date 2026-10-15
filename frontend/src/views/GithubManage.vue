<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    
    <!-- 全局 Token 状态提示 -->
    <a-alert
      v-if="tokenStatus.status"
      :type="tokenStatus.status === 'valid' ? 'success' : 'error'"
      show-icon
      style="margin-bottom: 16px;"
    >
      <template #message>
        <span style="font-weight: 500;">
          GitHub Token 状态: 
          <span v-if="tokenStatus.status === 'valid'" style="color: #52c41a;">{{ tokenStatus.msg }}</span>
          <span v-else style="color: #f5222d;">{{ tokenStatus.msg }}</span>
        </span>
      </template>
      <template #description v-if="tokenStatus.status !== 'valid'">
        <div style="margin-top: 4px;">
          当前模块（包含代码泄露监控、CVE、武器库追踪等）强依赖 GitHub Token，未配置或失效时可能被 GitHub 限流甚至封禁 IP。
          <a @click="goToGithubTokenConfig" style="margin-left: 4px;">前往配置 →</a>
        </div>
      </template>
    </a-alert>

    <a-tabs v-model:activeKey="mainTab" type="card" class="main-tabs" size="large">
      
<!-- ================= MAIN TAB 2: 威胁情报雷达 (情报侧) ================= -->
<a-tab-pane key="ti" tab="📡 威胁情报雷达">
  <a-card :bordered="false" style="border-radius: 8px;">
    


    <a-tabs v-model:activeKey="activeTabTi">
      <a-tab-pane key="cve_history" tab="🚨 CVE 漏洞雷达">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; background: var(--arl-bg-light); padding: 12px 16px; border-radius: 6px;">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div>
              <span style="margin-right: 8px;">定时开启:</span>
              <a-switch v-model:checked="cveConfig.enabled" @change="saveCveConfig" />
            </div>
            <div v-if="cveConfig.enabled">
              <span style="margin-right: 8px;">抓取频率:</span>
              <a-select v-model:value="cveConfig.interval" style="width: 120px" @change="saveCveConfig">
                <a-select-option :value="6">每 6 小时</a-select-option>
                <a-select-option :value="12">每 12 小时</a-select-option>
                <a-select-option :value="24">每 24 小时</a-select-option>
              </a-select>
            </div>
            <a-button type="primary" ghost @click="runCveOnce" :loading="cveRunLoading || cveConfig.is_running">立刻扫描一次</a-button>
            <a-tag v-if="cveConfig.is_running" color="processing">正在后台扫描</a-tag>
          </div>
          <a-button type="dashed" @click="fetchCveData">
            <template #icon><sync-outlined /></template> 刷新数据
          </a-button>
        </div>

        <!-- CVE搜索栏 -->
        <a-form layout="inline" style="row-gap: 16px; margin-bottom: 16px;">
          <a-form-item label="CVE 编号：">
            <a-input v-model:value="cveSearchForm.cve_name" placeholder="请输入 CVE 编号" style="width: 180px;" allowClear @pressEnter="onCveSearch">
              <template #suffix><search-outlined @click="onCveSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="描述：">
            <a-input v-model:value="cveSearchForm.desc" placeholder="请输入描述" style="width: 180px;" allowClear @pressEnter="onCveSearch">
              <template #suffix><search-outlined @click="onCveSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
        </a-form>

        <div style="margin-bottom: 16px; display: flex; gap: 16px;">
          <a-button @click="resetCveSearch">清 除</a-button>
          <a-popconfirm title="确认删除所选记录吗？" @confirm="handleCveBatchDelete">
            <a-button type="primary" danger :disabled="!cveHasSelected">批量删除</a-button>
          </a-popconfirm>
        </div>
        <a-table :row-selection="{ selectedRowKeys: cveSelectedRowKeys, onChange: onCveSelectChange, preserveSelectedRowKeys: true }" :loading="cveLoading" :dataSource="pagedCveData" :columns="cveColumns" :pagination="false" size="middle" rowKey="cve_name">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'cve_name'">
              <a :href="record.cve_url" target="_blank" style="color: #ff4d4f; font-weight: bold; font-size: 15px;">
                {{ record.cve_name }} <link-outlined />
              </a>
            </template>
            <template v-else-if="column.key === 'desc'">
              <a-typography-paragraph :ellipsis="{ rows: 2, expandable: true, symbol: '展开' }" style="margin-bottom: 0;">
                {{ record.desc }}
              </a-typography-paragraph>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-popconfirm title="确认删除？" @confirm="handleCveDelete(record.cve_name)">
                <a-button size="small" type="primary" danger ghost>删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0; margin-top: 16px;">
          <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(filteredCveData.length / cvePagination.pageSize) || 1 }} 页 / {{ filteredCveData.length }} 条数据</div>
          <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="cvePagination.current" v-model:pageSize="cvePagination.pageSize" :total="filteredCveData.length" show-size-changer @change="onCveTableChange" @showSizeChange="onCveTableChange" />
        </div>
      </a-tab-pane>

      <!-- 子 Tab 2: 武器库追踪 -->
      <a-tab-pane key="tools_target" tab="🛠️ 武器库追踪">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
          <div style="display: flex; gap: 16px; align-items: center;">
            <a-button type="primary" @click="openToolAdd">添加工具监控</a-button>
            <a-button type="primary" ghost @click="runToolsOnce" :loading="toolsRunLoading || toolsConfig.is_running">立刻扫描一次</a-button>
            <a-tag v-if="toolsConfig.is_running" color="processing">正在后台扫描</a-tag>
            
            <div style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 12px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>开启监控:</span>
              <a-switch v-model:checked="toolsConfig.enabled" @change="saveToolsConfig" />
            </div>
            
            <div v-if="toolsConfig.enabled" style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 12px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>周期策略:</span>
              <a-select v-model:value="toolsConfig.interval" style="width: 120px" @change="saveToolsConfig">
                <a-select-option :value="1">每 1 小时</a-select-option>
                <a-select-option :value="2">每 2 小时</a-select-option>
                <a-select-option :value="6">每 6 小时</a-select-option>
                <a-select-option :value="12">每 12 小时</a-select-option>
                <a-select-option :value="24">每天一次</a-select-option>
              </a-select>
            </div>
          </div>
          <a-button type="dashed" @click="fetchToolsData">
            <template #icon><sync-outlined /></template>
            刷新列表
          </a-button>
        </div>

        <!-- 武器库搜索栏 -->
        <a-form layout="inline" style="row-gap: 16px; margin-bottom: 16px;">
          <a-form-item label="工具URL：">
            <a-input v-model:value="toolsSearchForm.repo_url" placeholder="请输入工具URL" style="width: 250px;" allowClear @pressEnter="onToolsSearch">
              <template #suffix><search-outlined @click="onToolsSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
        </a-form>

        <div style="margin-bottom: 16px; display: flex; gap: 16px;">
          <a-button @click="resetToolsSearch">清 除</a-button>
          <a-popconfirm title="确认删除所选工具吗？" @confirm="handleToolsBatchDelete">
            <a-button type="primary" danger :disabled="!toolsHasSelected">批量删除</a-button>
          </a-popconfirm>
        </div>

        <a-table :row-selection="{ selectedRowKeys: toolsSelectedRowKeys, onChange: onToolsSelectChange, preserveSelectedRowKeys: true }" :loading="toolsLoading" :dataSource="pagedToolsData" :columns="toolsColumns" :pagination="false" size="middle" rowKey="repo_url">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'repo_url'">
              <a :href="record.repo_url.replace('api.github.com/repos', 'github.com')" target="_blank" style="color: #1890ff; font-weight: 500;">
                {{ record.repo_url.split('/').pop() }} <link-outlined />
              </a>
              <div style="color: var(--arl-text-color); opacity: 0.45; font-size: 12px;">{{ record.repo_url }}</div>
            </template>
            <template v-else-if="column.key === 'last_tag'">
              <a-tag color="cyan" v-if="record.last_tag">{{ record.last_tag }}</a-tag>
              <span v-else style="color: var(--arl-text-color); opacity: 0.25;">暂无版本</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a :href="record.repo_url.replace('api.github.com/repos', 'github.com')" target="_blank">
                <a-button size="small" type="primary" ghost style="margin-right: 8px;">查看</a-button>
              </a>
              <a-popconfirm title="确认取消监控该工具？" @confirm="handleToolDelete(record.repo_url)">
                <a-button size="small" type="primary" danger ghost>删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0; margin-top: 16px;">
          <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(filteredToolsData.length / toolsPagination.pageSize) || 1 }} 页 / {{ filteredToolsData.length }} 条数据</div>
          <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="toolsPagination.current" v-model:pageSize="toolsPagination.pageSize" :total="filteredToolsData.length" show-size-changer @change="onToolsTableChange" @showSizeChange="onToolsTableChange" />
        </div>
      </a-tab-pane>

      <!-- 子 Tab 3: 黑客动态监测 -->
      <a-tab-pane key="hackers_target" tab="👨‍💻 黑客动态监测">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
          <div style="display: flex; gap: 16px; align-items: center;">
            <a-button type="primary" @click="openHackerAdd">添加大佬监控</a-button>
            <a-button type="primary" ghost @click="runHackersOnce" :loading="hackersRunLoading || hackersConfig.is_running">立刻扫描一次</a-button>
            <a-tag v-if="hackersConfig.is_running" color="processing">正在后台扫描</a-tag>
            
            <div style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 12px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>开启监控:</span>
              <a-switch v-model:checked="hackersConfig.enabled" @change="saveHackersConfig" />
            </div>
            
            <div v-if="hackersConfig.enabled" style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 12px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>周期策略:</span>
              <a-select v-model:value="hackersConfig.interval" style="width: 120px" @change="saveHackersConfig">
                <a-select-option :value="1">每 1 小时</a-select-option>
                <a-select-option :value="2">每 2 小时</a-select-option>
                <a-select-option :value="6">每 6 小时</a-select-option>
                <a-select-option :value="12">每 12 小时</a-select-option>
                <a-select-option :value="24">每天一次</a-select-option>
              </a-select>
            </div>
          </div>
          <div style="display: flex; gap: 16px;">
            <a-button style="border-color: #fadb14; color: #faad14;" @click="openHackersHistoryDrawer">
              <template #icon>👀</template> 查看所有发现记录
            </a-button>
            <a-button type="dashed" @click="fetchHackersData">
              <template #icon><sync-outlined /></template>
              刷新列表
            </a-button>
          </div>
        </div>

        <!-- 黑客搜索栏 -->
        <a-form layout="inline" style="row-gap: 16px; margin-bottom: 16px;">
          <a-form-item label="Github ID：">
            <a-input v-model:value="hackersSearchForm.github_id" placeholder="请输入 Github ID" style="width: 180px;" allowClear @pressEnter="onHackersSearch">
              <template #suffix><search-outlined @click="onHackersSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
        </a-form>

        <div style="margin-bottom: 16px; display: flex; gap: 16px;">
          <a-button @click="resetHackersSearch">清 除</a-button>
          <a-popconfirm title="确认删除所选大佬吗？" @confirm="handleHackersBatchDelete">
            <a-button type="primary" danger :disabled="!hackersHasSelected">批量删除</a-button>
          </a-popconfirm>
        </div>

        <a-table :row-selection="{ selectedRowKeys: hackersSelectedRowKeys, onChange: onHackersSelectChange, preserveSelectedRowKeys: true }" :loading="hackersLoading" :dataSource="pagedHackersData" :columns="hackersColumns" :pagination="false" size="middle" rowKey="github_id">
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
              <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无监控大佬</div>
              <a-button type="link" @click="hackerForm.github_id = 'knownsec'; submitHackerModal()">一键添加 knownsec</a-button>
            </div>
          </template>
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'github_id'">
              <div style="display: flex; align-items: center; gap: 12px;">
                <a-avatar :src="`https://github.com/${(record.github_id || '').trim()}.png`" size="large" />
                <a :href="`https://github.com/${(record.github_id || '').trim()}`" target="_blank" style="font-weight: 500; font-size: 15px;">
                  {{ record.github_id }} <link-outlined />
                </a>
              </div>
            </template>
            <template v-if="column.key === 'found_count'">
              <a-badge :count="record.found_count" :number-style="{ backgroundColor: '#52c41a' }" show-zero />
            </template>
            <template v-if="column.key === 'action'">
              <a :href="`https://github.com/${record.github_id}`" target="_blank">
                <a-button size="small" type="primary" ghost style="margin-right: 8px;">主页</a-button>
              </a>
              <a-popconfirm title="确认取消监控？" @confirm="handleHackerDelete(record.github_id)">
                <a-button size="small" type="primary" danger ghost>删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0; margin-top: 16px;">
          <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(filteredHackersData.length / hackersPagination.pageSize) || 1 }} 页 / {{ filteredHackersData.length }} 条数据</div>
          <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="hackersPagination.current" v-model:pageSize="hackersPagination.pageSize" :total="filteredHackersData.length" show-size-changer @change="onHackersTableChange" @showSizeChange="onHackersTableChange" />
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-card>
</a-tab-pane>

      <!-- ================= MAIN TAB 1: 代码泄露监控 (防守侧) ================= -->
      <a-tab-pane key="dlp" tab="🛡️ 代码泄露监控">
        <a-card :bordered="false" style="border-radius: 8px;">
          <a-tabs v-model:activeKey="activeTabDlp">
            <!-- 子 Tab 1: 周期策略管理 -->
            <a-tab-pane key="scheduler" tab="周期策略管理">
        <div style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
          <a-button type="primary" @click="openSchedulerAdd">添加策略</a-button>
          <a-button type="dashed" @click="fetchSchedulerData">
            <template #icon><sync-outlined /></template>
            刷新列表
          </a-button>
        </div>

        <!-- 策略搜索栏 -->
        <a-form layout="inline" style="row-gap: 16px; margin-bottom: 16px;">
          <a-form-item label="策略名称：">
            <a-input v-model:value="schedulerSearchForm.name" placeholder="请输入策略名称" style="width: 180px;" allowClear @pressEnter="onSchedulerSearch">
              <template #suffix><search-outlined @click="onSchedulerSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="关键字：">
            <a-input v-model:value="schedulerSearchForm.keyword" placeholder="请输入关键字" style="width: 180px;" allowClear @pressEnter="onSchedulerSearch">
              <template #suffix><search-outlined @click="onSchedulerSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="状态：">
            <a-select v-model:value="schedulerSearchForm.status" placeholder="请选择状态" style="width: 180px;" allowClear @change="onSchedulerSearch">
              <a-select-option value="running">running</a-select-option>
              <a-select-option value="stop">stop</a-select-option>
              <a-select-option value="error">error</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>

        <!-- 批量操作 -->
        <div style="margin-bottom: 16px; display: flex; gap: 8px;">
          <a-button @click="resetSchedulerSearch">清 除</a-button>
          <a-popconfirm title="确认删除所选策略吗？" @confirm="handleSchedulerBatchDelete">
            <a-button :disabled="!schedulerHasSelected">批量删除</a-button>
          </a-popconfirm>
          <a-popconfirm title="确认停止所选策略吗？" @confirm="handleSchedulerBatchStop">
            <a-button :disabled="!schedulerHasSelected">批量停止</a-button>
          </a-popconfirm>
        </div>

        </div>
        <!-- 策略表格 -->
<a-table
            :row-selection="{ selectedRowKeys: schedulerSelectedRowKeys, onChange: onSchedulerSelectChange, preserveSelectedRowKeys: true }"
            :loading="schedulerLoading"
            :dataSource="schedulerData"
            :columns="schedulerColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record._id"
        >
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
              <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无策略数据</div>
            </div>
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a style="color: var(--arl-theme-color); font-weight: 500;" @click="openResultDrawer(record, 'scheduler')">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'running' ? 'blue' : record.status === 'stop' ? 'warning' : 'error'">
                {{ record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                  size="small"
                  type="link"
                  style="padding: 0 4px; margin-right: 8px;"
                  @click="openResultDrawer(record, 'scheduler')"
              >查看</a-button>

              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status !== 'running'"
                  @click="handleSchedulerSingleAction('stop', record._id)"
              >停止</a-button>
              
              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status !== 'stop' && record.status !== 'error'"
                  @click="handleSchedulerSingleAction('recover', record._id)"
              >恢复</a-button>

              <a-button size="small" style="margin-right: 8px;" @click="openSchedulerEdit(record)">修改</a-button>

              <a-popconfirm title="确认删除该策略？" @confirm="handleSchedulerSingleAction('delete', record._id)">
                <a-button size="small">删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- 策略分页 -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
          <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(schedulerPagination.total / schedulerPagination.pageSize) || 1 }} 页 / {{ schedulerPagination.total }} 条数据</div>
          <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="schedulerPagination.current" v-model:pageSize="schedulerPagination.pageSize" :total="schedulerPagination.total" show-size-changer @change="handleSchedulerTableChange" @showSizeChange="handleSchedulerTableChange" />
        </div>
      </a-tab-pane>

      <!-- 子 Tab 2: 单次扫描任务 -->
      <a-tab-pane key="task" tab="单次扫描任务">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
          <a-button type="primary" @click="openTaskAdd">新建单次任务</a-button>
          <a-button type="dashed" @click="fetchTaskData">
            <template #icon><sync-outlined /></template>
            刷新列表
          </a-button>
        </div>

        <!-- 任务搜索栏 -->
        <a-form layout="inline" style="row-gap: 16px; margin-bottom: 16px;">
          <a-form-item label="任务名称：">
            <a-input v-model:value="taskSearchForm.name" placeholder="请输入任务名称" style="width: 180px;" allowClear @pressEnter="onTaskSearch">
              <template #suffix><search-outlined @click="onTaskSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="关键字：">
            <a-input v-model:value="taskSearchForm.keyword" placeholder="请输入关键字" style="width: 180px;" allowClear @pressEnter="onTaskSearch">
              <template #suffix><search-outlined @click="onTaskSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="状态：">
            <a-select v-model:value="taskSearchForm.status" placeholder="请选择状态" style="width: 180px;" allowClear @change="onTaskSearch">
              <a-select-option value="waiting">waiting</a-select-option>
              <a-select-option value="running">running</a-select-option>
              <a-select-option value="done">done</a-select-option>
              <a-select-option value="error">error</a-select-option>
              <a-select-option value="stop">stop</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>

        <!-- 批量操作 -->
        <div style="margin-bottom: 16px; display: flex; gap: 8px;">
          <a-button @click="resetTaskSearch">清 除</a-button>
          <a-popconfirm title="确认删除所选任务吗？" @confirm="handleTaskBatchDelete">
            <a-button :disabled="!taskHasSelected">批量删除</a-button>
          </a-popconfirm>
          <a-popconfirm title="确认停止所选任务吗？" @confirm="handleTaskBatchStop">
            <a-button :disabled="!taskHasSelected">批量停止</a-button>
          </a-popconfirm>
        </div>

        <!-- 任务表格 -->
        <a-table
            :row-selection="{ selectedRowKeys: taskSelectedRowKeys, onChange: onTaskSelectChange, preserveSelectedRowKeys: true }"
            :loading="taskLoading"
            :dataSource="taskData"
            :columns="taskColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record._id"
        >
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
              <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无扫描任务</div>
            </div>
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a style="color: var(--arl-theme-color); font-weight: 500;" @click="openResultDrawer(record, 'task')">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag
                  :color="
                  record.status === 'running' || record.status === 'waiting' ? 'blue' :
                  record.status === 'error' ? 'error' :
                  'success'
                "
              >
                {{ record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                  size="small"
                  type="link"
                  style="padding: 0 4px; margin-right: 8px;"
                  @click="openResultDrawer(record, 'task')"
              >查看</a-button>

              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  type="primary" ghost
                  @click="handleTaskRestart(record)"
              >重启</a-button>

              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'"
                  @click="handleTaskSingleAction('stop', record._id)"
              >停止</a-button>

              <a-popconfirm title="确认删除该任务？" @confirm="handleTaskSingleAction('delete', record._id)">
                <a-button size="small">删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- 任务分页 -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
          <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(taskPagination.total / taskPagination.pageSize) || 1 }} 页 / {{ taskPagination.total }} 条数据</div>
          <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="taskPagination.current" v-model:pageSize="taskPagination.pageSize" :total="taskPagination.total" show-size-changer @change="handleTaskTableChange" @showSizeChange="handleTaskTableChange" />
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-card>
</a-tab-pane>



    </a-tabs>

    <!-- ================= 黑客发现记录抽屉 ================= -->
    <a-drawer
      title="👀 全网大佬工具发现记录"
      placement="right"
      :width="600"
      :open="historyDrawerVisible"
      @close="closeHackersHistoryDrawer"
    >
      <a-table :loading="historyLoading" :dataSource="hackersHistoryData" :columns="historyColumns" :pagination="true" size="middle" rowKey="full_name">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'full_name'">
            <a :href="`https://github.com/${record.full_name}`" target="_blank" style="font-weight: 500; color: #1890ff;">
              {{ record.full_name }} <link-outlined />
            </a>
          </template>
          <template v-else-if="column.key === 'insert_time'">
            <span style="color: var(--arl-text-color);"><clock-circle-outlined /> {{ record.insert_time }}</span>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- ================= GitHub 任务与监控结果详情抽屉 ================= -->
    <a-drawer
      :title="resultDrawerTitle"
      placement="right"
      :width="920"
      :open="resultDrawerVisible"
      @close="closeResultDrawer"
    >
      <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; background: var(--arl-bg-light); padding: 12px 16px; border-radius: 6px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <a-tag :color="resultDrawerType === 'task' ? 'blue' : 'purple'">
            {{ resultDrawerType === 'task' ? '单次扫描任务' : '周期监控策略' }}
          </a-tag>
          <span style="font-weight: 600; font-size: 14px;">{{ resultCurrentRecord?.name }}</span>
          <span style="color: var(--arl-text-color); opacity: 0.65; font-size: 12px;">关键字：{{ resultCurrentRecord?.keyword }}</span>
        </div>
        <a-button type="dashed" size="small" @click="fetchResultData" :loading="resultLoading">
          <template #icon><sync-outlined /></template> 刷新
        </a-button>
      </div>

      <a-tabs v-model:activeKey="resultActiveTab" type="card">
        <!-- Tab 1: 命中结果 -->
        <a-tab-pane key="result" tab="🎯 命中泄露结果">
          <!-- 搜索过滤栏 -->
          <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; align-items: center;">
            <a-input v-model:value="resultSearchForm.repo_full_name" placeholder="仓库名 (如 user/repo)" style="width: 180px;" allowClear @pressEnter="onResultSearch">
              <template #suffix><search-outlined @click="onResultSearch" style="cursor: pointer; opacity: 0.4;" /></template>
            </a-input>
            <a-input v-model:value="resultSearchForm.path" placeholder="文件路径 (如 config.py)" style="width: 180px;" allowClear @pressEnter="onResultSearch">
              <template #suffix><search-outlined @click="onResultSearch" style="cursor: pointer; opacity: 0.4;" /></template>
            </a-input>
            <a-input v-model:value="resultSearchForm.human_content" placeholder="代码内容关键词" style="width: 180px;" allowClear @pressEnter="onResultSearch">
              <template #suffix><search-outlined @click="onResultSearch" style="cursor: pointer; opacity: 0.4;" /></template>
            </a-input>
            <a-button @click="resetResultSearch">重置</a-button>
          </div>

          <a-table
            :loading="resultLoading"
            :dataSource="resultDataSource"
            :columns="resultColumns"
            :pagination="false"
            size="middle"
            rowKey="_id"
          >
            <template #emptyText>
              <div style="padding: 30px 0; text-align: center;">
                <inbox-outlined style="font-size: 40px; color: var(--arl-border-color);" />
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无泄露命中数据</div>
              </div>
            </template>
            <template #bodyCell="{ column, record, text }">
              <template v-if="column.key === 'repo_full_name'">
                <a :href="`https://github.com/${record.repo_full_name}`" target="_blank" style="word-break: break-all; font-weight: 500;">
                  {{ record.repo_full_name }} <link-outlined style="font-size: 11px;" />
                </a>
              </template>
              <template v-else-if="column.key === 'path'">
                <a :href="record.html_url || `https://github.com/${record.repo_full_name}/blob/master/${record.path}`" target="_blank" style="word-break: break-all;">
                  {{ record.path }}
                </a>
              </template>
              <template v-else-if="column.key === 'human_content'">
                <div style="white-space: pre-wrap; word-break: break-word; font-family: 'SFMono-Regular', Consolas, Monaco, monospace; max-height: 240px; overflow-y: auto; background: var(--arl-bg-light); padding: 10px; border-radius: 6px; border: 1px solid var(--arl-border-color); font-size: 12px; line-height: 1.5; color: var(--arl-text-color);">
                  {{ record.human_content }}
                </div>
              </template>
              <template v-else-if="column.key === 'keyword'">
                <a-tag color="blue">{{ record.keyword }}</a-tag>
              </template>
              <template v-else-if="column.key === 'commit_date'">
                <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.85;">{{ record.commit_date || record.insert_time || '-' }}</span>
              </template>
            </template>
          </a-table>

          <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
            <div style="color: var(--arl-text-color); opacity: 0.65; font-size: 12px;">共 {{ Math.ceil(resultPagination.total / resultPagination.pageSize) || 1 }} 页 / {{ resultPagination.total }} 条数据</div>
            <a-pagination size="small" :pageSizeOptions="['10', '20', '50']" v-model:current="resultPagination.current" v-model:pageSize="resultPagination.pageSize" :total="resultPagination.total" show-size-changer @change="handleResultTableChange" />
          </div>
        </a-tab-pane>

        <!-- Tab 2: 任务日志 (仅单次任务支持 syslog) -->
        <a-tab-pane v-if="resultDrawerType === 'task'" key="log" tab="📋 任务日志">
          <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
            <div ref="resultTerminalContainer" style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, monospace; padding: 14px; border-radius: 4px; height: 500px; overflow-y: auto; font-size: 12px; line-height: 1.6;">
              <div v-for="(log, idx) in resultLogDataSource" :key="log._id || idx" style="margin-bottom: 4px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.08); padding-bottom: 2px;">
                <span style="margin-right: 8px; opacity: 0.7;">[{{ log.create_time }}]</span>
                <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
                <span style="margin-right: 8px;" v-if="log.title">[{{ log.title }}]</span>
                <span style="color: #e6f7ff;">{{ log.message }}</span>
              </div>
              <div v-if="resultLogDataSource.length === 0 && !resultLogLoading" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录...</div>
              <div v-if="resultLogLoading" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 正在拉取日志...</div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

    <!-- ================= 策略弹窗 (新增/修改) ================= -->
    <a-modal
        v-model:open="schedulerModalVisible"
        :title="schedulerIsEdit ? '修改策略' : '添加策略'"
        @ok="submitSchedulerModal"
        :confirmLoading="schedulerSubmitLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="schedulerForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="策略名称" required>
          <a-input v-model:value="schedulerForm.name" placeholder="请输入策略名" />
        </a-form-item>

        <a-form-item label="关键字" required>
          <a-input v-model:value="schedulerForm.keyword" placeholder="请输入关键字" />
        </a-form-item>

        <a-form-item label="cron表达式" required>
          <a-input v-model:value="schedulerForm.cron" placeholder="请输入cron表达式，如 */30 * * * *" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 任务弹窗 (新增) ================= -->
    <a-modal
        v-model:open="taskModalVisible"
        title="新建单次扫描"
        @ok="submitTaskModal"
        :confirmLoading="taskSubmitLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="taskForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="任务名称" required>
          <a-input v-model:value="taskForm.name" placeholder="请输入任务名称" />
        </a-form-item>

        <a-form-item label="关键字" required>
          <a-input v-model:value="taskForm.keyword" placeholder="请输入关键字" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 工具新增弹窗 ================= -->
    <a-modal
        v-model:open="toolModalVisible"
        title="添加工具监控"
        @ok="submitToolModal"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="toolForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="仓库 URL" required>
          <a-input v-model:value="toolForm.repo_url" placeholder="如 https://github.com/chaitin/xray" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 大佬新增弹窗 ================= -->
    <a-modal
        v-model:open="hackerModalVisible"
        title="添加大佬监控"
        @ok="submitHackerModal"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="hackerForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="Github ID" required>
          <a-input v-model:value="hackerForm.github_id" placeholder="如 knownsec" />
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
defineOptions({ name: 'GithubManage' });
import { ref, reactive, onMounted, onDeactivated, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined, SyncOutlined, LinkOutlined, ClockCircleOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const router = useRouter();

// 深链到系统设置的 GitHub Token 字段并高亮，避免用户自己在设置页翻找
const goToGithubTokenConfig = () => {
  router.push({ path: '/systemSettings', query: { tab: 'api_config', focus: 'github_token' } });
};
const route = useRoute();
const globalPageSize = useGlobalPageSize(10);
const mainTab = ref('ti');
const activeTabDlp = ref('scheduler');
const activeTabTi = ref('cve_history');

// 💡 优先识别 URL 中传过来的参数（例如 dashboard 跳转过来默认指向对应 Tab）
onMounted(() => {
  if (route.query.tab && ['task', 'scheduler'].includes(route.query.tab)) {
    mainTab.value = 'dlp';
    activeTabDlp.value = route.query.tab;
  } else if (route.query.tab && ['cve_history', 'tools_target', 'hackers_target'].includes(route.query.tab)) {
    mainTab.value = 'ti';
    activeTabTi.value = route.query.tab;
  }
  fetchSchedulerData();
  fetchTaskData();
  fetchToolsData();
  fetchHackersData();
  fetchCveData();
  fetchCveConfig();
  fetchToolsConfig();
  fetchHackersConfig();
  fetchTokenStatus();
});

// 监听内部 Tab 切换拉取数据
watch(activeTabDlp, (newTab) => {
  if (newTab === 'scheduler') fetchSchedulerData();
  else if (newTab === 'task') fetchTaskData();
});

watch(activeTabTi, (newTab) => {
  if (newTab === 'cve_history') fetchCveData();
  else if (newTab === 'tools_target') fetchToolsData();
  else if (newTab === 'hackers_target') fetchHackersData();
});

// ==========================================
// ⚙️ 模块 A: 监控策略管理 (github_scheduler)
// ==========================================
const schedulerLoading = ref(false);
const schedulerData = ref([]);
const schedulerSearchForm = reactive({ name: '', keyword: '', status: undefined });
const schedulerPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(globalPageSize, (newSize) => {
  schedulerPagination.pageSize = newSize;
  taskPagination.pageSize = newSize;
  toolsPagination.pageSize = newSize;
  hackersPagination.pageSize = newSize;
  cvePagination.pageSize = newSize;
});

watch(() => schedulerPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => taskPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => toolsPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => hackersPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => cvePagination.pageSize, (newSize) => { globalPageSize.value = newSize; });

const schedulerSelectedRowKeys = ref([]);
const schedulerHasSelected = computed(() => schedulerSelectedRowKeys.value.length > 0);
const onSchedulerSelectChange = (keys) => { schedulerSelectedRowKeys.value = keys; };

const schedulerColumns = [
  { title: '策略名称', dataIndex: 'name', key: 'name', width: 150 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 150 },
  { title: 'cron表达式', dataIndex: 'cron', key: 'cron', width: 150 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '运行次数', dataIndex: 'run_number', key: 'run_number', width: 100 },
  { title: '上次运行时间', dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { title: '下次运行时间', dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { title: '操作', key: 'action', width: 280 }
];

const fetchSchedulerData = async () => {
  schedulerLoading.value = true;
  try {
    const params = { page: schedulerPagination.current, size: schedulerPagination.pageSize };
    if (schedulerSearchForm.name) params.name = schedulerSearchForm.name;
    if (schedulerSearchForm.keyword) params.keyword = schedulerSearchForm.keyword;
    if (schedulerSearchForm.status) params.status = schedulerSearchForm.status;

    const res = await request.get('/github_scheduler/', { params });
    if (res.code === 200) {
      schedulerData.value = res.items || [];
      schedulerPagination.total = res.total || 0;
      schedulerSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载监控策略失败');
  } finally {
    schedulerLoading.value = false;
  }
};

const resetSchedulerSearch = () => {
  Object.assign(schedulerSearchForm, { name: '', keyword: '', status: undefined });
  schedulerPagination.current = 1;
  onSchedulerSearch();
};
const onSchedulerSearch = () => { schedulerPagination.current = 1; fetchSchedulerData(); };
const handleSchedulerTableChange = (page, pageSize) => {
  schedulerPagination.current = page;
  schedulerPagination.pageSize = pageSize;
  fetchSchedulerData();
};

const goToSchedulerDetail = (record) => {
  openResultDrawer(record, 'scheduler');
};

const performSchedulerAction = async (actionType, idArray) => {
  try {
    const url = `/github_scheduler/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success('操作成功！');
      fetchSchedulerData();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (e) {
    message.error('请求异常');
  }
};

const handleSchedulerSingleAction = (type, id) => performSchedulerAction(type, [id]);
const handleSchedulerBatchDelete = () => performSchedulerAction('delete', schedulerSelectedRowKeys.value);
const handleSchedulerBatchStop = () => performSchedulerAction('stop', schedulerSelectedRowKeys.value);

// 策略弹窗逻辑
const schedulerModalVisible = ref(false);
const schedulerSubmitLoading = ref(false);
const schedulerIsEdit = ref(false);
const schedulerEditId = ref('');
const schedulerForm = reactive({ name: '', keyword: '', cron: '' });

const openSchedulerAdd = () => {
  schedulerIsEdit.value = false;
  schedulerEditId.value = '';
  Object.assign(schedulerForm, { name: '', keyword: '', cron: '' });
  schedulerModalVisible.value = true;
};

const openSchedulerEdit = (record) => {
  schedulerIsEdit.value = true;
  schedulerEditId.value = record._id;
  Object.assign(schedulerForm, { name: record.name, keyword: record.keyword, cron: record.cron });
  schedulerModalVisible.value = true;
};

const submitSchedulerModal = async () => {
  if (!schedulerForm.name || !schedulerForm.keyword || !schedulerForm.cron) {
    return message.warning('请填写所有必填项！');
  }
  schedulerSubmitLoading.value = true;
  try {
    let res;
    if (schedulerIsEdit.value) {
      const payload = { _id: schedulerEditId.value, ...schedulerForm };
      res = await request.post('/github_scheduler/update/', payload);
    } else {
      res = await request.post('/github_scheduler/', schedulerForm);
    }
    if (res.code === 200) {
      message.success(`${schedulerIsEdit.value ? '修改' : '添加'}策略成功！`);
      schedulerModalVisible.value = false;
      onSchedulerSearch();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (error) {
    message.error('请求异常');
  } finally {
    schedulerSubmitLoading.value = false;
  }
};


// ==========================================
// 👷 模块 B: 扫描任务实例 (github_task)
// ==========================================
const taskLoading = ref(false);
const taskData = ref([]);
const taskSearchForm = reactive({ name: '', keyword: '', status: undefined });
const taskPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const taskSelectedRowKeys = ref([]);
const taskHasSelected = computed(() => taskSelectedRowKeys.value.length > 0);
const onTaskSelectChange = (keys) => { taskSelectedRowKeys.value = keys; };

const taskColumns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 150 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 150 },
  { title: '结果数目', dataIndex: 'result_count', key: 'result_count', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 180 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 180 },
  { title: '任务id', dataIndex: '_id', key: '_id', width: 200 },
  { title: '操作', key: 'action', width: 150 }
];

const fetchTaskData = async () => {
  taskLoading.value = true;
  try {
    const params = { page: taskPagination.current, size: taskPagination.pageSize };
    if (taskSearchForm.name) params.name = taskSearchForm.name;
    if (taskSearchForm.keyword) params.keyword = taskSearchForm.keyword;
    if (taskSearchForm.status) params.status = taskSearchForm.status;

    const res = await request.get('/github_task/', { params });
    if (res.code === 200) {
      taskData.value = (res.items || []).map(item => {
        if (item.statistic && item.statistic.github_result_cnt !== undefined) {
          item.result_count = item.statistic.github_result_cnt;
        } else if (!item.result_count) {
          item.result_count = 0;
        }
        return item;
      });
      taskPagination.total = res.total || 0;
      taskSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载扫描任务失败');
  } finally {
    taskLoading.value = false;
  }
};

const resetTaskSearch = () => {
  Object.assign(taskSearchForm, { name: '', keyword: '', status: undefined });
  taskPagination.current = 1;
  onTaskSearch();
};
const onTaskSearch = () => { taskPagination.current = 1; fetchTaskData(); };
const handleTaskTableChange = (page, pageSize) => {
  taskPagination.current = page;
  taskPagination.pageSize = pageSize;
  fetchTaskData();
};

const goToTaskDetail = (record) => {
  openResultDrawer(record, 'task');
};

// ================= GitHub 任务与监控命中结果抽屉 =================
const resultDrawerVisible = ref(false);
const resultDrawerTitle = ref('');
const resultDrawerType = ref('task'); // 'task' | 'scheduler'
const resultCurrentRecord = ref(null);
const resultActiveTab = ref('result');
const resultLoading = ref(false);
const resultDataSource = ref([]);
const resultSearchForm = reactive({ path: '', repo_full_name: '', human_content: '' });
const resultPagination = reactive({ current: 1, pageSize: 10, total: 0 });

const resultColumns = [
  { title: '仓库名', dataIndex: 'repo_full_name', key: 'repo_full_name', width: 220 },
  { title: '文件路径', dataIndex: 'path', key: 'path', width: 260 },
  { title: '代码/命中内容', dataIndex: 'human_content', key: 'human_content' },
  { title: '提交/入库时间', dataIndex: 'commit_date', key: 'commit_date', width: 170 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 110 }
];

const openResultDrawer = (record, type) => {
  resultCurrentRecord.value = record;
  resultDrawerType.value = type;
  resultDrawerTitle.value = type === 'task' 
    ? `🎯 单次扫描任务结果 - ${record.name}` 
    : `🎯 周期监控命中结果 - ${record.name}`;
  resultActiveTab.value = 'result';
  resultSearchForm.path = '';
  resultSearchForm.repo_full_name = '';
  resultSearchForm.human_content = '';
  resultPagination.current = 1;
  resultDrawerVisible.value = true;
  fetchResultData();
};

const closeResultDrawer = () => {
  resultDrawerVisible.value = false;
  stopResultSyslogTimer();
};

const fetchResultData = async () => {
  if (!resultCurrentRecord.value?._id) return;
  resultLoading.value = true;
  try {
    const params = {
      page: resultPagination.current,
      size: resultPagination.pageSize
    };
    if (resultDrawerType.value === 'task') {
      params.github_task_id = resultCurrentRecord.value._id;
    } else {
      params.github_scheduler_id = resultCurrentRecord.value._id;
    }
    if (resultSearchForm.path) params.path = resultSearchForm.path;
    if (resultSearchForm.repo_full_name) params.repo_full_name = resultSearchForm.repo_full_name;
    if (resultSearchForm.human_content) params.human_content = resultSearchForm.human_content;

    const apiUrl = resultDrawerType.value === 'task' ? '/github_result/' : '/github_monitor_result/';
    const res = await request.get(apiUrl, { params });
    if (res.code === 200) {
      resultDataSource.value = res.items || [];
      resultPagination.total = res.total || 0;
    }
  } catch (e) {
    message.error('加载命中结果失败');
  } finally {
    resultLoading.value = false;
  }
};

const onResultSearch = () => {
  resultPagination.current = 1;
  fetchResultData();
};

const resetResultSearch = () => {
  resultSearchForm.path = '';
  resultSearchForm.repo_full_name = '';
  resultSearchForm.human_content = '';
  resultPagination.current = 1;
  fetchResultData();
};

const handleResultTableChange = (page, pageSize) => {
  resultPagination.current = page;
  resultPagination.pageSize = pageSize;
  fetchResultData();
};

// ================= 日志查询 (单次扫描) =================
const resultLogLoading = ref(false);
const resultLogDataSource = ref([]);
const resultTerminalContainer = ref(null);
let resultSyslogTimer = null;

const fetchResultLogData = async (isPolling = false) => {
  if (!resultCurrentRecord.value?._id || resultDrawerType.value !== 'task') return;
  if (!isPolling) resultLogLoading.value = true;
  try {
    const params = {
      size: 50000,
      task_id: resultCurrentRecord.value._id,
      order: 'create_time'
    };
    const res = await request.get('/syslog/', { params });
    if (res.code === 200) {
      resultLogDataSource.value = res.items || [];
      nextTick(() => {
        if (resultTerminalContainer.value) {
          resultTerminalContainer.value.scrollTop = resultTerminalContainer.value.scrollHeight;
        }
      });
    }
  } catch (e) {
    if (!isPolling) message.error('加载任务日志失败');
  } finally {
    if (!isPolling) resultLogLoading.value = false;
  }
};

const startResultSyslogTimer = () => {
  stopResultSyslogTimer();
  fetchResultLogData();
  resultSyslogTimer = setInterval(() => fetchResultLogData(true), 5000);
};

const stopResultSyslogTimer = () => {
  if (resultSyslogTimer) {
    clearInterval(resultSyslogTimer);
    resultSyslogTimer = null;
  }
};

watch(resultActiveTab, (tab) => {
  if (tab === 'result') {
    stopResultSyslogTimer();
    fetchResultData();
  } else if (tab === 'log') {
    startResultSyslogTimer();
  }
});

const performTaskAction = async (actionType, idArray) => {
  try {
    const url = `/github_task/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success('操作成功！');
      fetchTaskData();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (e) {
    message.error('请求异常');
  }
};

const handleTaskSingleAction = (type, id) => performTaskAction(type, [id]);
const handleTaskBatchDelete = () => performTaskAction('delete', taskSelectedRowKeys.value);
const handleTaskBatchStop = () => performTaskAction('stop', taskSelectedRowKeys.value);

const handleTaskRestart = async (record) => {
  try {
    const res = await request.post('/github_task/', { name: record.name, keyword: record.keyword });
    if (res.code === 200) {
      message.success('重启任务成功 (已下发新任务)！');
      onTaskSearch();
    } else {
      message.error('重启失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常');
  }
};

// 新增任务弹窗
const taskModalVisible = ref(false);
const taskSubmitLoading = ref(false);
const taskForm = reactive({ name: '', keyword: '' });

const openTaskAdd = () => {
  taskForm.name = '';
  taskForm.keyword = '';
  taskModalVisible.value = true;
};

const submitTaskModal = async () => {
  if (!taskForm.name || !taskForm.keyword) {
    return message.warning('请填写任务名称和关键字！');
  }
  taskSubmitLoading.value = true;
  try {
    const res = await request.post('/github_task/', taskForm);
    if (res.code === 200) {
      message.success('新建单次扫描任务成功！');
      taskModalVisible.value = false;
      onTaskSearch();
    } else {
      message.error('下发失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常');
  } finally {
    taskSubmitLoading.value = false;
  }
};

// ==========================================
// 🛠️ 模块 C: 红队工具监控 (github_tools_target)
// ==========================================
const toolsLoading = ref(false);
const toolsData = ref([]);

const toolsSearchForm = reactive({ repo_url: '' });
const appliedToolsSearchForm = reactive({ repo_url: '' });
const onToolsSearch = () => { Object.assign(appliedToolsSearchForm, toolsSearchForm); toolsPagination.current = 1; };

const filteredToolsData = computed(() => {
  return toolsData.value.filter(item => {
    if (appliedToolsSearchForm.repo_url && !item.repo_url.toLowerCase().includes(appliedToolsSearchForm.repo_url.toLowerCase())) return false;
    return true;
  });
});

const toolsPagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedToolsData = computed(() => {
  const start = (toolsPagination.current - 1) * toolsPagination.pageSize;
  return filteredToolsData.value.slice(start, start + toolsPagination.pageSize);
});
const onToolsTableChange = (page, pageSize) => { toolsPagination.current = page; toolsPagination.pageSize = pageSize; };
const resetToolsSearch = () => { toolsSearchForm.repo_url = ''; Object.assign(appliedToolsSearchForm, toolsSearchForm); toolsPagination.current = 1; };

const toolsSelectedRowKeys = ref([]);
const toolsHasSelected = computed(() => toolsSelectedRowKeys.value.length > 0);
const onToolsSelectChange = (keys) => { toolsSelectedRowKeys.value = keys; };

const handleToolsBatchDelete = async () => {
  const res = await request.post('/github_threat/tools_target/delete', { repo_urls: toolsSelectedRowKeys.value });
  if (res.code === 200) {
    message.success('批量删除成功');
    toolsSelectedRowKeys.value = [];
    fetchToolsData();
  } else {
    message.error(res.message);
  }
};

const toolModalVisible = ref(false);
const toolForm = reactive({ repo_url: '' });

const toolsColumns = [
  { title: '工具名称 / URL', dataIndex: 'repo_url', key: 'repo_url', width: 350 },
  { title: '最新版本', dataIndex: 'last_tag', key: 'last_tag', width: 120 },
  { title: '发布时间', dataIndex: 'last_commit_time', key: 'last_commit_time', width: 150 },
  { title: '入库时间', dataIndex: 'insert_time', key: 'insert_time', width: 150 },
  { title: '操作', key: 'action', width: 150 }
];

const fetchToolsData = async () => {
  toolsLoading.value = true;
  try {
    const res = await request.get('/github_threat/tools_target');
    if (res.code === 200) {
      toolsData.value = res.data || [];
    }
  } catch (error) {
    message.error('获取监控工具失败');
  } finally {
    toolsLoading.value = false;
  }
};

const handleToolDelete = async (repo_url) => {
  const res = await request.post('/github_threat/tools_target/delete', { repo_url });
  if (res.code === 200) {
    message.success('已取消监控');
    fetchToolsData();
  }
};

const openToolAdd = () => {
  toolForm.repo_url = '';
  toolModalVisible.value = true;
};

const submitToolModal = async () => {
  if (!toolForm.repo_url) return message.warning('URL 不能为空');
  const res = await request.post('/github_threat/tools_target', toolForm);
  if (res.code === 200) {
    message.success('添加成功');
    toolModalVisible.value = false;
    fetchToolsData();
  } else {
    message.error(res.message);
  }
};

// ==========================================
// 🧑‍💻 模块 D: 大佬动态监控 (github_hackers_target)
// ==========================================
const hackersLoading = ref(false);
const hackersData = ref([]);

const hackersSearchForm = reactive({ github_id: '' });
const appliedHackersSearchForm = reactive({ github_id: '' });
const onHackersSearch = () => { Object.assign(appliedHackersSearchForm, hackersSearchForm); hackersPagination.current = 1; };

const filteredHackersData = computed(() => {
  return hackersData.value.filter(item => {
    if (appliedHackersSearchForm.github_id && !item.github_id.toLowerCase().includes(appliedHackersSearchForm.github_id.toLowerCase())) return false;
    return true;
  });
});

const hackersPagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedHackersData = computed(() => {
  const start = (hackersPagination.current - 1) * hackersPagination.pageSize;
  return filteredHackersData.value.slice(start, start + hackersPagination.pageSize);
});
const onHackersTableChange = (page, pageSize) => { hackersPagination.current = page; hackersPagination.pageSize = pageSize; };
const resetHackersSearch = () => { hackersSearchForm.github_id = ''; Object.assign(appliedHackersSearchForm, hackersSearchForm); hackersPagination.current = 1; };

const hackersSelectedRowKeys = ref([]);
const hackersHasSelected = computed(() => hackersSelectedRowKeys.value.length > 0);
const onHackersSelectChange = (keys) => { hackersSelectedRowKeys.value = keys; };

const handleHackersBatchDelete = async () => {
  const res = await request.post('/github_threat/hackers_target/delete', { github_ids: hackersSelectedRowKeys.value });
  if (res.code === 200) {
    message.success('批量删除成功');
    hackersSelectedRowKeys.value = [];
    fetchHackersData();
  } else {
    message.error(res.message);
  }
};

const hackerModalVisible = ref(false);
const hackerForm = reactive({ github_id: '' });

const historyDrawerVisible = ref(false);
const historyLoading = ref(false);
const hackersHistoryData = ref([]);

const hackersColumns = [
  { title: 'Github ID (大牛/团队)', dataIndex: 'github_id', key: 'github_id', width: 250 },
  { title: '已发现开源工具数', dataIndex: 'found_count', key: 'found_count', width: 180 },
  { title: '监控添加时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { title: '操作', key: 'action', width: 150 }
];

const historyColumns = [
  { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { title: '工具仓库路径', dataIndex: 'full_name', key: 'full_name' }
];

const openHackersHistoryDrawer = () => {
  historyDrawerVisible.value = true;
  fetchHackersHistory();
};

const closeHackersHistoryDrawer = () => {
  historyDrawerVisible.value = false;
};

const fetchHackersHistory = async () => {
  historyLoading.value = true;
  try {
    const res = await request.get('/github_threat/hackers_history');
    if (res.code === 200) {
      hackersHistoryData.value = res.data || [];
    }
  } catch (error) {
    message.error('加载发现记录失败');
  } finally {
    historyLoading.value = false;
  }
};

const fetchHackersData = async () => {
  hackersLoading.value = true;
  try {
    const res = await request.get('/github_threat/hackers_target');
    if (res.code === 200) {
      hackersData.value = res.data || [];
    }
  } catch (error) {
    message.error('获取监控大牛失败');
  } finally {
    hackersLoading.value = false;
  }
};

const handleHackerDelete = async (github_id) => {
  const res = await request.post('/github_threat/hackers_target/delete', { github_id });
  if (res.code === 200) {
    message.success('已取消监控');
    fetchHackersData();
  }
};

const openHackerAdd = () => {
  hackerForm.github_id = '';
  hackerModalVisible.value = true;
};

const submitHackerModal = async () => {
  if (!hackerForm.github_id) return message.warning('ID 不能为空');
  const res = await request.post('/github_threat/hackers_target', hackerForm);
  if (res.code === 200) {
    message.success('添加成功');
    hackerModalVisible.value = false;
    fetchHackersData();
  } else {
    message.error(res.message);
  }
};

// ==========================================
// 🛡️ 模块 E: CVE 监控历史 (github_cve_history)
// ==========================================
const cveLoading = ref(false);
const cveData = ref([]);

const cveSearchForm = reactive({ cve_name: '', desc: '' });
const appliedCveSearchForm = reactive({ cve_name: '', desc: '' });
const onCveSearch = () => { Object.assign(appliedCveSearchForm, cveSearchForm); cvePagination.current = 1; };

const filteredCveData = computed(() => {
  return cveData.value.filter(item => {
    if (appliedCveSearchForm.cve_name && !item.cve_name.toLowerCase().includes(appliedCveSearchForm.cve_name.toLowerCase())) return false;
    if (appliedCveSearchForm.desc && !item.desc.toLowerCase().includes(appliedCveSearchForm.desc.toLowerCase())) return false;
    return true;
  });
});

const cvePagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedCveData = computed(() => {
  const start = (cvePagination.current - 1) * cvePagination.pageSize;
  return filteredCveData.value.slice(start, start + cvePagination.pageSize);
});
const onCveTableChange = (page, pageSize) => { cvePagination.current = page; cvePagination.pageSize = pageSize; };
const resetCveSearch = () => { cveSearchForm.cve_name = ''; cveSearchForm.desc = ''; Object.assign(appliedCveSearchForm, cveSearchForm); cvePagination.current = 1; };

const cveSelectedRowKeys = ref([]);
const cveHasSelected = computed(() => cveSelectedRowKeys.value.length > 0);
const onCveSelectChange = (keys) => { cveSelectedRowKeys.value = keys; };

const handleCveBatchDelete = async () => {
  const res = await request.post('/github_threat/cve_history/delete', { cve_names: cveSelectedRowKeys.value });
  if (res.code === 200) {
    message.success('批量删除成功');
    cveSelectedRowKeys.value = [];
    fetchCveData();
  } else {
    message.error(res.message);
  }
};

const handleCveDelete = async (cve_name) => {
  const res = await request.post('/github_threat/cve_history/delete', { cve_name });
  if (res.code === 200) {
    message.success('删除成功');
    fetchCveData();
  } else {
    message.error(res.message);
  }
};


const cveColumns = [
  { title: 'CVE 编号', dataIndex: 'cve_name', key: 'cve_name', width: 150 },
  { title: 'Github 地址', dataIndex: 'cve_url', key: 'cve_url', width: 250 },
  { title: '官方描述', dataIndex: 'desc', key: 'desc', width: 450 },
  { title: '最近推送', dataIndex: 'pushed_at', key: 'pushed_at', width: 120 },
  { title: '收录时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { title: '操作', key: 'action', width: 100 }
];

const fetchCveData = async () => {
  cveLoading.value = true;
  try {
    const res = await request.get('/github_threat/cve_history');
    if (res.code === 200) {
      cveData.value = res.data || [];
    }
  } catch (error) {
    message.error('获取 CVE 监控记录失败');
  } finally {
    cveLoading.value = false;
  }
};

const cveConfig = reactive({ enabled: false, interval: 6, is_running: false });
const cveRunLoading = ref(false);

const fetchCveConfig = async () => {
  try {
    const res = await request.get('/github_threat/cve_config');
    if (res.code === 200) {
      cveConfig.enabled = res.data.enabled;
      cveConfig.interval = res.data.interval;
      cveConfig.is_running = !!res.data.is_running;
    }
  } catch (error) {
    console.error(error);
  }
};

const saveCveConfig = async () => {
  try {
    const res = await request.post('/github_threat/cve_config', cveConfig);
    if (res.code === 200) {
      message.success('配置已保存');
    } else {
      message.error(res.message || '配置保存失败');
    }
  } catch (error) {
    message.error('配置保存失败');
  }
};

const runCveOnce = async () => {
  cveRunLoading.value = true;
  try {
    const res = await request.post('/github_threat/cve_run_once');
    if (res.code === 200) {
      message.success(res.data?.msg || 'CVE 监控任务已成功提交至后台队列！');
      cveConfig.is_running = true;
      fetchCveConfig();
      fetchCveData();
    } else {
      message.warning(res.data?.msg || res.message || '运行受阻');
    }
  } catch (error) {
    message.error('请求失败');
  } finally {
    cveRunLoading.value = false;
  }
};

const tokenStatus = reactive({ status: '', msg: '' });
const fetchTokenStatus = async () => {
  try {
    const res = await request.get('/github_threat/token_status');
    if (res.code === 200) {
      tokenStatus.status = res.data.status;
      tokenStatus.msg = res.data.msg;
    }
  } catch (error) {
    console.error(error);
  }
};

const toolsConfig = reactive({ enabled: false, interval: 6, is_running: false });
const toolsRunLoading = ref(false);
const hackersConfig = reactive({ enabled: false, interval: 6, is_running: false });
const hackersRunLoading = ref(false);

const fetchToolsConfig = async () => {
  try {
    const res = await request.get('/github_threat/tools_config');
    if (res.code === 200) {
      toolsConfig.enabled = res.data.enabled;
      toolsConfig.interval = res.data.interval;
      toolsConfig.is_running = !!res.data.is_running;
    }
  } catch (error) {
    console.error(error);
  }
};

const saveToolsConfig = async () => {
  try {
    const res = await request.post('/github_threat/tools_config', toolsConfig);
    if (res.code === 200) {
      message.success('配置已保存');
    } else {
      message.error(res.message || '配置保存失败');
    }
  } catch (error) {
    message.error('配置保存失败');
  }
};

const runToolsOnce = async () => {
  toolsRunLoading.value = true;
  try {
    const res = await request.post('/github_threat/tools_run_once');
    if (res.code === 200) {
      message.success(res.data?.msg || '安全工具监控任务已成功提交至后台队列！');
      toolsConfig.is_running = true;
      fetchToolsConfig();
      fetchToolsData();
    } else {
      message.warning(res.data?.msg || res.message || '运行受阻');
    }
  } catch (error) {
    message.error('请求失败');
  } finally {
    toolsRunLoading.value = false;
  }
};

const fetchHackersConfig = async () => {
  try {
    const res = await request.get('/github_threat/hackers_config');
    if (res.code === 200) {
      hackersConfig.enabled = res.data.enabled;
      hackersConfig.interval = res.data.interval;
      hackersConfig.is_running = !!res.data.is_running;
    }
  } catch (error) {
    console.error(error);
  }
};

const saveHackersConfig = async () => {
  try {
    const res = await request.post('/github_threat/hackers_config', hackersConfig);
    if (res.code === 200) {
      message.success('配置已保存');
    } else {
      message.error(res.message || '配置保存失败');
    }
  } catch (error) {
    message.error('配置保存失败');
  }
};

const runHackersOnce = async () => {
  hackersRunLoading.value = true;
  try {
    const res = await request.post('/github_threat/hackers_run_once');
    if (res.code === 200) {
      message.success(res.data?.msg || '黑客动态监控任务已成功提交至后台队列！');
      hackersConfig.is_running = true;
      fetchHackersConfig();
      fetchHackersData();
    } else {
      message.warning(res.data?.msg || res.message || '运行受阻');
    }
  } catch (error) {
    message.error('请求失败');
  } finally {
    hackersRunLoading.value = false;
  }
};

onDeactivated(() => {
  historyDrawerVisible.value = false;
  schedulerModalVisible.value = false;
  taskModalVisible.value = false;
  toolModalVisible.value = false;
  hackerModalVisible.value = false;
  resultDrawerVisible.value = false;
  stopResultSyslogTimer();
});

onUnmounted(() => {
  stopResultSyslogTimer();
});
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: var(--arl-text-color); margin-right: 8px; min-width: 70px; text-align: right; white-space: nowrap; }
</style>
