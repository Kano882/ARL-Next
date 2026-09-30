import unittest
from unittest.mock import MagicMock, patch
import os
import sys
from bson import ObjectId

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

from app.modules import TaskStatus
from app import celerytask
from celery.exceptions import WorkerLostError


class MockDbCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.inserted = []
        self.updated = []

    def _matches(self, doc, query):
        if not query:
            return True
        for k, v in query.items():
            doc_val = doc.get(k)
            if isinstance(v, dict):
                if "$nin" in v and isinstance(v["$nin"], (list, set, tuple)):
                    if doc_val in v["$nin"]:
                        return False
                elif "$in" in v and isinstance(v["$in"], (list, set, tuple)):
                    if doc_val not in v["$in"]:
                        return False
            elif doc_val != v:
                return False
        return True

    def find_one(self, query=None):
        query = query or {}
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    def insert_one(self, item):
        self.inserted.append(item)
        self.docs.append(item)
        return MagicMock(inserted_id=item.get("_id", ObjectId()))

    def update_one(self, query, update):
        self.updated.append((query, update))
        for doc in self.docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                return MagicMock(modified_count=1, matched_count=1)
        return MagicMock(modified_count=0, matched_count=0)


class TestOomTaskFailure(unittest.TestCase):
    def setUp(self):
        self.task_col = MockDbCollection()
        self.syslog_col = MockDbCollection()
        self.github_task_col = MockDbCollection()

        self.mock_db_map = {
            'task': self.task_col,
            'syslog': self.syslog_col,
            'github_task': self.github_task_col
        }

    def _mock_conn_db(self, name):
        return self.mock_db_map.get(name, MockDbCollection())

    @patch('app.utils.clean_task_tmp_files')
    @patch('app.utils.conn_db')
    def test_oom_worker_lost_error_handling(self, mock_conn, mock_clean):
        mock_conn.side_effect = self._mock_conn_db

        task_id = ObjectId()
        celery_id = "test-celery-oom-uuid-123"
        task_doc = {
            "_id": task_id,
            "name": "测试资产扫描",
            "status": "port_scan",
            "celery_id": celery_id,
            "type": "domain"
        }
        self.task_col.docs.append(task_doc)

        oom_exc = WorkerLostError("Worker exited prematurely: signal 9 (SIGKILL) Job: test-celery-oom-uuid-123")

        # 调用 handle_task_failure
        celerytask.handle_task_failure(
            sender=None,
            task_id=celery_id,
            exception=oom_exc,
            args=[{'options': {'data': {'task_id': str(task_id)}}}],
            kwargs={},
            traceback=None,
            einfo=None
        )

        # 1. 验证 task 状态原子置为 ERROR，end_reason 包含 OOM
        updated_task = self.task_col.find_one({"_id": task_id})
        self.assertEqual(updated_task["status"], TaskStatus.ERROR)
        self.assertIn("OOM", updated_task["end_reason"])
        self.assertIn("signal 9", updated_task["error_msg"])

        # 2. 验证 syslog 成功写入 CRITICAL 诊断卡片，且 timestamp 为整型
        syslog_entries = [log for log in self.syslog_col.inserted if log.get("task_id") == str(task_id)]
        self.assertEqual(len(syslog_entries), 1)
        log = syslog_entries[0]
        self.assertEqual(log["level"], "CRITICAL")
        self.assertIn("OOM-KILLER", log["message"])
        self.assertIn("port_scan", log["message"])
        self.assertIn("dmesg -T", log["message"])
        self.assertIsInstance(log["timestamp"], int)

    @patch('app.utils.conn_db')
    def test_normal_exception_handling(self, mock_conn):
        mock_conn.side_effect = self._mock_conn_db

        task_id = ObjectId()
        celery_id = "test-celery-normal-err-uuid"
        task_doc = {
            "_id": task_id,
            "name": "常规异常任务",
            "status": "domain_brute",
            "celery_id": celery_id,
            "type": "domain"
        }
        self.task_col.docs.append(task_doc)

        normal_exc = ValueError("Database connection timeout during scan")

        celerytask.handle_task_failure(
            sender=None,
            task_id=celery_id,
            exception=normal_exc,
            args=[],
            kwargs={'options': {'data': {'task_id': str(task_id)}}},
            traceback=None,
            einfo=None
        )

        updated_task = self.task_col.find_one({"_id": task_id})
        self.assertEqual(updated_task["status"], TaskStatus.ERROR)
        self.assertIn("任务执行异常", updated_task["end_reason"])
        self.assertIn("Database connection timeout", updated_task["error_msg"])

        syslog_entries = [log for log in self.syslog_col.inserted if log.get("task_id") == str(task_id)]
        self.assertEqual(len(syslog_entries), 1)
        self.assertEqual(syslog_entries[0]["level"], "ERROR")
        self.assertIn("任务执行异常", syslog_entries[0]["message"])

    @patch('app.utils.conn_db')
    def test_already_stopped_task_not_overwritten(self, mock_conn):
        mock_conn.side_effect = self._mock_conn_db

        task_id = ObjectId()
        celery_id = "test-celery-stopped-uuid"
        task_doc = {
            "_id": task_id,
            "name": "已被手动停止的任务",
            "status": TaskStatus.STOP,
            "celery_id": celery_id,
            "type": "domain"
        }
        self.task_col.docs.append(task_doc)

        oom_exc = WorkerLostError("Worker exited prematurely: signal 9 (SIGKILL)")

        celerytask.handle_task_failure(
            sender=None,
            task_id=celery_id,
            exception=oom_exc,
            args=[],
            kwargs={'options': {'data': {'task_id': str(task_id)}}},
            traceback=None,
            einfo=None
        )

        # 验证 STOP 状态不会被错误覆盖
        updated_task = self.task_col.find_one({"_id": task_id})
        self.assertEqual(updated_task["status"], TaskStatus.STOP)
        self.assertEqual(len(self.syslog_col.inserted), 0)

    @patch('app.utils.conn_db')
    def test_atomic_update_prevents_racing_stop(self, mock_conn):
        """测试当内存中读取为运行态，但并发原子更新时已被置为 STOP 时的防覆盖保护"""
        mock_conn.side_effect = self._mock_conn_db

        task_id = ObjectId()
        celery_id = "test-celery-racing-uuid"
        task_doc = {
            "_id": task_id,
            "name": "竞态停止任务",
            "status": TaskStatus.STOP,  # 模拟在进入更新前刚好被外部置为 STOP
            "celery_id": celery_id,
            "type": "domain"
        }
        self.task_col.docs.append(task_doc)

        oom_exc = WorkerLostError("Worker exited prematurely: signal 9 (SIGKILL)")

        celerytask.handle_task_failure(
            sender=None,
            task_id=celery_id,
            exception=oom_exc,
            args=[{'options': {'data': {'task_id': str(task_id)}}}],
            kwargs={},
            traceback=None,
            einfo=None
        )

        # 状态依然为 STOP，没有被覆盖成 ERROR
        updated_task = self.task_col.find_one({"_id": task_id})
        self.assertEqual(updated_task["status"], TaskStatus.STOP)

    @patch('app.utils.conn_db')
    def test_missing_options_fallback_to_celery_id(self, mock_conn):
        """测试 options 缺失或畸变时，通过 celery_id 反向查库兜底定位任务"""
        mock_conn.side_effect = self._mock_conn_db

        task_id = ObjectId()
        celery_id = "fallback-celery-uuid-999"
        task_doc = {
            "_id": task_id,
            "name": "反向查库兜底任务",
            "status": "port_scan",
            "celery_id": celery_id,
            "type": "domain"
        }
        self.task_col.docs.append(task_doc)

        oom_exc = WorkerLostError("Worker exited prematurely: signal 9 (SIGKILL)")

        # 故意不传 args/kwargs
        celerytask.handle_task_failure(
            sender=None,
            task_id=celery_id,
            exception=oom_exc,
            args=[],
            kwargs={},
            traceback=None,
            einfo=None
        )

        updated_task = self.task_col.find_one({"_id": task_id})
        self.assertEqual(updated_task["status"], TaskStatus.ERROR)
        self.assertIn("OOM", updated_task["end_reason"])

    @patch('app.utils.conn_db')
    def test_github_task_fallback(self, mock_conn):
        """测试 github_task 集合的任务分流与收敛"""
        mock_conn.side_effect = self._mock_conn_db

        task_id = ObjectId()
        celery_id = "github-celery-uuid-777"
        task_doc = {
            "_id": task_id,
            "name": "GitHub 监控任务",
            "status": "running",
            "celery_id": celery_id,
            "type": "github"
        }
        self.github_task_col.docs.append(task_doc)

        oom_exc = WorkerLostError("Worker exited prematurely: signal 9 (SIGKILL)")

        celerytask.handle_task_failure(
            sender=None,
            task_id=celery_id,
            exception=oom_exc,
            args=[{'options': {'task_id': str(task_id)}}],
            kwargs={},
            traceback=None,
            einfo=None
        )

        updated_task = self.github_task_col.find_one({"_id": task_id})
        self.assertEqual(updated_task["status"], TaskStatus.ERROR)
        self.assertIn("OOM", updated_task["end_reason"])


if __name__ == '__main__':
    unittest.main()
