#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARL-Next Nuclei 核心模块算法单元测试套件 (Unit Tests)
涵盖：
1. parse_and_validate_nuclei_yaml: 静态契约合法性、必填字段、异常输入与安全校验
2. extract_templates_zip_to_dir: 智能解压、协议目录保留、包装目录剥离与 Zip Slip 阻断
3. NucleiScan 核心单元逻辑: 排除清单生成、大小写多态变体、参数构造与物理无痕生命周期
"""

import sys
import os
import io
import json
import zipfile
import tempfile
import unittest

# 动态配置 import 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.routes.nuclei import parse_and_validate_nuclei_yaml, extract_templates_zip_to_dir
from app.services.nuclei_scan import NucleiScan


class TestNucleiUnit(unittest.TestCase):

    # --------------------------------------------------------------------------
    # 1. parse_and_validate_nuclei_yaml 契约校验单元测试
    # --------------------------------------------------------------------------
    def test_valid_yaml(self):
        content = """id: test-unit-poc
info:
  name: Unit Test Valid Vulnerability
  author: tester
  severity: high
  tags: unit,test
http:
  - method: GET
    path: ["{{BaseURL}}/"]
"""
        ok, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        self.assertTrue(ok)
        self.assertEqual(meta["template_id"], "test-unit-poc")
        self.assertEqual(meta["name"], "Unit Test Valid Vulnerability")
        self.assertEqual(meta["severity"], "high")
        self.assertIn("unit", meta["tags"])

    def test_invalid_yaml_syntax(self):
        content = "id: test\n  bad_indent: [1, 2"
        ok, err = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        self.assertFalse(ok)
        self.assertIn("YAML 语法解析错误", err)

    def test_yaml_not_a_mapping(self):
        content = "- item1\n- item2"
        ok, err = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        self.assertFalse(ok)
        self.assertIn("顶层 YAML 映射", err)

    def test_missing_id_or_name(self):
        no_id = "info:\n  name: Test\nhttp: []"
        ok1, err1 = parse_and_validate_nuclei_yaml(no_id, run_nuclei_validate=False)
        self.assertFalse(ok1)
        self.assertIn("缺少", err1)

        no_name = "id: test-poc\ninfo:\n  severity: high\nhttp: []"
        ok2, err2 = parse_and_validate_nuclei_yaml(no_name, run_nuclei_validate=False)
        self.assertFalse(ok2)
        self.assertIn("缺少", err2)

    # --------------------------------------------------------------------------
    # 2. extract_templates_zip_to_dir 解压与路径处理单元测试
    # --------------------------------------------------------------------------
    def test_extract_standard_protocol_dir_not_stripped(self):
        """核心防护验证：标准协议分类目录 (如 http) 不应作为外层前缀被剥离"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr("http/miscellaneous/test-poc.yaml", "id: test-poc\n")
            zip_buf.seek(0)
            zip_path = os.path.join(tmp_dir, "test.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_buf.getvalue())

            extract_dir = os.path.join(tmp_dir, "out")
            cnt = extract_templates_zip_to_dir(zip_path, extract_dir)
            self.assertEqual(cnt, 1)
            # 必须解压在 http/miscellaneous/ 下，而非直接在 miscellaneous/ 下
            target_file = os.path.join(extract_dir, "http/miscellaneous/test-poc.yaml")
            self.assertTrue(os.path.exists(target_file))

    def test_extract_outer_wrapper_stripped(self):
        """外部版本包装目录 (如 nuclei-templates-10.5.0/) 应被正确剥离"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr("nuclei-templates-10.5.0/http/cves/cve-1.yaml", "id: cve-1\n")
            zip_buf.seek(0)
            zip_path = os.path.join(tmp_dir, "test_wrap.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_buf.getvalue())

            extract_dir = os.path.join(tmp_dir, "out_wrap")
            cnt = extract_templates_zip_to_dir(zip_path, extract_dir)
            self.assertEqual(cnt, 1)
            # 应被剥离为 http/cves/cve-1.yaml
            target_file = os.path.join(extract_dir, "http/cves/cve-1.yaml")
            self.assertTrue(os.path.exists(target_file))

    def test_extract_zip_slip_protection(self):
        """Zip Slip 路径穿越目录跳出防御"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr("../evil.yaml", "id: evil\n")
            zip_buf.seek(0)
            zip_path = os.path.join(tmp_dir, "slip.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_buf.getvalue())

            extract_dir = os.path.join(tmp_dir, "out_slip")
            cnt = extract_templates_zip_to_dir(zip_path, extract_dir)
            self.assertEqual(cnt, 0)
            evil_path = os.path.join(tmp_dir, "evil.yaml")
            self.assertFalse(os.path.exists(evil_path))

    # --------------------------------------------------------------------------
    # 3. NucleiScan 排除清单生成单元测试
    # --------------------------------------------------------------------------
    def test_nuclei_scan_prepare_exclude_file_with_policy(self):
        scan = NucleiScan(targets=["127.0.0.1"], options={
            "nuclei_config": {
                "exclude_blacklist": False,
                "extra_exclude_ids": ["policy-exclude-1", "policy-exclude-2"]
            }
        })
        ex_file = scan._prepare_exclude_file()
        self.assertIsNotNone(ex_file)
        self.assertTrue(os.path.exists(ex_file))

        with open(ex_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        self.assertIn("policy-exclude-1", lines)
        self.assertIn("policy-exclude-2", lines)

        # 验证安全回收
        scan._delete_file()
        self.assertFalse(os.path.exists(ex_file))


if __name__ == "__main__":
    unittest.main()
