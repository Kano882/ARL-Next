import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import pymongo
pymongo.MongoClient = MagicMock()

from app.modules import CeleryAction
from app.tasks.github_threat_monitor import (
    dispatch_threat_task,
    run_threat_task_worker,
    threat_intelligence_scheduler,
    GithubCveMonitorTask,
    THREAT_CONFIG_MAP
)
from app.utils.arlupdate import normalize_threat_radar_configs


class MockUpdateResult:
    def __init__(self, modified_count=1, upserted_id=None):
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class TestThreatIntelligenceScheduler(unittest.TestCase):
    def setUp(self):
        self.db_store = {
            "cve_radar_config": {"_id": "cve_radar_config", "enabled": True, "interval": 6, "is_running": False, "last_run_time": 0},
            "tools_radar_config": {"_id": "tools_radar_config", "enabled": True, "interval": 6, "is_running": False, "last_run_time": 0},
            "hackers_radar_config": {"_id": "hackers_radar_config", "enabled": True, "interval": 6, "is_running": False, "last_run_time": 0}
        }

    def _mock_conn_db(self, col_name):
        mock_col = MagicMock()
        
        def mock_find_one(query):
            _id = query.get("_id")
            return self.db_store.get(_id)

        def mock_update_one(query, update, upsert=False):
            _id = query.get("_id")
            doc = self.db_store.get(_id)
            if not doc:
                if upsert:
                    new_doc = {"_id": _id}
                    if "$setOnInsert" in update:
                        new_doc.update(update["$setOnInsert"])
                    if "$set" in update:
                        new_doc.update(update["$set"])
                    self.db_store[_id] = new_doc
                    return MockUpdateResult(modified_count=0, upserted_id=_id)
                return MockUpdateResult(modified_count=0)

            # Check $or lock query
            if "$or" in query:
                running_since_cond = False
                for branch in query["$or"]:
                    if "is_running" in branch and doc.get("is_running") != True:
                        running_since_cond = True
                    if "running_since" in branch:
                        lt_val = branch["running_since"].get("$lt", 0)
                        if doc.get("running_since", 0) < lt_val:
                            running_since_cond = True
                if not running_since_cond:
                    return MockUpdateResult(modified_count=0)

            if "$set" in update:
                doc.update(update["$set"])
            return MockUpdateResult(modified_count=1)

        mock_col.find_one.side_effect = mock_find_one
        mock_col.update_one.side_effect = mock_update_one
        return mock_col

    @patch("app.tasks.github_threat_monitor.utils.conn_db")
    @patch("app.celerytask.arl_github.delay")
    def test_dispatch_threat_task_success(self, mock_delay, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        mock_delay.return_value = MagicMock(id="celery-threat-123")

        success, msg = dispatch_threat_task("cve")
        self.assertTrue(success)
        self.assertIn("成功提交", msg)
        self.assertTrue(self.db_store["cve_radar_config"]["is_running"])
        mock_delay.assert_called_once()
        call_options = mock_delay.call_args[1]["options"]
        self.assertEqual(call_options["celery_action"], CeleryAction.GITHUB_THREAT_CVE)

    @patch("app.tasks.github_threat_monitor.utils.conn_db")
    @patch("app.celerytask.arl_github.delay")
    def test_dispatch_threat_task_concurrency_lock(self, mock_delay, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        self.db_store["cve_radar_config"]["is_running"] = True
        self.db_store["cve_radar_config"]["running_since"] = time.time()

        success, msg = dispatch_threat_task("cve")
        self.assertFalse(success)
        self.assertIn("正在后台执行中", msg)
        mock_delay.assert_not_called()

    @patch("app.tasks.github_threat_monitor.utils.conn_db")
    @patch("app.celerytask.arl_github.delay")
    def test_dispatch_threat_task_timeout_self_healing(self, mock_delay, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        mock_delay.return_value = MagicMock(id="celery-threat-456")
        # 模拟 35 分钟前超时的任务未释放
        self.db_store["tools_radar_config"]["is_running"] = True
        self.db_store["tools_radar_config"]["running_since"] = time.time() - 2100

        success, msg = dispatch_threat_task("tools")
        self.assertTrue(success)
        mock_delay.assert_called_once()
        call_options = mock_delay.call_args[1]["options"]
        self.assertEqual(call_options["celery_action"], CeleryAction.GITHUB_THREAT_TOOLS)

    @patch("app.tasks.github_threat_monitor.utils.conn_db")
    def test_run_threat_task_worker_releases_lock(self, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        self.db_store["cve_radar_config"]["is_running"] = True

        with patch.object(GithubCveMonitorTask, "run", return_value=None):
            run_threat_task_worker("cve")

        self.assertFalse(self.db_store["cve_radar_config"]["is_running"])
        self.assertIn("last_finish_time", self.db_store["cve_radar_config"])

    @patch("app.tasks.github_threat_monitor.utils.conn_db")
    def test_run_threat_task_worker_releases_lock_on_exception(self, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        self.db_store["hackers_radar_config"]["is_running"] = True

        with patch("app.tasks.github_threat_monitor.GithubHackersMonitorTask.run", side_effect=RuntimeError("Worker error")):
            run_threat_task_worker("hackers")

        self.assertFalse(self.db_store["hackers_radar_config"]["is_running"])

    @patch("app.tasks.github_threat_monitor.utils.conn_db")
    @patch("app.tasks.github_threat_monitor.dispatch_threat_task")
    def test_threat_intelligence_scheduler_non_blocking(self, mock_dispatch, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        mock_dispatch.return_value = (True, "ok")
        # last_run_time is 0, now - 0 > 3600 * 6, so all 3 tasks should trigger non-blockingly
        threat_intelligence_scheduler()
        self.assertEqual(mock_dispatch.call_count, 3)

    @patch("app.tasks.github_threat_monitor.utils.http_req")
    def test_fetch_mitre_cve_desc_fallback(self, mock_http):
        mock_http.side_effect = Exception("Connection timeout")
        task = GithubCveMonitorTask()
        desc = task.fetch_mitre_cve_desc("CVE-2026-9999", default_desc="Repo POC Exploit")
        self.assertEqual(desc, "Repo POC Exploit")

    @patch("app.utils.arlupdate.conn_db")
    def test_normalize_threat_radar_configs(self, mock_conn):
        mock_conn.side_effect = self._mock_conn_db
        # 模拟重启前遗留的 is_running = True
        self.db_store["cve_radar_config"]["is_running"] = True
        normalize_threat_radar_configs()
        self.assertFalse(self.db_store["cve_radar_config"]["is_running"])


if __name__ == '__main__':
    unittest.main()
