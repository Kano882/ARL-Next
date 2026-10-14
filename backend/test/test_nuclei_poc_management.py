import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.routes.nuclei import parse_and_validate_nuclei_yaml, get_community_templates_dir
from app.services.nuclei_scan import NucleiScan


class TestNucleiPocManagement(unittest.TestCase):

    def test_parse_valid_yaml(self):
        sample_yaml = """
id: custom-test-cve-2024-0001
info:
  name: Custom Test CVE 2024 Vulnerability
  author: security-expert
  severity: critical
  description: This is a unit test custom template
  tags: cve,rce,test
  reference:
    - https://example.com/vuln
http:
  - method: GET
    path:
      - "{{BaseURL}}/test"
    matchers:
      - type: word
        words:
          - "vulnerable"
"""
        is_valid, meta = parse_and_validate_nuclei_yaml(sample_yaml)
        self.assertTrue(is_valid)
        self.assertEqual(meta["template_id"], "custom-test-cve-2024-0001")
        self.assertEqual(meta["name"], "Custom Test CVE 2024 Vulnerability")
        self.assertEqual(meta["severity"], "critical")
        self.assertIn("cve", meta["tags"])
        self.assertIn("rce", meta["tags"])
        self.assertEqual(meta["protocol"], "http")
        self.assertEqual(meta["author"], "security-expert")

    def test_parse_invalid_yaml(self):
        # 1. 语法错误
        bad_yaml = "id: [broken yaml"
        is_valid, err = parse_and_validate_nuclei_yaml(bad_yaml)
        self.assertFalse(is_valid)
        self.assertIn("YAML 语法解析错误", err)

        # 2. 缺失 id
        no_id_yaml = """
info:
  name: Missing ID Template
  severity: high
"""
        is_valid, err = parse_and_validate_nuclei_yaml(no_id_yaml)
        self.assertFalse(is_valid)
        self.assertIn("缺少根节点 'id'", err)

        # 3. 缺失 info.name
        no_name_yaml = """
id: test-no-name
info:
  severity: high
"""
        is_valid, err = parse_and_validate_nuclei_yaml(no_name_yaml)
        self.assertFalse(is_valid)
        self.assertIn("缺少有效 'name'", err)

    def test_nuclei_scan_options_materialize(self):
        fake_docs = [
            {
                "_id": "60a1234567890abcdef12345",
                "template_id": "test-mock-poc",
                "name": "Mock PoC",
                "content": "id: test-mock-poc\ninfo:\n  name: Mock PoC\n  severity: high\n",
                "enable": True
            }
        ]
        mock_col = MagicMock()
        mock_col.find.return_value = fake_docs

        with patch("app.utils.conn_db", return_value=mock_col):
            options = {
                "nuclei_config": {
                    "severity": ["critical", "high"],
                    "custom_template_mode": "all_enabled"
                }
            }
            scanner = NucleiScan(targets=["example.com"], options=options)
            scanner._gen_target_file = MagicMock()
            scanner._check_json_flag = MagicMock()
            scanner.nuclei_json_flag = "-jsonl"

            # 验证物化逻辑
            scanner._materialize_custom_templates()
            self.assertIsNotNone(scanner.custom_templates_path)
            self.assertTrue(os.path.isdir(scanner.custom_templates_path))

            created_file = os.path.join(scanner.custom_templates_path, "test-mock-poc.yaml")
            self.assertTrue(os.path.exists(created_file))

            # 验证清理逻辑
            scanner._delete_file()
            self.assertFalse(os.path.exists(scanner.custom_templates_path))

    def test_community_templates_dir(self):
        c_dir = get_community_templates_dir()
        # 宿主机上存在 /Users/sienchen/nuclei-templates
        self.assertTrue(bool(c_dir))
        self.assertTrue(os.path.isdir(c_dir))


if __name__ == '__main__':
    unittest.main()
