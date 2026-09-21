import os
import sys
import unittest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during initial config import
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import pymongo
pymongo.MongoClient = MagicMock()

from app.services.commonTask import WebSiteFetch


class TestIssue49DualLayerAmnesty(unittest.TestCase):
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
