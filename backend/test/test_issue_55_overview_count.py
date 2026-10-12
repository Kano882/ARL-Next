import unittest
from unittest.mock import MagicMock, patch
import os
import sys

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

from app.modules import TaskStatus
from app.utils.task_statistics import get_task_statistics, attach_task_statistics
from app.routes.task import TaskOverviewCount, ARLTask
from app.routes.icp import IcpTaskOverviewCount, IcpTask


class MockMongoAggregateCollection:
    def __init__(self, aggregate_results=None, raise_error=False):
        self.aggregate_results = aggregate_results if aggregate_results is not None else []
        self.raise_error = raise_error
        self.pipeline_received = None

    def aggregate(self, pipeline):
        if self.raise_error:
            raise RuntimeError("Database connection timed out")
        self.pipeline_received = pipeline
        return iter(self.aggregate_results)


class TestIssue55TaskOverviewCount(unittest.TestCase):
    """
    Issue #55 根治与防护测试：
    验证资产侦查任务与企业测绘任务的全局 4 维状态指标聚合接口 (GET /overview_count 与 /statistics)
    以及列表附带 include_statistics 的单 RPC 聚合能力
    """

    def setUp(self):
        Config.AUTH = False

    def test_task_overview_count_empty(self):
        """场景 1：数据库中没有任何任务时，所有统计指标应归零且返回成功"""
        mock_col = MockMongoAggregateCollection([])
        with patch('app.routes.task.utils.conn_db', return_value=mock_col):
            resource = TaskOverviewCount()
            response = resource.get()

            self.assertEqual(response.get("code"), 200)
            data = response.get("data", {})
            self.assertEqual(data.get("total"), 0)
            self.assertEqual(data.get("running"), 0)
            self.assertEqual(data.get("active"), 0)
            self.assertEqual(data.get("done"), 0)
            self.assertEqual(data.get("abnormal"), 0)
            self.assertEqual(data.get("details"), {
                "waiting": 0,
                "running": 0,
                "done": 0,
                "error": 0,
                "stop": 0
            })

    def test_task_overview_count_aggregation_logic(self):
        """场景 2：数据库包含各种状态分布时，指标分类与总计计算正确"""
        mock_results = [
            {"_id": TaskStatus.WAITING, "count": 2},
            {"_id": TaskStatus.RUNNING, "count": 5},
            {"_id": "custom_running_state", "count": 1},  # 阶段状态，应计入 running
            {"_id": TaskStatus.DONE, "count": 42},
            {"_id": TaskStatus.ERROR, "count": 3},
            {"_id": TaskStatus.STOP, "count": 4},
        ]
        mock_col = MockMongoAggregateCollection(mock_results)
        with patch('app.routes.task.utils.conn_db', return_value=mock_col):
            resource = TaskOverviewCount()
            response = resource.get()

            self.assertEqual(response.get("code"), 200)
            data = response.get("data", {})
            # running: (5 + 1) = 6
            self.assertEqual(data.get("running"), 6)
            # active: running + waiting = 6 + 2 = 8
            self.assertEqual(data.get("active"), 8)
            # done: 42
            self.assertEqual(data.get("done"), 42)
            # abnormal: 3 + 4 = 7 (error + stop)
            self.assertEqual(data.get("abnormal"), 7)
            # total: 2 + 5 + 1 + 42 + 3 + 4 = 57
            self.assertEqual(data.get("total"), 57)
            self.assertEqual(data.get("details", {}).get("waiting"), 2)
            self.assertEqual(data.get("details", {}).get("error"), 3)
            self.assertEqual(data.get("details", {}).get("stop"), 4)

    def test_task_overview_count_exception_resilience(self):
        """场景 3：数据库异常时，优雅降级返回错误响应，不引发未捕获崩溃"""
        mock_col = MockMongoAggregateCollection(raise_error=True)
        with patch('app.routes.task.utils.conn_db', return_value=mock_col):
            resource = TaskOverviewCount()
            response = resource.get()

            self.assertNotEqual(response.get("code"), 200)
            self.assertIn("Database connection timed out", str(response))

    def test_icp_task_overview_count_aggregation(self):
        """场景 4：企业测绘任务指标聚合接口同样正确计算 4 维指标"""
        mock_results = [
            {"_id": TaskStatus.WAITING, "count": 1},
            {"_id": TaskStatus.RUNNING, "count": 2},
            {"_id": TaskStatus.DONE, "count": 15},
            {"_id": TaskStatus.ERROR, "count": 1},
            {"_id": TaskStatus.STOP, "count": 2},
        ]
        mock_col = MockMongoAggregateCollection(mock_results)
        with patch('app.routes.icp.conn_db', return_value=mock_col):
            resource = IcpTaskOverviewCount()
            response = resource.get()

            self.assertEqual(response.get("code"), 200)
            data = response.get("data", {})
            # running: 2, active: 2 + 1 = 3
            self.assertEqual(data.get("running"), 2)
            self.assertEqual(data.get("active"), 3)
            self.assertEqual(data.get("done"), 15)
            # abnormal: 1 + 2 = 3
            self.assertEqual(data.get("abnormal"), 3)
            # total: 1 + 2 + 15 + 1 + 2 = 21
            self.assertEqual(data.get("total"), 21)

    def test_attach_task_statistics_helper(self):
        """场景 5：attach_task_statistics 辅助函数能够正确将聚合统计附加至列表返回体"""
        mock_results = [
            {"_id": TaskStatus.DONE, "count": 10},
            {"_id": TaskStatus.RUNNING, "count": 2}
        ]
        mock_col = MockMongoAggregateCollection(mock_results)
        data = {"code": 200, "items": [], "total": 12}
        logger = MagicMock()

        attach_task_statistics(data, mock_col, logger, include_stage_statuses=True)
        self.assertIn("statistics", data)
        self.assertEqual(data["statistics"]["total"], 12)
        self.assertEqual(data["statistics"]["done"], 10)
        self.assertEqual(data["statistics"]["running"], 2)


if __name__ == '__main__':
    unittest.main()
