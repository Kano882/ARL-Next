import asyncio
import unittest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'osint_service')))

from routes.recon_routes import reconcile_orphan_tasks, submit_recon_job
from task_manager import TaskManager


class TestOsintReconciliation(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_reconcile_orphan_tasks(self):
        async def run_test():
            task_manager = TaskManager()
            app = {'task_manager': task_manager}

            mock_db = MagicMock()
            # 1 running task
            running_tasks = [
                {"_id": "running_1", "status": "running"}
            ]
            # 2 waiting tasks (1 ICP, 1 TYC)
            waiting_tasks = [
                {"_id": "waiting_icp_1", "name": "ICP任务1", "target": "example.com", "query_type": ["web"], "status": "waiting"},
                {"_id": "waiting_tyc_2", "name": "TYC任务2", "task_type": "tyc", "gid": "12345", "depth": 2, "invest_ratio": 50, "query_type": ["invest"], "status": "waiting"}
            ]

            mock_running_cursor = MagicMock()
            mock_running_cursor.to_list = AsyncMock(return_value=running_tasks)

            mock_waiting_cursor = MagicMock()
            mock_waiting_cursor.sort = MagicMock(return_value=mock_waiting_cursor)
            mock_waiting_cursor.to_list = AsyncMock(return_value=waiting_tasks)

            def collection_find(query):
                if query.get("status") == "running":
                    return mock_running_cursor
                elif query.get("status") == "waiting":
                    return mock_waiting_cursor
                return MagicMock()

            mock_db.__getitem__.return_value.find.side_effect = collection_find
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=MagicMock())
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value={"tyc_id": "mock_id", "tyc_token": "mock_token"})

            mock_job_runner = MagicMock()
            mock_job_runner.db = mock_db
            mock_job_runner.curr_date = MagicMock(return_value="2026-09-14 12:00:00")
            mock_job_runner.run_recon_job = AsyncMock()

            with patch.dict('sys.modules', {'clients.job_runner': mock_job_runner}):
                await reconcile_orphan_tasks(app)

                # Verify running task was stopped
                mock_db.__getitem__.return_value.update_one.assert_any_call(
                    {"_id": "running_1"},
                    {"$set": {
                        "status": "stop",
                        "end_time": "2026-09-14 12:00:00",
                        "error_msg": "服务异常重启中断，已自动置为已停止，可按需手动重启"
                    }}
                )

                # Verify waiting tasks were registered into task_manager
                self.assertIsNotNone(task_manager.get_task("waiting_icp_1"))
                self.assertIsNotNone(task_manager.get_task("waiting_tyc_2"))

        self.loop.run_until_complete(run_test())

    def test_reconcile_tyc_missing_credentials(self):
        async def run_test():
            task_manager = TaskManager()
            app = {'task_manager': task_manager}

            mock_db = MagicMock()
            waiting_tasks = [
                {"_id": "waiting_tyc_missing", "name": "TYC缺凭据", "task_type": "tyc", "gid": "999", "status": "waiting"}
            ]

            mock_running_cursor = MagicMock()
            mock_running_cursor.to_list = AsyncMock(return_value=[])

            mock_waiting_cursor = MagicMock()
            mock_waiting_cursor.sort = MagicMock(return_value=mock_waiting_cursor)
            mock_waiting_cursor.to_list = AsyncMock(return_value=waiting_tasks)

            def collection_find(query):
                if query.get("status") == "running":
                    return mock_running_cursor
                elif query.get("status") == "waiting":
                    return mock_waiting_cursor
                return MagicMock()

            mock_db.__getitem__.return_value.find.side_effect = collection_find
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=MagicMock())
            # Empty credentials
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)

            mock_job_runner = MagicMock()
            mock_job_runner.db = mock_db
            mock_job_runner.curr_date = MagicMock(return_value="2026-09-14 12:00:00")
            mock_job_runner.run_recon_job = AsyncMock()

            with patch.dict('sys.modules', {'clients.job_runner': mock_job_runner}):
                await reconcile_orphan_tasks(app)

                mock_db.__getitem__.return_value.update_one.assert_called_with(
                    {"_id": "waiting_tyc_missing"},
                    {"$set": {"status": "error", "error_msg": "系统未配置天眼查凭据，自愈恢复失败"}}
                )
                self.assertIsNone(task_manager.get_task("waiting_tyc_missing"))

        self.loop.run_until_complete(run_test())

    def test_reconcile_no_tasks(self):
        async def run_test():
            task_manager = TaskManager()
            app = {'task_manager': task_manager}

            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_cursor.sort = MagicMock(return_value=mock_cursor)
            mock_db.__getitem__.return_value.find.return_value = mock_cursor

            mock_job_runner = MagicMock()
            mock_job_runner.db = mock_db
            mock_job_runner.curr_date = MagicMock(return_value="2026-09-14 12:00:00")

            with patch.dict('sys.modules', {'clients.job_runner': mock_job_runner}):
                await reconcile_orphan_tasks(app)
                mock_db.__getitem__.return_value.update_one.assert_not_called()

        self.loop.run_until_complete(run_test())

    def test_reconcile_single_task_failure_does_not_block_others(self):
        async def run_test():
            task_manager = TaskManager()
            app = {'task_manager': task_manager}

            mock_db = MagicMock()
            interrupted_tasks = [
                {"_id": "run_fail", "status": "running"},
                {"_id": "run_ok", "status": "running"}
            ]
            waiting_tasks = [
                {"_id": "wait_corrupted", "name": "坏数据", "query_type": None, "task_type": "tyc", "gid": None},  # Will fail when accessing
                {"_id": "wait_ok", "name": "正常任务", "target": "example.com", "query_type": ["web"]}
            ]

            mock_running_cursor = MagicMock()
            mock_running_cursor.to_list = AsyncMock(return_value=interrupted_tasks)

            mock_waiting_cursor = MagicMock()
            mock_waiting_cursor.sort = MagicMock(return_value=mock_waiting_cursor)
            mock_waiting_cursor.to_list = AsyncMock(return_value=waiting_tasks)

            def collection_find(query):
                if query.get("status") == "running":
                    return mock_running_cursor
                elif query.get("status") == "waiting":
                    return mock_waiting_cursor
                return MagicMock()

            async def mock_update_one(query, update):
                if query.get("_id") == "run_fail":
                    raise RuntimeError("Simulated DB connection error on run_fail")
                return MagicMock()

            mock_db.__getitem__.return_value.find.side_effect = collection_find
            mock_db.__getitem__.return_value.update_one = AsyncMock(side_effect=mock_update_one)
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value={"tyc_id": "id", "tyc_token": "token"})

            mock_job_runner = MagicMock()
            mock_job_runner.db = mock_db
            mock_job_runner.curr_date = MagicMock(return_value="2026-09-14 12:00:00")
            mock_job_runner.run_recon_job = AsyncMock()

            with patch.dict('sys.modules', {'clients.job_runner': mock_job_runner}):
                await reconcile_orphan_tasks(app)

                # Verify run_ok was still processed despite run_fail error
                mock_db.__getitem__.return_value.update_one.assert_any_call(
                    {"_id": "run_ok"},
                    {"$set": {
                        "status": "stop",
                        "end_time": "2026-09-14 12:00:00",
                        "error_msg": "服务异常重启中断，已自动置为已停止，可按需手动重启"
                    }}
                )

                # Verify wait_ok was successfully re-enqueued despite wait_corrupted
                self.assertIsNotNone(task_manager.get_task("wait_ok"))

        self.loop.run_until_complete(run_test())


if __name__ == '__main__':
    unittest.main()

