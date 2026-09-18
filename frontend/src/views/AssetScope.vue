<template>
  <div style="min-height: calc(100vh - 96px); background-color: var(--arl-bg-layout); position: relative;">
    <!-- 隐形定位锚点 (用于精准定位 fixed 侧边栏左边界) -->
    <div ref="sidebarAnchorRef" style="position: absolute; top: 0; left: 0; width: 0; height: 0; pointer-events: none;"></div>

    <!-- 左侧集团分组固定侧边栏 (Fixed 视口绝对锁定，绝不随页面滚动) -->
    <div
      class="asset-group-sidebar"
      :style="{
        position: 'fixed',
        top: '80px',
        bottom: '16px',
        left: (sidebarLeft || 186) + 'px',
        width: isSidebarCollapsed ? '0px' : '240px',
        overflow: 'hidden',
        opacity: isSidebarCollapsed ? 0 : 1,
        transition: 'width 0.25s, opacity 0.25s, left 0.2s',
        background: 'var(--arl-bg-white)',
        borderRight: isSidebarCollapsed ? 'none' : '1px solid var(--arl-border-color)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 15,
        boxShadow: isSidebarCollapsed ? 'none' : '2px 0 8px rgba(0,0,0,0.03)'
      }"
    >
      <div class="sidebar-header">
        <div style="display: flex; align-items: center; gap: 8px;">
          <ApartmentOutlined style="font-size: 16px; color: var(--arl-theme-color);" />
          <span style="font-weight: 600; font-size: 15px; color: var(--arl-text-color);">集团分组</span>
          <span class="sidebar-total-badge">{{ groupList.length }}</span>
        </div>
        <a-tooltip title="新建集团">
          <a-button type="text" size="small" class="sidebar-add-btn" @click="openAddEnterpriseGroupModal">
            <plus-outlined />
          </a-button>
        </a-tooltip>
      </div>
      <div class="sidebar-search-container">
        <a-input v-model:value="groupSearchKey" placeholder="搜索集团..." allowClear size="small">
          <template #prefix><search-outlined style="color: var(--arl-text-color); opacity: 0.35;" /></template>
        </a-input>
      </div>
      <div style="flex: 1; min-height: 0; overflow-y: auto; padding: 6px 0;">
        <a-menu
          mode="inline"
          :selectedKeys="[activeGroupId]"
          @click="handleGroupSwitch"
          class="sidebar-group-menu"
          style="border-right: none;"
        >
          <a-menu-item key="all">
            <template #icon><appstore-outlined /></template>
            全部资产组
          </a-menu-item>
          <a-menu-item key="unassigned">
            <template #icon><inbox-outlined /></template>
            未分组
          </a-menu-item>
          <a-menu-divider style="margin: 4px 12px;" />
          <a-menu-item v-for="group in filteredGroupList" :key="group._id">
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
              <span class="group-name-text" :title="group.name" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; margin-right: 8px;">{{ group.name }}</span>
              <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
                <span class="sidebar-scope-pill">
                  {{ group.scope_count || 0 }}
                </span>
                <a-dropdown :trigger="['click']" :getPopupContainer="getBodyContainer">
                  <span class="group-action-icon" @click.stop><more-outlined /></span>
                  <template #overlay>
                    <a-menu @click="(e) => handleGroupAction(e, group)">
                      <a-menu-item key="edit">重命名</a-menu-item>
                      <a-menu-item key="delete" style="color: #ff4d4f;">删除</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
            </div>
          </a-menu-item>
        </a-menu>
        <div v-if="groupSearchKey && filteredGroupList.length === 0" style="padding: 24px 16px; text-align: center; color: var(--arl-text-color); opacity: 0.5; font-size: 12px;">
          <div>未找到匹配集团</div>
          <a-button type="link" size="small" style="font-size: 11px; padding: 0; margin-top: 4px;" @click="groupSearchKey = ''">清空搜索</a-button>
        </div>
      </div>
    </div>

    <!-- 侧边栏折叠把手（展开态：垂直居中悬浮在 Fixed 侧边栏右边缘） -->
    <div 
      v-if="!isSidebarCollapsed" 
      @click="isSidebarCollapsed = true" 
      :style="{
        position: 'fixed',
        top: '50%',
        transform: 'translateY(-50%)',
        left: ((sidebarLeft || 186) + 240) + 'px',
        width: '14px',
        height: '44px',
        background: 'var(--arl-bg-white)',
        border: '1px solid var(--arl-border-color)',
        borderLeft: 'none',
        borderRadius: '0 6px 6px 0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        zIndex: 16,
        boxShadow: '2px 0 8px rgba(0,0,0,0.06)',
        transition: 'left 0.2s ease, background 0.2s'
      }"
      class="sidebar-collapse-handle"
      title="收起集团分组"
    >
      <left-outlined style="font-size: 10px; color: var(--arl-text-color); opacity: 0.65;" />
    </div>

    <!-- 侧边栏展开把手（收起态：细条垂直居中，高度撑满） -->
    <div 
      v-if="isSidebarCollapsed" 
      @click="isSidebarCollapsed = false" 
      :style="{
        position: 'fixed',
        top: '80px',
        bottom: '16px',
        left: (sidebarLeft || 186) + 'px',
        width: '26px',
        background: 'var(--arl-bg-white)',
        borderRight: '1px solid var(--arl-border-color)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        zIndex: 15
      }"
      class="sidebar-expand-handle"
      title="展开集团分组"
    >
      <right-outlined style="font-size: 11px; color: var(--arl-text-color); opacity: 0.65;" />
      <span style="writing-mode: vertical-lr; font-size: 11px; letter-spacing: 2px; color: var(--arl-text-color); opacity: 0.65;">集团</span>
    </div>

    <!-- 右侧主工作区 (现代化一体卡片容器) -->
    <div 
      :style="{
        marginLeft: isSidebarCollapsed ? '34px' : '248px',
        transition: 'margin-left 0.25s ease',
        padding: '16px 20px',
        minWidth: 0,
        position: 'relative'
      }"
    >
      <div class="arl-scope-main-card">
        <!-- 头部吸附操作区 (含标题、全局搜索与批量操作) -->
        <div ref="actionBarRef" class="arl-scope-action-bar">

          <!-- 顶行：标题与快捷操作按钮 -->
          <div class="scope-header-top">
            <div class="scope-title-area">
              <a-breadcrumb v-if="isSidebarCollapsed">
                <a-breadcrumb-item>资产分组</a-breadcrumb-item>
                <a-breadcrumb-item>
                  <a-dropdown :getPopupContainer="getBodyContainer">
                    <span class="group-switch-trigger">
                      {{ currentGroupName }} <down-outlined style="font-size: 10px;" />
                    </span>
                    <template #overlay>
                      <a-menu :selectedKeys="[activeGroupId]" @click="handleGroupSwitch">
                        <a-menu-item key="all">全部资产组</a-menu-item>
                        <a-menu-item key="unassigned">未分组</a-menu-item>
                        <a-menu-divider />
                        <a-menu-item v-for="g in groupList" :key="g._id">{{ g.name }}</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-breadcrumb-item>
              </a-breadcrumb>
              <div v-else class="scope-title-wrap">
                <span class="scope-title-text">{{ currentGroupName }}</span>
                <span class="scope-total-tag" v-if="pagination.total !== undefined">共 {{ pagination.total }} 个资产组</span>
              </div>
            </div>
            <div class="scope-header-actions">
              <a-button @click="reconDrawerVisible = true" class="header-action-btn">
                <ApartmentOutlined /> 企业测绘任务
              </a-button>
              <a-button type="primary" @click="openAddModal" class="header-action-btn">
                <PlusOutlined /> 新建资产分组
              </a-button>
            </div>
          </div>

          <!-- 筛选表单栏 -->
          <div class="scope-filter-toolbar">
            <a-form :model="searchForm" layout="inline" class="scope-filter-form" @submit.prevent>
              <a-form-item label="资产组名称">
                <a-input v-model:value="searchForm.name" placeholder="输入名称搜索" style="width: 170px;" allowClear @pressEnter="onSearch" />
              </a-form-item>
              <a-form-item label="资产范围">
                <a-input v-model:value="searchForm.scope" placeholder="输入域名/IP搜索" style="width: 175px;" allowClear @pressEnter="onSearch" />
              </a-form-item>
              <a-form-item label="资产范围ID">
                <a-input v-model:value="searchForm._id" placeholder="输入ID搜索" style="width: 170px;" allowClear @pressEnter="onSearch" />
              </a-form-item>
              <a-form-item class="filter-actions-item">
                <a-space size="small">
                  <a-button type="primary" @click="onSearch">
                    <SearchOutlined /> 查 询
                  </a-button>
                  <a-button @click="resetSearch">
                    <ReloadOutlined /> 重 置
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </div>

          <!-- 批量操作栏与选中信息条 -->
          <div class="scope-batch-toolbar">
            <div class="batch-buttons-group">
              <a-button :disabled="!hasSelected" @click="openBatchMoveModal">
                <FolderOpenOutlined /> 批量移动至集团
              </a-button>
              <a-button danger :disabled="!hasSelected" @click="handleBatchDelete">
                <DeleteOutlined /> 批量删除
              </a-button>
              <a-dropdown :disabled="!hasSelected" :getPopupContainer="getBodyContainer">
                <template #overlay>
                  <a-menu @click="handleBatchExport">
                    <a-menu-item key="asset_domain">域名批量导出</a-menu-item>
                    <a-menu-item key="asset_ip">IP 批量导出</a-menu-item>
                    <a-menu-item key="asset_site">站点批量导出</a-menu-item>
                    <a-menu-item key="asset_wih">WIH批量导出</a-menu-item>
                  </a-menu>
                </template>
                <a-button>
                  批量导出 <DownOutlined />
                </a-button>
              </a-dropdown>
            </div>

            <div v-if="hasSelected" class="selection-indicator">
              <InfoCircleOutlined style="color: var(--arl-theme-color);" />
              <span>已勾选 <strong>{{ selectedRowKeys.length }}</strong> 项</span>
              <a-button type="link" size="small" @click="selectedRowKeys = []" style="padding: 0 4px;">清空已选</a-button>
            </div>
          </div>

        </div>

        <a-table 
          :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
          :loading="loading"
          :dataSource="dataSource"
          :columns="columns"
          :pagination="false"
          :scroll="{ x: 1360 }"
          bordered
          class="arl-scope-table"
          size="middle"
          :rowKey="(record) => record._id"
        >
          <template #bodyCell="{ column, record }">

            <template v-if="column.key === 'name'">
              <div class="group-name-cell">
                <div class="group-name-title-row">
                  <a class="group-name-title" @click="goToDetail(record)">{{ record.name }}</a>
                  <a-badge v-if="record.has_increment" count="增量" :number-style="{ backgroundColor: '#52c41a', fontSize: '10px' }" />
                </div>
                <div v-if="record.enterprise_name" class="enterprise-tag-row">
                  <a-tag color="cyan" size="small" class="enterprise-osint-tag" @click.stop="goToOsintDetail(record)">
                    <BankOutlined style="margin-right: 2px;" />{{ record.enterprise_name }}
                  </a-tag>
                </div>
              </div>
            </template>

            <template v-else-if="column.key === 'group_name'">
              <a-tag v-if="record.group_name" color="blue" class="group-cell-tag" @click="activeGroupId = record.group_id">
                {{ record.group_name }}
              </a-tag>
              <span v-else style="color: var(--arl-text-color); opacity: 0.45;">-</span>
            </template>

            <template v-else-if="column.key === 'scope_array'">
              <div class="domain-scope-tags-wrapper">
                <a-tooltip
                  v-for="(item, idx) in (record._sorted_scopes || record.scope_array || []).slice(0, 5)"
                  :key="idx"
                  placement="topLeft"
                  :getPopupContainer="getBodyContainer"
                >
                  <template #title>
                    <div style="font-size: 12px; line-height: 1.6; padding: 2px;">
                      <div><b>目标:</b> {{ item }}</div>
                      <div><b>状态:</b> {{ getDomainStatusLabel(record, item) }}</div>
                      <template v-if="record.domain_status?.[item]?.sync_source === 'icp'">
                        <div style="color: #69c0ff;"><b>来源:</b> 企业资产查询</div>
                        <div v-if="record.domain_status?.[item]?.task_name"><b>关联任务:</b> {{ record.domain_status[item].task_name }}</div>
                        <div v-if="record.domain_status?.[item]?.sync_time"><b>同步时间:</b> {{ record.domain_status[item].sync_time }}</div>
                        <div v-if="record.domain_status?.[item]?.task_id" style="margin-top: 4px; border-top: 1px dashed rgba(255,255,255,0.3); padding-top: 4px;">
                          <a style="color: #40a9ff; font-weight: 500;" @click="goToReconDetail(record.domain_status[item].task_id)">
                            查看企业资产任务详情 &rarr;
                          </a>
                        </div>
                      </template>
                      <div v-else-if="record.domain_status?.[item]?.sync_time">
                        <b>更新时间:</b> {{ record.domain_status[item].sync_time }}
                      </div>
                    </div>
                  </template>
                  <a-tag
                    closable
                    class="domain-scope-item-tag"
                    @close="(e) => { e.preventDefault(); handleRemoveSingleScope(record, item); }"
                    :style="getDomainTagStyle(record, item)"
                  >
                    <span class="domain-status-dot" :class="'status-' + getDomainStatus(record, item)"></span>
                    <span v-if="record.domain_status?.[item]?.sync_source === 'icp'" style="color: var(--arl-theme-color); margin-right: 3px; font-size: 11px;" title="来自企业资产同步">⚑</span>
                    <span class="domain-name-text">{{ item }}</span>
                  </a-tag>
                </a-tooltip>
                <a-popover v-if="(record.scope_array || []).length > 5" placement="bottomLeft" :getPopupContainer="getBodyContainer">
                  <template #content>
                    <div style="max-width: 440px; max-height: 300px; overflow-y: auto; display: flex; flex-wrap: wrap; gap: 6px; padding: 6px;">
                      <a-tooltip
                        v-for="(item, idx) in (record._sorted_scopes || record.scope_array || []).slice(5)"
                        :key="idx"
                        placement="topLeft"
                        :getPopupContainer="getBodyContainer"
                      >
                        <template #title>
                          <div style="font-size: 12px; line-height: 1.6; padding: 2px;">
                            <div><b>目标:</b> {{ item }}</div>
                            <div><b>状态:</b> {{ getDomainStatusLabel(record, item) }}</div>
                            <template v-if="record.domain_status?.[item]?.sync_source === 'icp'">
                              <div style="color: #69c0ff;"><b>来源:</b> 企业资产查询</div>
                              <div v-if="record.domain_status?.[item]?.task_name"><b>关联任务:</b> {{ record.domain_status[item].task_name }}</div>
                              <div v-if="record.domain_status?.[item]?.sync_time"><b>同步时间:</b> {{ record.domain_status[item].sync_time }}</div>
                              <div v-if="record.domain_status?.[item]?.task_id" style="margin-top: 4px; border-top: 1px dashed rgba(255,255,255,0.3); padding-top: 4px;">
                                <a style="color: #40a9ff; font-weight: 500;" @click="goToReconDetail(record.domain_status[item].task_id)">
                                  查看企业资产任务详情 &rarr;
                                </a>
                              </div>
                            </template>
                            <div v-else-if="record.domain_status?.[item]?.sync_time">
                              <b>更新时间:</b> {{ record.domain_status[item].sync_time }}
                            </div>
                          </div>
                        </template>
                        <a-tag
                          closable
                          class="domain-scope-item-tag"
                          @close="(e) => { e.preventDefault(); handleRemoveSingleScope(record, item); }"
                          :style="getDomainTagStyle(record, item)"
                        >
                          <span class="domain-status-dot" :class="'status-' + getDomainStatus(record, item)"></span>
                          <span v-if="record.domain_status?.[item]?.sync_source === 'icp'" style="color: var(--arl-theme-color); margin-right: 3px; font-size: 11px;" title="来自企业资产同步">⚑</span>
                          <span class="domain-name-text">{{ item }}</span>
                        </a-tag>
                      </a-tooltip>
                    </div>
                  </template>
                  <a-tag class="domain-scope-more-tag">
                    +{{ record.scope_array.length - 5 }} 更多
                  </a-tag>
                </a-popover>
                <a-tag 
                  class="domain-scope-add-tag" 
                  @click="openEditGroupModal(record)"
                >
                  <plus-outlined /> 添加
                </a-tag>
              </div>
            </template>

            <template v-else-if="column.key === 'domain_stat'">
              <a-tooltip
                v-if="record.domain_stat && record.domain_stat.total > 0"
                placement="top"
              >
                <template #title>
                  <div style="line-height: 1.8;">
                    <div>总资产范围数: <strong>{{ record.domain_stat.total }}</strong></div>
                    <div v-if="record.domain_stat.scanning > 0">探测中数量: <strong style="color: #1890ff;">{{ record.domain_stat.scanning }}</strong></div>
                    <div>已探测数量: <strong style="color: #52c41a;">{{ record.domain_stat.probed }}</strong> ({{ Math.round((record.domain_stat.probed / record.domain_stat.total) * 100) }}%)</div>
                    <div v-if="record.domain_stat.unprobed > 0">待探测数量: <strong style="color: #faad14;">{{ record.domain_stat.unprobed }}</strong></div>
                    <div v-if="record.domain_stat.error > 0">探测异常数量: <strong style="color: #ff4d4f;">{{ record.domain_stat.error }}</strong></div>
                  </div>
                </template>
                <div class="stat-badge-group">
                  <span v-if="record.domain_stat.scanning > 0" class="stat-pill-badge badge-scanning">
                    {{ record.domain_stat.scanning }} 探测中
                  </span>
                  <span v-if="record.domain_stat.probed > 0 || (!record.domain_stat.scanning && !record.domain_stat.unprobed)" class="stat-pill-badge badge-probed">
                    {{ record.domain_stat.probed }} 已测
                  </span>
                  <span v-if="record.domain_stat.unprobed > 0" class="stat-pill-badge badge-unprobed">
                    {{ record.domain_stat.unprobed }} 待测
                  </span>
                  <span v-if="record.domain_stat.error > 0" class="stat-pill-badge badge-error">
                    {{ record.domain_stat.error }} 异常
                  </span>
                </div>
              </a-tooltip>
              <span v-else style="color: var(--arl-text-color); opacity: 0.45;">-</span>
            </template>

            <template v-else-if="column.key === 'scope_id'">
              <div style="display: flex; align-items: center; gap: 8px;">
                <a class="scope-id-text" @click="goToDetail(record)">{{ record._id }}</a>
                <a-tooltip title="复制所有资产范围">
                  <copy-outlined
                    class="copy-id-icon"
                    @click="copyText(record.scope_array ? record.scope_array.join('\n') : '')"
                  />
                </a-tooltip>
              </div>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="table-actions-container">
                <a-button type="link" size="small" class="grid-action-btn" @click="openEditGroupModal(record)">
                  <EditOutlined />编辑
                </a-button>
                <a-button v-if="record.has_increment" type="link" size="small" class="grid-action-btn btn-success" @click="openSyncIncrement(record)">
                  <SyncOutlined />增量
                </a-button>
                <a-button v-else-if="!record.synced_icp_task_id" type="link" size="small" class="grid-action-btn btn-theme" @click="openBindEnterprise(record)">
                  <LinkOutlined />绑定企业
                </a-button>
                <a-button type="link" size="small" class="grid-action-btn" @click="openAddMonitorModal(record)">
                  <DashboardOutlined />资产监控
                </a-button>
                <a-button type="link" size="small" class="grid-action-btn" @click="openAddSiteMonitorModal(record)">
                  <GlobalOutlined />站点监控
                </a-button>
                <a-button type="link" size="small" class="grid-action-btn" @click="openAddWihMonitorModal(record)">
                  <RadarChartOutlined />WIH
                </a-button>
                <a-button type="link" danger size="small" class="grid-action-btn btn-danger" @click="handleSingleDelete(record)">
                  <DeleteOutlined />删除
                </a-button>
              </div>
            </template>

          </template>
        </a-table>

        <div class="table-pagination-footer">
          <div class="pagination-summary">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
          <a-pagination 
            :pageSizeOptions="$pageSizeOptions" 
            v-model:current="pagination.current" 
            v-model:pageSize="pagination.pageSize" 
            :total="pagination.total" 
            show-size-changer 
            @change="handleTableChange" 
            @showSizeChange="handleTableChange" 
          />
        </div>
      </div>

    <!-- 新建资产分组弹窗 -->
    <a-modal
      v-model:open="addModalVisible"
      title="新建资产分组"
      :width="creationMode === 'wizard' && wizardStep === 2 ? '780px' : '580px'"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :footer="creationMode === 'wizard' ? null : undefined"
      @ok="handleAddSubmit"
      :confirmLoading="addLoading"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <div style="margin-bottom: 20px; text-align: center;">
        <a-radio-group v-model:value="creationMode" button-style="solid" size="middle">
          <a-radio-button value="manual">✍️ 手工录入</a-radio-button>
          <a-radio-button value="wizard">🏢 自动测绘</a-radio-button>
        </a-radio-group>
      </div>

      <!-- 手工录入模式 -->
      <a-form
        v-if="creationMode === 'manual'"
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        :label-col="{ span: 5 }"
        :wrapper-col="{ span: 18 }"
        style="margin-top: 10px;"
      >
        <a-form-item label="所属集团" name="group_id">
          <a-select v-model:value="addForm.group_id" placeholder="请选择所属集团（可选）" allowClear :getPopupContainer="(trigger) => trigger.parentNode">
            <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="资产组名称" name="name">
          <a-input v-model:value="addForm.name" placeholder="请输入资产组名称" />
        </a-form-item>

        <a-form-item label="资产范围" name="scope">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.65;">输入目标或从已有任务导入</span>
            <a-button type="link" size="small" style="padding: 0; height: auto;" @click="openIcpImportModal('add')">
              <cloud-download-outlined /> 从企业资产任务导入
            </a-button>
          </div>
          <a-textarea
            v-model:value="addForm.scope"
            :rows="5"
            placeholder="请输入资产范围（支持同时混填 IP、CIDR 与域名，如: 1.1.1.1, baidu.com, 192.168.1.0/24），多个请用逗号或换行分隔"
            style="font-family: monospace; font-size: 13px;"
          />
        </a-form-item>
      </a-form>

      <!-- 企业测绘向导模式 -->
      <div v-else-if="creationMode === 'wizard'">
        <!-- Stage 1: 测绘检索表单 -->
        <div v-if="wizardStep === 1">
          <a-spin :spinning="wizardLoading" :tip="wizardLoadingTip">
            <a-form
              ref="wizardFormRef"
              :model="wizardForm"
              :label-col="{ span: 5 }"
              :wrapper-col="{ span: 18 }"
              style="margin-top: 10px;"
            >
              <a-form-item label="测绘引擎">
                <a-radio-group v-model:value="wizardForm.engine">
                  <a-radio value="tyc">天眼查工商测绘 (推荐)</a-radio>
                  <a-radio value="icp">工信部ICP备案</a-radio>
                </a-radio-group>
              </a-form-item>

              <a-form-item
                v-if="wizardForm.engine === 'tyc'"
                label="公司ID (TYC_id)"
                required
                tooltip="可在天眼查企业详情页 URL 中获取，例如 https://www.tianyancha.com/company/25174642 中的 25174642"
              >
                <a-input
                  v-model:value="wizardForm.target"
                  placeholder="请输入天眼查公司 ID（纯数字/字母，例如：25174642）"
                  @pressEnter="startWizardRecon"
                />
              </a-form-item>

              <a-form-item
                v-else
                label="企业目标"
                required
              >
                <a-input
                  v-model:value="wizardForm.target"
                  placeholder="请输入企业全称或主域名（如：腾讯科技 或 qq.com）"
                  @pressEnter="startWizardRecon"
                />
              </a-form-item>

              <a-form-item
                label="分组名称"
                :required="wizardForm.engine === 'tyc'"
              >
                <a-input
                  v-model:value="wizardForm.name"
                  :placeholder="wizardForm.engine === 'tyc' ? '请输入分组/企业名称（如：腾讯科技）' : (wizardForm.target ? wizardForm.target : '若留空则自动采用企业目标名称')"
                />
              </a-form-item>

              <a-form-item label="所属集团">
                <a-select v-model:value="wizardForm.group_id" placeholder="请选择所属集团（可选）" allowClear :getPopupContainer="(trigger) => trigger.parentNode">
                  <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
                </a-select>
              </a-form-item>

              <template v-if="wizardForm.engine === 'tyc'">
                <a-form-item label="投资层级">
                  <a-input-number v-model:value="wizardForm.depth" :min="1" :max="3" style="width: 120px;" addon-after="层" />
                </a-form-item>
                <a-form-item label="投资比例">
                  <a-input-number v-model:value="wizardForm.invest_ratio" :min="1" :max="100" style="width: 120px;" addon-after="%" />
                </a-form-item>
              </template>

              <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px;">
                <a-button @click="addModalVisible = false">取 消</a-button>
                <a-button type="primary" :loading="wizardLoading" @click="startWizardRecon">
                  开始检索并解析 &rarr;
                </a-button>
              </div>
            </a-form>
          </a-spin>
        </div>

        <!-- Stage 2: 域名挑选与创建入库 -->
        <div v-else-if="wizardStep === 2">
          <div style="margin-bottom: 14px;">
            <a-alert
              type="success"
              show-icon
              :message="`企业测绘检索完成！共发现 ${wizardDomains.length} 个网站域名`"
              :description="`所属集团：${getGroupName(wizardForm.group_id) || '未分组'} | 资产组名称：${wizardForm.name.trim() || (wizardForm.engine === 'tyc' ? 'TYC_' + wizardForm.target.trim() : wizardForm.target.trim())}`"
            />
          </div>

          <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; gap: 6px; align-items: center;">
              <a-input v-model:value="wizardDomainSearch" placeholder="过滤域名..." size="small" style="width: 160px;" allowClear />
              <a-button size="small" @click="selectAllWizardDomains">全选</a-button>
              <a-button size="small" @click="selectedWizardDomains = []">清空</a-button>
            </div>
            <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7;">
              已勾选 <b style="color: var(--arl-theme-color);">{{ selectedWizardDomains.length }}</b> / {{ wizardDomains.length }} 项
            </span>
          </div>

          <div style="max-height: 200px; overflow-y: auto; border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 8px; background: var(--arl-bg-light); display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px;">
            <div v-for="d in filteredWizardDomains" :key="d" style="display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; background: var(--arl-bg-white); border-radius: 4px; font-family: monospace; font-size: 12px;">
              <a-checkbox :checked="selectedWizardDomains.includes(d)" @change="e => toggleWizardDomain(d, e.target.checked)">
                {{ d }}
              </a-checkbox>
            </div>
            <div v-if="filteredWizardDomains.length === 0" style="text-align: center; color: #bfbfbf; padding: 16px; font-size: 12px;">
              未发现匹配的域名
            </div>
          </div>

          <div style="background: var(--arl-bg-light); padding: 12px; border-radius: 6px; border: 1px solid var(--arl-border-color); margin-bottom: 20px;">
            <a-form-item label="自动探测" style="margin-bottom: 8px;">
              <a-checkbox v-model:checked="wizardAutoScan">立即对勾选域名发起主动探测扫描</a-checkbox>
            </a-form-item>
            <template v-if="wizardAutoScan">
              <a-form-item label="任务类型" style="margin-bottom: 8px;">
                <a-radio-group v-model:value="wizardTaskType">
                  <a-radio value="oneshot">一次性扫描</a-radio>
                  <a-radio value="periodic">周期性监控</a-radio>
                </a-radio-group>
              </a-form-item>
              <a-form-item label="扫描策略" style="margin-bottom: 0;" required>
                <a-select v-model:value="wizardPolicyId" placeholder="请选择扫描策略" :options="policyList.map(p => ({ value: p._id, label: p.name }))" />
              </a-form-item>
            </template>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center;">
            <a-button @click="wizardStep = 1">&larr; 返回修改</a-button>
            <div style="display: flex; gap: 8px;">
              <a-button @click="addModalVisible = false">取 消</a-button>
              <a-button type="primary" :loading="wizardSubmitting" :disabled="selectedWizardDomains.length === 0" @click="submitWizardSync">
                确认建组并入库 ({{ selectedWizardDomains.length }} 项)
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 编辑资产分组弹窗 -->
    <a-modal
      v-model:open="editGroupModalVisible"
      title="编辑资产分组"
      @ok="handleEditGroupSubmit"
      :confirmLoading="editGroupLoading"
      width="640px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="保 存"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form
        ref="editGroupFormRef"
        :model="editGroupForm"
        :rules="editGroupRules"
        :label-col="{ span: 4 }"
        :wrapper-col="{ span: 19 }"
        style="margin-top: 20px;"
      >
        <a-form-item label="所属集团" name="group_id">
          <a-select v-model:value="editGroupForm.group_id" placeholder="请选择所属集团（可选）" allowClear :getPopupContainer="(trigger) => trigger.parentNode">
            <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="资产组名称" name="name">
          <a-input v-model:value="editGroupForm.name" placeholder="请输入资产组名称" />
        </a-form-item>

        <a-form-item label="资产范围" name="scope">
          <!-- 模式切换与统计栏 -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.85;">
              <span>共 <strong style="color: var(--arl-theme-color, #1890ff);">{{ editGroupScopeList.length }}</strong> 个有效目标</span>
              <span v-if="editGroupMode === 'visual' && editGroupSearchKeyword.trim()" style="margin-left: 6px;">
                (匹配到 <strong style="color: #52c41a;">{{ filteredScopeList.length }}</strong> 个)
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <a-button 
                type="link" 
                size="small" 
                style="padding: 0; height: auto;" 
                @click="openIcpImportModal('edit')"
              >
                <cloud-download-outlined style="margin-right: 4px;" />从企业资产导入
              </a-button>
              <a-button 
                type="link" 
                size="small" 
                style="padding: 0; height: auto;" 
                @click="toggleEditGroupMode"
              >
                <template v-if="editGroupMode === 'visual'">
                  <file-text-outlined style="margin-right: 4px;" />纯文本批量模式
                </template>
                <template v-else>
                  <tags-outlined style="margin-right: 4px;" />可视化标签模式
                </template>
              </a-button>
            </div>
          </div>

          <!-- 可视化管理模式 -->
          <div v-if="editGroupMode === 'visual'" class="arl-scope-visual-panel">
            <!-- 搜索与批量删除工具栏 -->
            <div style="display: flex; gap: 8px; margin-bottom: 8px;">
              <a-input
                v-model:value="editGroupSearchKeyword"
                placeholder="搜索资产 (支持域名/IP模糊过滤)"
                allowClear
                size="middle"
                style="flex: 1;"
              >
                <template #prefix>
                  <search-outlined style="color: #bfbfbf;" />
                </template>
              </a-input>

              <a-popconfirm
                v-if="editGroupSearchKeyword.trim() && filteredScopeList.length > 0"
                :title="`确定批量移除匹配到的 ${filteredScopeList.length} 个资产范围吗？`"
                ok-text="删除"
                cancel-text="取消"
                ok-type="danger"
                @confirm="removeFilteredScopes"
              >
                <a-button danger size="middle">
                  <delete-outlined /> 删除筛选结果 ({{ filteredScopeList.length }})
                </a-button>
              </a-popconfirm>
            </div>

            <!-- 快捷追加输入 -->
            <div style="display: flex; gap: 8px; margin-bottom: 10px;">
              <a-input
                v-model:value="editGroupNewInput"
                placeholder="追加新资产（支持多行/逗号批量粘贴，回车快速添加）"
                size="middle"
                @pressEnter="addScopesFromInput"
                style="flex: 1;"
              />
              <a-button type="primary" size="middle" @click="addScopesFromInput">
                <plus-outlined /> 添加
              </a-button>
            </div>

            <!-- 资产标签滚动展示区 -->
            <div class="arl-scope-tag-container">
              <template v-if="filteredScopeList.length > 0">
                <a-tag
                  v-for="item in filteredScopeList"
                  :key="item"
                  closable
                  @close.prevent="removeScopeItem(item)"
                  class="arl-scope-edit-item-tag"
                >
                  {{ item }}
                </a-tag>
              </template>
              <div v-else class="arl-scope-empty-hint">
                {{ editGroupSearchKeyword.trim() ? '未找到匹配的资产' : '暂无资产，请在上方输入添加' }}
              </div>
            </div>
          </div>

          <!-- 纯文本批量模式 -->
          <div v-else>
            <a-textarea
              v-model:value="editGroupForm.scope"
              :rows="7"
              placeholder="请输入资产范围（支持同时混填 IP 与域名），多个请用逗号或换行分隔"
              style="font-family: monospace; font-size: 13px;"
            />
            <div style="margin-top: 6px; font-size: 12px; color: var(--arl-text-color); opacity: 0.65; display: flex; justify-content: space-between; align-items: center;">
              <span>当前共 <strong style="color: #1890ff;">{{ parseScopeList(editGroupForm.scope).length }}</strong> 个有效目标</span>
              <a-button type="link" size="small" style="padding: 0; height: auto;" @click="formatEditGroupScopes">格式化规整</a-button>
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加常规监控任务 -->
    <a-modal
      v-model:open="addMonitorVisible"
      @ok="submitAddMonitor"
      :confirmLoading="addMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <template #title>
        添加监控任务
        <a-tooltip title="将对资产组已发现域名与本次新发现域名取并集后执行策略，当前结果仅展示资产组的增量更新（新增及变动数据）。">
          <QuestionCircleOutlined style="font-size: 14px; color: #8c8c8c; cursor: pointer; margin-left: 4px;" />
        </a-tooltip>
      </template>
      <a-form ref="addMonitorFormRef" :model="addMonitorForm" :rules="addMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="范围" name="domains">
          <div style="margin-bottom: 8px; display: flex; gap: 6px; flex-wrap: wrap;">
            <a-button size="small" @click="selectAllDomains">全选 ({{ (currentRecord?.scope_array || []).length }})</a-button>
            <a-button 
              size="small" 
              type="primary" 
              ghost 
              @click="selectUnprobedDomains"
              :style="{ borderColor: unprobedDomainList.length > 0 ? '#faad14' : '', color: unprobedDomainList.length > 0 ? '#d48806' : '' }"
            >
              仅选未探测域名 ({{ unprobedDomainList.length }})
            </a-button>
            <a-button size="small" @click="selectProbedDomains">仅选已探测 ({{ probedDomainList.length }})</a-button>
            <a-button size="small" @click="clearDomains">清空</a-button>
          </div>
          <a-select mode="multiple" v-model:value="addMonitorForm.domains" placeholder="请选择范围" style="width: 100%;">
            <a-select-option v-for="item in currentRecord?.scope_array || []" :key="item" :value="item">
              <span style="display: flex; justify-content: space-between; align-items: center;">
                <span>{{ item }}</span>
                <span :style="{ 
                  fontSize: '11px', 
                  marginLeft: '8px',
                  color: getDomainStatus(currentRecord, item) === 'unprobed' ? '#faad14' : 
                         getDomainStatus(currentRecord, item) === 'scanning' ? '#1890ff' : 
                         getDomainStatus(currentRecord, item) === 'error' ? '#ff4d4f' : '#52c41a' 
                }">
                  [{{ getDomainStatusLabel(currentRecord, item) }}]
                </span>
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="任务类型" name="task_type">
          <a-radio-group v-model:value="addMonitorForm.task_type">
            <a-radio value="periodic">周期性监控</a-radio>
            <a-radio value="oneshot">一次性扫描</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="运行间隔" name="interval_hours" v-if="addMonitorForm.task_type === 'periodic'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>

        <a-form-item label="策略" name="policy_id">
          <a-select v-model:value="addMonitorForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>

      </a-form>
    </a-modal>

    <!-- 添加站点监控任务 -->
    <a-modal
      v-model:open="addSiteMonitorVisible"
      title="添加站点监控任务"
      @ok="submitAddSiteMonitor"
      :confirmLoading="addSiteMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form ref="addSiteMonitorFormRef" :model="addSiteMonitorForm" :rules="addSiteMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="运行间隔" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addSiteMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加WIH监控任务 -->
    <a-modal
      v-model:open="addWihMonitorVisible"
      title="添加WIH监控任务"
      @ok="submitAddWihMonitor"
      :confirmLoading="addWihMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form ref="addWihMonitorFormRef" :model="addWihMonitorForm" :rules="addWihMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="运行间隔" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addWihMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>

      </a-form>
    </a-modal>


    <!-- 新建/重命名集团弹窗 -->
    <a-modal
      v-model:open="enterpriseGroupModalVisible"
      :title="enterpriseGroupForm.isEdit ? '重命名集团' : '新建集团'"
      @ok="submitEnterpriseGroup"
      :confirmLoading="enterpriseGroupLoading"
      width="480px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form :model="enterpriseGroupForm" layout="vertical" style="margin-top: 16px;">
        <a-form-item label="集团名称" required>
          <a-input v-model:value="enterpriseGroupForm.name" placeholder="请输入集团名称" />
        </a-form-item>
        <a-form-item label="描述" v-if="!enterpriseGroupForm.isEdit">
          <a-textarea v-model:value="enterpriseGroupForm.description" placeholder="请输入描述（可选）" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 批量移动至集团弹窗 -->
    <a-modal
      v-model:open="batchMoveModalVisible"
      title="批量移动至集团"
      @ok="submitBatchMove"
      :confirmLoading="batchMoveLoading"
      width="480px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form layout="vertical" style="margin-top: 16px;">
        <p>已选择 <strong>{{ selectedRowKeys.length }}</strong> 个资产组。</p>
        <a-form-item label="目标集团" required>
          <a-select v-model:value="batchMoveTargetGroupId" placeholder="请选择目标集团" :getPopupContainer="(trigger) => trigger.parentNode">
            <a-select-option value="unassigned">取消分组 (移至未分组)</a-select-option>
            <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 从企业资产任务导入弹窗 -->
    <a-modal
      v-model:open="icpImportModalVisible"
      title="从企业资产查询导入资产"
      :footer="null"
      width="720px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      destroyOnClose
    >
      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <a-input
          v-model:value="icpImportSearchKey"
          placeholder="搜索任务名称或目标企业..."
          allowClear
          style="width: 280px;"
        >
          <template #prefix><search-outlined style="color: #bfbfbf;" /></template>
        </a-input>
        <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.65;">
          展示已完成的企业资产/ICP查询任务
        </span>
      </div>

      <a-table
        :dataSource="filteredIcpTasks"
        :columns="icpImportColumns"
        :loading="icpImportLoading"
        :pagination="{ pageSize: 5, size: 'small' }"
        size="small"
        :rowKey="r => r._id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'statistic'">
            <span>{{ (record.statistic?.web_cnt !== undefined ? record.statistic.web_cnt : (record.statistic?.asset_cnt || 0)) }} 个网站</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button
              type="primary"
              size="small"
              :loading="importingTaskId === record._id"
              @click="handleImportFromTask(record)"
            >
              导入该任务资产
            </a-button>
          </template>
        </template>
      </a-table>
    </a-modal>

    <!-- 企业测绘任务抽屉组件 -->
    <ReconTaskDrawer
      v-model:open="reconDrawerVisible"
      @synced="handleReconDrawerSynced"
    />

    <!-- 同步增量弹窗 -->
    <SyncToScopeModal
      v-model:open="syncIncrementModalVisible"
      :task="currentIncrementTask"
      @success="handleIncrementSyncSuccess"
    />

    <!-- 列表操作栏：绑定企业主体弹窗 -->
    <a-modal
      v-model:open="bindScopeModalVisible"
      title="资产组绑定企业主体"
      @ok="submitBindScopeEnterprise"
      :confirmLoading="bindScopeLoading"
      width="540px"
      wrapClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="当前资产组">
          <span style="font-weight: 500;">{{ currentBindingScope?.name }}</span>
        </a-form-item>
        <a-form-item label="企业测绘" required>
          <a-select
            v-model:value="selectedBindScopeTaskId"
            placeholder="请选择已完成的企业测绘任务"
            show-search
            option-filter-prop="label"
            :options="completedIcpTasks.map(t => ({
              value: t._id,
              label: t.task_type === 'tyc'
                ? `${t.name || t.target} [TYC: ${t.gid || (t.target ? t.target.replace(/^TYC_/, '') : '')}]`
                : `${t.target || t.name} (ICP)`
            }))"
          />
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
  <!-- Close Root wrapper div added at step 1 -->
  </div>
</template>

<script setup>
defineOptions({ name: 'AssetScope' });

import { ref, reactive, computed, createVNode, watch, onActivated, onDeactivated, onUnmounted, onMounted } from 'vue';
import { useSticky } from '../utils/useSticky';
const sidebarAnchorRef = ref(null);
const sidebarLeft = ref(186);

const updateSidebarLeft = () => {
  if (sidebarAnchorRef.value) {
    const rect = sidebarAnchorRef.value.getBoundingClientRect();
    if (rect.left > 0) {
      sidebarLeft.value = rect.left;
    }
  }
};

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import ReconTaskDrawer from '../components/ReconTaskDrawer.vue';
import SyncToScopeModal from '../components/SyncToScopeModal.vue';
import { 
  SearchOutlined, 
  DownOutlined, 
  ExclamationCircleOutlined, 
  QuestionCircleOutlined, 
  PlusOutlined, 
  DeleteOutlined,
  CopyOutlined,
  FileTextOutlined,
  TagsOutlined,
  AppstoreOutlined,
  InboxOutlined,
  MoreOutlined,
  RightOutlined,
  LeftOutlined,
  CloudDownloadOutlined,
  ProfileOutlined,
  BankOutlined,
  SyncOutlined,
  ReloadOutlined,
  FolderOpenOutlined,
  EditOutlined,
  LinkOutlined,
  DashboardOutlined,
  GlobalOutlined,
  RadarChartOutlined,
  HistoryOutlined,
  ApartmentOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { copyText as copyToClipboard } from '../utils/clipboard';

const getBodyContainer = () => document.body;

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({ group_id: undefined });
const currentRecord = ref(null);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

// 表格列定义
const columns = computed(() => {
  const baseColumns = [
    { title: '资产组名称', key: 'name', width: 210, sorter: true },
    { title: '资产范围', key: 'scope_array', minWidth: 260 },
    { title: '探测覆盖度', key: 'domain_stat', width: 130 },
    { title: '资产范围ID', key: 'scope_id', width: 180 },
    { title: '操作', key: 'action', width: 420, fixed: 'right' }
  ];
  if (activeGroupId.value === 'all') {
    baseColumns.splice(1, 0, { title: '所属集团', key: 'group_name', width: 120 });
  }
  return baseColumns;
});

// 获取主域名探测状态与展示样式
const getDomainStatus = (record, domain) => {
  if (!record || !domain) return 'unprobed';
  return record.domain_status?.[domain]?.status || 'unprobed';
};

const getDomainStatusLabel = (record, domain) => {
  const st = getDomainStatus(record, domain);
  if (st === 'probed') return '已探测';
  if (st === 'scanning') return '探测中';
  if (st === 'error') return '探测异常';
  return '未探测';
};

const getDomainTagStyle = (record, domain) => {
  return {
    background: 'var(--arl-bg-light, #f8fafc)',
    color: 'var(--arl-text-color, #334155)',
    borderColor: 'var(--arl-border-color, #e2e8f0)',
    marginRight: '0'
  };
};

const getDomainTooltip = (record, domain) => {
  const meta = record?.domain_status?.[domain] || {};
  const statusLabel = getDomainStatusLabel(record, domain);
  const time = meta.last_probe_time || meta.sync_time || '-';
  return `域名: ${domain} | 状态: ${statusLabel} | 更新: ${time}`;
};

// 解析文本中的目标数组（去重去空小写）
const parseScopeList = (text) => {
  if (!text) return [];
  const rawList = text.split(/[\n,]+/);
  const seen = new Set();
  const result = [];
  for (let item of rawList) {
    item = item.trim().toLowerCase();
    if (item && !seen.has(item)) {
      seen.add(item);
      result.push(item);
    }
  }
  return result;
};

// 复制功能 (复用 utils/clipboard，兼容非 HTTPS 环境)
const copyText = async (text) => {
  const ok = await copyToClipboard(text);
  if (ok) {
    message.success('复制成功');
  } else {
    message.error('复制失败，请手动选取复制');
  }
};

// 域名标签优先级预排序（探测中 > 待测 > 异常 > 已测），预处理挂载到 _sorted_scopes 杜绝模板渲染卡顿
const processScopeItems = (items) => {
  const statusWeight = { scanning: 0, unprobed: 1, error: 2, probed: 3 };
  return (items || []).map(record => {
    const arr = record?.scope_array || [];
    let sorted = arr;
    if (arr.length > 5) {
      sorted = [...arr].sort((a, b) => {
        const weightA = statusWeight[getDomainStatus(record, a)] ?? 4;
        const weightB = statusWeight[getDomainStatus(record, b)] ?? 4;
        return weightA - weightB;
      });
    }
    return {
      ...record,
      _sorted_scopes: sorted
    };
  });
};


// 轮询调度管理：如果有正在扫描中的资产组，则每 5 秒静默轮询一次
let pollTimer = null;
const stopPoll = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const checkAndSchedulePoll = () => {
  stopPoll();
  const hasScanning = (dataSource.value || []).some(item => (item?.domain_stat?.scanning || 0) > 0);
  if (hasScanning) {
    pollTimer = setTimeout(() => {
      fetchData(true);
    }, 5000);
  }
};

// 拉取表格数据（增加防重与竞态保护）
let isFetching = false;
let currentFetchContextId = null;

const fetchData = async (silent = false) => {
  if (isFetching) return;
  isFetching = true;
  if (!silent) {
    loading.value = true;
  }
  
  const fetchContextId = activeGroupId.value;
  currentFetchContextId = fetchContextId;

  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    for (const key in searchForm.value) {
      if (searchForm.value[key]) params[key] = searchForm.value[key];
    }
    const res = await request.get('/asset_scope/', { params });
    
    // 竞态防御：如果上下文 ID 已变更，说明已经切换了集团，直接丢弃本次请求结果
    if (currentFetchContextId !== fetchContextId) return;

    if (res.code === 200) {
      dataSource.value = processScopeItems(res.items || []);
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
      checkAndSchedulePoll();
    }
  } catch (error) {
    if (currentFetchContextId === fetchContextId) {
      message.error('加载资产分组失败');
    }
  } finally {
    if (currentFetchContextId === fetchContextId) {
      isFetching = false;
      if (!silent) {
        loading.value = false;
      }
    } else {
      isFetching = false;
    }
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const resetSearch = () => {
  searchForm.value = {};
  onSearch();
};
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };


const isSidebarCollapsed = ref(false);
const activeGroupId = ref('all');
const groupSearchKey = ref('');
const groupList = ref([]);
const filteredGroupList = computed(() => {
  if (!groupSearchKey.value) return groupList.value;
  return groupList.value.filter(g => g.name.toLowerCase().includes(groupSearchKey.value.toLowerCase()));
});

const currentGroupName = computed(() => {
  if (activeGroupId.value === 'all') return '全部资产组';
  if (activeGroupId.value === 'unassigned') return '未分组';
  const g = groupList.value.find(x => x._id === activeGroupId.value);
  return g ? g.name : '未知分组';
});

// fetch groups
const fetchGroups = async () => {
  try {
    const res = await request.get('/asset_group/');
    if (res.code === 200) {
      groupList.value = res.items || [];
    }
  } catch (err) {}
};

// handle group switch with confirmation guard
const handleGroupSwitch = (info) => {
  const newKey = info.key;
  if (newKey === activeGroupId.value) return;
  
  if (selectedRowKeys.value.length > 0) {
    Modal.confirm({
      title: '切换分组提示',
      content: `您在当前分组下已勾选了 ${selectedRowKeys.value.length} 个资产组尚未处理。切换分组将清空当前勾选，是否继续？`,
      onOk: () => {
        selectedRowKeys.value = [];
        activeGroupId.value = newKey;
      }
    });
  } else {
    activeGroupId.value = newKey;
  }
};

watch(activeGroupId, (newVal) => {
  selectedRowKeys.value = [];
  searchForm.value.group_id = newVal === 'all' ? undefined : newVal;
  pagination.current = 1;
  fetchData();
});

// Group Actions
const handleGroupAction = (e, group) => {
  if (e.key === 'edit') {
    enterpriseGroupForm.isEdit = true;
    enterpriseGroupForm._id = group._id;
    enterpriseGroupForm.name = group.name;
    enterpriseGroupModalVisible.value = true;
  } else if (e.key === 'delete') {
    if (group.scope_count > 0) {
      Modal.warning({
        title: '无法删除集团',
        content: `集团【${group.name}】下仍有关联的 ${group.scope_count} 个资产组，禁止删除。请先将下属资产组批量划转至其他集团或移至未分组后再进行删除。`,
        okText: '知道了'
      });
      return;
    }
    Modal.confirm({
      title: '删除集团确认',
      content: `确定要删除空集团【${group.name}】吗？删除后该操作不可恢复。`,
      okType: 'danger',
      okText: '确 定',
      cancelText: '取 消',
      onOk: async () => {
        try {
          const res = await request.post('/asset_group/delete/', { _id: group._id });
          if (res.code === 200) {
            message.success('删除集团成功');
            if (activeGroupId.value === group._id) {
              activeGroupId.value = 'all'; // Fallback focus
            }
            fetchGroups();
          } else {
            message.error(res.message || '删除失败');
          }
        } catch(err) {
          message.error('请求异常');
        }
      }
    });
  }
};

// Enterprise Group Modal
const enterpriseGroupModalVisible = ref(false);
const enterpriseGroupLoading = ref(false);
const enterpriseGroupForm = reactive({ isEdit: false, _id: '', name: '', description: '' });

const openAddEnterpriseGroupModal = () => {
  enterpriseGroupForm.isEdit = false;
  enterpriseGroupForm._id = '';
  enterpriseGroupForm.name = '';
  enterpriseGroupForm.description = '';
  enterpriseGroupModalVisible.value = true;
};

const submitEnterpriseGroup = async () => {
  if (!enterpriseGroupForm.name) {
    message.warning('请输入集团名称');
    return;
  }
  enterpriseGroupLoading.value = true;
  try {
    let res;
    if (enterpriseGroupForm.isEdit) {
      res = await request.post('/asset_group/edit/', { _id: enterpriseGroupForm._id, name: enterpriseGroupForm.name });
    } else {
      res = await request.post('/asset_group/', { name: enterpriseGroupForm.name, description: enterpriseGroupForm.description });
    }
    if (res.code === 200) {
      message.success(enterpriseGroupForm.isEdit ? '重命名成功' : '新建集团成功');
      enterpriseGroupModalVisible.value = false;
      fetchGroups();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch(err) {
    message.error('请求异常');
  } finally {
    enterpriseGroupLoading.value = false;
  }
};

// Batch Move Modal
const batchMoveModalVisible = ref(false);
const batchMoveLoading = ref(false);
const batchMoveTargetGroupId = ref(undefined);

const openBatchMoveModal = () => {
  batchMoveTargetGroupId.value = undefined;
  batchMoveModalVisible.value = true;
};

const submitBatchMove = async () => {
  if (!batchMoveTargetGroupId.value) {
    message.warning('请选择目标集团');
    return;
  }
  batchMoveLoading.value = true;
  try {
    const res = await request.post('/asset_scope/batch_move_group/', {
      scope_ids: selectedRowKeys.value,
      group_id: batchMoveTargetGroupId.value === 'unassigned' ? '' : batchMoveTargetGroupId.value
    });
    if (res.code === 200) {
      message.success('批量移动成功');
      batchMoveModalVisible.value = false;
      selectedRowKeys.value = [];
      fetchData();
      fetchGroups();
    } else {
      message.error(res.message || '移动失败');
    }
  } catch(err) {
    message.error('请求异常');
  } finally {
    batchMoveLoading.value = false;
  }
};

// initialize
let siderObserver = null;

onMounted(() => {
  if (route.path === '/group') {
    fetchGroups();
  }
  updateSidebarLeft();
  window.addEventListener('resize', updateSidebarLeft);
  const siderEl = document.querySelector('.ant-layout-sider');
  if (siderEl) {
    const handleSiderChange = () => {
      updateSidebarLeft();
      setTimeout(updateSidebarLeft, 250);
      setTimeout(updateSidebarLeft, 550);
    };
    siderObserver = new MutationObserver(handleSiderChange);
    siderObserver.observe(siderEl, { attributes: true, attributeFilter: ['style', 'class'] });
    siderEl.addEventListener('transitionend', updateSidebarLeft);
  }
});

onActivated(() => {
  if (route.path === '/group') {
    fetchGroups();
    fetchData(true);
  }
  updateSidebarLeft();
});

// Update the initial addForm and editGroupForm state definitions

// ================= 新建资产分组逻辑 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addFormRef = ref();

const addForm = reactive({
  group_id: undefined,
  name: '',
  scope: ''
});

const addRules = {
  name: [{ required: true, message: '请输入资产组名称', trigger: 'blur' }],
  scope: [{ required: true, message: '请输入资产范围', trigger: 'blur' }]
};

// ================= 企业测绘任务抽屉与向导建组状态 =================
const reconDrawerVisible = ref(false);
const handleReconDrawerSynced = () => {
  fetchData();
};

watch(() => route.query.drawer, (d) => {
  if (d === 'reconHistory') {
    reconDrawerVisible.value = true;
  }
}, { immediate: true });

// 新建资产分组模式与向导状态
const creationMode = ref('manual'); // 'manual' | 'wizard'
const wizardStep = ref(1);
const wizardLoading = ref(false);
const wizardLoadingTip = ref('正在发起企业测绘...');
const wizardTaskId = ref('');
const wizardDomains = ref([]);
const selectedWizardDomains = ref([]);
const wizardDomainSearch = ref('');
const wizardAutoScan = ref(false);
const wizardTaskType = ref('oneshot');
const wizardPolicyId = ref('');
const wizardSubmitting = ref(false);
const policyList = ref([]);

const wizardForm = reactive({
  group_id: undefined,
  target: '',
  name: '',
  engine: 'tyc',
  depth: 1,
  invest_ratio: 50
});

const getGroupName = (gid) => {
  const g = groupList.value.find(item => item._id === gid);
  return g ? g.name : '';
};

const filteredWizardDomains = computed(() => {
  if (!wizardDomainSearch.value.trim()) return wizardDomains.value;
  return wizardDomains.value.filter(d => d.includes(wizardDomainSearch.value.trim().toLowerCase()));
});

const toggleWizardDomain = (d, checked) => {
  if (checked) {
    if (!selectedWizardDomains.value.includes(d)) selectedWizardDomains.value.push(d);
  } else {
    selectedWizardDomains.value = selectedWizardDomains.value.filter(item => item !== d);
  }
};

const selectAllWizardDomains = () => {
  selectedWizardDomains.value = wizardDomains.value.slice();
};

const startWizardRecon = async () => {
  const target = (wizardForm.target || '').trim();
  const name = (wizardForm.name || '').trim();

  if (wizardForm.engine === 'tyc') {
    if (!target) {
      message.warning('请输入天眼查公司 ID (TYC_id)');
      return;
    }
    if (!/^[a-zA-Z0-9]+$/.test(target)) {
      message.warning('天眼查公司 ID 格式不正确，请输入纯数字/字母 ID（例如：25174642）');
      return;
    }
    if (!name) {
      message.warning('使用天眼查测绘时，请输入分组名称（如：腾讯科技）');
      return;
    }
  } else {
    if (!target) {
      message.warning('请输入企业全称或主域名');
      return;
    }
  }

  wizardLoading.value = true;
  wizardLoadingTip.value = '正在检索企业工商与备案资产，预计需 5~15 秒...';
  try {
    let taskRes;
    const tName = (name || target) + '企业测绘';
    if (wizardForm.engine === 'tyc') {
      taskRes = await request.post('/icp/tyc_task', {
        name: tName,
        gid: target,
        depth: wizardForm.depth || 1,
        invest_ratio: wizardForm.invest_ratio || 50,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo']
      });
    } else {
      taskRes = await request.post('/icp/task', {
        name: tName,
        target: target,
        query_type: ['web', 'app', 'mapp']
      });
    }

    if (!taskRes || taskRes.code !== 200) {
      message.error(taskRes?.message || '发起测绘失败');
      wizardLoading.value = false;
      return;
    }

    const taskId = taskRes.data?.task_id || taskRes.data?._id || taskRes.task_id;
    wizardTaskId.value = taskId;

    // 获取可用策略列表
    if (policyList.value.length === 0) {
      const pRes = await request.get('/policy/', { params: { size: 100 } });
      if (pRes.code === 200) {
        policyList.value = pRes.items || [];
        if (policyList.value.length > 0) {
          wizardPolicyId.value = policyList.value[0]._id;
        }
      }
    }

    let attempts = 0;
    const maxAttempts = 30;
    const pollInterval = 2000;

    const pollTask = async () => {
      attempts++;
      try {
        const checkRes = await request.get('/icp/task', { params: { _id: taskId } });
        if (checkRes.code === 200 && checkRes.items && checkRes.items.length > 0) {
          const taskObj = checkRes.items[0];
          if (taskObj.status === 'done' || taskObj.status === 'stop') {
            const assetRes = await request.get('/icp/asset', { params: { task_id: taskId, query_type: 'web', size: 5000 } });
            const domainSet = new Set();
            if (assetRes.code === 200 && assetRes.items) {
              assetRes.items.forEach(item => {
                const d = item.domain || item.ym;
                if (d && typeof d === 'string') domainSet.add(d.trim().toLowerCase());
              });
            }
            wizardDomains.value = Array.from(domainSet);
            selectedWizardDomains.value = Array.from(domainSet);
            wizardStep.value = 2;
            wizardLoading.value = false;
            return;
          } else if (taskObj.status === 'error') {
            message.error('测绘任务执行异常');
            wizardLoading.value = false;
            return;
          }
        }
      } catch (err) {
        console.error(err);
      }

      if (attempts < maxAttempts) {
        setTimeout(pollTask, pollInterval);
      } else {
        message.info('测绘数据量较大，已转入后台运行。您可稍后在【企业测绘任务】中查看。');
        wizardLoading.value = false;
        addModalVisible.value = false;
      }
    };

    setTimeout(pollTask, pollInterval);
  } catch (err) {
    message.error('请求网络错误');
    wizardLoading.value = false;
  }
};

const submitWizardSync = async () => {
  if (selectedWizardDomains.value.length === 0) {
    message.warning('请至少勾选一个入库域名');
    return;
  }
  wizardSubmitting.value = true;
  try {
    const payload = {
      mode: 'new',
      target_name: wizardForm.name.trim() || wizardForm.target.trim(),
      group_id: wizardForm.group_id || '',
      selected_domains: selectedWizardDomains.value,
      auto_scan: wizardAutoScan.value,
      task_type: wizardTaskType.value,
      policy_id: wizardPolicyId.value
    };
    const res = await request.post(`/icp/sync/${wizardTaskId.value}`, payload);
    if (res.code === 200) {
      message.success('资产组创建成功并已导入资产');
      addModalVisible.value = false;
      fetchData();
    } else {
      message.error(res.message || '入库失败');
    }
  } catch (err) {
    message.error('网络请求失败');
  } finally {
    wizardSubmitting.value = false;
  }
};

// 增量同步弹窗
const syncIncrementModalVisible = ref(false);
const currentIncrementTask = ref(null);

const openSyncIncrement = async (record) => {
  if (!record.synced_icp_task_id) return;
  try {
    const res = await request.get('/icp/task', { params: { _id: record.synced_icp_task_id } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      currentIncrementTask.value = res.items[0];
      syncIncrementModalVisible.value = true;
    } else {
      message.error('未找到关联的企业测绘任务');
    }
  } catch (err) {
    message.error('加载任务失败');
  }
};

const handleIncrementSyncSuccess = () => {
  fetchData();
};


// 资产组绑定已有企业主体
const bindScopeModalVisible = ref(false);
const bindScopeLoading = ref(false);
const currentBindingScope = ref(null);
const selectedBindScopeTaskId = ref(undefined);
const completedIcpTasks = ref([]);

const openBindEnterprise = async (record) => {
  currentBindingScope.value = record;
  selectedBindScopeTaskId.value = undefined;
  bindScopeModalVisible.value = true;
  try {
    const res = await request.get('/icp/task', { params: { size: 100 } });
    if (res.code === 200) {
      completedIcpTasks.value = res.items || [];
    }
  } catch (err) {
    console.error(err);
  }
};

const submitBindScopeEnterprise = async () => {
  if (!selectedBindScopeTaskId.value) {
    message.warning('请选择要绑定的企业测绘任务');
    return;
  }
  bindScopeLoading.value = true;
  try {
    const res = await request.post('/asset_scope/bind_enterprise/', {
      scope_id: currentBindingScope.value._id,
      task_id: selectedBindScopeTaskId.value
    });
    if (res && res.code === 200) {
      message.success('绑定企业主体成功');
      bindScopeModalVisible.value = false;
      fetchData();
    } else {
      message.error(res.message || '绑定失败');
    }
  } catch (err) {
    message.error('网络请求失败');
  } finally {
    bindScopeLoading.value = false;
  }
};

const goToOsintDetail = (record) => {
  router.push({
    path: '/groupAssetsManagement/groupAssetsDetail',
    query: { scope_id: record._id, targetName: record.name, view: 'osint' }
  });
};

const openAddModal = () => {
  creationMode.value = 'manual';
  wizardStep.value = 1;
  wizardForm.group_id = activeGroupId.value === 'all' || activeGroupId.value === 'unassigned' ? undefined : activeGroupId.value;
  wizardForm.target = '';
  wizardForm.name = '';
  wizardForm.engine = 'tyc';
  wizardDomains.value = [];
  selectedWizardDomains.value = [];
  wizardDomainSearch.value = '';
  wizardAutoScan.value = false;

  addForm.group_id = activeGroupId.value === 'all' || activeGroupId.value === 'unassigned' ? undefined : activeGroupId.value;
  addForm.name = '';
  addForm.scope = '';
  addModalVisible.value = true;
};

const handleAddSubmit = async () => {
  try {
    await addFormRef.value.validate();
    addLoading.value = true;
    const res = await request.post('/asset_scope/', addForm);

    if (res.code === 200) {
      message.success('新建资产分组成功！');
      addModalVisible.value = false;
      pagination.current = 1;
      fetchData();
    } else {
      message.error('新建失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    console.warn('提交中断或校验失败', error);
  } finally {
    addLoading.value = false;
  }
};

// ================= 编辑资产分组逻辑 =================
const editGroupModalVisible = ref(false);
const editGroupLoading = ref(false);
const editGroupFormRef = ref();
const editGroupMode = ref('visual'); // 'visual' | 'text'
const editGroupScopeList = ref([]);
const editGroupSearchKeyword = ref('');
const editGroupNewInput = ref('');

const editGroupForm = reactive({
  _id: '',
  group_id: undefined,
  name: '',
  scope: ''
});

const editGroupRules = {
  name: [{ required: true, message: '请输入资产组名称', trigger: 'blur' }],
  scope: [
    {
      validator: async () => {
        const list = editGroupMode.value === 'visual' 
          ? editGroupScopeList.value 
          : parseScopeList(editGroupForm.scope);
        if (!list || list.length === 0) {
          return Promise.reject(new Error('请输入或保留至少一个资产范围'));
        }
        return Promise.resolve();
      },
      trigger: 'change'
    }
  ]
};

// 搜索过滤后的资产列表
const filteredScopeList = computed(() => {
  const keyword = editGroupSearchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return editGroupScopeList.value;
  }
  return editGroupScopeList.value.filter(item => item.toLowerCase().includes(keyword));
});

// 打开编辑分组弹窗
const openEditGroupModal = (record) => {
  currentRecord.value = record;
  editGroupForm._id = record._id;
  editGroupForm.group_id = record.group_id || undefined;
  editGroupForm.name = record.name || '';
  editGroupScopeList.value = [...(record.scope_array || [])];
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  editGroupMode.value = 'visual';
  editGroupSearchKeyword.value = '';
  editGroupNewInput.value = '';
  editGroupModalVisible.value = true;
};

// 模式切换
const toggleEditGroupMode = () => {
  if (editGroupMode.value === 'visual') {
    // 切换到纯文本模式
    editGroupForm.scope = editGroupScopeList.value.join('\n');
    editGroupMode.value = 'text';
  } else {
    // 切换到可视化模式
    editGroupScopeList.value = parseScopeList(editGroupForm.scope);
    editGroupForm.scope = editGroupScopeList.value.join('\n');
    editGroupMode.value = 'visual';
    editGroupSearchKeyword.value = '';
  }
};

// 单项移除资产
const removeScopeItem = (item) => {
  editGroupScopeList.value = editGroupScopeList.value.filter(x => x !== item);
  editGroupForm.scope = editGroupScopeList.value.join('\n');
};

// 批量删除搜索筛选结果
const removeFilteredScopes = () => {
  const toRemove = new Set(filteredScopeList.value);
  editGroupScopeList.value = editGroupScopeList.value.filter(x => !toRemove.has(x));
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  message.success(`已批量移除 ${toRemove.size} 个匹配资产`);
  editGroupSearchKeyword.value = '';
};

// 快捷追加资产
const addScopesFromInput = () => {
  if (!editGroupNewInput.value.trim()) return;
  const newItems = parseScopeList(editGroupNewInput.value);
  if (newItems.length === 0) return;
  const existingSet = new Set(editGroupScopeList.value);
  let addedCount = 0;
  for (const item of newItems) {
    if (!existingSet.has(item)) {
      existingSet.add(item);
      editGroupScopeList.value.push(item);
      addedCount++;
    }
  }
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  editGroupNewInput.value = '';
  if (addedCount > 0) {
    message.success(`成功追加 ${addedCount} 个新资产！`);
  } else {
    message.info('所填资产已全部存在，未重复添加');
  }
};

// 格式化文本模式下的资产
const formatEditGroupScopes = () => {
  const list = parseScopeList(editGroupForm.scope);
  editGroupScopeList.value = list;
  editGroupForm.scope = list.join('\n');
  message.success('已自动去重并按行规整！');
};

// 提交编辑保存
const handleEditGroupSubmit = async () => {
  try {
    if (editGroupMode.value === 'visual') {
      editGroupForm.scope = editGroupScopeList.value.join('\n');
    } else {
      editGroupScopeList.value = parseScopeList(editGroupForm.scope);
      editGroupForm.scope = editGroupScopeList.value.join('\n');
    }

    await editGroupFormRef.value.validate();
    const newScopeList = parseScopeList(editGroupForm.scope);
    if (newScopeList.length === 0) {
      message.error('资产组必须保留至少一个资产范围，禁止清空！');
      return;
    }

    const originalScopes = currentRecord.value?.scope_array || [];
    const newSet = new Set(newScopeList);
    const removed = originalScopes.filter(x => !newSet.has(x));

    if (removed.length > 0) {
      Modal.confirm({
        title: '⚠️ 资产范围剔除与级联清理确认',
        icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
        content: createVNode('div', null, [
          createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `检测到您从资产组【${editGroupForm.name}】中移除了以下 ${removed.length} 个资产范围：`),
          createVNode('div', { style: 'max-height: 100px; overflow-y: auto; background: #fff1f0; padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 12px; color: #cf1322;' }, removed.join(', ')),
          createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, '警告：移除上述主干目标后，系统将自动物理级联清理该组下所有归属于这些目标的已发现子域名、IP、站点和 WIH 沉淀资产，此操作不可逆！是否确认更新？')
        ]),
        okText: '确认更新并清理',
        okType: 'danger',
        cancelText: '取 消',
        onOk: () => {
          submitEditGroupUpdate(newScopeList);
        }
      });
    } else {
      submitEditGroupUpdate(newScopeList);
    }
  } catch (error) {
    console.warn('编辑校验失败', error);
  }
};

const submitEditGroupUpdate = async (scopeList) => {
  try {
    editGroupLoading.value = true;
    const res = await request.post('/asset_scope/update/', {
      _id: editGroupForm._id,
      group_id: editGroupForm.group_id || '',
      name: editGroupForm.name,
      scope: scopeList.join(',')
    });

    if (res.code === 200) {
      message.success('资产分组更新成功！');
      editGroupModalVisible.value = false;
      fetchData();
    } else {
      message.error('更新失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('请求异常，更新失败');
  } finally {
    editGroupLoading.value = false;
  }
};

// ================= 表格 Tag 快捷单个移除范围 =================
const handleRemoveSingleScope = (record, scopeItem) => {
  if ((record.scope_array || []).length <= 1) {
    message.error('资产组必须保留至少一个资产范围，禁止清空！如需彻底销毁该分组，请直接删除资产组。');
    return;
  }

  Modal.confirm({
    title: '⚠️ 资产范围剔除与级联清理确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `检测到您正准备从资产组【${record.name}】中移除资产范围：`),
      createVNode('div', { style: 'background: #fff1f0; padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 13px; font-weight: bold; color: #cf1322;' }, scopeItem),
      createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, '警告：移除该主干目标后，系统将自动物理级联清理该组下所有归属于该目标的已发现子域名、IP、站点和 WIH 沉淀资产，此操作不可逆！是否确认移除？')
    ]),
    okText: '确认移除并清理',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.get('/asset_scope/delete/', {
          params: {
            scope_id: record._id,
            scope: scopeItem
          }
        });
        if (res.code === 200) {
          message.success(`已成功移除资产范围：${scopeItem}`);
          fetchData(true);
        } else {
          message.error('移除失败: ' + (res.message || res.data?.error || '未知错误'));
        }
      } catch (e) {
        message.error('请求异常，移除失败');
      }
    }
  });
};

// ================= 单行删除资产分组 =================
const handleSingleDelete = (record) => {
  Modal.confirm({
    title: '⚠️ 资产分组彻底销毁确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `确定要彻底删除资产分组【${record.name}】吗？`),
      createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, '警告：该操作将同时物理级联清理该组关联的所有已发现子域名、IP、站点、WIH 以及所有定时监控任务，此操作不可逆！')
    ]),
    okText: '彻底删除',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.post('/asset_scope/delete/', {
          scope_id: [record._id]
        });

        if (res.code === 200) {
          message.success('资产分组删除成功！');
          if (dataSource.value.length === 1 && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData();
        } else {
          message.error('删除失败: ' + res.message);
        }
      } catch (error) {
        message.error('请求异常，删除失败');
      }
    }
  });
};

// ================= 批量删除逻辑 =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: '⚠️ 批量删除资产分组确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: `确定要彻底删除选中的 ${selectedRowKeys.value.length} 个资产分组吗？删除后将同时物理级联清理所有关联的子资产与监控任务，不可恢复。`,
    okText: '彻底删除',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.post('/asset_scope/delete/', {
          scope_id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success('批量删除成功！');
          selectedRowKeys.value = [];
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData();
        } else {
          message.error('删除失败: ' + res.message);
        }
      } catch (error) {
        message.error('请求异常，删除失败');
      }
    }
  });
};

// ================= 批量导出逻辑 =================
const handleBatchExport = async ({ key }) => {
  const url = `/batch_export/${key}/`;
  const nameMap = {
    'asset_domain': '域名',
    'asset_ip': 'IP',
    'asset_site': '站点',
    'asset_wih': 'WIH'
  };
  const exportName = nameMap[key];

  try {
    message.loading({ content: `正在生成 ${exportName} 导出文件...`, key: 'export_data' });

    const res = await request.post(url, { scope_id: selectedRowKeys.value, group_id: searchForm.value.group_id }, { responseType: 'blob' });
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Export_${exportName}_${new Date().getTime()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `${exportName} 导出成功！`, key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: `${exportName} 导出失败`, key: 'export_data', duration: 2 });
  }
};

// 丝滑跳转至详情页
const goToDetail = (record) => {
  router.push({
    path: '/groupAssetsManagement/groupAssetsDetail',
    query: {
      scope_id: record._id,
      targetName: record._id
    }
  });
};

// ================= 添加监控任务 =================
const addMonitorVisible = ref(false);
const addMonitorLoading = ref(false);
const addMonitorFormRef = ref();
const policies = ref([]);

const addMonitorForm = reactive({ domains: [], interval_hours: 24, policy_id: undefined, task_type: 'periodic' });
const addMonitorRules = {
  domains: [{ type: 'array', required: true, message: '请选择范围', trigger: 'change' }],
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }],
  policy_id: [{ required: true, message: '请选择策略', trigger: 'change' }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }]
};

const openAddMonitorModal = async (record) => {
  currentRecord.value = record;
  addMonitorForm.domains = [];
  addMonitorForm.interval_hours = 24;
  addMonitorForm.policy_id = undefined;
  addMonitorForm.task_type = 'periodic';
  addMonitorVisible.value = true;

  if (policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if (res.code === 200) policies.value = res.items || [];
  }
};

const unprobedDomainList = computed(() => {
  const scopes = currentRecord.value?.scope_array || [];
  return scopes.filter(d => getDomainStatus(currentRecord.value, d) === 'unprobed');
});

const probedDomainList = computed(() => {
  const scopes = currentRecord.value?.scope_array || [];
  return scopes.filter(d => getDomainStatus(currentRecord.value, d) === 'probed');
});

const selectAllDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...currentRecord.value.scope_array];
  }
};

const selectUnprobedDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = unprobedDomainList.value.length > 0 ? [...unprobedDomainList.value] : [...currentRecord.value.scope_array];
  }
};

const selectProbedDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...probedDomainList.value];
  }
};

const clearDomains = () => {
  addMonitorForm.domains = [];
};

const submitAddMonitor = async () => {
  try {
    await addMonitorFormRef.value.validate();
    addMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      domain: addMonitorForm.domains.join(','),
      interval: addMonitorForm.interval_hours * 3600,
      policy_id: addMonitorForm.policy_id,
      name: ''
    };
    
    if (addMonitorForm.task_type === 'oneshot') {
      delete payload.interval;
    }

    const apiUrl = addMonitorForm.task_type === 'oneshot' ? '/scheduler/one_time_scan/' : '/scheduler/add/';
    const res = await request.post(apiUrl, payload);

    if (res.code === 200) {
      const successCount = (res.data || res.items || []).length;
      const countMsg = successCount > 0 ? `，共成功下发 ${successCount} 个任务！` : '！';
      
      message.success(addMonitorForm.task_type === 'oneshot' ? `一次性监控任务下发成功${countMsg}` : `添加监控任务成功${countMsg}`);
      addMonitorVisible.value = false;
    } else if (res.code === 699) {
      message.error(res.message);
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addMonitorLoading.value = false;
  }
};

// ================= 添加站点监控任务 =================
const addSiteMonitorVisible = ref(false);
const addSiteMonitorLoading = ref(false);
const addSiteMonitorFormRef = ref();

const addSiteMonitorForm = reactive({ interval_hours: 24 });
const addSiteMonitorRules = {
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }]
};

const openAddSiteMonitorModal = (record) => {
  currentRecord.value = record;
  addSiteMonitorForm.interval_hours = 24;
  addSiteMonitorVisible.value = true;
};

const submitAddSiteMonitor = async () => {
  try {
    await addSiteMonitorFormRef.value.validate();
    addSiteMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      interval: addSiteMonitorForm.interval_hours * 3600
    };

    const res = await request.post('/scheduler/add/site_monitor/', payload);

    if (res.code === 200) {
      message.success('添加站点监控任务成功！');
      addSiteMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message);
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addSiteMonitorLoading.value = false;
  }
};

// ================= 添加WIH监控任务 =================
const addWihMonitorVisible = ref(false);
const addWihMonitorLoading = ref(false);
const addWihMonitorFormRef = ref();

const addWihMonitorForm = reactive({ interval_hours: 24 });
const addWihMonitorRules = {
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }]
};

const openAddWihMonitorModal = (record) => {
  currentRecord.value = record;
  addWihMonitorForm.interval_hours = 24;
  addWihMonitorVisible.value = true;
};

const submitAddWihMonitor = async () => {
  try {
    await addWihMonitorFormRef.value.validate();
    addWihMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      interval: addWihMonitorForm.interval_hours * 3600
    };

    const res = await request.post('/scheduler/add/wih_monitor/', payload);

    if (res.code === 200) {
      message.success('添加WIH监控任务成功！');
      addWihMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message);
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addWihMonitorLoading.value = false;
  }
};

// 监听路由参数联动
watch(() => route.query.scope_id, (newScopeId) => {
  if (newScopeId) {
    activeGroupId.value = 'all';
    searchForm.value._id = newScopeId;
    pagination.current = 1;
    fetchData();
  } else if (searchForm.value._id) {
    searchForm.value._id = undefined;
    pagination.current = 1;
    fetchData();
  }
}, { immediate: true });

const goToReconDetail = (taskId) => {
  if (taskId) {
    router.push({
      path: '/assetRecon/assetDetail',
      query: { task_id: taskId }
    });
  }
};

// ================= 从企业资产任务导入逻辑 =================
const icpImportModalVisible = ref(false);
const icpImportLoading = ref(false);
const importingTaskId = ref('');
const icpImportSearchKey = ref('');
const icpTaskList = ref([]);
const icpImportTarget = ref('add'); // 'add' | 'edit'

const icpImportColumns = [
  { title: '任务名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '查询目标', dataIndex: 'target', key: 'target', ellipsis: true },
  { title: '网站资产数', key: 'statistic', width: 120 },
  { title: '完成时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: '操作', key: 'action', width: 130, align: 'center' }
];

const filteredIcpTasks = computed(() => {
  if (!icpImportSearchKey.value.trim()) return icpTaskList.value;
  const kw = icpImportSearchKey.value.trim().toLowerCase();
  return icpTaskList.value.filter(t =>
    (t.name && t.name.toLowerCase().includes(kw)) ||
    (t.target && t.target.toLowerCase().includes(kw))
  );
});

const openIcpImportModal = async (target = 'add') => {
  icpImportTarget.value = target;
  icpImportModalVisible.value = true;
  icpImportSearchKey.value = '';
  icpImportLoading.value = true;
  try {
    const res = await request.get('/icp/task', { params: { size: 50, status: 'done' } });
    if (res.code === 200) {
      icpTaskList.value = res.items || [];
    }
  } catch (err) {
    console.error('获取企业资产任务列表失败', err);
  } finally {
    icpImportLoading.value = false;
  }
};

const handleImportFromTask = async (task) => {
  importingTaskId.value = task._id;
  try {
    const res = await request.get('/icp/asset', { params: { task_id: task._id, query_type: 'web', size: 10000 } });
    const items = res.items || res.data?.items || [];
    const domainSet = new Set();
    items.forEach(item => {
      const d = item.domain || item.ym;
      if (d && typeof d === 'string') domainSet.add(d.trim().toLowerCase());
    });
    const domainList = Array.from(domainSet);

    if (domainList.length === 0) {
      message.warning('该任务未发现可导入的网站资产');
      return;
    }

    if (icpImportTarget.value === 'add') {
      if (!addForm.name.trim()) {
        addForm.name = task.name || task.target || '';
      }
      const existing = parseScopeList(addForm.scope);
      const merged = Array.from(new Set([...existing, ...domainList]));
      addForm.scope = merged.join('\n');
    } else {
      if (editGroupMode.value === 'visual') {
        const merged = Array.from(new Set([...editGroupScopeList.value, ...domainList]));
        editGroupScopeList.value = merged;
      } else {
        const existing = parseScopeList(editGroupForm.scope);
        const merged = Array.from(new Set([...existing, ...domainList]));
        editGroupForm.scope = merged.join('\n');
      }
    }

    message.success(`成功从任务【${task.name || task.target}】导入 ${domainList.length} 个资产域名！`);
    icpImportModalVisible.value = false;
  } catch (err) {
    console.error('导入资产失败', err);
    message.error('导入失败，请稍后重试');
  } finally {
    importingTaskId.value = '';
  }
};



onDeactivated(() => {
  stopPoll();
});

onUnmounted(() => {
  window.removeEventListener('resize', updateSidebarLeft);
  const siderEl = document.querySelector('.ant-layout-sider');
  if (siderEl) {
    siderEl.removeEventListener('transitionend', updateSidebarLeft);
  }
  if (siderObserver) siderObserver.disconnect();
  stopPoll();
});

</script>

<style scoped>
.arl-scope-visual-panel {
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  background: var(--arl-bg-light, rgba(0, 0, 0, 0.02));
}

.arl-scope-tag-container {
  max-height: 220px;
  min-height: 110px;
  overflow-y: auto;
  padding: 8px;
  border: 1px dashed var(--arl-border-color, #d9d9d9);
  border-radius: 6px;
  background: var(--arl-bg-white, #ffffff);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-content: flex-start;
}

.arl-scope-edit-item-tag {
  margin: 0 !important;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  background: var(--arl-bg-light, #f1f5f9);
  border-color: var(--arl-border-color, #d9d9d9);
  color: var(--arl-text-color, rgba(0, 0, 0, 0.85));
}

.arl-scope-edit-item-tag:hover {
  border-color: #ff4d4f !important;
  background: #fff1f0 !important;
  color: #cf1322 !important;
}

.arl-scope-empty-hint {
  width: 100%;
  text-align: center;
  color: var(--arl-text-color, #8c8c8c);
  opacity: 0.55;
  padding: 36px 0;
  font-size: 13px;
}

.sidebar-collapse-handle {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}
.sidebar-collapse-handle:hover {
  background: var(--arl-bg-light, #f1f5f9) !important;
}
.sidebar-collapse-handle:hover :deep(.anticon) {
  color: var(--arl-theme-color) !important;
}

.sidebar-expand-handle {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}
.sidebar-expand-handle:hover {
  background: var(--arl-bg-light, #f1f5f9) !important;
}
.sidebar-expand-handle:hover :deep(.anticon) {
  color: var(--arl-theme-color) !important;
}

/* 一体化卡片容器 */
.arl-scope-main-card {
  background: var(--arl-bg-white, #ffffff);
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
  padding: 20px 24px;
  position: relative;
  min-height: calc(100vh - 128px);
}

/* 顶部吸附操作区 */
.arl-scope-action-bar {
  position: sticky;
  top: 0px;
  z-index: 10;
  background-color: var(--arl-bg-white, #ffffff);
  margin: -20px -24px 16px -24px;
  padding: 20px 24px 14px 24px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  border-bottom: 1px solid var(--arl-border-color, #e2e8f0);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
}

/* 顶部标题与操作 */
.scope-header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.scope-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.scope-title-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--arl-text-color);
  letter-spacing: -0.2px;
}
.scope-total-tag {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.55;
  background: var(--arl-bg-light, #f1f5f9);
  padding: 2px 8px;
  border-radius: 10px;
}
.group-switch-trigger {
  cursor: pointer;
  color: var(--arl-theme-color);
  font-weight: 500;
}
.scope-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* 筛选表单栏 */
.scope-filter-toolbar {
  margin-bottom: 14px;
}
.scope-filter-form {
  row-gap: 12px;
  align-items: center;
}
.filter-actions-item {
  margin-right: 0 !important;
}

/* 批量操作与选中反馈 */
.scope-batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.batch-buttons-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.selection-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 4px 12px;
  background: rgba(250, 84, 28, 0.08);
  border: 1px solid rgba(250, 84, 28, 0.2);
  border-radius: 6px;
}

/* 表格主体美化 */
.arl-scope-table {
  margin-bottom: 16px;
}
:deep(.arl-scope-table .ant-table-thead > tr > th) {
  font-weight: 600;
  background: var(--arl-bg-light, #f8fafc) !important;
  color: var(--arl-text-color);
  font-size: 13px;
}
:deep(.arl-scope-table .ant-table-tbody > tr > td) {
  padding: 10px 12px !important;
}

/* 资产组名称单元格 */
.group-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}
.group-name-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.group-name-title {
  font-weight: 600;
  color: var(--arl-text-color);
  transition: color 0.2s;
  font-size: 13px;
}
.group-name-title:hover {
  color: var(--arl-theme-color);
}
.enterprise-tag-row {
  display: flex;
  align-items: center;
}
.enterprise-osint-tag {
  font-size: 11px !important;
  line-height: 18px !important;
  cursor: pointer;
  margin-right: 0 !important;
  border-radius: 4px;
}
.group-cell-tag {
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 0;
}

/* 资产范围 Tag 与微圆点 */
.domain-scope-tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
}
.domain-scope-item-tag {
  display: inline-flex !important;
  align-items: center !important;
  font-size: 12px !important;
  line-height: 20px !important;
  padding: 1px 7px !important;
  border-radius: 4px !important;
  margin: 0 !important;
  transition: all 0.2s ease;
}
.domain-scope-item-tag:hover {
  border-color: var(--arl-theme-color) !important;
}
.domain-name-text {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.domain-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 5px;
  flex-shrink: 0;
}
.domain-status-dot.status-probed {
  background-color: #52c41a;
  box-shadow: 0 0 0 1.5px rgba(82, 196, 26, 0.25);
}
.domain-status-dot.status-scanning {
  background-color: #1890ff;
  box-shadow: 0 0 0 1.5px rgba(24, 144, 255, 0.25);
  animation: pulse-dot 1.5s infinite ease-in-out;
}
.domain-status-dot.status-unprobed {
  background-color: #faad14;
  box-shadow: 0 0 0 1.5px rgba(250, 173, 20, 0.25);
}
.domain-status-dot.status-error {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 1.5px rgba(255, 77, 79, 0.25);
}
@keyframes pulse-dot {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
}
.domain-scope-more-tag {
  background: var(--arl-bg-white) !important;
  border: 1px dashed var(--arl-border-color) !important;
  color: var(--arl-text-color) !important;
  opacity: 0.75;
  cursor: pointer;
  margin: 0 !important;
  border-radius: 4px !important;
  font-size: 11px !important;
}
.domain-scope-more-tag:hover {
  border-color: var(--arl-theme-color) !important;
  color: var(--arl-theme-color) !important;
  opacity: 1;
}
.domain-scope-add-tag {
  background: var(--arl-bg-white) !important;
  border: 1px dashed var(--arl-theme-color) !important;
  color: var(--arl-theme-color) !important;
  cursor: pointer;
  margin: 0 !important;
  border-radius: 4px !important;
  font-size: 11px !important;
}
.domain-scope-add-tag:hover {
  background: var(--arl-bg-light) !important;
}

/* 覆盖度胶囊徽章 */
.stat-badge-group {
  display: flex;
  gap: 5px;
  align-items: center;
  flex-wrap: wrap;
  cursor: pointer;
}
.stat-pill-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  line-height: 18px;
}
.stat-pill-badge.badge-scanning {
  background: #e6f7ff;
  color: #096dd9;
  border: 1px solid #91d5ff;
}
.stat-pill-badge.badge-probed {
  background: #f6ffed;
  color: #389e0d;
  border: 1px solid #b7eb8f;
}
.stat-pill-badge.badge-unprobed {
  background: #fffbe6;
  color: #d48806;
  border: 1px solid #ffe58f;
}
.stat-pill-badge.badge-error {
  background: #fff2f0;
  color: #cf1322;
  border: 1px solid #ffccc7;
}

/* ID 样式 */
.scope-id-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.85;
}
.scope-id-text:hover {
  color: var(--arl-theme-color);
}
.copy-id-icon {
  cursor: pointer;
  color: var(--arl-text-color);
  opacity: 0.4;
  font-size: 12px;
  transition: opacity 0.2s;
}
.copy-id-icon:hover {
  opacity: 1;
  color: var(--arl-theme-color);
}

/* 操作列平铺紧凑按钮 */
.table-actions-container {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 2px;
}
:deep(.arl-scope-table .ant-table-cell:last-child) {
  padding-left: 6px !important;
  padding-right: 6px !important;
}
.grid-action-btn {
  padding: 0 4px !important;
  height: 24px !important;
  line-height: 24px !important;
  font-size: 12px !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 2px !important;
  white-space: nowrap !important;
  color: var(--arl-text-color);
  opacity: 0.85;
  transition: all 0.2s ease;
}
.grid-action-btn:hover {
  opacity: 1;
  color: var(--arl-theme-color);
}
.grid-action-btn.btn-theme {
  color: var(--arl-theme-color) !important;
  opacity: 1;
}
.grid-action-btn.btn-success {
  color: #52c41a !important;
  font-weight: 500;
  opacity: 1;
}
.grid-action-btn.btn-danger {
  color: #ff4d4f !important;
  opacity: 0.85;
}
.grid-action-btn.btn-danger:hover {
  opacity: 1;
}

/* 分页条 */
.table-pagination-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px 0 4px;
}
.pagination-summary {
  color: var(--arl-text-color);
  opacity: 0.65;
  font-size: 13px;
}

/* 左侧集团侧边栏样式 */
.sidebar-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--arl-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.sidebar-total-badge {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.55;
  background: var(--arl-bg-light);
  padding: 1px 7px;
  border-radius: 10px;
}
.sidebar-add-btn {
  color: var(--arl-text-color);
  opacity: 0.65;
  transition: all 0.2s;
}
.sidebar-add-btn:hover {
  opacity: 1;
  color: var(--arl-theme-color);
  background: var(--arl-bg-light);
}
.sidebar-search-container {
  padding: 10px 12px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--arl-border-color);
}
.sidebar-scope-pill {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.6;
  background: var(--arl-bg-light, #f1f5f9);
  padding: 0 6px;
  border-radius: 10px;
  line-height: 18px;
  font-weight: 500;
  transition: all 0.2s;
}
.sidebar-group-menu :deep(.ant-menu-item) {
  margin: 2px 8px !important;
  width: calc(100% - 16px) !important;
  border-radius: 6px !important;
  height: 36px !important;
  line-height: 36px !important;
  transition: all 0.2s ease !important;
}
.sidebar-group-menu :deep(.ant-menu-item-selected) {
  background-color: rgba(250, 84, 28, 0.08) !important;
  color: var(--arl-theme-color) !important;
  font-weight: 600 !important;
}
.sidebar-group-menu :deep(.ant-menu-item-selected) .sidebar-scope-pill {
  background-color: var(--arl-bg-white) !important;
  color: var(--arl-theme-color) !important;
  opacity: 0.9;
}
.group-action-icon {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  opacity: 0.45;
  transition: opacity 0.2s;
}
.group-action-icon:hover {
  opacity: 1;
  color: var(--arl-theme-color);
}
</style>