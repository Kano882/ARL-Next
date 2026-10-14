import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Setup mocks for app dependencies before importing push
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

mock_app = MagicMock()
mock_utils = MagicMock()
mock_config = MagicMock()

sys.modules.setdefault('app', mock_app)
sys.modules.setdefault('app.utils', mock_utils)
sys.modules.setdefault('app.config', mock_config)

# Import push directly
import importlib.util
spec = importlib.util.spec_from_file_location('push_module', ROOT / 'app/utils/push.py')
push_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push_module)

Push = push_module.Push
CATEGORY_LABELS = push_module.CATEGORY_LABELS
strip_markdown_syntax = push_module.strip_markdown_syntax


class TestPushSummary(unittest.TestCase):

    def test_strip_markdown_syntax(self):
        """测试 Markdown 语法脱敏清洗器"""
        raw_text = """### 🎯 标题测试
**粗体内容** 和 *斜体* 以及 `代码片段`
> 引用信息说明
[项目链接](https://example.com/project)
| 资产类型 | 数量 |
| :--- | :---: |
| 站点 | 10 |
---
完成"""
        cleaned = strip_markdown_syntax(raw_text)
        self.assertNotIn("###", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn(">", cleaned)
        self.assertNotIn("| :--- |", cleaned)
        self.assertIn("标题测试", cleaned)
        self.assertIn("粗体内容", cleaned)
        self.assertIn("代码片段", cleaned)
        self.assertIn("项目链接 (https://example.com/project)", cleaned)

    def test_empty_asset_push(self):
        """测试无资产变动场景"""
        asset_map = {"task_name": "example.com_recon"}
        asset_counter = {"domain": 0, "ip": 0, "site": 0}
        p = Push(asset_map=asset_map, asset_counter=asset_counter)

        self.assertFalse(p.has_any_data)
        
        plain = p._generate_plain_text_payload()
        self.assertIn("任务已执行完毕，本次未发现新增或变动资产", plain)
        self.assertIn("example.com_recon", plain)
        self.assertNotIn("###", plain)
        self.assertNotIn("**", plain)

        html = p._generate_html_payload()
        self.assertIn("任务已执行完毕，本次未发现新增或变动资产", html)

    def test_normal_asset_summary(self):
        """测试正常资产变动概要统计及纯文本排版"""
        asset_map = {"task_name": "target.corp_scan"}
        asset_counter = {
            "domain": 10,
            "site": 5,
            "ip": 3,
            "service": 8,
            "vuln": 0
        }
        update_counter = {
            "site": 2,
            "ip": 1
        }
        p = Push(asset_map=asset_map, asset_counter=asset_counter, update_counter=update_counter)

        self.assertTrue(p.has_any_data)
        rows, total_new, total_update, has_vuln = p._get_summary_data()

        self.assertEqual(total_new, 26)  # 10 + 5 + 3 + 8
        self.assertEqual(total_update, 3) # 2 + 1
        self.assertFalse(has_vuln)

        # 1. 纯文本排版校验 (彻底不包含 Markdown 标记)
        plain = p._generate_plain_text_payload()
        self.assertIn("【ARL-Next 任务完成通知】", plain)
        self.assertIn("任务名称：target.corp_scan", plain)
        self.assertIn("🌟 新增资产总计：26 项", plain)
        self.assertIn("🔄 更新资产总计：3 项", plain)
        self.assertIn("• Web 站点：新增 5，更新 2", plain)
        self.assertIn("• 域名资产：新增 10，更新 0", plain)
        self.assertIn("• IP 地址：新增 3，更新 1", plain)
        self.assertIn("• 开放端口服务：新增 8，更新 0", plain)
        self.assertNotIn("###", plain)
        self.assertNotIn("**", plain)
        self.assertNotIn("`", plain)
        self.assertNotIn("|", plain)
        self.assertNotIn("应用系统漏洞", plain)

        # 2. 邮件 HTML 卡片与表格校验
        html = p._generate_html_payload()
        self.assertIn("target.corp_scan", html)
        self.assertIn(">26<", html)
        self.assertIn(">3<", html)
        self.assertIn("Web 站点", html)
        self.assertIn("<table", html)
        self.assertIn("ARL-Next 控制台", html)

    def test_vulnerability_alert(self):
        """测试检出漏洞时的安全预警"""
        asset_map = {"task_name": "vuln_target_scan"}
        asset_counter = {
            "site": 2,
            "vuln": 3,
            "nuclei_result": 1
        }
        p = Push(asset_map=asset_map, asset_counter=asset_counter)

        self.assertTrue(p.has_any_data)
        rows, total_new, total_update, has_vuln = p._get_summary_data()

        self.assertTrue(has_vuln)

        plain = p._generate_plain_text_payload()
        self.assertIn("⚠️ 安全预警：检出 4 项漏洞风险，请尽快排查！", plain)
        self.assertNotIn("###", plain)
        self.assertNotIn("**", plain)

        html = p._generate_html_payload()
        self.assertIn("安全风险预警", html)
        self.assertIn("4", html)


if __name__ == '__main__':
    unittest.main()
