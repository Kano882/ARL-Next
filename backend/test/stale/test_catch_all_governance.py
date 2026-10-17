import sys
import os
import unittest
from unittest.mock import patch, MagicMock

if os.path.exists('/code/backend'):
    sys.path.insert(0, '/code/backend')
else:
    sys.path.insert(0, '/Users/sienchen/Documents/github_project/ARL-Next/backend')

from app.tasks.scheduler import DomainExecutor
from app.services.commonTask import WebSiteFetch
from app import utils


class TestWildcardDomainGovernance(unittest.TestCase):
    """验证域名层多 A 记录与泛解析治理 (scheduler.py)"""

    def setUp(self):
        class MockDomainExecutor(DomainExecutor):
            def __init__(self):
                self.wildcard_map = {
                    "example.com": {
                        "ips": {"10.0.0.1"},
                        "is_rotating": False,
                        "static_cnames": set()
                    },
                    "rotating.com": {
                        "ips": {"10.0.0.2", "10.0.0.3"},
                        "is_rotating": True,
                        "static_cnames": set()
                    }
                }
                self.scope_domain_set = {"whitelisted.example.com"}
                self.scope_domains = set()

        self.executor = MockDomainExecutor()

    def test_single_a_wildcard_filtered(self):
        """单 A 记录泛解析应当被过滤"""
        items = [{
            "domain": "fake.example.com",
            "ip_list": ["10.0.0.1"],
            "type": "A"
        }]
        res = self.executor.clear_wildcard_domain_info(items)
        self.assertEqual(len(res), 0)

    def test_multi_a_wildcard_filtered(self):
        """包含泛解析 IP 的多 A 记录 (10.0.0.1 + 1.1.1.1) 应当被识别并过滤 (交集比例 >= 0.5)"""
        items = [{
            "domain": "multi-a.example.com",
            "ip_list": ["10.0.0.1", "1.1.1.1"],
            "type": "A"
        }]
        res = self.executor.clear_wildcard_domain_info(items)
        self.assertEqual(len(res), 0, "多 A 记录包含泛解析 IP 时应被成功过滤，不可漏过！")

    def test_real_multi_a_retained(self):
        """不包含泛解析 IP 的多 A 记录应当正常放行"""
        items = [{
            "domain": "real.example.com",
            "ip_list": ["1.1.1.1", "2.2.2.2"],
            "type": "A"
        }]
        res = self.executor.clear_wildcard_domain_info(items)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["domain"], "real.example.com")

    def test_whitelisted_domain_retained(self):
        """白名单子域即便 IP 命中泛解析也应当特赦放行"""
        items = [{
            "domain": "whitelisted.example.com",
            "ip_list": ["10.0.0.1"],
            "type": "A"
        }]
        res = self.executor.clear_wildcard_domain_info(items)
        self.assertEqual(len(res), 1)


class TestSiteCatchAllControlProbe(unittest.TestCase):
    """验证站点层双探针对照、特赦机制与处置闭环 (commonTask.py)"""

    def setUp(self):
        class MockWebSiteFetch(WebSiteFetch):
            def __init__(self, site_info_list, options=None):
                self.task_id = "test_task"
                self.site_info_list = site_info_list
                self.available_sites = []
                self.catch_all_sites = set()
                self._poc_sites = None
                self.options = options or {}

        self.MockWebSiteFetch = MockWebSiteFetch

    def test_parent_domain_extraction(self):
        """测试父域提取逻辑（纯 IP 拦截、二级公共后缀处理）"""
        # 纯 IP 应当返回 None
        self.assertIsNone(WebSiteFetch._wildcard_parent("192.168.1.1"))
        # 普通子域提取父域
        self.assertEqual(WebSiteFetch._wildcard_parent("sub.test.com"), "test.com")
        # 多级子域提取直接父域
        self.assertEqual(WebSiteFetch._wildcard_parent("a.b.test.com"), "b.test.com")
        # 双公共后缀 (ccTLD) 提取有效主域（admin.edu.cn 作为二级可注册主域，不再截为公共后缀 edu.cn）
        self.assertEqual(WebSiteFetch._wildcard_parent("admin.edu.cn"), "admin.edu.cn")
        self.assertEqual(WebSiteFetch._wildcard_parent("app.admin.edu.cn"), "admin.edu.cn")
        self.assertEqual(WebSiteFetch._wildcard_parent("sub.app.admin.edu.cn"), "app.admin.edu.cn")

    def test_simhash_hamming_distance(self):
        """测试 SimHash 汉明距离容差判定"""
        # 全等
        self.assertTrue(WebSiteFetch._simhash_within_distance("123456", "123456", max_distance=3))
        # 相同数值不同类型
        self.assertTrue(WebSiteFetch._simhash_within_distance(123456, "123456", max_distance=3))

    def test_business_amnesty(self):
        """测试多维业务特征特赦 (Amnesty)"""
        # 1. 标题含关键词特赦
        item_title = {"title": "集团统一登录中心 - 用户认证", "site": "https://sso.example.com"}
        self.assertTrue(WebSiteFetch._has_business_amnesty(item_title))

        # 2. 标题含英文 dashboard 特赦
        item_admin = {"title": "Cloud Ops Dashboard", "site": "https://ops.example.com"}
        self.assertTrue(WebSiteFetch._has_business_amnesty(item_admin))

        # 3. 独立 CMS / 业务中间件指纹特赦
        item_cms = {"title": "404 Not Found", "finger": ["WordPress", "PHP"]}
        self.assertTrue(WebSiteFetch._has_business_amnesty(item_cms))

        item_middleware = {"title": "404 Not Found", "finger": ["Apache-ActiveMQ"]}
        self.assertTrue(WebSiteFetch._has_business_amnesty(item_middleware))

        # 4. 基础设施指纹（Web服务器、CDN、负载均衡、WAF）不予特赦
        item_nginx = {"title": "404 Not Found", "finger": ["Nginx"]}
        self.assertFalse(WebSiteFetch._has_business_amnesty(item_nginx))

        item_bytedance_cdn = {"title": "404 Not Found", "finger": ["ByteDance-CDN"]}
        self.assertFalse(WebSiteFetch._has_business_amnesty(item_bytedance_cdn))

        item_bytedance_tlb = {"title": "404 Not Found", "finger": ["ByteDance-TLB"]}
        self.assertFalse(WebSiteFetch._has_business_amnesty(item_bytedance_tlb))

        item_cloudflare = {"title": "404 Not Found", "finger": ["Cloudflare"]}
        self.assertFalse(WebSiteFetch._has_business_amnesty(item_cloudflare))

        item_aliyun_waf = {"title": "404 Not Found", "finger": ["Aliyun-WAF"]}
        self.assertFalse(WebSiteFetch._has_business_amnesty(item_aliyun_waf))

        # 5. 混合指纹：基础设施 + 业务框架，应当得到特赦
        item_hybrid = {"title": "404 Not Found", "finger": ["ByteDance-CDN", "WordPress"]}
        self.assertTrue(WebSiteFetch._has_business_amnesty(item_hybrid))

        # 6. SSL 证书精确匹配特赦
        item_cert = {
            "title": "",
            "hostname": "api.example.com",
            "cert": {"subject_cn": "api.example.com"}
        }
        self.assertTrue(WebSiteFetch._has_business_amnesty(item_cert))

        # 7. SSL 证书为泛域名时不特赦
        item_wc_cert = {
            "title": "",
            "hostname": "api.example.com",
            "cert": {"subject_cn": "*.example.com"}
        }
        self.assertFalse(WebSiteFetch._has_business_amnesty(item_wc_cert))

    @patch.object(WebSiteFetch, '_probe_catch_all_reference')
    def test_dual_probe_inconsistent_rejected(self, mock_probe):
        """双探针响应不一致时，应拒绝确立基准，防止 WAF 频控污染基准"""
        fetcher = self.MockWebSiteFetch([])
        # 探针 1 返回 200，探针 2 返回 403 频控
        mock_probe.side_effect = [
            {"status": 200, "title": "OK", "body_length": 100, "simhash": "1000"},
            {"status": 403, "title": "WAF Blocked", "body_length": 500, "simhash": "2000"}
        ]
        ref = fetcher._fetch_catch_all_reference("1.1.1.1", "http", 80, "sub.example.com")
        self.assertIsNone(ref, "双探针状态码不一致时必须拒绝确立基准！")

    @patch.object(WebSiteFetch, '_fetch_catch_all_reference')
    def test_catch_all_blocking_and_representative_retention(self, mock_fetch_ref):
        """
        验证全流程闭环：
        1. 20 个默认后端站点（状态码 200 OK，包含 ALB not found server）；
        2. 首个站点保留入库打标；
        3. 其余 19 个站点被剔除出 site_info_list 与 available_sites；
        4. 全量 20 个站点加入 catch_all_sites 阻断集合，poc_sites 归零！
        """
        # 模拟有效基准快照 (HTTP 200)
        mock_fetch_ref.return_value = {
            "status": 200,
            "title": "",
            "body_length": 115,
            "simhash": "123456789"
        }

        # 构造 20 个默认后端站点 + 1 个带特赦的真实业务站点
        mock_sites = []
        for i in range(20):
            mock_sites.append({
                "site": f"http://dummy{i}.example.com",
                "hostname": f"dummy{i}.example.com",
                "ip": "1.1.1.1",
                "status": 200,
                "title": "",
                "body_length": 115,
                "simhash": "123456789"
            })

        # 加入 1 个真实业务（具有登录标题）
        mock_sites.append({
            "site": "http://login.example.com",
            "hostname": "login.example.com",
            "ip": "1.1.1.1",
            "status": 200,
            "title": "管理后台登录",
            "body_length": 115,
            "simhash": "123456789"
        })

        fetcher = self.MockWebSiteFetch(mock_sites)
        fetcher.filter_catch_all_by_control_probe()

        # 检查 site_info_list：
        # 应该保留：1 个代表默认后端 + 1 个特赦真实业务 = 2 个站点
        retained_sites = [s["site"] for s in fetcher.site_info_list]
        self.assertEqual(len(retained_sites), 2)
        self.assertIn("http://dummy0.example.com", retained_sites)
        self.assertIn("http://login.example.com", retained_sites)

        # 检查代表站点打标
        rep_site = fetcher.site_info_list[0]
        self.assertTrue(rep_site.get("is_catch_all"))
        self.assertIn("catch_all_vhost", rep_site.get("tag", []))

        # 检查阻断集合 catch_all_sites：包含所有 20 个默认后端，但不包含特赦的真实业务
        self.assertEqual(len(fetcher.catch_all_sites), 20)
        self.assertNotIn("http://login.example.com", fetcher.catch_all_sites)

        # 检查下游 PoC 巡航目标池 poc_sites：
        for s in fetcher.site_info_list:
            fetcher.available_sites.append(s["site"])

        poc_targets = fetcher.poc_sites
        # 默认后端被阻断，唯独特赦的真实业务进入下游 PoC 扫描！
        self.assertEqual(len(poc_targets), 1)
        self.assertIn("http://login.example.com", poc_targets)
        self.assertNotIn("http://dummy0.example.com", poc_targets)



class TestDualLayerCatchAllPipeline(unittest.TestCase):
    """验证双层站点治理全链路端到端协同与防回归 (Issue #49 根治验证)"""

    def setUp(self):
        class MockWebSiteFetch(WebSiteFetch):
            def __init__(self, site_info_list, options=None):
                self.task_id = "test_pipeline"
                self.site_info_list = site_info_list
                self.available_sites = []
                self.catch_all_sites = set()
                self._poc_sites = None
                self.options = options or {}

        self.MockWebSiteFetch = MockWebSiteFetch

    @patch.object(WebSiteFetch, '_fetch_catch_all_reference')
    def test_pipeline_business_amnesty_immunity(self, mock_fetch_ref):
        """
        场景 1: Issue #49 核心回归
        12 个同一 IP、统一返回 403、Title 为“统一身份认证中心 - 管理后台登录”的特赦业务站点。
        首层特赦放行后，串联流经第二层，必须 100% 豁免聚类删除，阻断集合大小为 0，下游 PoC 目标全量保留！
        """
        mock_fetch_ref.return_value = {
            "status": 403,
            "title": "403 Forbidden - Default Gateway",
            "body_length": 650,
            "simhash": "12345"
        }

        mock_sites = []
        for i in range(12):
            mock_sites.append({
                "site": f"http://sso{i}.example.com",
                "hostname": f"sso{i}.example.com",
                "ip": "10.10.10.10",
                "status": 403,
                "title": "统一身份认证中心 - 管理后台登录",
                "body_length": 650,
                "simhash": "12345"
            })

        fetcher = self.MockWebSiteFetch(mock_sites)
        # 串联执行两层流水线
        fetcher.filter_catch_all_by_control_probe()
        fetcher.filter_catch_all_vhost()

        # 1. 验证 site_info_list：12 个特赦站点必须 100% 全部保留，绝不可被剔除！
        self.assertEqual(len(fetcher.site_info_list), 12, "特赦业务站点绝不能被第二层聚类剔除！")
        
        # 2. 验证 catch_all_sites 阻断集合：不能有任何特赦站点被误阻断
        self.assertEqual(len(fetcher.catch_all_sites), 0, "特赦业务站点绝不能被加入阻断黑名单！")

        # 3. 验证下游 PoC 巡航目标：12 个特赦业务站点必须全部正常开放给下游检测
        for s in fetcher.site_info_list:
            fetcher.available_sites.append(s["site"])
        self.assertEqual(len(fetcher.poc_sites), 12, "特赦业务站点必须完整保留在下游 PoC 探测池中！")

    @patch.object(WebSiteFetch, '_fetch_catch_all_reference')
    def test_pipeline_max_entry_truncation_immunity(self, mock_fetch_ref):
        """
        场景 2: Subagent 重点揭示的 P0 级 MAX_ENTRY 配额截断边界
        构造 35 个不同端口的入口（超出默认 CATCH_ALL_CONTROL_MAX_ENTRY=30 配额）。
        第 31~35 个入口未被首层双探针探测，流入第二层后必须依然享受记忆化特赦保护，100% 保留！
        """
        mock_fetch_ref.return_value = {
            "status": 403,
            "title": "Default Page",
            "body_length": 650,
            "simhash": "99999"
        }

        mock_sites = []
        # 构造 35 个不同端口的入口，每个端口 1 个特赦站点
        for i in range(35):
            port = 8000 + i
            mock_sites.append({
                "site": f"http://app{i}.example.com:{port}",
                "hostname": f"app{i}.example.com",
                "ip": "10.10.10.10",
                "status": 403,
                "title": "管理后台登录 - 核心系统",
                "body_length": 650,
                "simhash": "99999"
            })

        fetcher = self.MockWebSiteFetch(mock_sites)
        fetcher.filter_catch_all_by_control_probe()
        fetcher.filter_catch_all_vhost()

        # 全部 35 个站点（含超出配额被截断的 5 个入口）必须全部完好存活！
        self.assertEqual(len(fetcher.site_info_list), 35, "超出 MAX_ENTRY 配额截断的特赦站点必须依然 100% 存活！")
        self.assertEqual(len(fetcher.catch_all_sites), 0)

    @patch.object(WebSiteFetch, '_fetch_catch_all_reference')
    def test_pipeline_unverified_fallback_clustering(self, mock_fetch_ref):
        """
        场景 3: 第二道防线正常定位（首层网络超时未建基准时的纯默认后端兜底去噪）
        首层双探针因超时或网络异常返回 None，未能确立基准。
        12 个纯默认 403 页面（无特赦词）。
        第二层必须成功生效：聚类剔除 11 个，保留 1 个代表站点打标阻断！
        """
        mock_fetch_ref.return_value = None  # 首层超时未能确立基准

        mock_sites = []
        for i in range(12):
            mock_sites.append({
                "site": f"http://junk{i}.example.com",
                "hostname": f"junk{i}.example.com",
                "ip": "1.2.3.4",
                "status": 403,
                "title": "403 Forbidden - nginx",
                "body_length": 450,
                "simhash": "88888"
            })

        fetcher = self.MockWebSiteFetch(mock_sites)
        fetcher.filter_catch_all_by_control_probe()
        fetcher.filter_catch_all_vhost()

        # 第二层成功去噪：12 个站点去噪保留 1 个代表
        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertTrue(fetcher.site_info_list[0].get("is_catch_all"))
        self.assertIn("catch_all_vhost", fetcher.site_info_list[0].get("tag", []))
        self.assertEqual(len(fetcher.catch_all_sites), 12)

    def test_memoization_cache_behavior(self):
        """
        场景 4: 记忆化特赦缓存行为与 O(1) 性能验证
        """
        item = {
            "title": "统一身份认证中心 - 登录平台",
            "hostname": "sso.corp.com"
        }
        # 第一次调用：执行计算并缓存
        res1 = WebSiteFetch._has_business_amnesty(item)
        self.assertTrue(res1)
        self.assertIn("has_business_amnesty", item)
        self.assertTrue(item["has_business_amnesty"])

        # 第二次调用：修改 title，但因为缓存已存在，直接返回缓存值
        item["title"] = "Modified Title"
        res2 = WebSiteFetch._has_business_amnesty(item)
        self.assertTrue(res2, "第二次调用必须直接命中已有的记忆化缓存！")


if __name__ == "__main__":
    unittest.main(verbosity=2)

