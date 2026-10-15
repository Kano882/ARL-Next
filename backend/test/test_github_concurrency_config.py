"""GitHub 队列并发纳入统一配置的兼容性测试。

背景：arlgithub 队列原先在 start_worker_prod.sh 中硬编码 -c 2，既不经过
系统设置页也无法调节，是唯一游离于并发治理之外的队列。本次将其纳入
performance_config 统一管理。

核心风险是**存量部署的兼容性**，本测试锁定三点：
1. 存量 performance 文档缺 github_concurrency 时读取不报错，回退默认值；
2. 旧版调用方不传该字段时，不得把它意外重置（保留库中现值）；
3. 迁移函数只补缺失字段，绝不覆盖用户已保存的其他并发值。
"""
import ast
import copy
import sys
import types
import unittest
from unittest.mock import patch

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path, func_names, env_extra=None):
    """按本项目既有范式，用 AST 抽取目标函数注入受控环境执行。"""
    tree = ast.parse((ROOT / rel_path).read_text())
    funcs = [copy.deepcopy(n) for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in func_names]
    assigns = [copy.deepcopy(n) for n in tree.body
               if isinstance(n, ast.Assign) and any(
                   getattr(t, 'id', '').isupper() or getattr(t, 'id', '').startswith('DEFAULT')
                   or getattr(t, 'id', '').startswith('CONCURRENCY')
                   for t in n.targets)]
    mod = ast.Module(body=assigns + funcs, type_ignores=[])
    env = dict(env_extra or {})
    exec(compile(ast.fix_missing_locations(mod), rel_path, 'exec'), env)
    return env


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or {}
        self.updates = []

    def find_one(self, query, projection=None):
        return self.docs.get(query.get('_id'))

    def update_one(self, query, update, upsert=False):
        self.updates.append((dict(query), copy.deepcopy(update)))
        _id = query.get('_id')
        if '$set' in update:
            doc = self.docs.setdefault(_id, {'_id': _id})
            doc.update(update['$set'])


class PerformanceConfigTests(unittest.TestCase):
    def setUp(self):
        self.coll = FakeCollection()
        coll = self.coll
        conn_mod = types.ModuleType('app.utils.conn')
        conn_mod.conn_db = lambda name: coll
        utils_mod = types.ModuleType('app.utils')
        utils_mod.conn = conn_mod
        self._patcher = patch.dict(sys.modules, {
            'app': types.ModuleType('app'),
            'app.utils': utils_mod,
            'app.utils.conn': conn_mod,
        })
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        self.env = _load_module(
            'app/utils/performance_config.py',
            {'get_performance_config', 'update_performance_config'},
            {'conn_db': conn_mod.conn_db},
        )
        self.get = self.env['get_performance_config']
        self.update = self.env['update_performance_config']

    # ---------- 存量兼容 ----------

    def test_legacy_doc_without_github_field_reads_default(self):
        """存量文档缺 github_concurrency 时必须回退默认值而非 KeyError。"""
        self.coll.docs['performance'] = {
            '_id': 'performance',
            'celery_heavy_concurrency': 4,
            'celery_light_concurrency': 2,
            'osint_concurrency': 1,
        }
        cfg = self.get()
        self.assertEqual(cfg['github_concurrency'], 1)
        # 其他字段必须原样返回，不被默认值污染
        self.assertEqual(cfg['celery_heavy_concurrency'], 4)
        self.assertEqual(cfg['celery_light_concurrency'], 2)

    def test_default_is_one(self):
        """默认值必须为 1：该队列原先固定 2 个进程，在 2 核小内存机器上偏重。"""
        cfg = self.get()
        self.assertEqual(cfg['github_concurrency'], 1)

    def test_missing_doc_returns_all_defaults(self):
        """全新部署（无 performance 文档）返回完整默认配置。"""
        cfg = self.get()
        for key in ('celery_heavy_concurrency', 'celery_light_concurrency',
                    'osint_concurrency', 'github_concurrency'):
            self.assertIn(key, cfg)
            self.assertEqual(cfg[key], 1)

    # ---------- 不覆盖语义 ----------

    def test_omitting_github_preserves_stored_value(self):
        """核心回归：旧版前端不传该字段时，不得重置库中现值。"""
        self.coll.docs['performance'] = {'_id': 'performance', 'github_concurrency': 5}
        self.update(2, 2, 1)  # 不传 github_concurrency
        doc = self.coll.docs['performance']
        self.assertEqual(doc['github_concurrency'], 5, '未传字段应保留现值')
        self.assertEqual(doc['celery_heavy_concurrency'], 2)

    def test_passing_github_updates_it(self):
        self.coll.docs['performance'] = {'_id': 'performance', 'github_concurrency': 5}
        self.update(1, 1, 1, 3)
        self.assertEqual(self.coll.docs['performance']['github_concurrency'], 3)

    def test_explicit_none_preserves_value(self):
        """显式传 None 同样视为"未指定"，保留现值。"""
        self.coll.docs['performance'] = {'_id': 'performance', 'github_concurrency': 7}
        self.update(1, 1, 1, None)
        self.assertEqual(self.coll.docs['performance']['github_concurrency'], 7)

    # ---------- 上游/下游契约 ----------

    def test_defaults_cover_all_written_fields(self):
        """DEFAULT_CONCURRENCY 必须覆盖写入路径涉及的每个字段，否则读取会缺键。"""
        env = _load_module('app/utils/performance_config.py', set())
        defaults = env['DEFAULT_CONCURRENCY']
        self.assertIn('github_concurrency', defaults)
        for key in ('celery_heavy_concurrency', 'celery_light_concurrency',
                    'osint_concurrency', 'github_concurrency'):
            self.assertIsInstance(defaults[key], int)
            self.assertGreaterEqual(defaults[key], 1)


class MigrationTests(unittest.TestCase):
    """arlupdate.migrate_performance_config_schema 的补齐行为。"""

    def setUp(self):
        self.coll = FakeCollection()
        coll = self.coll
        conn_mod = types.ModuleType('app.utils.conn')
        conn_mod.conn_db = lambda name: coll
        # 迁移函数内部 from app.utils.performance_config import DEFAULT_CONCURRENCY
        perf_mod = types.ModuleType('app.utils.performance_config')
        perf_mod.DEFAULT_CONCURRENCY = {
            'celery_heavy_concurrency': 1,
            'celery_light_concurrency': 1,
            'osint_concurrency': 1,
            'github_concurrency': 1,
        }
        utils_mod = types.ModuleType('app.utils')
        utils_mod.conn = conn_mod
        utils_mod.performance_config = perf_mod
        self._patcher = patch.dict(sys.modules, {
            'app': types.ModuleType('app'),
            'app.utils': utils_mod,
            'app.utils.conn': conn_mod,
            'app.utils.performance_config': perf_mod,
        })
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        tree = ast.parse((ROOT / 'app/utils/arlupdate.py').read_text())
        node = copy.deepcopy(next(n for n in tree.body
                                  if isinstance(n, ast.FunctionDef)
                                  and n.name == 'migrate_performance_config_schema'))
        mod = ast.Module(body=[node], type_ignores=[])
        env = {'conn_db': conn_mod.conn_db}
        exec(compile(ast.fix_missing_locations(mod), 'arlupdate', 'exec'), env)
        self.migrate = env['migrate_performance_config_schema']

    def test_backfills_only_missing_github_field(self):
        """只补缺失字段，不触碰已有值。"""
        self.coll.docs['performance'] = {
            '_id': 'performance',
            'celery_heavy_concurrency': 8,
            'celery_light_concurrency': 4,
            'osint_concurrency': 2,
        }
        self.migrate()
        doc = self.coll.docs['performance']
        self.assertEqual(doc['github_concurrency'], 1)
        # 用户已保存的值必须原样保留
        self.assertEqual(doc['celery_heavy_concurrency'], 8)
        self.assertEqual(doc['celery_light_concurrency'], 4)
        self.assertEqual(doc['osint_concurrency'], 2)

    def test_does_not_overwrite_existing_github_value(self):
        """已有 github_concurrency 时不得被默认值覆盖。"""
        self.coll.docs['performance'] = {'_id': 'performance', 'github_concurrency': 6}
        self.migrate()
        self.assertEqual(self.coll.docs['performance']['github_concurrency'], 6)

    def test_noop_when_document_absent(self):
        """全新部署无 performance 文档时不写入，交由读取侧回退默认值。"""
        self.migrate()
        self.assertNotIn('performance', self.coll.docs)

    def test_no_update_when_nothing_missing(self):
        """字段齐备时不产生无谓写操作。"""
        self.coll.docs['performance'] = {
            '_id': 'performance',
            'celery_heavy_concurrency': 1, 'celery_light_concurrency': 1,
            'osint_concurrency': 1, 'github_concurrency': 1,
        }
        self.migrate()
        self.assertEqual(self.coll.updates, [])

    def test_failure_is_swallowed(self):
        """迁移异常不得向上抛出，避免阻断启动链路。"""
        with patch.object(self.coll, 'find_one', side_effect=RuntimeError('db down')):
            self.migrate()  # 不应抛出


if __name__ == '__main__':
    unittest.main()
