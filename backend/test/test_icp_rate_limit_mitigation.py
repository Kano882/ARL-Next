# -*- coding: utf-8 -*-
"""
工信部 ICP 限流熔断与规避体系单元测试集
验证：
1. 创宇盾 WAF HTML 真实报文 client_ip 正则提取
2. 出口代理自动解析、优先级继承与封禁 IP 自动剔除
3. 自适应物理流控消峰 (Rate Slot) 间隔保证
4. 详情级专属熔断与列表级熔断的分级隔离 (Detail WAF Isolation)
5. 全局熔断判定与健康代理自愈感知
"""
import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.append(os.path.abspath("backend/osint_service"))
from ymicp import beian


class TestIcpRateLimitMitigation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.icp = beian()

    def test_extract_waf_blocked_ip_from_html(self):
        """测试从创宇盾真实拦截 HTML 报文中精确提取 client_ip"""
        sample_waf_html = """
        <!DOCTYPE html><html><body>
        <script>
        var data = {"client_ip":"198.51.100.158","time_error":"20/Oct/2026:21:42:28 +0800","error_403_type":"cli_ip","error_403":"您的IP最近有可疑的攻击行为，请稍后重试."};
        document.getElementById('error_403').innerText = data['error_403'];
        </script>
        </body></html>
        """
        ip = self.icp._extract_waf_blocked_ip(sample_waf_html)
        self.assertEqual(ip, "198.51.100.158")

        # 容错：空报文或非HTML
        self.assertIsNone(self.icp._extract_waf_blocked_ip(""))
        self.assertIsNone(self.icp._extract_waf_blocked_ip(None))
        self.assertIsNone(self.icp._extract_waf_blocked_ip("<html>normal content</html>"))

    def test_extract_proxy_ip(self):
        """测试从各种代理 URL 中提取 IP/主机名"""
        self.assertEqual(self.icp._extract_proxy_ip("http://192.168.1.100:8080"), "192.168.1.100")
        self.assertEqual(self.icp._extract_proxy_ip("http://user:pass@10.0.0.5:9999"), "10.0.0.5")
        self.assertEqual(self.icp._extract_proxy_ip("http://proxy.example.com:8080"), "proxy.example.com")
        self.assertIsNone(self.icp._extract_proxy_ip(None))

    def test_resolve_proxy_precedence(self):
        """测试出口代理的优先级解析链与黑名单剔除"""
        # 1. 显式代理优先
        explicit = "http://1.1.1.1:8080"
        self.assertEqual(self.icp._resolve_proxy(explicit), explicit)

        # 2. 显式代理若被拉黑，回退到下一个层级
        self.icp._add_blocked_ip("1.1.1.1")
        # 此时 tunnel 为空，代理池为空，回退到 None
        self.assertIsNone(self.icp._resolve_proxy(explicit))

        # 3. 隧道代理继承
        with patch("ymicp.config") as mock_cfg:
            mock_cfg.proxy.tunnel.url = "http://tunnel.example.com:8888"
            self.assertEqual(self.icp._resolve_proxy(None), "http://tunnel.example.com:8888")

            # 若隧道被拉黑，回退到代理池或 None
            self.icp._add_blocked_ip("tunnel.example.com")
            self.assertIsNone(self.icp._resolve_proxy(None))

    async def test_acquire_rate_slot_spacing(self):
        """测试物理流控消峰锁强制施加安全间隔"""
        # 模拟单 IP 模式，设定短安全间隔测试时间差
        with patch("random.uniform", return_value=0.15):
            t0 = time.time()
            await self.icp._acquire_rate_slot(is_proxied=False)
            t1 = time.time()
            await self.icp._acquire_rate_slot(is_proxied=False)
            t2 = time.time()

            # 第二次调用必须等待至少 0.15s
            self.assertGreaterEqual(t2 - t1, 0.14)

    def test_detail_waf_isolation(self):
        """测试详情级熔断与列表级熔断的严格分级隔离"""
        self.assertFalse(self.icp._waf_open())
        self.assertFalse(self.icp._detail_waf_open())

        # 触发详情熔断
        self.icp._detail_waf_trip("测试详情获取")

        # 详情熔断应开启，但全局列表熔断必须依然保持关闭（保护列表抓取不受殃及）
        self.assertTrue(self.icp._detail_waf_open())
        self.assertFalse(self.icp._waf_open())

    def test_is_global_waf_blocked_respects_proxies(self):
        """测试有健康代理时全局熔断不生效（保持不停机）"""
        # 触发列表熔断
        self.icp._waf_trip("测试列表查询")
        self.assertTrue(self.icp._waf_open())

        # 单 IP 模式（无健康代理可用）-> 全局熔断生效
        with patch.object(self.icp, "_has_healthy_proxy", return_value=False):
            self.assertTrue(self.icp._is_global_waf_blocked())

        # 多代理模式（有健康代理可用）-> 全局熔断不生效（自动由健康代理接管）
        with patch.object(self.icp, "_has_healthy_proxy", return_value=True):
            self.assertFalse(self.icp._is_global_waf_blocked())

    def test_is_rate_limited_hints(self):
        """测试 MIIT 业务层限流文案的精准识别"""
        self.assertTrue(self.icp._is_rate_limited("您目前访问频次过高[访问ip:1.2.3.4]，请稍后再试"))
        self.assertTrue(self.icp._is_rate_limited("操作频繁，请稍候再试"))
        self.assertTrue(self.icp._is_rate_limited("请求过快"))
        self.assertFalse(self.icp._is_rate_limited("查询成功"))
        self.assertFalse(self.icp._is_rate_limited(None))


if __name__ == "__main__":
    unittest.main()
