# coding: utf-8
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import unittest
from unittest.mock import MagicMock
from app.routes.icp import normalize_icp_asset_item, IcpAsset

class TestKappQueryAndNormalization(unittest.TestCase):
    def test_normalize_kapp_asset_item(self):
        item = {
            "serviceName": "测试快应用",
            "serviceLicence": "京ICP备12345678号-1K",
            "unitName": "北京测试信息科技有限公司",
            "mainLicence": "京ICP备12345678号",
            "contentTypeName": "无",
            "updateRecordTime": "2024-05-20 10:00:00",
            "query_type": "kapp",
            "task_id": "6ad74406e005cc7b69f710bf"
        }
        normalized = normalize_icp_asset_item(item)
        
        # 1. 名称双向对齐
        self.assertEqual(normalized["serviceName"], "测试快应用")
        self.assertEqual(normalized["name"], "测试快应用")

        # 2. 单位双向对齐
        self.assertEqual(normalized["unitName"], "北京测试信息科技有限公司")
        self.assertEqual(normalized["companyName"], "北京测试信息科技有限公司")

        # 3. 备案号双向对齐
        self.assertEqual(normalized["serviceLicence"], "京ICP备12345678号-1K")
        self.assertEqual(normalized["serviceFilingNumber"], "京ICP备12345678号-1K")

        # 4. 时间双向对齐
        self.assertEqual(normalized["updateRecordTime"], "2024-05-20 10:00:00")
        self.assertEqual(normalized["examineDate"], "2024-05-20 10:00:00")

    def test_build_db_query_kapp_independent_licenses(self):
        asset_resource = IcpAsset()
        
        # 测试同时传入主体备案号和服务备案号时，两者均被独立多路匹配，互不覆盖丢失
        args = {
            "task_id": "6ad74406e005cc7b69f710bf",
            "query_type": "kapp",
            "mainLicence": "京ICP备12345678号",
            "serviceLicence": "京ICP备12345678号-1K",
            "serviceName": "测试快应用",
            "unitName": "北京测试科技"
        }
        
        query = asset_resource.build_db_query(args)
        
        self.assertEqual(query.get("task_id"), "6ad74406e005cc7b69f710bf")
        self.assertEqual(query.get("query_type"), "kapp")
        
        and_conditions = query.get("$and", [])
        self.assertTrue(len(and_conditions) >= 4)
        
        # 验证主体备案号查询组
        main_lic_group = next((c["$or"] for c in and_conditions if any("mainLicence" in sub for sub in c.get("$or", []))), None)
        self.assertIsNotNone(main_lic_group)
        self.assertTrue(any("mainLicence" in cond for cond in main_lic_group))
        self.assertTrue(any("liscense" in cond for cond in main_lic_group))
        
        # 验证服务备案号查询组
        service_lic_group = next((c["$or"] for c in and_conditions if any("serviceLicence" in sub for sub in c.get("$or", []))), None)
        self.assertIsNotNone(service_lic_group)
        self.assertTrue(any("serviceLicence" in cond for cond in service_lic_group))
        self.assertTrue(any("serviceFilingNumber" in cond for cond in service_lic_group))

        # 验证名称查询组
        name_group = next((c["$or"] for c in and_conditions if any("serviceName" in sub for sub in c.get("$or", []))), None)
        self.assertIsNotNone(name_group)

        # 验证单位查询组
        unit_group = next((c["$or"] for c in and_conditions if any("unitName" in sub for sub in c.get("$or", []))), None)
        self.assertIsNotNone(unit_group)

if __name__ == '__main__':
    unittest.main()
