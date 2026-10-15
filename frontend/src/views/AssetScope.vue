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
          <span style="font-weight: 600; font-size: 15px; color: var(--arl-text-color);">资产组视图</span>
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
          :selectedKeys="['all', 'unassigned'].includes(activeGroupId) ? [activeGroupId] : []"
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
        </a-menu>
        
        <div class="sidebar-group-divider"></div>

        <!-- 可拖拽自定义集团列表容器 -->
        <div ref="draggableGroupListRef" class="sidebar-group-draggable-list">
          <div
            v-for="group in filteredGroupList"
            :key="group._id"
            :data-id="group._id"
            class="group-nav-item"
            :class="{ 'group-nav-item-active': activeGroupId === group._id }"
            @click="handleGroupSwitch(group._id)"
          >
            <div style="display: flex; align-items: center; gap: 4px; flex: 1; min-width: 0;">
              <a-tooltip :title="groupSearchKey ? '搜索筛选中已禁用排序' : '按住拖动调整顺序'" placement="left" :mouseEnterDelay="0.4">
                <span
                  class="group-drag-handle"
                  :class="{ 'group-drag-handle-disabled': !!groupSearchKey }"
                  @click.stop
                >
                  <holder-outlined />
                </span>
              </a-tooltip>
              <span
                class="group-name-text"
                :title="group.name"
                style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0;"
              >
                {{ group.name }}
              </span>
            </div>
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
        </div>

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
                <a-breadcrumb-item>资产组</a-breadcrumb-item>
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
            <div class="scope-header-actions" style="display: flex; align-items: center; gap: 12px;">
              <!-- 后台正在自动建组中的任务轻量状态标签 -->
              <a-popover v-if="runningReconTasks.length > 0" placement="bottomRight">
                <template #title>
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600;">企业全景测绘建组队列 ({{ runningReconTasks.length }})</span>
                    <a-button type="link" size="small" style="padding: 0; font-size: 11px; height: auto;" @click="clearAllRunningReconTasks">
                      清空队列
                    </a-button>
                  </div>
                </template>
                <template #content>
                  <div style="min-width: 280px; max-width: 360px;">
                    <div 
                      v-for="t in runningReconTasks" 
                      :key="t.taskId"
                      style="padding: 8px 0; border-bottom: 1px solid var(--arl-border-color); display: flex; justify-content: space-between; align-items: center; gap: 10px;"
                    >
                      <div style="flex: 1; min-width: 0;">
                        <div style="font-weight: 500; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          {{ t.name || t.target }}
                        </div>
                        <div style="font-size: 11px; color: var(--arl-text-color); opacity: 0.65; margin-top: 2px;">
                          天眼查与工商双轨穿透 · 自动建组托管中
                        </div>
                      </div>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <a-tag color="processing" style="margin: 0; font-size: 11px;">
                          <sync-outlined spin /> 测绘中
                        </a-tag>
                        <a-tooltip title="停止追踪并移出队列">
                          <close-outlined 
                            style="cursor: pointer; color: #8c8c8c; font-size: 12px; padding: 2px; transition: color 0.2s;"
                            @click.stop="dismissPendingReconTask(t.taskId)" 
                          />
                        </a-tooltip>
                      </div>
                    </div>
                  </div>
                </template>
                <a-tag color="processing" style="cursor: pointer; padding: 4px 10px; border-radius: 14px; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;">
                  <sync-outlined spin /> <b>{{ runningReconTasks.length }}</b> 个企业全景测绘中
                </a-tag>
              </a-popover>

              <a-button type="primary" @click="openAddModal" class="header-action-btn">
                <PlusOutlined /> 新建资产组
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
              <a-button type="link" size="small" @click="selectedRowKeys = []" style="padding: 0 4px;">取消选择</a-button>
            </div>
          </div>

        </div>

        <a-table 
          :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
          :loading="loading"
          :dataSource="dataSource"
          :columns="columns"
          :pagination="false"
          :scroll="{ x: 1000 }"
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

            <template v-else-if="column.key === 'scope_and_stat'">
              <div class="scope-stat-compact-cell">
                <!-- 顶行：前两个核心主域 + 总数胶囊 -->
                <div class="scope-compact-header">
                  <div class="scope-compact-tags">
                    <span 
                      v-for="(item, idx) in (record.scope_array || []).slice(0, 2)" 
                      :key="idx" 
                      class="scope-compact-domain"
                      :title="item"
                    >
                      <span class="domain-status-dot" :class="'status-' + getDomainStatus(record, item)"></span>
                      {{ item }}
                    </span>
                  </div>
                  <a-popover 
                    v-if="(record.scope_array || []).length > 0" 
                    placement="bottomLeft" 
                    :getPopupContainer="getBodyContainer"
                    trigger="hover"
                  >
                    <template #content>
                      <div class="scope-popover-panel">
                        <div class="scope-popover-header">
                          <span class="scope-popover-title">种子目标清单 ({{ (record.scope_array || []).length }})</span>
                          <a-button type="link" size="small" class="scope-popover-copy-btn" @click="copyText((record.scope_array || []).join('\n'))">
                            <copy-outlined /> 复制全部
                          </a-button>
                        </div>
                        <div class="scope-popover-list">
                          <a-tooltip
                            v-for="(item, idx) in (record._sorted_scopes || record.scope_array || [])"
                            :key="idx"
                            placement="right"
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
                            <div class="scope-popover-item">
                              <div class="scope-popover-item-main">
                                <span class="domain-status-dot" :class="'status-' + getDomainStatus(record, item)"></span>
                                <span v-if="record.domain_status?.[item]?.sync_source === 'icp'" style="color: var(--arl-theme-color); margin-right: 3px; font-size: 11px;" title="来自企业资产同步">⚑</span>
                                <span class="scope-popover-item-text">{{ item }}</span>
                              </div>
                              <span class="scope-popover-item-status" :class="'text-' + getDomainStatus(record, item)">
                                {{ getDomainStatusLabel(record, item) }}
                              </span>
                            </div>
                          </a-tooltip>
                        </div>
                      </div>
                    </template>
                    <span class="scope-compact-count-badge">
                      共 {{ (record.scope_array || []).length }} 个
                    </span>
                  </a-popover>
                  <span v-else style="color: var(--arl-text-color); opacity: 0.45; font-size: 12px;">无目标</span>
                </div>

                <!-- 底行：微型健康进度条与覆盖率 -->
                <div v-if="record.domain_stat && record.domain_stat.total > 0" class="scope-compact-progress-row">
                  <a-tooltip placement="top">
                    <template #title>
                      <div style="line-height: 1.8; font-size: 12px;">
                        <div>总种子数: <strong>{{ record.domain_stat.total }}</strong></div>
                        <div v-if="record.domain_stat.scanning > 0">探测中: <strong style="color: #1890ff;">{{ record.domain_stat.scanning }}</strong></div>
                        <div>已探测: <strong style="color: #52c41a;">{{ record.domain_stat.probed }}</strong> ({{ Math.round((record.domain_stat.probed / record.domain_stat.total) * 100) }}%)</div>
                        <div v-if="record.domain_stat.unprobed > 0">待探测: <strong style="color: #faad14;">{{ record.domain_stat.unprobed }}</strong></div>
                        <div v-if="record.domain_stat.error > 0">探测异常: <strong style="color: #ff4d4f;">{{ record.domain_stat.error }}</strong></div>
                      </div>
                    </template>
                    <div class="scope-mini-progress-bar">
                      <div 
                        class="progress-seg probed" 
                        :style="{ width: ((record.domain_stat.probed / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                      <div 
                        v-if="record.domain_stat.scanning > 0" 
                        class="progress-seg scanning" 
                        :style="{ width: ((record.domain_stat.scanning / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                      <div 
                        v-if="record.domain_stat.error > 0" 
                        class="progress-seg error" 
                        :style="{ width: ((record.domain_stat.error / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                      <div 
                        v-if="record.domain_stat.unprobed > 0" 
                        class="progress-seg unprobed" 
                        :style="{ width: ((record.domain_stat.unprobed / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                    </div>
                  </a-tooltip>
                  <span class="scope-compact-progress-text">
                    {{ Math.round((record.domain_stat.probed / record.domain_stat.total) * 100) }}% 覆盖
                  </span>
                </div>
              </div>
            </template>

            <template v-else-if="column.key === 'scope_id'">
              <div style="display: flex; align-items: center; gap: 8px;">
                <a class="scope-id-text" @click="goToDetail(record)">{{ record._id }}</a>
                <a-tooltip title="复制资产组 ID">
                  <copy-outlined
                    class="copy-id-icon"
                    @click="copyText(record._id)"
                  />
                </a-tooltip>
              </div>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="table-actions-container">
                <a-button type="link" size="small" class="grid-action-btn btn-theme" @click="goToDetail(record)">
                  <RightCircleOutlined />进入
                </a-button>
                <a-button type="link" size="small" class="grid-action-btn" @click="openEditGroupModal(record)">
                  <EditOutlined />编辑
                </a-button>
                <a-dropdown :getPopupContainer="getBodyContainer">
                  <a-button type="link" size="small" class="grid-action-btn">
                    <ScheduleOutlined />调度 <DownOutlined style="font-size: 10px;" />
                  </a-button>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="monitor" @click="openAddMonitorModal(record)">
                        <DashboardOutlined style="color: #1890ff; margin-right: 6px;" />资产监控扫描
                      </a-menu-item>
                      <a-menu-item key="site" @click="openAddSiteMonitorModal(record)">
                        <GlobalOutlined style="color: #52c41a; margin-right: 6px;" />站点存活监控
                      </a-menu-item>
                      <a-menu-item key="wih" @click="openAddWihMonitorModal(record)">
                        <RadarChartOutlined style="color: #722ed1; margin-right: 6px;" />WIH 监控
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
                <a-button
                  v-if="record.has_increment"
                  type="link"
                  size="small"
                  class="grid-action-btn btn-success"
                  @click="openSyncIncrement(record)"
                  title="发现新增资产，点击同步入库"
                >
                  <SyncOutlined />增量
                </a-button>
                <a-button
                  v-else-if="!record.synced_icp_task_id"
                  type="link"
                  size="small"
                  class="grid-action-btn"
                  style="color: #fa8c16;"
                  @click="openBindEnterprise(record)"
                  title="尚未绑定企业主体，点击关联"
                >
                  <LinkOutlined />绑定
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

    <!-- 新建资产组弹窗 -->
    <a-modal
      v-model:open="addModalVisible"
      title="新建资产组"
      :width="creationMode === 'wizard' && wizardStep === 2 ? '780px' : '640px'"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :footer="creationMode === 'wizard' && wizardStep === 1 ? null : (creationMode === 'wizard' ? null : undefined)"
      @ok="handleAddSubmit"
      :confirmLoading="addLoading"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <div style="margin-bottom: 20px; text-align: center;">
        <a-radio-group v-model:value="creationMode" button-style="solid" size="middle">
          <a-radio-button value="wizard">🏢 企业全景测绘建组</a-radio-button>
          <a-radio-button value="manual">✍️ 手工录入资产</a-radio-button>
        </a-radio-group>
      </div>

      <!-- 手工录入模式 -->
      <a-form
        v-if="creationMode === 'manual'"
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        :label-col="{ style: { width: '110px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 110px)' } }"
        style="margin-top: 10px;"
      >
        <a-form-item label="所属集团" name="group_id">
          <a-select v-model:value="addForm.group_id" placeholder="请选择所属集团（可选）" allowClear :getPopupContainer="(trigger) => trigger.parentNode">
            <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="资产组名称" name="name">
          <a-input v-model:value="addForm.name" placeholder="请输入资产组名称" allowClear />
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

      <!-- 企业全景测绘建组模式 -->
      <div v-else-if="creationMode === 'wizard'">
        <!-- Stage 1: 全景测绘建组表单 -->
        <div v-if="wizardStep === 1">
          <a-spin :spinning="wizardLoading" :tip="wizardLoadingTip">
            <a-form
              ref="wizardFormRef"
              :model="wizardForm"
              :label-col="{ style: { width: '120px' } }"
              :wrapper-col="{ style: { width: 'calc(100% - 120px)' } }"
              style="margin-top: 8px;"
            >
              <!-- 引擎引导提示 -->
              <a-alert
                type="info"
                show-icon
                style="margin-bottom: 16px; border-radius: 6px; font-size: 12px;"
              >
                <template #message>
                  <span style="color: var(--arl-text-color); line-height: 1.5;">
                    输入天眼查企业链接或纯数字 GID，系统将穿透投资控股树，并联动工信部 ICP 双轨查重；建组后由当前页面自动纳管入库。
                  </span>
                </template>
              </a-alert>

              <!-- 输入目标: 企业目标 (支持链接与纯数字ID) -->
              <a-form-item
                label="企业目标"
                required
                :validateStatus="wizardTargetError ? 'error' : ''"
                :help="wizardTargetError"
              >
                <a-input
                  v-model:value="wizardForm.target"
                  placeholder="可粘贴天眼查链接（如 company/25174642）、GID 或企业工商全称"
                  allowClear
                  @change="onTycTargetChange"
                  @pressEnter="startWizardRecon"
                >
                  <template #prefix>
                    <component :is="parsedTycGid ? 'LinkOutlined' : 'BankOutlined'" style="color: #bfbfbf;" />
                  </template>
                </a-input>
                <div v-if="parsedTycGid" style="margin-top: 4px; font-size: 12px; color: var(--ant-primary-color); display: flex; align-items: center; gap: 4px;">
                  <check-circle-outlined /> <span>按天眼查 GID 解析: <b>{{ parsedTycGid }}</b> (将在提交后校验并执行全景双轨穿透)</span>
                </div>
                <div v-else-if="isWizardCompanyName" style="margin-top: 4px; font-size: 12px; color: #722ed1; display: flex; align-items: center; gap: 4px;">
                  <safety-certificate-outlined /> <span>已识别企业工商主体: <b>{{ wizardForm.target.trim() }}</b> (来源：工信部 ICP 备案)</span>
                </div>
              </a-form-item>

              <!-- 资产组名称 (选填，留空自动生成) -->
              <a-form-item
                label="资产组名称"
                tooltip="留空将默认采用企业官方工商全称或 TYC_公司ID 自动命名"
              >
                <a-input
                  v-model:value="wizardForm.name"
                  placeholder="选填，留空将自动根据企业工商全称命名"
                  allowClear
                  @pressEnter="startWizardRecon"
                />
              </a-form-item>

              <!-- 所属集团 (选填) -->
              <a-form-item label="所属集团">
                <a-select
                  v-model:value="wizardForm.group_id"
                  placeholder="请选择所属集团（可选）"
                  allowClear
                  show-search
                  option-filter-prop="label"
                  :getPopupContainer="(trigger) => trigger.parentNode"
                >
                  <a-select-option v-for="g in groupList" :key="g._id" :value="g._id" :label="g.name">{{ g.name }}</a-select-option>
                </a-select>
              </a-form-item>

              <!-- 自动化托管与探测偏好 -->
              <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px 14px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                  <span style="font-weight: 500; font-size: 13px;">⚡ 自动化建组与探测偏好</span>
                </div>
                <div style="margin-bottom: 10px;">
                  <a-checkbox v-model:checked="wizardAutoSync">
                    <b>测绘完成后自动纳管建组</b>
                    <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7; margin-left: 6px;">
                      (测绘完成后由后端自动检索并建组入库，无需保持本页面打开)
                    </span>
                  </a-checkbox>
                </div>
                <div>
                  <a-checkbox v-model:checked="wizardAutoScan">
                    <b>建组后立即发起主动探测扫描</b>
                    <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7; margin-left: 6px;">
                      (对新发现网站域名自动下发端口与指纹探测)
                    </span>
                  </a-checkbox>
                </div>

                <div v-if="wizardAutoScan" style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--arl-border-color);">
                  <a-row :gutter="12">
                    <a-col :span="12">
                      <a-form-item label="扫描策略" :label-col="{ style: { width: '80px' } }" :wrapper-col="{ style: { width: 'calc(100% - 80px)' } }" style="margin-bottom: 0;" required>
                        <a-select
                          v-model:value="wizardPolicyId"
                          placeholder="请选择扫描策略"
                          size="small"
                          :options="policyList.map(p => ({ value: p._id, label: p.name }))"
                        />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="任务类型" :label-col="{ style: { width: '80px' } }" :wrapper-col="{ style: { width: 'calc(100% - 80px)' } }" style="margin-bottom: 0;">
                        <a-radio-group v-model:value="wizardTaskType" size="small">
                          <a-radio-button value="oneshot">一次性扫描</a-radio-button>
                          <a-radio-button value="periodic">周期监控</a-radio-button>
                        </a-radio-group>
                      </a-form-item>
                    </a-col>
                  </a-row>
                </div>
              </div>

              <!-- 高级测绘参数（常驻平铺展示） -->
              <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px 14px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                  <span style="font-weight: 500; font-size: 13px;">⚙️ 高级测绘参数</span>
                </div>
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item
                      label="投资层级"
                      :label-col="{ style: { width: '90px' } }"
                      :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
                      style="margin-bottom: 8px;"
                      tooltip="穿透控股子公司与参股公司的递归深度 (1~20)。层级越高，天眼查 API 调用量与执行耗时增长越明显，且会消耗付费查询额度，请按需设置"
                    >
                      <a-input-number
                        v-model:value="wizardForm.depth"
                        :min="1"
                        :max="20"
                        size="small"
                        style="width: 110px;"
                        addon-after="层"
                      />
                      <div v-if="wizardForm.depth > 1" class="depth-cost-hint">
                        已设置为 {{ wizardForm.depth }} 层，将递归查询下属企业，API 调用量与付费额度消耗相应增加
                      </div>
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item
                      label="控股比例"
                      :label-col="{ style: { width: '90px' } }"
                      :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
                      style="margin-bottom: 8px;"
                      tooltip="对外投资的最小持股比例 (1~100%)"
                    >
                      <a-input-number
                        v-model:value="wizardForm.invest_ratio"
                        :min="1"
                        :max="100"
                        size="small"
                        style="width: 110px;"
                        addon-after="%"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>

                <a-form-item
                  label="ICP 双轨查重"
                  :label-col="{ style: { width: '90px' } }"
                  :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
                  style="margin-bottom: 0;"
                  tooltip="调用工信部 ICP 备案数据接口进行双轨校对与兜底补全"
                >
                  <a-switch v-model:checked="wizardForm.enable_icp" size="small" />
                  <span style="font-size: 12px; margin-left: 8px; color: var(--arl-text-color); opacity: 0.7;">
                    {{ wizardForm.enable_icp ? '已启用（推荐）' : '已关闭' }}
                  </span>
                </a-form-item>
              </div>

              <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px;">
                <a-button @click="addModalVisible = false">取 消</a-button>
                <a-button type="primary" :loading="wizardLoading" @click="startWizardRecon">
                  <template #icon><rocket-outlined /></template>
                  {{ wizardAutoSync ? '🚀 开始全景测绘并自动建组' : '开始全景测绘并解析 →' }}
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
              :description="`所属集团：${getGroupName(wizardForm.group_id) || '未分组'} | 资产组名称：${wizardForm.name.trim() || (wizardForm.target.trim() ? 'TYC_' + wizardForm.target.trim() : '未命名')}`"
            />
          </div>

          <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; gap: 6px; align-items: center;">
              <a-input v-model:value="wizardDomainSearch" placeholder="过滤域名..." size="small" style="width: 160px;" allowClear />
              <a-button size="small" @click="selectAllWizardDomains">全选</a-button>
              <a-button size="small" @click="selectedWizardDomains = []">取消全选</a-button>
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

    <!-- 编辑资产组弹窗 -->
    <a-modal
      v-model:open="editGroupModalVisible"
      title="编辑资产组"
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
          <!-- 提前告知剔除范围的级联后果，避免用户仅在点击保存后才被动获知 -->
          <div style="background: rgba(250, 173, 20, 0.12); border: 1px solid rgba(250, 173, 20, 0.3); border-radius: 4px; padding: 6px 10px; margin-bottom: 8px; font-size: 12px; color: #faad14; line-height: 1.5;">
            ⚠️ 移除资产范围将同时级联清理该范围内已发现的子域名、IP、站点与 WIH 资产，且不可恢复；保存前会再次确认。
          </div>
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

import { ref, reactive, computed, createVNode, watch, onActivated, onDeactivated, onUnmounted, onMounted, nextTick } from 'vue';
import Sortable from 'sortablejs';
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
import { message, Modal, notification, Button } from 'ant-design-vue';
import { h } from 'vue';
import SyncToScopeModal from '../components/SyncToScopeModal.vue';
import { 
  SearchOutlined, 
  DownOutlined, 
  ExclamationCircleOutlined, 
  QuestionCircleOutlined, 
  PlusOutlined, 
  DeleteOutlined,
  BankOutlined,
  SyncOutlined,
  ReloadOutlined,
  FolderOpenOutlined,
  EditOutlined,
  LinkOutlined,
  DashboardOutlined,
  GlobalOutlined,
  RadarChartOutlined,
  ApartmentOutlined,
  InfoCircleOutlined,
  RightCircleOutlined,
  ScheduleOutlined,
  CloseOutlined
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
    { title: '资产组名称', key: 'name', width: 220, sorter: true },
    { title: '种子目标与覆盖度', key: 'scope_and_stat', minWidth: 260 },
    { title: '组 ID', key: 'scope_id', width: 150 },
    { title: '操作', key: 'action', width: 250, fixed: 'right' }
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
      if (!silent) {
        selectedRowKeys.value = [];
      }
      checkAndSchedulePoll();
    }
  } catch (error) {
    if (currentFetchContextId === fetchContextId) {
      message.error('加载资产组失败');
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

// Sortable 拖拽排序逻辑
const draggableGroupListRef = ref(null);
let sortableInstance = null;
let originalListSnapshot = null;
let saveOrderTimer = null;

const initSortable = () => {
  if (!draggableGroupListRef.value) return;
  if (sortableInstance) {
    sortableInstance.destroy();
    sortableInstance = null;
  }
  sortableInstance = new Sortable(draggableGroupListRef.value, {
    animation: 150,
    handle: '.group-drag-handle',
    ghostClass: 'group-drag-ghost',
    chosenClass: 'group-drag-chosen',
    dragClass: 'group-drag-active',
    filter: '.group-action-icon, .ant-dropdown-trigger, .group-drag-handle-disabled',
    preventOnFilter: false,
    disabled: !!groupSearchKey.value,
    onEnd: (evt) => {
      const { oldIndex, newIndex, item, from } = evt;
      if (oldIndex === newIndex || oldIndex == null || newIndex == null) return;
      
      // 记录首轮拖动前的原始快照（用于故障原子回滚）
      if (!originalListSnapshot) {
        originalListSnapshot = [...groupList.value];
      }

      // 核心加固：撤销 Sortable 的物理 DOM 变更，使真实 DOM 树与 Vue 虚拟 DOM 现有状态对齐，杜绝高亮激活项重复插入
      if (from && item && item.parentNode === from) {
        from.removeChild(item);
        if (oldIndex >= from.children.length) {
          from.appendChild(item);
        } else {
          from.insertBefore(item, from.children[oldIndex]);
        }
      }
      
      // 乐观重排前端响应式数据
      const movedItem = groupList.value.splice(oldIndex, 1)[0];
      groupList.value.splice(newIndex, 0, movedItem);
      
      // 防抖触发持久化保存
      triggerSaveOrder();
    }
  });
};

const triggerSaveOrder = () => {
  if (saveOrderTimer) clearTimeout(saveOrderTimer);
  saveOrderTimer = setTimeout(async () => {
    const rollbackSnapshot = originalListSnapshot;
    originalListSnapshot = null;
    try {
      const orderIds = groupList.value.map(g => g._id);
      const res = await request.post('/asset_group/reorder/', { order_ids: orderIds });
      if (res.code === 200) {
        groupList.value.forEach((g, idx) => {
          g.sort_order = idx;
        });
      } else {
        message.error(res.message || '排序保存失败，已自动恢复');
        if (rollbackSnapshot) {
          groupList.value = rollbackSnapshot;
        }
      }
    } catch (err) {
      message.error('网络请求异常，排序已自动恢复');
      if (rollbackSnapshot) {
        groupList.value = rollbackSnapshot;
      }
    }
  }, 400);
};

watch(groupSearchKey, (newVal) => {
  if (sortableInstance) {
    sortableInstance.option('disabled', !!newVal);
  }
});

// fetch groups
const fetchGroups = async () => {
  try {
    const res = await request.get('/asset_group/', { params: { size: 1000 } });
    if (res.code === 200) {
      groupList.value = res.items || [];
      nextTick(() => {
        initSortable();
      });
    }
  } catch (err) {}
};

// handle group switch with confirmation guard
const handleGroupSwitch = (info) => {
  const newKey = (info && typeof info === 'object' && info.key) ? info.key : info;
  if (newKey === activeGroupId.value) return;
  
  if (selectedRowKeys.value.length > 0) {
    Modal.confirm({
      title: '切换分组提示',
      content: `您当前已勾选 ${selectedRowKeys.value.length} 个资产组尚未处理。切换左侧视图将取消这些勾选，是否继续？`,
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
  loadPendingReconTasks();
  if (pendingReconTasks.value.some(t => t.status === 'running')) {
    startReconPoller();
  }
});

onActivated(() => {
  if (route.path === '/group') {
    fetchGroups();
    fetchData(true);
  }
  updateSidebarLeft();
  loadPendingReconTasks();
  if (pendingReconTasks.value.some(t => t.status === 'running')) {
    startReconPoller();
  }
});

// Update the initial addForm and editGroupForm state definitions

// ================= 新建资产组逻辑 =================
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

// 新建资产组模式与向导状态
const creationMode = ref('wizard'); // 'wizard' | 'manual'
const wizardStep = ref(1);
const wizardLoading = ref(false);
const wizardLoadingTip = ref('正在发起企业测绘...');
const wizardTaskId = ref('');
const wizardDomains = ref([]);
const selectedWizardDomains = ref([]);
const wizardDomainSearch = ref('');
const wizardAutoSync = ref(true); // 测绘完成后是否由后端自动纳管建组
const wizardAutoScan = ref(false);
const wizardTaskType = ref('oneshot');
const wizardPolicyId = ref('');
const wizardSubmitting = ref(false);
const policyList = ref([]);
const wizardEngine = ref('tyc'); // 'tyc' | 'icp'
const wizardTargetError = ref('');

const wizardForm = reactive({
  group_id: undefined,
  target: '',
  name: '',
  depth: 1,
  invest_ratio: 50,
  enable_icp: true
});

const parseTycInput = (input) => {
  if (!input) return { gid: '', isUrl: false, isName: false, raw: '' };
  const str = input.trim();
  const urlMatch = str.match(/(?:tianyancha\.com\/company\/|^company\/)([a-zA-Z0-9]+)/i);
  if (urlMatch && urlMatch[1]) {
    return { gid: urlMatch[1], isUrl: true, isName: false, raw: str };
  }
  // 仅纯数字串视为 GID（天眼查 GID 为数字）；其余字母数字混排（如 "alibaba"）
  // 按企业名称处理，交由后端检索匹配，避免误把普通输入当成 GID。
  if (/^\d+$/.test(str)) {
    return { gid: str, isUrl: false, isName: false, raw: str };
  }
  if (str.length >= 2) {
    return { gid: '', isUrl: false, isName: true, raw: str };
  }
  return { gid: '', isUrl: false, isName: false, raw: str };
};

const parsedTycGid = computed(() => {
  if (!wizardForm.target) return '';
  const parsed = parseTycInput(wizardForm.target);
  return parsed.gid;
});

const isWizardCompanyName = computed(() => {
  if (!wizardForm.target) return false;
  const parsed = parseTycInput(wizardForm.target);
  return parsed.isName;
});

const onTycTargetChange = () => {
  wizardTargetError.value = '';
};

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

// ================= 企业测绘后台异步追踪与免等建组 =================
const PENDING_RECON_KEY = 'arl_pending_wizard_recon_tasks';
const pendingReconTasks = ref([]);
const activeResumeTaskId = ref('');

const loadPendingReconTasks = () => {
  try {
    const raw = localStorage.getItem(PENDING_RECON_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        const now = Date.now();
        const valid = parsed.filter(t => (now - (t.startTime || 0)) < 86400000);
        const expired = parsed.filter(t => (now - (t.startTime || 0)) >= 86400000);
        pendingReconTasks.value = valid;
        // 超期追踪记录不再轮询，仅如实告知，避免任务静默停留于“测绘中”
        if (expired.length > 0) {
          notification.warning({
            key: 'recon_expired_notice',
            message: `有 ${expired.length} 个企业全景测绘任务已超出自动追踪时限`,
            description: '自动纳管建组已改由后端执行，不依赖本页面。此处仅停止本页面的进度展示，请前往任务管理查看最终结果。',
            duration: 10
          });
        }
      }
    }
  } catch (e) {
    console.error('Failed to load pending recon tasks', e);
  }
};

const savePendingReconTasks = () => {
  try {
    localStorage.setItem(PENDING_RECON_KEY, JSON.stringify(pendingReconTasks.value));
  } catch (e) {
    console.error('Failed to save pending recon tasks', e);
  }
};

const addPendingReconTask = (task) => {
  const existingIdx = pendingReconTasks.value.findIndex(t => t.taskId === task.taskId);
  if (existingIdx >= 0) {
    pendingReconTasks.value[existingIdx] = task;
  } else {
    pendingReconTasks.value.unshift(task);
  }
  savePendingReconTasks();
};

const dismissPendingReconTask = (taskId) => {
  pendingReconTasks.value = pendingReconTasks.value.filter(t => t.taskId !== taskId);
  savePendingReconTasks();
  notification.close(`recon_done_${taskId}`);
};

const clearAllRunningReconTasks = () => {
  pendingReconTasks.value = [];
  savePendingReconTasks();
  stopReconPoller();
  message.success('已清空后台企业测绘建组队列');
};

const runningReconTasks = computed(() => {
  return pendingReconTasks.value.filter(t => t.status === 'running');
});

let reconPollerTimer = null;

const startReconPoller = () => {
  if (reconPollerTimer) return;
  reconPollerTimer = setInterval(pollRunningReconTasks, 4000);
};

const stopReconPoller = () => {
  if (reconPollerTimer) {
    clearInterval(reconPollerTimer);
    reconPollerTimer = null;
  }
};

const pollRunningReconTasks = async () => {
  const runningTasks = pendingReconTasks.value.filter(t => t.status === 'running');
  if (runningTasks.length === 0) {
    stopReconPoller();
    return;
  }

  for (const task of runningTasks) {
    try {
      const checkRes = await request.get('/icp/task', { params: { _id: task.taskId } });
      if (checkRes.code === 200 && checkRes.items) {
        if (checkRes.items.length === 0) {
          // 数据库中该任务已不存在（已被删除），立即收敛移除追踪，不再轮询
          dismissPendingReconTask(task.taskId);
          continue;
        }

        const taskObj = checkRes.items[0];
        // 关键：只要任务不是 running 也不是 waiting，一律从运行追踪队列收敛
        if (taskObj.status !== 'running' && taskObj.status !== 'waiting') {
          if (taskObj.status === 'stop') {
            task.status = 'stop';
            savePendingReconTasks();
            dismissPendingReconTask(task.taskId);
            notification.warning({
              key: `recon_stop_${task.taskId}`,
              message: `企业全景测绘已手动停止：${task.name || task.target}`,
              description: '任务已被停止，系统不会自动建组或纳管资产。',
              duration: 6
            });
            continue;
          }

          if (taskObj.status === 'error') {
            task.status = 'error';
            savePendingReconTasks();
            dismissPendingReconTask(task.taskId);
            notification.error({
              key: `recon_err_${task.taskId}`,
              message: `企业全景测绘执行异常：${task.name || task.target}`,
              description: taskObj.error_msg || '测绘任务执行发生错误，您可前往任务管理查看详细执行日志。'
            });
            continue;
          }

          if (taskObj.status === 'done') {
            const assetRes = await request.get('/icp/asset', { params: { task_id: task.taskId, query_type: 'web', size: 5000 } });
            const domainSet = new Set();
            if (assetRes.code === 200 && assetRes.items) {
              assetRes.items.forEach(item => {
                const d = item.domain || item.ym;
                if (d && typeof d === 'string') domainSet.add(d.trim().toLowerCase());
              });
            }
            const domainList = Array.from(domainSet);
            task.status = 'done';
            task.domains = domainList;
            savePendingReconTasks();

            // 若开启了免等自动建组 (autoSync 默认开启)
            if (task.autoSync) {
              if (domainList.length === 0) {
                dismissPendingReconTask(task.taskId);
                notification.warning({
                  key: `recon_done_${task.taskId}`,
                  message: `企业全景测绘未发现网站域名：${task.name || task.target}`,
                  description: '已完成企业关系与备案检索，但在工信部与天眼查未发现可纳管的网站域名。',
                  duration: 6
                });
              } else {
                const targetName = task.groupName || taskObj.company_name || (task.name ? task.name.replace(/(?:企业测绘|全景测绘)$/, '') : ('TYC_' + task.target));
                const syncPayload = {
                  mode: 'new',
                  target_name: targetName,
                  group_id: task.group_id || '',
                  selected_domains: domainList,
                  auto_scan: !!task.autoScan,
                  task_type: task.taskType || 'oneshot',
                  policy_id: task.policyId || ''
                };
                const syncRes = await request.post(`/icp/sync/${task.taskId}`, syncPayload);
                dismissPendingReconTask(task.taskId);
                if (syncRes.code === 200) {
                  notification.success({
                    key: `recon_done_${task.taskId}`,
                    message: `🎉 企业资产组已自动创建完成`,
                    description: `企业【${targetName}】已成功建组并纳管 ${domainList.length} 个网站域名${task.autoScan ? '，已同步下发主动探测扫描' : ''}！`,
                    duration: 8
                  });
                  fetchData();
                } else {
                  notification.error({
                    key: `recon_done_${task.taskId}`,
                    message: `自动建组失败：${targetName}`,
                    description: syncRes.message || '资产导入异常'
                  });
                }
              }
            } else {
              // 用户显式取消了自动成组，保留手动确认
              notification.success({
                key: `recon_done_${task.taskId}`,
                message: `企业全景测绘已完成：${task.name || task.target}`,
                description: `共发现 ${domainList.length} 个网站域名资产，可立即挑选入库并激活资产组。`,
                btn: () => h(
                  Button,
                  {
                    type: 'primary',
                    size: 'small',
                    onClick: () => {
                      notification.close(`recon_done_${task.taskId}`);
                      resumeWizardFromCompletedTask(task);
                    }
                  },
                  { default: () => '立即挑选建组 →' }
                ),
                duration: 0
              });
            }
            continue;
          }

          // 兜底任何其他非运行状态
          dismissPendingReconTask(task.taskId);
        }
      }
    } catch (err) {
      console.error(`Error polling recon task ${task.taskId}`, err);
    }
  }
};

const resumeWizardFromCompletedTask = async (task) => {
  creationMode.value = 'wizard';
  wizardStep.value = 2;
  wizardTaskId.value = task.taskId;
  wizardForm.group_id = task.group_id;
  wizardForm.target = task.target;
  wizardForm.name = task.name.startsWith('TYC_') ? '' : task.name.replace(/(?:企业测绘|全景测绘)$/, '');
  wizardDomains.value = task.domains || [];
  selectedWizardDomains.value = (task.domains || []).slice();
  wizardDomainSearch.value = '';
  wizardAutoScan.value = false;
  activeResumeTaskId.value = task.taskId;

  if (policyList.value.length === 0) {
    try {
      const pRes = await request.get('/policy/', { params: { size: 100 } });
      if (pRes.code === 200 && pRes.items?.length > 0) {
        policyList.value = pRes.items;
        wizardPolicyId.value = pRes.items[0]._id;
      }
    } catch (e) {
      console.error(e);
    }
  }

  addModalVisible.value = true;
};

// 自动纳管建组意图随任务一并下发，由后端调度器消费。
// 这样建组不再依赖当前浏览器页面存活，关闭页面也会正常完成。
const buildAutoGroupIntent = () => ({
  auto_group: wizardAutoSync.value,
  auto_group_scan: wizardAutoScan.value,
  auto_group_task_type: wizardTaskType.value || 'oneshot',
  auto_group_policy_id: wizardPolicyId.value || '',
  auto_group_interval_hours: 24,
  group_id: wizardForm.group_id || ''
});

const startWizardRecon = async () => {
  wizardTargetError.value = '';
  const rawTarget = (wizardForm.target || '').trim();
  const customName = (wizardForm.name || '').trim();

  if (!rawTarget) {
    wizardTargetError.value = '请输入天眼查企业链接、GID 或企业工商全称';
    return;
  }

  const parsed = parseTycInput(rawTarget);
  if (!parsed.gid && !parsed.isName) {
    wizardTargetError.value = '未能识别有效目标，请输入企业主页链接、ID 或企业工商注册全称';
    return;
  }

  // 校验自动扫描策略
  if (wizardAutoScan.value && !wizardPolicyId.value) {
    message.warning('已勾选自动探测，请选择扫描策略');
    return;
  }

  wizardLoading.value = true;
  try {
    let taskId = '';
    let taskName = '';
    let isTycUpgraded = false;

    if (parsed.gid) {
      taskName = customName ? (customName + '全景测绘') : ('TYC_' + parsed.gid);
      const payload = {
        name: taskName,
        gid: parsed.gid,
        depth: wizardForm.depth || 1,
        invest_ratio: wizardForm.invest_ratio || 50,
        enable_icp: wizardForm.enable_icp !== false,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
        ...buildAutoGroupIntent()
      };
      if (customName) {
        payload.company_name = customName;
      }
      const taskRes = await request.post('/icp/tyc_task', payload);
      if (!taskRes || taskRes.code !== 200) {
        message.error(taskRes?.message || '发起企业全景测绘失败');
        wizardLoading.value = false;
        return;
      }
      taskId = taskRes.data?.task_id || taskRes.data?._id || taskRes.task_id;
    } else {
      taskName = customName || rawTarget;
      const payload = {
        name: taskName,
        target: rawTarget,
        depth: wizardForm.depth || 1,
        invest_ratio: wizardForm.invest_ratio || 50,
        enable_icp: wizardForm.enable_icp !== false,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
        ...buildAutoGroupIntent()
      };
      const taskRes = await request.post('/icp/task', payload);
      if (!taskRes || taskRes.code !== 200) {
        message.error(taskRes?.message || '发起企业全景测绘失败');
        wizardLoading.value = false;
        return;
      }
      taskId = taskRes.data?.task_id || taskRes.data?._id || taskRes.task_id;
      isTycUpgraded = !!taskRes.data?.matched_tyc;
    }

    wizardTaskId.value = taskId;

    // 立即关闭弹窗，改为后台异步追踪建组状态
    addModalVisible.value = false;
    wizardLoading.value = false;

    // 注册到后台追踪队列
    addPendingReconTask({
      taskId: taskId,
      engine: (parsed.gid || isTycUpgraded) ? 'tyc' : 'icp',
      name: taskName,
      target: parsed.gid || rawTarget,
      groupName: customName,
      group_id: wizardForm.group_id || '',
      autoSync: wizardAutoSync.value,
      autoScan: wizardAutoScan.value,
      taskType: wizardTaskType.value,
      policyId: wizardPolicyId.value,
      status: 'running',
      startTime: Date.now()
    });

    // 启动非阻塞轮询器
    startReconPoller();

    // 弹出通知
    notification.info({
      key: `recon_start_${taskId}`,
      message: '企业全景测绘建组任务已提交后台',
      description: wizardAutoSync.value
        ? `目标【${taskName}】全景测绘已下发。系统将检索并纳管资产，完成后由后端自动创建资产组并导入资产。`
        : `目标【${taskName}】全景测绘已下发，完成后将通知您挑选域名建组。`,
      duration: 4.5
    });

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
      target_name: wizardForm.name.trim() || ('TYC_' + wizardForm.target.trim()),
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
      if (activeResumeTaskId.value) {
        dismissPendingReconTask(activeResumeTaskId.value);
        activeResumeTaskId.value = '';
      } else if (wizardTaskId.value) {
        dismissPendingReconTask(wizardTaskId.value);
      }
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

const openAddModal = async () => {
  creationMode.value = 'wizard';
  wizardStep.value = 1;
  wizardEngine.value = 'tyc';
  wizardAutoSync.value = true;
  wizardAutoScan.value = false;
  wizardTaskType.value = 'oneshot';
  wizardTargetError.value = '';

  const defaultGroupId = (activeGroupId.value === 'all' || activeGroupId.value === 'unassigned') ? undefined : activeGroupId.value;
  wizardForm.group_id = defaultGroupId;
  wizardForm.target = '';
  wizardForm.name = '';
  wizardForm.depth = 1;
  wizardForm.invest_ratio = 50;
  wizardForm.enable_icp = true;
  wizardDomains.value = [];
  selectedWizardDomains.value = [];
  wizardDomainSearch.value = '';

  addForm.group_id = defaultGroupId;
  addForm.name = '';
  addForm.scope = '';

  // 预拉取扫描策略列表供自动探测选择
  if (policyList.value.length === 0) {
    try {
      const pRes = await request.get('/policy/', { params: { size: 100 } });
      if (pRes.code === 200 && pRes.items?.length > 0) {
        policyList.value = pRes.items;
        if (!wizardPolicyId.value) {
          wizardPolicyId.value = pRes.items[0]._id;
        }
      }
    } catch (e) {
      console.error('预拉取策略列表失败', e);
    }
  }

  addModalVisible.value = true;
};

const handleAddSubmit = async () => {
  try {
    await addFormRef.value.validate();
    addLoading.value = true;
    const res = await request.post('/asset_scope/', addForm);

    if (res.code === 200) {
      message.success('新建资产组成功！');
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

// ================= 编辑资产组逻辑 =================
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
          createVNode('div', { style: 'max-height: 100px; overflow-y: auto; background: rgba(255, 77, 79, 0.12); border: 1px solid rgba(255, 77, 79, 0.25); padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 12px; color: #ff4d4f;' }, removed.join(', ')),
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
      message.success('资产组更新成功！');
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
      createVNode('div', { style: 'background: rgba(255, 77, 79, 0.12); border: 1px solid rgba(255, 77, 79, 0.25); padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 13px; font-weight: bold; color: #ff4d4f;' }, scopeItem),
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

// ================= 单行删除资产组 =================
const handleSingleDelete = (record) => {
  Modal.confirm({
    title: '⚠️ 资产组彻底销毁确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `确定要彻底删除资产组【${record.name}】吗？`),
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
          message.success('资产组删除成功！');
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
    title: '⚠️ 批量删除资产组确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: `确定要彻底删除选中的 ${selectedRowKeys.value.length} 个资产组吗？删除后将同时物理级联清理所有关联的子资产与监控任务，不可恢复。`,
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
watch(
  () => ({ path: route.path, scopeId: route.query.scope_id }),
  (curr, prev) => {
    // 核心加固：仅在当前路由精确处于 /group 页面时响应外部 query 联动，杜绝子页面或详情页穿透
    if (curr.path !== '/group') return;

    // 如果是从二级详情页或其他页面返回 /group，严禁重置或覆盖已有一级页面状态
    if (prev && prev.path !== '/group') return;

    // 响应外部传入或 /group 内部的有效 scope_id 联动
    if (curr.scopeId && curr.scopeId !== searchForm.value._id) {
      activeGroupId.value = 'all';
      searchForm.value._id = curr.scopeId;
      pagination.current = 1;
      fetchData();
    } else if (!curr.scopeId && prev && prev.scopeId && searchForm.value._id === prev.scopeId) {
      // 仅当之前是在 /group 页面且显式携带了 scopeId，现被主动清空时才重置
      searchForm.value._id = undefined;
      pagination.current = 1;
      fetchData();
    }
  },
  { immediate: true }
);

const goToReconDetail = (taskId, taskType = 'icp') => {
  if (taskId) {
    router.push({
      path: '/taskList/taskDetail',
      query: { task_id: taskId, task_type: taskType }
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
  stopReconPoller();
  // 离开页面时安全收起弹窗，避免浮层遮挡其他视图
  addModalVisible.value = false;
  editGroupModalVisible.value = false;
  enterpriseGroupModalVisible.value = false;
  batchMoveModalVisible.value = false;
  icpImportModalVisible.value = false;
  syncIncrementModalVisible.value = false;
  bindScopeModalVisible.value = false;
  addMonitorVisible.value = false;
  addSiteMonitorVisible.value = false;
  addWihMonitorVisible.value = false;
});

onUnmounted(() => {
  window.removeEventListener('resize', updateSidebarLeft);
  const siderEl = document.querySelector('.ant-layout-sider');
  if (siderEl) {
    siderEl.removeEventListener('transitionend', updateSidebarLeft);
  }
  if (siderObserver) siderObserver.disconnect();
  if (sortableInstance) {
    sortableInstance.destroy();
    sortableInstance = null;
  }
  if (saveOrderTimer) {
    clearTimeout(saveOrderTimer);
  }
  stopPoll();
  stopReconPoller();
});

</script>

<style scoped>
/* 投资层级成本提示：层级越高，天眼查付费额度消耗越大 */
.depth-cost-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-warning-color, #faad14);
}

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
  background: rgba(255, 77, 79, 0.12) !important;
  color: #ff4d4f !important;
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

/* 种子目标与覆盖度复合单元格 */
.scope-stat-compact-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.scope-compact-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.scope-compact-tags {
  display: flex;
  align-items: center;
  gap: 5px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}
.scope-compact-domain {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  background: var(--arl-bg-light, #f8fafc);
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  color: var(--arl-text-color, #334155);
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scope-compact-count-badge {
  font-size: 11px;
  color: var(--arl-theme-color, #1890ff);
  background: rgba(24, 144, 255, 0.08);
  border: 1px solid rgba(24, 144, 255, 0.2);
  border-radius: 10px;
  padding: 1px 7px;
  cursor: pointer;
  white-space: nowrap;
  font-weight: 500;
  transition: all 0.2s ease;
}
.scope-compact-count-badge:hover {
  background: var(--arl-theme-color, #1890ff);
  color: #fff;
}
.scope-compact-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.scope-mini-progress-bar {
  flex: 1;
  height: 5px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  overflow: hidden;
  display: flex;
  cursor: pointer;
}
.progress-seg {
  height: 100%;
  transition: width 0.3s ease;
}
.progress-seg.probed {
  background: #52c41a;
}
.progress-seg.scanning {
  background: #1890ff;
  animation: progress-pulse 1.5s infinite;
}
.progress-seg.error {
  background: #ff4d4f;
}
.progress-seg.unprobed {
  background: #d9d9d9;
}
@keyframes progress-pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
.scope-compact-progress-text {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.65;
  white-space: nowrap;
  font-family: ui-monospace, monospace;
}

/* 种子目标悬浮 Popover 面板 */
.scope-popover-panel {
  max-width: 380px;
  min-width: 260px;
  max-height: 280px;
  display: flex;
  flex-direction: column;
}
.scope-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--arl-border-color, #f0f0f0);
  margin-bottom: 6px;
}
.scope-popover-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.scope-popover-copy-btn {
  padding: 0 !important;
  font-size: 11px !important;
  height: auto !important;
}
.scope-popover-list {
  overflow-y: auto;
  max-height: 220px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.scope-popover-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 6px;
  border-radius: 4px;
  background: var(--arl-bg-light, #fafafa);
  font-size: 12px;
  cursor: pointer;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.scope-popover-item:hover {
  background: rgba(24, 144, 255, 0.08);
}
.scope-popover-item-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.scope-popover-item-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scope-popover-item-status {
  font-size: 11px;
  margin-left: 8px;
  white-space: nowrap;
}
.scope-popover-item-status.text-probed { color: #52c41a; }
.scope-popover-item-status.text-scanning { color: #1890ff; }
.scope-popover-item-status.text-unprobed { color: #faad14; }
.scope-popover-item-status.text-error { color: #ff4d4f; }

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

.sidebar-group-divider {
  margin: 6px 12px;
  height: 1px;
  background: var(--arl-border-color);
  opacity: 0.6;
}

.sidebar-group-draggable-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0;
}

.group-nav-item {
  margin: 2px 8px;
  padding: 0 10px 0 6px;
  border-radius: 6px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  font-size: 14px;
  color: var(--arl-text-color);
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
  user-select: none;
  position: relative;
  background: transparent;
  border: 1px solid transparent;
}

.group-nav-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.group-nav-item-active {
  background-color: rgba(250, 84, 28, 0.08) !important;
  color: var(--arl-theme-color) !important;
  font-weight: 600 !important;
}

.group-nav-item-active .sidebar-scope-pill {
  background-color: var(--arl-bg-white) !important;
  color: var(--arl-theme-color) !important;
  opacity: 0.9;
}

/* 拖拽微动抓手 */
.group-drag-handle {
  cursor: grab;
  color: var(--arl-text-color);
  opacity: 0.35;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 24px;
  font-size: 13px;
  border-radius: 4px;
  flex-shrink: 0;
  user-select: none;
}

.group-nav-item:hover .group-drag-handle {
  opacity: 0.85;
  color: var(--arl-theme-color);
}

.group-drag-handle:hover {
  opacity: 1 !important;
  background: rgba(250, 84, 28, 0.1);
}

.group-drag-handle:active {
  cursor: grabbing;
}

.group-drag-handle-disabled {
  cursor: not-allowed !important;
  opacity: 0.15 !important;
}

.group-drag-handle-disabled:hover {
  background: transparent !important;
  color: var(--arl-text-color) !important;
}

/* Sortable 正在被拖动的元素浮动预览状态 (Drag Class) */
.group-drag-active {
  opacity: 0.96 !important;
  background: var(--arl-bg-white) !important;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12), 0 2px 6px rgba(250, 84, 28, 0.12) !important;
  border: 1px solid var(--arl-theme-color) !important;
  border-radius: 6px !important;
  transform: scale(1.02);
  z-index: 1000 !important;
  cursor: grabbing !important;
}

/* 目标位置的幽灵占位符状态 (Ghost Class) */
.group-drag-ghost {
  opacity: 0.55 !important;
  background: rgba(250, 84, 28, 0.06) !important;
  border: 1px dashed var(--arl-theme-color) !important;
  border-radius: 6px !important;
  box-shadow: inset 0 0 8px rgba(250, 84, 28, 0.08) !important;
}

/* 选中但未开始移动状态 (Chosen Class) */
.group-drag-chosen {
  cursor: grabbing !important;
}
</style>