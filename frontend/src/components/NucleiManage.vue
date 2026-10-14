<template>
  <div class="nuclei-manage-container">
    <!-- 统计指示条 -->
    <div class="stats-overview-bar">
      <div class="stat-pill">
        <span class="stat-label">自建模板</span>
        <span class="stat-val highlight">{{ stats.custom_total }}</span>
      </div>
      <div class="stat-pill">
        <span class="stat-label">已启用自建</span>
        <span class="stat-val active">{{ stats.custom_enabled }}</span>
      </div>
      <div class="stat-pill">
        <span class="stat-label">官方社区库</span>
        <span class="stat-val">{{ stats.community_total ? stats.community_total.toLocaleString() : '扫描中...' }}</span>
      </div>
      <div class="stat-pill">
        <span class="stat-label">已屏蔽误报</span>
        <span class="stat-val" style="color: #fa8c16; font-weight: 600;">{{ stats.blacklist_total || 0 }}</span>
      </div>
      <div class="stat-pill">
        <span class="stat-label">社区模板版本</span>
        <a-tag :color="stats.has_template_update ? 'orange' : 'cyan'" style="margin: 0; font-weight: 500;">
          {{ stats.template_version || '未知' }}
          <span v-if="stats.has_template_update" style="margin-left: 4px; font-size: 11px;">(可更新至 {{ stats.template_latest_version }})</span>
        </a-tag>
      </div>
      <div class="stat-pill">
        <span class="stat-label">Nuclei 引擎</span>
        <a-tag :color="stats.nuclei_version !== '未知' ? 'green' : 'orange'" style="margin: 0; font-weight: 500;">
          {{ stats.nuclei_version }}
        </a-tag>
      </div>
    </div>

    <!-- 二级 Sub-Tabs -->
    <a-tabs v-model:activeKey="innerTab" type="card" class="nuclei-inner-tabs">
      <!-- 1. 社区模板库 (只读检索) -->
      <a-tab-pane key="community" tab="社区模板库 (只读检索)">
        <div class="tab-content-wrapper">
          <div class="filter-bar-row">
            <div class="filter-item">
              <span class="filter-label">关键词 / CVE：</span>
              <a-input v-model:value="communitySearch.search" placeholder="输入 CVE 或名称进行检索" style="width: 240px;" allowClear @pressEnter="onSearchCommunity" />
            </div>
            <div class="filter-item">
              <span class="filter-label">危害级别：</span>
              <a-select v-model:value="communitySearch.severity" style="width: 130px;" allowClear placeholder="全部级别" @change="onSearchCommunity">
                <a-select-option value="critical">严重 (Critical)</a-select-option>
                <a-select-option value="high">高危 (High)</a-select-option>
                <a-select-option value="medium">中危 (Medium)</a-select-option>
                <a-select-option value="low">低危 (Low)</a-select-option>
                <a-select-option value="info">信息 (Info)</a-select-option>
              </a-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">扫描状态：</span>
              <a-select v-model:value="communitySearch.blacklist_status" style="width: 140px;" placeholder="全部状态" @change="onSearchCommunity">
                <a-select-option value="all">全部模板</a-select-option>
                <a-select-option value="normal">正常扫描</a-select-option>
                <a-select-option value="blacklisted">已屏蔽(误报)</a-select-option>
              </a-select>
            </div>
            <div class="filter-actions">
              <a-button type="primary" @click="onSearchCommunity"><template #icon><search-outlined /></template>查 询</a-button>
              <a-button @click="resetSearchCommunity">重 置</a-button>
            </div>

            <div style="margin-left: auto; display: flex; align-items: center; gap: 8px;">
              <!-- 同步状态指示 -->
              <a-tag v-if="syncStatus.status === 'syncing'" color="processing" style="cursor: pointer; padding: 3px 8px;" @click="openSyncLogModal">
                <template #icon><sync-outlined spin /></template>
                官方模板加速同步中...
              </a-tag>
              <a-tag v-else-if="syncStatus.status === 'success'" color="success" style="cursor: pointer; padding: 3px 8px;" @click="openSyncLogModal">
                <template #icon><check-circle-outlined /></template>
                同步已完成 ({{ syncStatus.diff_count >= 0 ? '+' : '' }}{{ syncStatus.diff_count }}条)
              </a-tag>
              <a-tag v-else-if="syncStatus.status === 'failed'" color="error" style="cursor: pointer; padding: 3px 8px;" @click="openSyncLogModal">
                <template #icon><close-circle-outlined /></template>
                同步异常 (点击查看)
              </a-tag>

              <!-- 查看日志按钮 -->
              <a-button type="link" size="small" style="padding: 0 4px;" @click="openSyncLogModal">
                <template #icon><file-text-outlined /></template>
                查看同步日志
              </a-button>

              <!-- 在线同步按钮 -->
              <a-popconfirm
                title="确认启动官方模板库加速同步吗？系统将自动通过镜像加速通道更新至最新版本。"
                ok-text="确认同步"
                cancel-text="取消"
                @confirm="handleSyncCommunity"
              >
                <a-button type="primary" :loading="syncStatus.status === 'syncing'">
                  <template #icon><sync-outlined /></template>
                  同步最新官方版本
                </a-button>
              </a-popconfirm>

              <!-- 离线更新包按钮 -->
              <a-button @click="isOfflineModalVisible = true">
                <template #icon><cloud-upload-outlined /></template>
                离线更新包
              </a-button>
            </div>
          </div>

          <!-- 社区模板表格 -->
          <a-table
            :loading="communityLoading"
            :dataSource="communityList"
            :columns="communityColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record.file_path || record.template_id"
          >
            <template #bodyCell="{ column, record, index }">
              <template v-if="column.key === 'index'">
                <span>{{ (communityPagination.current - 1) * communityPagination.pageSize + index + 1 }}</span>
              </template>
              <template v-if="column.key === 'template_id'">
                <span style="font-family: monospace; font-weight: 600;">{{ record.template_id }}</span>
              </template>
              <template v-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)" style="font-weight: 500; text-transform: uppercase;">
                  {{ record.severity || 'UNKNOWN' }}
                </a-tag>
              </template>
              <template v-if="column.key === 'status'">
                <a-tooltip v-if="record.is_blacklisted" :title="record.blacklist_reason ? `屏蔽原因: ${record.blacklist_reason}` : '已加入误报黑名单，扫描不执行'">
                  <a-tag color="orange" style="cursor: pointer;">已屏蔽 (误报)</a-tag>
                </a-tooltip>
                <a-tag v-else color="blue">正常扫描</a-tag>
              </template>
              <template v-if="column.key === 'file_path'">
                <span style="font-family: monospace; font-size: 12px; color: var(--arl-text-color); opacity: 0.65;">
                  {{ record.file_path }}
                </span>
              </template>
              <template v-if="column.key === 'action'">
                <div style="display: flex; gap: 10px; align-items: center; justify-content: center;">
                  <a @click="viewCommunitySource(record)">
                    <file-text-outlined /> 查看 YAML
                  </a>
                  <a-popconfirm
                    v-if="record.is_blacklisted"
                    title="确认解除该模板的误报屏蔽（恢复参与扫描）吗？"
                    ok-text="解除屏蔽"
                    cancel-text="取消"
                    @confirm="handleRemoveBlacklist(record.template_id)"
                  >
                    <a style="color: #52c41a;"><check-outlined /> 解除屏蔽</a>
                  </a-popconfirm>
                  <a v-else style="color: #fa8c16;" @click="openMarkBlacklistModal(record)">
                    <stop-outlined /> 标记误报
                  </a>
                </div>
              </template>
            </template>
          </a-table>

          <!-- 分页器 -->
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
            <div style="color: var(--arl-text-color); opacity: 0.65;">
              共 {{ Math.ceil(communityPagination.total / communityPagination.pageSize) || 1 }} 页 / {{ communityPagination.total }} 条数据
            </div>
            <a-pagination
              :pageSizeOptions="$pageSizeOptions"
              v-model:current="communityPagination.current"
              v-model:pageSize="communityPagination.pageSize"
              :total="communityPagination.total"
              show-size-changer
              @change="fetchCommunityTemplates"
            />
          </div>
        </div>
      </a-tab-pane>

      <!-- 2. 误报黑名单 (集中治理) -->
      <a-tab-pane key="blacklist" tab="误报黑名单 (集中治理)">
        <div class="tab-content-wrapper">
          <!-- 顶部操作栏 -->
          <div class="action-bar-row">
            <a-button type="primary" @click="openAddBlacklistModal">
              <template #icon><plus-outlined /></template>
              手动录入误报
            </a-button>
            <a-popconfirm
              title="确认将选中的模板从误报黑名单移除（恢复参与扫描）吗？"
              ok-text="确认移除"
              cancel-text="取消"
              @confirm="handleBatchRemoveBlacklist"
              :disabled="blacklistSelectedRowKeys.length === 0"
            >
              <a-button danger :disabled="blacklistSelectedRowKeys.length === 0">
                <template #icon><delete-outlined /></template>
                批量解除屏蔽
              </a-button>
            </a-popconfirm>
            <div style="margin-left: auto; color: var(--arl-text-color); opacity: 0.65; font-size: 13px;">
              💡 提示：被屏蔽的模板将在后续全站所有 Nuclei 扫描任务中自动排除（通过引擎原生 -eid 临时清单注入，零篡改模板文件）
            </div>
          </div>

          <!-- 搜索过滤栏 -->
          <div class="filter-bar-row">
            <div class="filter-item">
              <span class="filter-label">关键词：</span>
              <a-input v-model:value="blacklistSearch.search" placeholder="输入 ID、名称或误报原因" style="width: 240px;" allowClear @pressEnter="onSearchBlacklist" />
            </div>
            <div class="filter-item">
              <span class="filter-label">危害级别：</span>
              <a-select v-model:value="blacklistSearch.severity" style="width: 130px;" allowClear placeholder="全部级别" @change="onSearchBlacklist">
                <a-select-option value="critical">严重 (Critical)</a-select-option>
                <a-select-option value="high">高危 (High)</a-select-option>
                <a-select-option value="medium">中危 (Medium)</a-select-option>
                <a-select-option value="low">低危 (Low)</a-select-option>
                <a-select-option value="info">信息 (Info)</a-select-option>
              </a-select>
            </div>
            <div class="filter-actions">
              <a-button type="primary" @click="onSearchBlacklist"><template #icon><search-outlined /></template>查 询</a-button>
              <a-button @click="resetSearchBlacklist">重 置</a-button>
            </div>
          </div>

          <!-- 黑名单数据表格 -->
          <a-table
            :loading="blacklistLoading"
            :dataSource="blacklistItems"
            :columns="blacklistColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record.template_id"
            :rowSelection="{ selectedRowKeys: blacklistSelectedRowKeys, onChange: onBlacklistSelectChange, preserveSelectedRowKeys: true }"
          >
            <template #bodyCell="{ column, record, index }">
              <template v-if="column.key === 'index'">
                <span>{{ (blacklistPagination.current - 1) * blacklistPagination.pageSize + index + 1 }}</span>
              </template>
              <template v-if="column.key === 'template_id'">
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-family: monospace; font-weight: 600; color: #fa8c16;">{{ record.template_id }}</span>
                  <a-tooltip title="复制模板 ID">
                    <copy-outlined style="cursor: pointer; opacity: 0.5; font-size: 12px;" @click="copyText(record.template_id)" />
                  </a-tooltip>
                </div>
              </template>
              <template v-if="column.key === 'name'">
                <span style="font-weight: 500;">{{ record.name }}</span>
              </template>
              <template v-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)" style="font-weight: 500; text-transform: uppercase;">
                  {{ record.severity || 'UNKNOWN' }}
                </a-tag>
              </template>
              <template v-if="column.key === 'reason'">
                <span style="color: var(--arl-text-color); font-size: 13px;">{{ record.reason || '手工标记误报' }}</span>
              </template>
              <template v-if="column.key === 'created_at'">
                <span style="font-size: 12px; opacity: 0.7;">{{ record.created_at || '-' }}</span>
              </template>
              <template v-if="column.key === 'action'">
                <div style="display: flex; gap: 10px; align-items: center; justify-content: center;">
                  <a @click="viewCommunitySource(record)">
                    <file-text-outlined /> 查看 YAML
                  </a>
                  <a-popconfirm
                    title="确认将该模板移出误报黑名单（恢复参与扫描）吗？"
                    ok-text="解除屏蔽"
                    cancel-text="取消"
                    @confirm="handleRemoveBlacklist(record.template_id)"
                  >
                    <a style="color: #52c41a;"><check-outlined /> 解除屏蔽</a>
                  </a-popconfirm>
                </div>
              </template>
            </template>
            <template #emptyText>
              <div style="padding: 40px 0;">
                <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无被屏蔽的误报模板，扫描将使用官方推荐规则执行</div>
              </div>
            </template>
          </a-table>

          <!-- 分页器 -->
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
            <div style="color: var(--arl-text-color); opacity: 0.65;">
              共 {{ Math.ceil(blacklistPagination.total / blacklistPagination.pageSize) || 1 }} 页 / {{ blacklistPagination.total }} 条被屏蔽规则
            </div>
            <a-pagination
              :pageSizeOptions="$pageSizeOptions"
              v-model:current="blacklistPagination.current"
              v-model:pageSize="blacklistPagination.pageSize"
              :total="blacklistPagination.total"
              show-size-changer
              @change="fetchBlacklist"
            />
          </div>
        </div>
      </a-tab-pane>

      <!-- 3. 自建模板库 (工作台) -->
      <a-tab-pane key="custom" tab="自建模板库 (工作台)">
        <div class="tab-content-wrapper">
          <!-- 顶部操作栏 -->
          <div class="action-bar-row">
            <a-button type="primary" @click="openCreateModal">
              <template #icon><plus-outlined /></template>
              新建模板
            </a-button>
            <a-button type="primary" @click="isImportModalVisible = true">
              <template #icon><cloud-upload-outlined /></template>
              导入模板
            </a-button>
            <a-button @click="downloadSampleTemplate">
              <template #icon><download-outlined /></template>
              下载标准模板
            </a-button>
            <a-button @click="handleExport">
              <template #icon><cloud-download-outlined /></template>
              导出所选 / 全部
            </a-button>
            <a-button :disabled="selectedRowKeys.length === 0" @click="handleBatchToggle(true)">
              批量启用
            </a-button>
            <a-button :disabled="selectedRowKeys.length === 0" @click="handleBatchToggle(false)">
              批量禁用
            </a-button>
            <a-popconfirm
              title="确认批量删除选中的自建模板吗？此操作不可逆！"
              ok-text="确认"
              cancel-text="取消"
              @confirm="handleBatchDelete"
              :disabled="selectedRowKeys.length === 0"
            >
              <a-button type="primary" danger :disabled="selectedRowKeys.length === 0" :loading="batchDeleteLoading">
                <template #icon><delete-outlined /></template>
                批量删除
              </a-button>
            </a-popconfirm>
          </div>

          <!-- 搜索与筛选区 -->
          <div class="filter-bar-row">
            <div class="filter-item">
              <span class="filter-label">模板 ID：</span>
              <a-input v-model:value="customSearch.template_id" placeholder="如 cve-2024" style="width: 170px;" allowClear @pressEnter="onSearchCustom" />
            </div>
            <div class="filter-item">
              <span class="filter-label">漏洞名称：</span>
              <a-input v-model:value="customSearch.name" placeholder="请输入名称" style="width: 170px;" allowClear @pressEnter="onSearchCustom" />
            </div>
            <div class="filter-item">
              <span class="filter-label">危害级别：</span>
              <a-select v-model:value="customSearch.severity" style="width: 130px;" allowClear placeholder="全部级别" @change="onSearchCustom">
                <a-select-option value="critical">严重 (Critical)</a-select-option>
                <a-select-option value="high">高危 (High)</a-select-option>
                <a-select-option value="medium">中危 (Medium)</a-select-option>
                <a-select-option value="low">低危 (Low)</a-select-option>
                <a-select-option value="info">信息 (Info)</a-select-option>
              </a-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">标签 Tag：</span>
              <a-input v-model:value="customSearch.tag" placeholder="如 rce, spring" style="width: 150px;" allowClear @pressEnter="onSearchCustom" />
            </div>
            <div class="filter-actions">
              <a-button type="primary" @click="onSearchCustom"><template #icon><search-outlined /></template>查 询</a-button>
              <a-button @click="resetSearchCustom">重 置</a-button>
            </div>
          </div>

          <!-- 自建模板数据表格 -->
          <a-table
            :loading="customLoading"
            :dataSource="customList"
            :columns="customColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record.template_id"
            :rowSelection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
          >
            <template #bodyCell="{ column, record, index }">
              <template v-if="column.key === 'index'">
                <span>{{ (customPagination.current - 1) * customPagination.pageSize + index + 1 }}</span>
              </template>

              <template v-if="column.key === 'template_id'">
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-family: monospace; font-weight: 600; color: var(--arl-text-color);">{{ record.template_id }}</span>
                  <a-tooltip title="复制模板 ID">
                    <copy-outlined style="cursor: pointer; opacity: 0.5; font-size: 12px;" @click="copyText(record.template_id)" />
                  </a-tooltip>
                </div>
              </template>

              <template v-if="column.key === 'name'">
                <a @click="openEditModal(record)" style="font-weight: 500;">{{ record.name }}</a>
                <div v-if="record.description" style="font-size: 12px; color: var(--arl-text-color); opacity: 0.55; max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ record.description }}
                </div>
              </template>

              <template v-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)" style="font-weight: 500; text-transform: uppercase;">
                  {{ record.severity || 'UNKNOWN' }}
                </a-tag>
              </template>

              <template v-if="column.key === 'tags'">
                <div style="display: flex; flex-wrap: wrap; gap: 4px; max-width: 220px;">
                  <a-tag v-for="tag in (record.tags || []).slice(0, 3)" :key="tag" color="blue" size="small">{{ tag }}</a-tag>
                  <span v-if="(record.tags || []).length > 3" style="font-size: 11px; opacity: 0.6;">+{{ (record.tags || []).length - 3 }}</span>
                </div>
              </template>

              <template v-if="column.key === 'enable'">
                <a-switch
                  :checked="record.enable"
                  :loading="record._toggling"
                  checked-children="启用"
                  un-checked-children="禁用"
                  @change="(val) => handleToggleEnable(record, val)"
                />
              </template>

              <template v-if="column.key === 'action'">
                <div style="display: flex; gap: 12px; align-items: center;">
                  <a @click="openEditModal(record)">编辑源码</a>
                  <a @click="openDryRunDirect(record)" style="color: #52c41a;">
                    <thunderbolt-outlined /> 调试
                  </a>
                  <a-popconfirm title="确认删除此模板吗？" ok-text="删除" cancel-text="取消" @confirm="handleSingleDelete(record.template_id)">
                    <a style="color: #ff4d4f;">删除</a>
                  </a-popconfirm>
                </div>
              </template>
            </template>

            <template #emptyText>
              <div style="padding: 40px 0;">
                <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无自建模板，点击上方「新建模板」或「导入」开始使用</div>
              </div>
            </template>
          </a-table>

          <!-- 分页器 -->
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
            <div style="color: var(--arl-text-color); opacity: 0.65;">
              共 {{ Math.ceil(customPagination.total / customPagination.pageSize) || 1 }} 页 / {{ customPagination.total }} 条数据
            </div>
            <a-pagination
              :pageSizeOptions="$pageSizeOptions"
              v-model:current="customPagination.current"
              v-model:pageSize="customPagination.pageSize"
              :total="customPagination.total"
              show-size-changer
              @change="fetchCustomTemplates"
            />
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- 弹窗 1：新建 / 编辑自建模板弹窗 (带 Dry Run) -->
    <a-modal
      v-model:open="isEditModalVisible"
      :title="isCreateMode ? '新建 Nuclei 模板' : `编辑模板 - ${currentEditTemplateId}`"
      width="900px"
      :footer="null"
      :destroyOnClose="true"
    >
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <!-- 骨架模板快速填充选择器 (仅新建时显示) -->
        <div v-if="isCreateMode" style="display: flex; align-items: center; justify-content: space-between; background: var(--arl-bg-layout); padding: 8px 12px; border-radius: 4px;">
          <span style="font-size: 13px; font-weight: 500;">快速预设骨架：</span>
          <a-select v-model:value="selectedSkeleton" style="width: 240px;" @change="handleSkeletonChange">
            <a-select-option value="http_get">标准 HTTP GET 漏洞验证</a-select-option>
            <a-select-option value="http_post">HTTP POST 带有 Body 与标头</a-select-option>
            <a-select-option value="file_leak">敏感信息泄露 / 备份文件</a-select-option>
            <a-select-option value="dns_check">DNS 解析记录匹配</a-select-option>
          </a-select>
        </div>

        <!-- CodeMirror 代码编辑区域 -->
        <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden;">
          <codemirror
            v-model="currentEditorCode"
            placeholder="请在此输入合规的 Nuclei YAML 规则..."
            :style="{ height: '400px', fontSize: '13px' }"
            :autofocus="true"
            :indent-with-tab="true"
            :tab-size="2"
            :extensions="editExtensions"
          />
        </div>

        <!-- 错误提示横条 -->
        <a-alert v-if="saveErrorMsg" :message="saveErrorMsg" type="error" show-icon closable @close="saveErrorMsg = ''" />

        <!-- 在线即时调试 (Dry Run) 面板 -->
        <div class="dryrun-panel">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <div style="font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <thunderbolt-outlined style="color: #faad14;" />
              <span>在线单目标即时调试 (Dry Run)</span>
            </div>
            <span style="font-size: 12px; opacity: 0.5;">限时 30 秒执行，所见即所得</span>
          </div>

          <div style="display: flex; gap: 8px; margin-bottom: 8px;">
            <a-input v-model:value="dryRunTarget" placeholder="输入测试目标 (如: https://example.com 或 1.2.3.4:8080)" style="flex: 1;" />
            <a-button type="primary" ghost :loading="dryRunLoading" @click="executeDryRun">
              <template #icon><play-circle-outlined /></template>
              发送测试
            </a-button>
          </div>

          <div v-if="dryRunOutput" class="dryrun-console">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px; color: #8c8c8c; font-size: 11px;">
              <span>Nuclei 回显控制台 (耗时: {{ dryRunCost }}s)</span>
              <a-tag :color="dryRunMatched ? 'red' : 'default'" size="small">
                {{ dryRunMatched ? '🎯 匹配漏洞命中' : '⚪ 未触发匹配' }}
              </a-tag>
            </div>
            <pre class="console-pre">{{ dryRunOutput }}</pre>
          </div>
        </div>

        <!-- 底部保存按钮 -->
        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 8px;">
          <a-button @click="isEditModalVisible = false">取 消</a-button>
          <a-button type="primary" :loading="saveLoading" @click="saveTemplate">
            保 存 模 板
          </a-button>
        </div>
      </div>
    </a-modal>

    <!-- 弹窗 2：导入模板弹窗 -->
    <a-modal v-model:open="isImportModalVisible" title="批量导入 Nuclei 模板" :footer="null">
      <a-upload-dragger
        name="file"
        :multiple="true"
        action="/api/nuclei/template/import/"
        :headers="uploadHeaders"
        accept=".yaml,.yml,.zip"
        @change="handleUploadChange"
      >
        <p class="ant-upload-drag-icon"><inbox-outlined /></p>
        <p class="ant-upload-text">点击或将文件拖拽到这里上传</p>
        <p class="ant-upload-hint">支持 .yaml / .yml 单文件，或打包了模板的 .zip 压缩包</p>
      </a-upload-dragger>
      <div style="margin-top: 12px; display: flex; justify-content: flex-end; align-items: center; font-size: 13px;">
        <span style="color: var(--arl-text-color); opacity: 0.65;">需要标准格式参考？</span>
        <a @click="downloadSampleTemplate" style="margin-left: 6px; font-weight: 500;">
          <download-outlined /> 下载标准 YAML 模板
        </a>
      </div>
    </a-modal>

    <!-- 抽屉：查看社区模板源码 -->
    <a-drawer
      v-model:open="isCommunityDrawerVisible"
      :title="`社区模板源码 - ${selectedCommunityRecord?.template_id || ''}`"
      placement="right"
      width="750"
    >
      <div v-if="communitySourceLoading" style="text-align: center; padding: 60px 0;">
        <a-spin tip="加载模板源码中..." />
      </div>
      <div v-else style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden;">
        <codemirror
          v-model="communitySourceCode"
          :disabled="true"
          :style="{ height: 'calc(100vh - 140px)', fontSize: '13px' }"
          :indent-with-tab="true"
          :tab-size="2"
          :extensions="editExtensions"
        />
      </div>
    </a-drawer>

    <!-- 弹窗 3：官方模板同步控制台 -->
    <a-modal
      v-model:open="isSyncLogModalVisible"
      title="官方社区模板同步控制台"
      width="800px"
      :footer="null"
    >
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <!-- 状态与指标面板 -->
        <div style="background: var(--arl-bg-layout); padding: 12px 16px; border-radius: 6px; border: 1px solid var(--arl-border-color); display: flex; flex-wrap: wrap; gap: 16px; align-items: center;">
          <div>
            <span style="color: var(--arl-text-color); opacity: 0.65; font-size: 13px;">当前状态：</span>
            <a-tag v-if="syncStatus.status === 'syncing'" color="processing"><sync-outlined spin /> 同步进行中</a-tag>
            <a-tag v-else-if="syncStatus.status === 'success'" color="success"><check-circle-outlined /> 同步成功</a-tag>
            <a-tag v-else-if="syncStatus.status === 'failed'" color="error"><close-circle-outlined /> 同步失败</a-tag>
            <a-tag v-else>空闲</a-tag>
          </div>
          <div>
            <span style="color: var(--arl-text-color); opacity: 0.65; font-size: 13px;">当前版本：</span>
            <a-tag color="blue">{{ syncStatus.current_version || '未知' }}</a-tag>
          </div>
          <div>
            <span style="color: var(--arl-text-color); opacity: 0.65; font-size: 13px;">官方最新：</span>
            <a-tag color="purple">{{ syncStatus.latest_version || '未知' }}</a-tag>
          </div>
          <div>
            <span style="color: var(--arl-text-color); opacity: 0.65; font-size: 13px;">增量模板：</span>
            <span style="font-weight: 600; color: #1890ff;">{{ syncStatus.diff_count >= 0 ? '+' : '' }}{{ syncStatus.diff_count }}</span>
          </div>
          <div style="margin-left: auto;">
            <a-button size="small" :loading="syncStatusLoading" @click="fetchSyncStatus">
              <template #icon><sync-outlined /></template> 刷新状态
            </a-button>
          </div>
        </div>

        <!-- 错误警示 (若有) -->
        <a-alert
          v-if="syncStatus.status === 'failed' && syncStatus.error_message"
          type="error"
          show-icon
          :message="'同步异常: ' + syncStatus.error_message"
          style="margin-bottom: 4px;"
        />

        <!-- 终端日志窗口 -->
        <div style="position: relative;">
          <div style="position: absolute; right: 12px; top: 10px; z-index: 10;">
            <a-button size="small" type="link" style="color: #aaa;" @click="copyText(syncStatus.log)">
              <template #icon><copy-outlined /></template> 复制日志
            </a-button>
          </div>
          <pre class="sync-terminal-log">{{ syncStatus.log || '暂无控制台日志，点击上方「同步最新官方版本」启动' }}</pre>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <a-button @click="isSyncLogModalVisible = false">关 闭</a-button>
        </div>
      </div>
    </a-modal>

    <!-- 弹窗 4：离线全量模板 ZIP 包导入 -->
    <a-modal v-model:open="isOfflineModalVisible" title="导入官方模板全量离线包 (.zip)" :footer="null">
      <a-alert
        type="info"
        show-icon
        message="离线更新模式说明"
        description="支持将官方 nuclei-templates.zip 全量压缩包直接上传覆盖至生产环境。适用于无法直连外网 GitHub 的严苛内网隔离环境。"
        style="margin-bottom: 16px;"
      />
      <a-upload-dragger
        name="file"
        :multiple="false"
        action="/api/nuclei/community/sync_offline/"
        :headers="uploadHeaders"
        accept=".zip"
        @change="handleOfflineUploadChange"
      >
        <p class="ant-upload-drag-icon"><cloud-upload-outlined /></p>
        <p class="ant-upload-text">点击或将 nuclei-templates.zip 拖拽至此处</p>
        <p class="ant-upload-hint">上传后系统将在后台解压覆盖至官方模板目录，并自动同步至 Worker 扫描节点</p>
      </a-upload-dragger>
    </a-modal>

    <!-- 弹窗 5：标记误报原因录入弹窗 -->
    <a-modal
      v-model:open="isMarkModalVisible"
      title="标记为误报并屏蔽扫描"
      :confirmLoading="markModalLoading"
      @ok="handleConfirmMarkBlacklist"
    >
      <div style="display: flex; flex-direction: column; gap: 14px; padding-top: 8px;">
        <a-alert
          type="warning"
          show-icon
          message="屏蔽说明"
          description="将此模板加入全局误报黑名单后，全站所有扫描策略默认将不再加载执行该模板探测，避免产生无意义告警。"
        />
        <div>
          <span style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65;">模板 ID：</span>
          <span style="font-family: monospace; font-weight: 600; color: #fa8c16; margin-left: 6px;">{{ markModalForm.template_id }}</span>
        </div>
        <div>
          <span style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65;">漏洞名称：</span>
          <span style="font-weight: 500; margin-left: 6px;">{{ markModalForm.name }}</span>
        </div>
        <div>
          <div style="margin-bottom: 6px; font-size: 13px; font-weight: 500;">
            误报原因 / 屏蔽说明：
          </div>
          <a-textarea
            v-model:value="markModalForm.reason"
            placeholder="例如：在目标业务架构下命中泛解析或统一错误页面造成误报"
            :rows="3"
            allowClear
          />
          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;">
            <span style="font-size: 12px; opacity: 0.6;">快捷标签：</span>
            <a-tag style="cursor: pointer;" @click="markModalForm.reason = '内网泛解析与统一404状态码误判'">泛解析误判</a-tag>
            <a-tag style="cursor: pointer;" @click="markModalForm.reason = '特定CMS版本指纹匹配过宽'">指纹过宽</a-tag>
            <a-tag style="cursor: pointer;" @click="markModalForm.reason = '反向代理网关默认返回特定响应头误报'">网关返回误报</a-tag>
            <a-tag style="cursor: pointer;" @click="markModalForm.reason = '业务自定义静态资源文件名称重合'">路径重合</a-tag>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 弹窗 6：手动录入误报模板弹窗 -->
    <a-modal
      v-model:open="isAddBlacklistModalVisible"
      title="手动添加误报黑名单"
      :confirmLoading="addBlacklistLoading"
      @ok="handleConfirmAddBlacklist"
    >
      <div style="display: flex; flex-direction: column; gap: 14px; padding-top: 8px;">
        <a-form layout="vertical">
          <a-form-item label="模板 ID (必填)" required>
            <a-input v-model:value="addBlacklistForm.template_id" placeholder="例如：cve-2021-41773 或 apache-status" allowClear />
          </a-form-item>
          <a-form-item label="漏洞名称 (选填)">
            <a-input v-model:value="addBlacklistForm.name" placeholder="请输入漏洞简要描述" allowClear />
          </a-form-item>
          <a-form-item label="危害级别">
            <a-select v-model:value="addBlacklistForm.severity" style="width: 100%;">
              <a-select-option value="critical">严重 (Critical)</a-select-option>
              <a-select-option value="high">高危 (High)</a-select-option>
              <a-select-option value="medium">中危 (Medium)</a-select-option>
              <a-select-option value="low">低危 (Low)</a-select-option>
              <a-select-option value="info">信息 (Info)</a-select-option>
              <a-select-option value="unknown">未知 (Unknown)</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="误报原因说明">
            <a-textarea v-model:value="addBlacklistForm.reason" placeholder="说明为何屏蔽此模板" :rows="3" allowClear />
          </a-form-item>
        </a-form>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { message, notification } from 'ant-design-vue';
import {
  PlusOutlined,
  CloudUploadOutlined,
  CloudDownloadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  SearchOutlined,
  InboxOutlined,
  SyncOutlined,
  CopyOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  CheckOutlined
} from '@ant-design/icons-vue';
import { Codemirror } from 'vue-codemirror';
import { oneDark } from '@codemirror/theme-one-dark';
import request from '../utils/request';

const editExtensions = [oneDark];
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token');
  return token ? { Token: token } : {};
});

// ---------- 页面状态与统计 ----------
const innerTab = ref('community');
const stats = reactive({
  custom_total: 0,
  custom_enabled: 0,
  community_total: 0,
  blacklist_total: 0,
  nuclei_version: '检测中',
  template_version: '检测中',
  template_latest_version: '未知',
  has_template_update: false
});

const fetchStats = async () => {
  try {
    const res = await request.get('/nuclei/stats/');
    if (res.code === 200 && res.data) {
      stats.custom_total = res.data.custom_total || 0;
      stats.custom_enabled = res.data.custom_enabled || 0;
      stats.community_total = res.data.community_total || 0;
      stats.blacklist_total = res.data.blacklist_total || 0;
      stats.nuclei_version = res.data.nuclei_version || '未知';
      stats.template_version = res.data.template_version || '未知';
      stats.template_latest_version = res.data.template_latest_version || '未知';
      stats.has_template_update = Boolean(res.data.has_template_update);
    }
  } catch (e) {
    console.error('Failed to fetch nuclei stats:', e);
  }
};

// ---------- 自建模板工作区 ----------
const customLoading = ref(false);
const customList = ref([]);
const selectedRowKeys = ref([]);
const batchDeleteLoading = ref(false);

const customSearch = reactive({
  template_id: '',
  name: '',
  severity: undefined,
  tag: ''
});

const customPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
});

const customColumns = [
  { title: '序号', key: 'index', width: 65, align: 'center' },
  { title: '模板 ID', key: 'template_id', width: 220 },
  { title: '漏洞名称', key: 'name', minWidth: 200 },
  { title: '危害级别', key: 'severity', width: 110, align: 'center' },
  { title: '标签 Tags', key: 'tags', width: 180 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '状态', key: 'enable', width: 90, align: 'center' },
  { title: '操作', key: 'action', width: 180, align: 'center' }
];

const fetchCustomTemplates = async () => {
  customLoading.value = true;
  try {
    const params = {
      page: customPagination.current,
      size: customPagination.pageSize,
      template_id: customSearch.template_id || undefined,
      name: customSearch.name || undefined,
      severity: customSearch.severity || undefined,
      tag: customSearch.tag || undefined
    };
    const res = await request.get('/nuclei/template/', { params });
    if (res.code === 200 && res.data) {
      customList.value = res.data.items || [];
      customPagination.total = res.data.total || 0;
    }
  } catch (e) {
    message.error('加载自建模板失败');
  } finally {
    customLoading.value = false;
  }
};

const onSearchCustom = () => {
  customPagination.current = 1;
  fetchCustomTemplates();
};

const resetSearchCustom = () => {
  customSearch.template_id = '';
  customSearch.name = '';
  customSearch.severity = undefined;
  customSearch.tag = '';
  onSearchCustom();
};

const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};

// 单个启停切换
const handleToggleEnable = async (record, val) => {
  record._toggling = true;
  try {
    const res = await request.post('/nuclei/template/toggle/', {
      template_id: record.template_id,
      enable: val
    });
    if (res.code === 200) {
      record.enable = val;
      message.success(`模板已${val ? '启用' : '禁用'}`);
      fetchStats();
    } else {
      message.error(res.message || res.error || '状态切换失败');
    }
  } catch (e) {
    message.error('请求异常');
  } finally {
    record._toggling = false;
  }
};

// 批量启停切换
const handleBatchToggle = async (enableVal) => {
  if (selectedRowKeys.value.length === 0) return;
  try {
    const res = await request.post('/nuclei/template/batch_toggle/', {
      template_ids: selectedRowKeys.value,
      enable: enableVal
    });
    if (res.code === 200) {
      message.success(`已批量${enableVal ? '启用' : '禁用'} ${res.data?.modified_count || selectedRowKeys.value.length} 个模板`);
      fetchCustomTemplates();
      fetchStats();
    }
  } catch (e) {
    message.error('批量操作失败');
  }
};

// 单个删除
const handleSingleDelete = async (templateId) => {
  try {
    const res = await request.post('/nuclei/template/delete/', { template_ids: [templateId] });
    if (res.code === 200) {
      message.success('模板删除成功');
      selectedRowKeys.value = selectedRowKeys.value.filter(k => k !== templateId);
      fetchCustomTemplates();
      fetchStats();
    }
  } catch (e) {
    message.error('删除请求失败');
  }
};

// 批量删除
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) return;
  batchDeleteLoading.value = true;
  try {
    const res = await request.post('/nuclei/template/delete/', { template_ids: selectedRowKeys.value });
    if (res.code === 200) {
      message.success(`成功删除 ${res.data?.delete_cnt || 0} 个模板`);
      selectedRowKeys.value = [];
      fetchCustomTemplates();
      fetchStats();
    }
  } catch (e) {
    message.error('批量删除失败');
  } finally {
    batchDeleteLoading.value = false;
  }
};

// 导出
const handleExport = () => {
  let url = '/api/nuclei/template/export/';
  if (selectedRowKeys.value.length > 0) {
    url += `?template_ids=${selectedRowKeys.value.join(',')}`;
  }
  const token = localStorage.getItem('token');
  const a = document.createElement('a');
  a.href = url + (url.includes('?') ? '&' : '?') + (token ? `token=${token}` : '');
  a.download = 'nuclei_templates.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

// ---------- 骨架模板预设 ----------
const skeletonTemplates = {
  http_get: `id: custom-poc-demo

info:
  name: Custom Demo Vulnerability (GET)
  author: security-team
  severity: high
  description: 探测目标是否存在特定敏感路径与漏洞关键字
  tags: custom,demo,rce

http:
  - method: GET
    path:
      - "{{BaseURL}}/actuator/env"
      - "{{BaseURL}}/env"
    matchers-condition: and
    matchers:
      - type: word
        words:
          - "spring.cloud"
          - "server.port"
        condition: or
      - type: status
        status:
          - 200
`,
  http_post: `id: custom-poc-post-payload

info:
  name: Custom POST Exploit Check
  author: security-team
  severity: critical
  description: 带有自定义 Header 与 Payload 的 POST 请求验证
  tags: custom,rce

http:
  - method: POST
    path:
      - "{{BaseURL}}/api/check"
    headers:
      Content-Type: application/json
      X-Forwarded-For: 127.0.0.1
    body: |
      {"action": "test", "command": "id"}
    matchers-condition: and
    matchers:
      - type: word
        words:
          - "uid="
          - "gid="
      - type: status
        status:
          - 200
`,
  file_leak: `id: custom-sensitive-file-leak

info:
  name: Sensitive Backup File Leak
  author: security-team
  severity: medium
  description: 检测 Web 站点是否存在常见数据库与备份配置泄露
  tags: leak,config

http:
  - method: GET
    path:
      - "{{BaseURL}}/.git/config"
      - "{{BaseURL}}/.env"
      - "{{BaseURL}}/config.inc.php.bak"
    matchers-condition: or
    matchers:
      - type: word
        words:
          - "[core]"
          - "DB_PASSWORD"
      - type: status
        status:
          - 200
`,
  dns_check: `id: custom-dns-cname-takeover

info:
  name: DNS CNAME Takeover Check
  author: security-team
  severity: high
  description: 针对域名的 CNAME 悬挂指向实施探测
  tags: dns,takeover

dns:
  - name: "{{FQDN}}"
    type: CNAME
    matchers:
      - type: word
        words:
          - "trafficmanager.net"
          - "herokuapp.com"
`
};

// ---------- 新建 / 编辑弹窗逻辑 ----------
const isEditModalVisible = ref(false);
const isCreateMode = ref(false);
const currentEditTemplateId = ref('');
const currentEditorCode = ref('');
const selectedSkeleton = ref('http_get');
const saveLoading = ref(false);
const saveErrorMsg = ref('');

const openCreateModal = () => {
  isCreateMode.value = true;
  currentEditTemplateId.value = '';
  selectedSkeleton.value = 'http_get';
  currentEditorCode.value = skeletonTemplates.http_get;
  saveErrorMsg.value = '';
  dryRunOutput.value = '';
  isEditModalVisible.value = true;
};

const openEditModal = async (record) => {
  isCreateMode.value = false;
  currentEditTemplateId.value = record.template_id;
  saveErrorMsg.value = '';
  dryRunOutput.value = '';
  isEditModalVisible.value = true;

  try {
    const res = await request.get('/nuclei/template/detail/', { params: { template_id: record.template_id } });
    if (res.code === 200 && res.data) {
      currentEditorCode.value = res.data.content || '';
    } else {
      message.error('获取模板源码失败: ' + (res.message || '未知错误'));
    }
  } catch (e) {
    message.error('获取模板数据异常');
  }
};

const handleSkeletonChange = (val) => {
  if (skeletonTemplates[val]) {
    currentEditorCode.value = skeletonTemplates[val];
  }
};

const saveTemplate = async () => {
  saveErrorMsg.value = '';
  if (!currentEditorCode.value.trim()) {
    saveErrorMsg.value = '模板内容不可为空';
    return;
  }
  saveLoading.value = true;
  try {
    const endpoint = isCreateMode.value ? '/nuclei/template/create/' : '/nuclei/template/update/';
    const payload = isCreateMode.value
      ? { content: currentEditorCode.value, enable: true }
      : { template_id: currentEditTemplateId.value, content: currentEditorCode.value };

    const res = await request.post(endpoint, payload);
    if (res.code === 200) {
      message.success(isCreateMode.value ? '模板创建成功' : '模板更新成功');
      isEditModalVisible.value = false;
      fetchCustomTemplates();
      fetchStats();
    } else {
      saveErrorMsg.value = res.message || res.error || '保存失败';
    }
  } catch (e) {
    saveErrorMsg.value = '请求通信异常，未能保存';
  } finally {
    saveLoading.value = false;
  }
};

// ---------- Dry Run 即时调试 ----------
const dryRunTarget = ref('');
const dryRunLoading = ref(false);
const dryRunOutput = ref('');
const dryRunMatched = ref(false);
const dryRunCost = ref(0);

const openDryRunDirect = (record) => {
  openEditModal(record);
};

const executeDryRun = async () => {
  if (!dryRunTarget.value.trim()) {
    message.warning('请输入调试目标 URL');
    return;
  }
  dryRunLoading.value = true;
  dryRunOutput.value = '正在下发 Nuclei 引擎探测中，请稍候...';
  try {
    const res = await request.post('/nuclei/template/test/', {
      content: currentEditorCode.value,
      target: dryRunTarget.value.trim()
    });
    if (res.code === 200 && res.data) {
      dryRunOutput.value = res.data.output || '(无标准输出)';
      dryRunMatched.value = !!res.data.matched;
      dryRunCost.value = res.data.cost_seconds || 0;
      if (dryRunMatched.value) {
        message.success('🎯 命中漏洞匹配条件！');
      } else {
        message.info('探测完毕，未触发漏洞规则');
      }
    } else {
      dryRunOutput.value = '执行失败: ' + (res.message || res.error || '未知错误');
      dryRunMatched.value = false;
    }
  } catch (e) {
    dryRunOutput.value = '请求异常: ' + e.message;
  } finally {
    dryRunLoading.value = false;
  }
};

// ---------- 导入弹窗 ----------
const isImportModalVisible = ref(false);
const handleUploadChange = (info) => {
  const status = info.file.status;
  if (status === 'done') {
    const res = info.file.response;
    if (res && res.code === 200) {
      message.success(`导入完成：成功 ${res.data.success_count || 0} 个，失败 ${res.data.fail_count || 0} 个`);
      isImportModalVisible.value = false;
      fetchCustomTemplates();
      fetchStats();
    } else {
      message.error(res?.message || res?.error || '导入失败');
    }
  } else if (status === 'error') {
    message.error('文件上传通信错误');
  }
};

// 下载标准 YAML 模板
const downloadSampleTemplate = () => {
  const blob = new Blob([skeletonTemplates.http_get], { type: 'text/yaml;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'nuclei_sample_template.yaml';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// ---------- 社区模板库只读检索 ----------
const communityLoading = ref(false);
const communityList = ref([]);
const communitySearch = reactive({
  search: '',
  severity: undefined,
  blacklist_status: 'all'
});
const communityPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
});

const communityColumns = [
  { title: '序号', key: 'index', width: 65, align: 'center' },
  { title: '模板 ID', key: 'template_id', width: 220 },
  { title: '漏洞名称', dataIndex: 'name', key: 'name', minWidth: 220 },
  { title: '危害级别', key: 'severity', width: 110, align: 'center' },
  { title: '状态', key: 'status', width: 120, align: 'center' },
  { title: '文件相对路径', key: 'file_path', minWidth: 260 },
  { title: '操作', key: 'action', width: 200, align: 'center' }
];

const fetchCommunityTemplates = async () => {
  communityLoading.value = true;
  try {
    const params = {
      page: communityPagination.current,
      size: communityPagination.pageSize,
      search: communitySearch.search || undefined,
      severity: communitySearch.severity || undefined,
      blacklist_status: communitySearch.blacklist_status !== 'all' ? communitySearch.blacklist_status : undefined
    };
    const res = await request.get('/nuclei/community/', { params });
    if (res.code === 200 && res.data) {
      communityList.value = res.data.items || [];
      communityPagination.total = res.data.total || 0;
    }
  } catch (e) {
    message.error('加载社区模板失败');
  } finally {
    communityLoading.value = false;
  }
};

const onSearchCommunity = () => {
  communityPagination.current = 1;
  fetchCommunityTemplates();
};

const resetSearchCommunity = () => {
  communitySearch.search = '';
  communitySearch.severity = undefined;
  communitySearch.blacklist_status = 'all';
  onSearchCommunity();
};

// ---------- 误报黑名单治理管理 (Blacklist) ----------
const blacklistLoading = ref(false);
const blacklistItems = ref([]);
const blacklistSelectedRowKeys = ref([]);
const blacklistSearch = reactive({
  search: '',
  severity: undefined
});
const blacklistPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
});

const blacklistColumns = [
  { title: '序号', key: 'index', width: 65, align: 'center' },
  { title: '模板 ID', key: 'template_id', width: 220 },
  { title: '漏洞名称', key: 'name', minWidth: 200 },
  { title: '危害级别', key: 'severity', width: 110, align: 'center' },
  { title: '误报原因说明', key: 'reason', minWidth: 260 },
  { title: '屏蔽时间', key: 'created_at', width: 170, align: 'center' },
  { title: '操作', key: 'action', width: 170, align: 'center' }
];

const fetchBlacklist = async () => {
  blacklistLoading.value = true;
  try {
    const params = {
      page: blacklistPagination.current,
      size: blacklistPagination.pageSize,
      search: blacklistSearch.search || undefined,
      severity: blacklistSearch.severity || undefined
    };
    const res = await request.get('/nuclei/blacklist/', { params });
    if (res.code === 200 && res.data) {
      blacklistItems.value = res.data.items || [];
      blacklistPagination.total = res.data.total || 0;
    }
  } catch (e) {
    message.error('加载误报黑名单失败');
  } finally {
    blacklistLoading.value = false;
  }
};

const onSearchBlacklist = () => {
  blacklistPagination.current = 1;
  fetchBlacklist();
};

const resetSearchBlacklist = () => {
  blacklistSearch.search = '';
  blacklistSearch.severity = undefined;
  onSearchBlacklist();
};

const onBlacklistSelectChange = (keys) => {
  blacklistSelectedRowKeys.value = keys;
};

// 标记误报弹窗
const isMarkModalVisible = ref(false);
const markModalLoading = ref(false);
const markModalForm = reactive({
  template_id: '',
  name: '',
  severity: '',
  tags: [],
  reason: ''
});

const openMarkBlacklistModal = (record) => {
  markModalForm.template_id = record.template_id;
  markModalForm.name = record.name || record.template_id;
  markModalForm.severity = record.severity || 'unknown';
  markModalForm.tags = record.tags || [];
  markModalForm.reason = '内网泛解析与统一404状态码误判';
  isMarkModalVisible.value = true;
};

const handleConfirmMarkBlacklist = async () => {
  if (!markModalForm.template_id) return;
  markModalLoading.value = true;
  try {
    const res = await request.post('/nuclei/blacklist/', {
      template_id: markModalForm.template_id,
      name: markModalForm.name,
      severity: markModalForm.severity,
      tags: markModalForm.tags,
      reason: markModalForm.reason || '手工标记误报'
    });
    if (res.code === 200) {
      message.success(`模板 ${markModalForm.template_id} 已加入误报黑名单`);
      isMarkModalVisible.value = false;
      fetchCommunityTemplates();
      fetchBlacklist();
      fetchStats();
    } else {
      message.error(res.message || '标记失败');
    }
  } catch (e) {
    message.error('请求通信异常');
  } finally {
    markModalLoading.value = false;
  }
};

// 手动录入误报弹窗
const isAddBlacklistModalVisible = ref(false);
const addBlacklistLoading = ref(false);
const addBlacklistForm = reactive({
  template_id: '',
  name: '',
  severity: 'unknown',
  reason: ''
});

const openAddBlacklistModal = () => {
  addBlacklistForm.template_id = '';
  addBlacklistForm.name = '';
  addBlacklistForm.severity = 'unknown';
  addBlacklistForm.reason = '';
  isAddBlacklistModalVisible.value = true;
};

const handleConfirmAddBlacklist = async () => {
  if (!addBlacklistForm.template_id.trim()) {
    message.warning('请输入模板 ID');
    return;
  }
  addBlacklistLoading.value = true;
  try {
    const res = await request.post('/nuclei/blacklist/', {
      template_id: addBlacklistForm.template_id.trim(),
      name: addBlacklistForm.name.trim() || addBlacklistForm.template_id.trim(),
      severity: addBlacklistForm.severity,
      reason: addBlacklistForm.reason.trim() || '手动录入误报'
    });
    if (res.code === 200) {
      message.success(`模板 ${addBlacklistForm.template_id} 已成功加入黑名单`);
      isAddBlacklistModalVisible.value = false;
      fetchBlacklist();
      fetchCommunityTemplates();
      fetchStats();
    } else {
      message.error(res.message || '添加失败');
    }
  } catch (e) {
    message.error('网络请求异常');
  } finally {
    addBlacklistLoading.value = false;
  }
};

// 单个解除屏蔽
const handleRemoveBlacklist = async (templateId) => {
  try {
    const res = await request.delete(`/nuclei/blacklist/${templateId}/`);
    if (res.code === 200) {
      message.success(`模板 ${templateId} 已恢复扫描参与`);
      fetchBlacklist();
      fetchCommunityTemplates();
      fetchStats();
      blacklistSelectedRowKeys.value = blacklistSelectedRowKeys.value.filter(k => k !== templateId);
    } else {
      message.error(res.message || '解除失败');
    }
  } catch (e) {
    message.error('请求失败');
  }
};

// 批量解除屏蔽
const handleBatchRemoveBlacklist = async () => {
  if (blacklistSelectedRowKeys.value.length === 0) return;
  try {
    const res = await request.post('/nuclei/blacklist/delete/', { template_ids: blacklistSelectedRowKeys.value });
    if (res.code === 200) {
      message.success(`已成功解除 ${res.data?.deleted_count || 0} 个模板的误报屏蔽`);
      blacklistSelectedRowKeys.value = [];
      fetchBlacklist();
      fetchCommunityTemplates();
      fetchStats();
    } else {
      message.error(res.message || '批量操作失败');
    }
  } catch (e) {
    message.error('网络请求异常');
  }
};

// ---------- 官方社区模板同步控制中心 ----------
const isSyncLogModalVisible = ref(false);
const isOfflineModalVisible = ref(false);
const syncStatusLoading = ref(false);
let syncTimer = null;

const syncStatus = reactive({
  status: 'idle',
  sync_mode: 'online',
  start_time: '',
  end_time: '',
  current_version: '未知',
  latest_version: '未知',
  has_update: false,
  before_total: 0,
  after_total: 0,
  diff_count: 0,
  log: '',
  error_message: ''
});

const openSyncLogModal = () => {
  fetchSyncStatus();
  isSyncLogModalVisible.value = true;
};

const fetchSyncStatus = async () => {
  syncStatusLoading.value = true;
  try {
    const res = await request.get('/nuclei/community/sync_status/');
    if (res.code === 200 && res.data) {
      Object.assign(syncStatus, res.data);
      if (syncStatus.status === 'syncing' && !syncTimer) {
        startSyncPolling();
      }
    }
  } catch (e) {
    console.error('获取同步状态失败:', e);
  } finally {
    syncStatusLoading.value = false;
  }
};

const stopSyncPolling = () => {
  if (syncTimer) {
    clearInterval(syncTimer);
    syncTimer = null;
  }
};

const startSyncPolling = () => {
  stopSyncPolling();
  syncTimer = setInterval(async () => {
    try {
      const res = await request.get('/nuclei/community/sync_status/');
      if (res.code === 200 && res.data) {
        Object.assign(syncStatus, res.data);
        if (syncStatus.status !== 'syncing') {
          stopSyncPolling();
          if (syncStatus.status === 'success') {
            notification.success({
              message: '官方模板库同步成功',
              description: `已成功更新至最新版 (${syncStatus.current_version})，增量更新 ${syncStatus.diff_count >= 0 ? '+' : ''}${syncStatus.diff_count} 条模板。`,
              duration: 5
            });
            fetchStats();
            fetchCommunityTemplates();
          } else if (syncStatus.status === 'failed') {
            notification.error({
              message: '官方模板库同步失败',
              description: syncStatus.error_message || '同步过程异常，请点击「查看同步日志」排查原因。',
              duration: 7
            });
          }
        }
      }
    } catch (e) {
      console.error('轮询同步状态异常:', e);
    }
  }, 2500);
};

const handleSyncCommunity = async () => {
  try {
    const res = await request.post('/nuclei/community/sync/');
    if (res.code === 200) {
      message.loading('官方模板加速同步任务已下发，正在后台拉取中...', 2.5);
      syncStatus.status = 'syncing';
      startSyncPolling();
    } else {
      message.warning(res.message || '触发同步受阻');
    }
  } catch (e) {
    message.error('触发同步请求失败');
  }
};

const handleOfflineUploadChange = (info) => {
  const status = info.file.status;
  if (status === 'done') {
    const res = info.file.response;
    if (res && res.code === 200) {
      message.success(res.data?.message || '离线模板包上传成功，已触发后台解压');
      isOfflineModalVisible.value = false;
      syncStatus.status = 'syncing';
      startSyncPolling();
    } else {
      message.error(res?.message || '离线包解析失败');
    }
  } else if (status === 'error') {
    message.error('上传离线包失败');
  }
};

// 社区源码抽屉
const isCommunityDrawerVisible = ref(false);
const selectedCommunityRecord = ref(null);
const communitySourceCode = ref('');
const communitySourceLoading = ref(false);

const viewCommunitySource = async (record) => {
  selectedCommunityRecord.value = record;
  communitySourceCode.value = '正在读取官方模板 YAML 源码...';
  communitySourceLoading.value = true;
  isCommunityDrawerVisible.value = true;
  try {
    const res = await request.get('/nuclei/community/source/', {
      params: { file_path: record.file_path, template_id: record.template_id }
    });
    if (res.code === 200 && res.data) {
      communitySourceCode.value = res.data.content || '';
    } else {
      communitySourceCode.value = '读取失败: ' + (res.message || '找不到该文件');
    }
  } catch (e) {
    communitySourceCode.value = '请求发生异常';
  } finally {
    communitySourceLoading.value = false;
  }
};

// 辅助方法
const getSeverityColor = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return 'red';
  if (s === 'high') return 'volcano';
  if (s === 'medium') return 'orange';
  if (s === 'low') return 'blue';
  if (s === 'info') return 'green';
  return 'default';
};

const copyText = (txt) => {
  navigator.clipboard.writeText(txt);
  message.success('已复制到剪贴板');
};

watch(innerTab, (newTab) => {
  if (newTab === 'blacklist') {
    fetchBlacklist();
  } else if (newTab === 'community') {
    fetchCommunityTemplates();
  } else if (newTab === 'custom') {
    fetchCustomTemplates();
  }
});

onMounted(() => {
  fetchStats();
  fetchCustomTemplates();
  fetchCommunityTemplates();
  fetchBlacklist();
  fetchSyncStatus();
});

onBeforeUnmount(() => {
  stopSyncPolling();
});
</script>

<style scoped>
.sync-terminal-log {
  background: #181a1f;
  color: #abb2bf;
  font-family: 'Fira Code', Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  padding: 14px 16px;
  border-radius: 6px;
  max-height: 380px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  border: 1px solid var(--arl-border-color);
  margin: 0;
}

.nuclei-manage-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-overview-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--arl-bg-layout);
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding-right: 16px;
  border-right: 1px solid var(--arl-border-color);
}
.stat-pill:last-child {
  border-right: none;
}

.stat-label {
  color: var(--arl-text-color);
  opacity: 0.65;
}

.stat-val {
  font-weight: 700;
  font-size: 15px;
  color: var(--arl-text-color);
}
.stat-val.highlight {
  color: #1890ff;
}
.stat-val.active {
  color: #52c41a;
}

.tab-content-wrapper {
  background: var(--arl-bg-layout);
  padding: 16px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.action-bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.filter-bar-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.filter-label {
  font-size: 13px;
  color: var(--arl-text-color);
  opacity: 0.85;
}

.filter-actions {
  display: flex;
  gap: 10px;
}

.dryrun-panel {
  background: rgba(0, 0, 0, 0.03);
  border: 1px dashed var(--arl-border-color);
  padding: 12px;
  border-radius: 6px;
}

.dryrun-console {
  background: #141414;
  border-radius: 4px;
  padding: 10px;
  margin-top: 8px;
}

.console-pre {
  color: #d4d4d4;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
