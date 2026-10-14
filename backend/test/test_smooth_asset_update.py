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

# Prevent pymongo connection attempt during utils import
import pymongo
pymongo.MongoClient = MagicMock()

from app.config import Config
Config.AUTH = False

import openpyxl
import openpyxl.writer.excel
openpyxl.writer.excel.save_virtual_workbook = MagicMock()
import types
import importlib.machinery

class AutoModule(types.ModuleType):
    def __getattr__(self, name):
        return MagicMock()

xing_pkg = AutoModule('xing')
xing_pkg.__path__ = []
xing_pkg.__spec__ = importlib.machinery.ModuleSpec('xing', None, is_package=True)
sys.modules['xing'] = xing_pkg

for sub in ['conf', 'core', 'utils', 'plugins']:
    sm = AutoModule(f'xing.{sub}')
    sm.__path__ = []
    sm.__spec__ = importlib.machinery.ModuleSpec(f'xing.{sub}', None, is_package=True)
    sys.modules[f'xing.{sub}'] = sm
    setattr(xing_pkg, sub, sm)

import bson
from bson import ObjectId

# 模拟数据库集合
class MockCollection:
    def __init__(self, data=None):
        self.data = data if data is not None else []
        self.updated = []

    def find_one(self, filter_query, *args, **kwargs):
        for item in self.data:
            match = True
            for k, v in filter_query.items():
                if k == '_id' and isinstance(v, ObjectId):
                    if item.get('_id') != v:
                        match = False
                        break
                elif item.get(k) != v:
                    match = False
                    break
            if match:
                return dict(item)
        return None

    def find(self, filter_query=None, *args, **kwargs):
        results = []
        filter_query = filter_query or {}
        for item in self.data:
            match = True
            if "$or" in filter_query:
                or_match = False
                for sub_q in filter_query["$or"]:
                    sub_ok = True
                    for k, v in sub_q.items():
                        if isinstance(v, dict) and "$in" in v:
                            if item.get(k) not in v["$in"]:
                                sub_ok = False
                                break
                        elif item.get(k) != v:
                            sub_ok = False
                            break
                    if sub_ok:
                        or_match = True
                        break
                if not or_match:
                    match = False
            elif "updating_icp_task_id" in filter_query:
                # 检查 exists
                if not item.get("updating_icp_task_id"):
                    match = False
            else:
                for k, v in filter_query.items():
                    if item.get(k) != v:
                        match = False
                        break
            if match:
                results.append(dict(item))
        return results

    def insert_one(self, doc):
        d = dict(doc)
        if '_id' not in d:
            d['_id'] = ObjectId()
        self.data.append(d)
        res = MagicMock()
        res.inserted_id = d['_id']
        return res

    def update_one(self, filter_query, update_doc):
        self.updated.append((filter_query, update_doc))
        for item in self.data:
            match = True
            for k, v in filter_query.items():
                if k == '_id' and item.get('_id') != v:
                    match = False
                    break
                elif k != '_id' and item.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update_doc:
                    for sk, sv in update_doc["$set"].items():
                        item[sk] = sv
                if "$unset" in update_doc:
                    for uk in update_doc["$unset"].keys():
                        item.pop(uk, None)
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)


class TestSmoothAssetUpdate(unittest.TestCase):
    """
    主体资产平滑更新与双指针机制单元测试
    """

    def test_heal_stale_updating_icp_tasks_done(self):
        """测试已完成任务自动晋升为 synced_icp_task_id"""
        from app.utils.arlupdate import heal_stale_updating_icp_tasks

        scope_id = ObjectId()
        task_done_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": "old_task_id",
                "updating_icp_task_id": str(task_done_id)
            }
        ])
        mock_task_col = MockCollection([
            {
                "_id": task_done_id,
                "status": "done"
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        with patch('app.utils.arlupdate.conn_db', side_effect=fake_conn_db):
            heal_stale_updating_icp_tasks()

            scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(scope.get("synced_icp_task_id"), str(task_done_id))
            self.assertNotIn("updating_icp_task_id", scope)

    def test_heal_stale_updating_icp_tasks_error(self):
        """测试异常任务自动清理 updating_icp_task_id 并保留原主指针"""
        from app.utils.arlupdate import heal_stale_updating_icp_tasks

        scope_id = ObjectId()
        task_err_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": "old_task_id",
                "updating_icp_task_id": str(task_err_id)
            }
        ])
        mock_task_col = MockCollection([
            {
                "_id": task_err_id,
                "status": "error",
                "error_msg": "API quota exceeded"
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        with patch('app.utils.arlupdate.conn_db', side_effect=fake_conn_db):
            heal_stale_updating_icp_tasks()

            scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(scope.get("synced_icp_task_id"), "old_task_id")
            self.assertNotIn("updating_icp_task_id", scope)

    def test_restart_single_icp_task_double_pointer(self):
        """测试重启任务时主指针不变，新任务被记录到 updating_icp_task_id"""
        from app.routes.icp import _restart_single_icp_task

        old_task_id = ObjectId()
        scope_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": str(old_task_id)
            }
        ])
        mock_task_col = MockCollection([
            {
                "_id": old_task_id,
                "name": "测试企业主体",
                "target": "测试企业",
                "task_type": "icp",
                "query_type": ["web"],
                "status": "done",
                "synced_scope_id": str(scope_id)
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        # 复刻微服务真实确认响应：_request_recon 会校验 code 与 task_id 必须回显一致。
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = lambda: {
            "code": 200, "msg": "Task accepted",
            "task_id": str(mock_task_col.data[-1]["_id"])
        }
        mock_requests_post = MagicMock(return_value=mock_response)

        with patch('app.routes.icp.conn_db', side_effect=fake_conn_db), \
             patch('requests.post', mock_requests_post):
            ok, reason, res = _restart_single_icp_task(str(old_task_id))

            self.assertTrue(ok)
            self.assertEqual(reason, "success")
            new_task_id = res.get("new_task_id")
            self.assertIsNotNone(new_task_id)
            self.assertNotEqual(str(old_task_id), new_task_id)

            # 验证资产组主指针未被篡改，依然指向旧任务
            scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(scope.get("synced_icp_task_id"), str(old_task_id))
            # 验证 updating_icp_task_id 指向新任务
            self.assertEqual(scope.get("updating_icp_task_id"), new_task_id)

            # 验证新任务记录了 prev_task_id
            new_task = mock_task_col.find_one({"_id": ObjectId(new_task_id)})
            self.assertEqual(new_task.get("prev_task_id"), str(old_task_id))

    def test_asset_scope_enrich_running_and_done(self):
        """测试 AssetScope 列表与详情接口富化双指针：running保持展示旧任务，done原子晋升"""
        from app.routes.assetScope import ARLAssetScope

        old_task_id = ObjectId()
        new_running_id = ObjectId()
        scope_1_id = ObjectId()

        # 场景 A：任务正在运行中，AssetScope 保持指向旧任务，同时透传 updating_icp_task_id 与 updating_status
        items = [
            {
                "_id": scope_1_id,
                "name": "资产组A",
                "synced_icp_task_id": str(old_task_id),
                "updating_icp_task_id": str(new_running_id)
            }
        ]

        mock_scope_col = MockCollection(items)
        mock_task_col = MockCollection([
            {
                "_id": old_task_id,
                "name": "旧测绘任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "done"
            },
            {
                "_id": new_running_id,
                "name": "新测绘任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "running",
                "start_time": "2026-10-13 16:00:00"
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        with patch('app.routes.assetScope.utils.conn_db', side_effect=fake_conn_db):
            resource = ARLAssetScope()
            # 模拟 resource.get() 中的 build_data 阶段
            data = {"items": items, "total": 1}
            with patch.object(resource, 'build_data', return_value=data), \
                 patch.object(resource.parser, 'parse_args', return_value={}):
                res = resource.get()
                item = res['items'][0]
                # 依然保持指向旧任务，存量资产视图正常
                self.assertEqual(item.get('synced_icp_task_id'), str(old_task_id))
                self.assertEqual(item.get('updating_icp_task_id'), str(new_running_id))
                self.assertEqual(item.get('updating_status'), 'running')

        # 场景 B：新测绘任务已完成，查询时自动原子晋升并清理 updating_icp_task_id
        done_task_id = ObjectId()
        scope_2_id = ObjectId()
        items_b = [
            {
                "_id": scope_2_id,
                "name": "资产组B",
                "synced_icp_task_id": str(old_task_id),
                "updating_icp_task_id": str(done_task_id)
            }
        ]
        mock_scope_col_b = MockCollection(items_b)
        mock_task_col_b = MockCollection([
            {
                "_id": old_task_id,
                "name": "旧测绘任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "done"
            },
            {
                "_id": done_task_id,
                "name": "新已完成任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "done"
            }
        ])

        def fake_conn_db_b(table):
            if table == 'asset_scope':
                return mock_scope_col_b
            elif table == 'icp_task':
                return mock_task_col_b
            return MockCollection()

        with patch('app.routes.assetScope.utils.conn_db', side_effect=fake_conn_db_b):
            resource = ARLAssetScope()
            data_b = {"items": items_b, "total": 1}
            with patch.object(resource, 'build_data', return_value=data_b), \
                 patch.object(resource.parser, 'parse_args', return_value={}):
                res_b = resource.get()
                item_b = res_b['items'][0]
                # 主指针原子晋升为新任务 ID，updating_icp_task_id 清除
                self.assertEqual(item_b.get('synced_icp_task_id'), str(done_task_id))
                self.assertNotIn('updating_icp_task_id', item_b)
                # 数据库中的持久化指针亦被同步更新
                db_scope = mock_scope_col_b.find_one({"_id": scope_2_id})
                self.assertEqual(db_scope.get("synced_icp_task_id"), str(done_task_id))
                self.assertNotIn("updating_icp_task_id", db_scope)

    def test_job_runner_scope_sync_helper(self):
        """测试 job_runner 中异步任务完成后的 _sync_scope_after_task_completion 协程"""
        import asyncio
        from osint_service.clients.job_runner import _sync_scope_after_task_completion, db

        scope_id = ObjectId()
        task_id = str(ObjectId())

        # 模拟 Motor / AsyncIOMotorClient collection
        class AsyncMockCollection:
            def __init__(self, data):
                self.data = data

            async def find_one(self, query):
                for item in self.data:
                    match = True
                    for k, v in query.items():
                        if item.get(k) != v:
                            match = False
                            break
                    if match:
                        return dict(item)
                return None

            async def update_one(self, query, update):
                for item in self.data:
                    match = True
                    for k, v in query.items():
                        if item.get(k) != v:
                            match = False
                            break
                    if match:
                        if "$set" in update:
                            for sk, sv in update["$set"].items():
                                item[sk] = sv
                        if "$unset" in update:
                            for uk in update["$unset"]:
                                item.pop(uk, None)
                        return MagicMock(modified_count=1)
                return MagicMock(modified_count=0)

        # 测试任务成功完成场景
        scope_data = [{
            "_id": scope_id,
            "synced_icp_task_id": "old_id",
            "updating_icp_task_id": task_id
        }]
        mock_col = AsyncMockCollection(scope_data)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        with patch('osint_service.clients.job_runner.db', mock_db):
            asyncio.run(_sync_scope_after_task_completion(task_id, "done"))
            self.assertEqual(scope_data[0].get("synced_icp_task_id"), task_id)
            self.assertNotIn("updating_icp_task_id", scope_data[0])

        # 测试任务失败熔断场景
        task_fail_id = str(ObjectId())
        scope_data_fail = [{
            "_id": scope_id,
            "synced_icp_task_id": "old_id",
            "updating_icp_task_id": task_fail_id
        }]
        mock_col_fail = AsyncMockCollection(scope_data_fail)
        mock_db_fail = MagicMock()
        mock_db_fail.__getitem__.return_value = mock_col_fail
        with patch('osint_service.clients.job_runner.db', mock_db_fail):
            asyncio.run(_sync_scope_after_task_completion(task_fail_id, "error"))
            self.assertEqual(scope_data_fail[0].get("synced_icp_task_id"), "old_id")
            self.assertNotIn("updating_icp_task_id", scope_data_fail[0])


if __name__ == '__main__':
    unittest.main()
