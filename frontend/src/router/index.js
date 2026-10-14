import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/Login.vue'),
        beforeEnter: (to, from, next) => {
            if (localStorage.getItem('token')) next('/')
            else next()
        }
    },
    {
        path: '/',
        name: 'Layout',
        component: () => import('../views/Layout.vue'),
        redirect: '/dashboard',
        beforeEnter: (to, from, next) => {
            const token = localStorage.getItem('token')
            if (!token) {
                return next('/login')
            }
            next()
        },
        children: [
            {
                path: 'dashboard',
                name: 'Dashboard',
                component: () => import('../views/Dashboard.vue'),
                meta: { title: '仪表盘' }
            },
            {
                path: 'taskList',
                name: 'TaskList',
                component: () => import('../views/TaskList.vue')
            },
            {
                // 新增详情页路由
                path: 'taskList/taskDetail',
                name: 'TaskDetail',
                component: () => import('../views/TaskDetail.vue')
            },

            {
                path: '/asset-search',
                name: 'AssetSearch',
                component: () => import('../views/AssetSearch.vue'), // 指向你刚才新建的文件
                meta: { title: '资产搜索' } // 可选：如果有面包屑或页面标题依赖 meta，可以加上
            },
            {
                // 调度中心整合：/assetsMonitor 平滑重定向至 /planningTasks?tab=monitor
                path: '/assetsMonitor',
                redirect: '/planningTasks?tab=monitor'
            },
            {
                // 🚨 核心修改：将 '/asset-scope' 改为 '/group'
                path: '/group',
                name: 'AssetScope',
                component: () => import('../views/AssetScope.vue'),
                meta: { title: '资产组' }
            },
            {
                path: '/groupAssetsManagement/groupAssetsDetail',
                name: 'GroupAssetsDetail',
                component: () => import('../views/GroupAssetsDetail.vue'),
                meta: { title: '资产组详情' }
            },
            // 在你的 routes 数组中添加：
// 找到你之前加 /policy 的地方，紧挨着追加这一段：
            {
                path: '/policy',
                name: 'Policy',
                component: () => import('../views/Policy.vue')
            },
// 🚨 新增：策略配置的独立新建/编辑页面
            {
                path: '/policyDetail',
                name: 'PolicyDetail',
                component: () => import('../views/PolicyDetail.vue')
            },
            {
                path: '/fingerprint', // 对应你左侧菜单的路径
                name: 'Fingerprint',
                component: () => import('../views/Fingerprint.vue'),
                meta: { title: '指纹管理' }
            },
            {
                path: '/pocList', // 请确保这和你菜单配置的路径一致
                name: 'PocList',
                component: () => import('../views/PocList.vue'),
                meta: { title: 'POC管理' }
            },

            {
                path: '/planningTasks', // 请确保这和你菜单配置的路径一致
                name: 'PlanningTasks',
                component: () => import('../views/PlanningTasks.vue'),
                meta: { title: '计划与调度' }
            },


            {
                path: '/GitHubTasks/GitHubTasksList',
                name: 'GithubManage',
                component: () => import('../views/GithubManage.vue'),
                meta: { title: 'GitHub监控' }
            },
            {
                path: '/systemSettings',
                name: 'SystemSettings',
                component: () => import('../views/SystemSettings.vue'),
                meta: { title: '系统设置' }
            }
        ]


    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router