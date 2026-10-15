"""跨进程配置缓存失效测试。

背景：gunicorn 以多 worker 进程运行，每个进程持有独立的 _config_cache。
写入方只能清空自身缓存，其他 worker 会在 CACHE_TTL 内继续返回旧值，
用户表现为「保存成功但刷新页面没变化」。修复方式是递增一个存放在 MongoDB 的
版本号，读取方发现版本变化即作废本地缓存。

本测试锁定两个回归点：
1. 版本变化必须使本地缓存失效（跨进程可见性）；
2. 版本未变化时必须继续命中缓存（否则每次读取都查库，失去缓存意义）。
"""
import ast
import copy
import sys
import types
import unittest
from unittest.mock import patch

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_config_helpers(env):
    """从 app/config.py 抽取缓存相关函数注入受控环境。

    config.py 顶层依赖 yaml / 文件 IO，无法直接 import，故按本项目既有
    测试范式用 AST 抽取目标函数。
    """
    tree = ast.parse((ROOT / 'app/config.py').read_text())
    wanted_funcs = {'get_system_config_value', 'clear_system_config_cache',
                    'bump_system_config_version', '_read_config_version'}
    funcs = [copy.deepcopy(n) for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in wanted_funcs]
    wanted_assigns = ['_config_cache', 'CACHE_TTL', '_CONFIG_VERSION_COLLECTION',
                      '_CONFIG_VERSION_DOC']
    assigns = [copy.deepcopy(n) for n in tree.body
               if isinstance(n, ast.Assign) and any(
                   getattr(t, 'id', '') in wanted_assigns for t in n.targets)]
    mod = ast.Module(body=assigns + funcs, type_ignores=[])
    # 被测函数依赖 time（config.py 在模块级 import），AST 抽取会丢掉该导入，
    # 必须显式补齐，否则函数体内的 except 会把 NameError 一并吞掉，表现为静默失败。
    exec(compile(ast.fix_missing_locations(mod), 'app.config.cache', 'exec'),
         {'time': __import__('time'), **env})
    # exec 到临时 dict 不会回填调用方 env，需显式取回函数与常量
    tmp = {'time': __import__('time'), **env}
    exec(compile(ast.fix_missing_locations(mod), 'app.config.cache', 'exec'), tmp)
    env.update({k: v for k, v in tmp.items() if not k.startswith('__')})
    return env


class FakeCollection:
    """受控的 system_config 集合。"""

    def __init__(self):
        self.docs = {}
        self.find_calls = []

    def find_one(self, query, projection=None):
        self.find_calls.append(dict(query))
        return self.docs.get(query.get('_id'))

    def update_one(self, query, update, upsert=False):
        _id = query.get('_id')
        if '$inc' in update:
            doc = self.docs.setdefault(_id, {'_id': _id})
            for k, v in update['$inc'].items():
                doc[k] = doc.get(k, 0) + v
        elif '$set' in update:
            doc = self.docs.setdefault(_id, {'_id': _id})
            doc.update(update['$set'])


class CacheInvalidationTests(unittest.TestCase):
    def setUp(self):
        self.coll = FakeCollection()
        self.env = {}
        _load_config_helpers(self.env)

        # 预置配置与版本文档
        self.coll.docs['general_config'] = {'_id': 'general_config', 'fofa_url': 'v1'}
        self.coll.docs['_config_cache_version'] = {'_id': '_config_cache_version', 'version': 1}

        # 以持续生效的模块补丁承载 conn_db：被测函数内部是惰性 import，
        # 必须保证每次调用时 app.utils.conn 都可解析。
        coll = self.coll
        conn_mod = types.ModuleType('app.utils.conn')
        conn_mod.conn_db = lambda name: coll
        utils_mod = types.ModuleType('app.utils')
        utils_mod.conn = conn_mod
        app_mod = types.ModuleType('app')
        self._patcher = patch.dict(sys.modules, {
            'app': app_mod,
            'app.utils': utils_mod,
            'app.utils.conn': conn_mod,
        })
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        self.get = self.env['get_system_config_value']
        self.clear = self.env['clear_system_config_cache']
        self.bump = self.env['bump_system_config_version']

    def test_cache_hit_when_version_unchanged(self):
        """版本未变时应命中缓存，不重复查库（否则缓存形同虚设）。"""
        self.get('fofa_url', 'default')
        before = len(self.coll.find_calls)
        self.get('fofa_url', 'default')
        after = len(self.coll.find_calls)
        # 第二次读取只应有版本查询，不应有 general_config 查询
        general_queries = [c for c in self.coll.find_calls[before:after]
                           if c.get('_id') == 'general_config']
        self.assertEqual(general_queries, [])

    def test_other_worker_write_invalidates_local_cache(self):
        """核心回归：其他 worker 递增版本后，本进程必须回源而非返回旧值。"""
        first = self.get('fofa_url', 'default')
        self.assertEqual(first, 'v1')

        # 模拟另一个 gunicorn worker 保存了新配置并递增版本
        self.coll.docs['general_config'] = {'_id': 'general_config', 'fofa_url': 'v2'}
        self.bump()

        second = self.get('fofa_url', 'default')
        self.assertEqual(second, 'v2', '版本变化后必须回源读取新值')

    def test_stale_read_without_bump_is_bounded_by_ttl(self):
        """未递增版本时（如直接改库），缓存行为保持 TTL 语义。

        注意：必须替换为新的 dict 对象而非原地修改——原地修改会穿透缓存
        （缓存持有同一 dict 引用），测不出 TTL 命中行为。
        """
        self.get('fofa_url', 'default')
        self.coll.docs['general_config'] = {'_id': 'general_config', 'fofa_url': 'v2'}
        # 未调用 bump：版本未变，本地缓存仍在 TTL 内，返回旧值属预期
        still_old = self.get('fofa_url', 'default')
        self.assertEqual(still_old, 'v1')

    def test_local_clear_still_works(self):
        """本进程 clear 后应立即回源。"""
        self.get('fofa_url', 'default')
        self.coll.docs['general_config'] = {'_id': 'general_config', 'fofa_url': 'v2'}
        self.clear()
        got = self.get('fofa_url', 'default')
        self.assertEqual(got, 'v2')

    def test_cache_filled_before_version_exists_is_invalidated(self):
        """核心回归：版本机制生效前填充的缓存（seen is None）也必须能被作废。

        真实场景：某 gunicorn worker 在 _config_cache_version 文档创建之前就已
        缓存了配置，其 _config_cache["version"] 为 None。此时若按"无法判定"
        跳过版本比对，该 worker 会持续返回旧值直到 TTL 到期，表现为
        "保存成功但部分请求仍读到旧值"（实测 8 次读取中夹杂旧值）。
        """
        # 清掉版本文档，模拟机制生效前的状态
        self.coll.docs.pop('_config_cache_version', None)
        first = self.get('fofa_url', 'default')
        self.assertEqual(first, 'v1')
        # 此时缓存中的 version 应为 None
        self.assertIsNone(self.env['_config_cache'].get('version'))

        # 另一个 worker 保存配置：写入新值并新建/递增版本号
        self.coll.docs['general_config'] = {'_id': 'general_config', 'fofa_url': 'v2'}
        self.bump()

        second = self.get('fofa_url', 'default')
        self.assertEqual(second, 'v2', 'seen 为 None 时也必须失效重取')

    def test_bump_is_monotonic(self):
        """版本号必须单调递增，否则跨 worker 失效判定会失效。"""
        v0 = self.coll.docs['_config_cache_version']['version']
        self.bump()
        self.bump()
        v2 = self.coll.docs['_config_cache_version']['version']
        self.assertEqual(v2, v0 + 2)

    def test_default_returned_when_key_missing(self):
        self.assertEqual(self.get('nonexistent_key', 'fallback'), 'fallback')

    def test_bump_failure_is_swallowed(self):
        """版本递增失败不应向上抛出，避免保存主流程因缓存标记失败而报错。"""
        def boom(_):
            raise RuntimeError('collection unavailable')
        with patch.object(self.coll, 'update_one', side_effect=boom):
            self.bump()  # 不应抛出

    def test_read_failure_degrades_without_spurious_invalidation(self):
        """版本读取失败时返回 None，不得误判为版本变化。"""
        with patch.object(self.coll, 'find_one', side_effect=RuntimeError('down')):
            self.assertIsNone(self.env['_read_config_version']())


if __name__ == '__main__':
    unittest.main()


class SecurityPolicyCacheTests(unittest.TestCase):
    """security_policy 模块的跨进程缓存失效。

    该模块持有独立的 _cache（TTL 60s），与 app.config 的 _config_cache 相互独立，
    因此需要单独覆盖：修复 config.py 时曾遗漏此处，留下同一缺陷。
    """

    def setUp(self):
        tree = ast.parse((ROOT / 'app/utils/security_policy.py').read_text())
        funcs = [copy.deepcopy(n) for n in tree.body
                 if isinstance(n, ast.FunctionDef)
                 and n.name in {'get_security_policy', 'update_security_policy'}]
        assigns = [copy.deepcopy(n) for n in tree.body
                   if isinstance(n, ast.Assign) and any(
                       getattr(t, 'id', '') in {'_cache', 'CACHE_TTL'} for t in n.targets)]
        # security_policy 顶层 from app.config import Config，AST 抽取后需补齐
        mod = ast.Module(body=assigns + funcs, type_ignores=[])

        self.coll = FakeCollection()
        self.coll.docs['security_policy'] = {
            '_id': 'security_policy',
            'black_ips': ['10.0.0.0/8'],
            'forbidden_domains': ['gov.cn'],
        }
        self.coll.docs['_config_cache_version'] = {'_id': '_config_cache_version', 'version': 1}

        coll = self.coll
        coll_conn_db = lambda name: coll
        conn_mod = types.ModuleType('app.utils.conn')
        conn_mod.conn_db = coll_conn_db
        cfg_mod = types.ModuleType('app.config')
        cfg_mod.Config = types.SimpleNamespace(BLACK_IPS=[], FORBIDDEN_DOMAINS=[])
        cfg_mod._read_config_version = lambda: coll.docs.get(
            '_config_cache_version', {}).get('version')
        cfg_mod.bump_system_config_version = lambda: coll.update_one(
            {'_id': '_config_cache_version'}, {'$inc': {'version': 1}}, upsert=True)
        self.cfg_mod = cfg_mod

        app_mod = types.ModuleType('app')
        utils_mod = types.ModuleType('app.utils')
        utils_mod.conn = conn_mod
        self._patcher = patch.dict(sys.modules, {
            'app': app_mod, 'app.config': cfg_mod,
            'app.utils': utils_mod, 'app.utils.conn': conn_mod,
        })
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        # security_policy.py 在模块级 `from app.utils.conn import conn_db`，
        # AST 抽取会丢掉该导入，须显式补齐函数体内引用的名字。
        env = {
            'time': __import__('time'),
            'conn_db': coll_conn_db,
            'Config': cfg_mod.Config,
        }
        exec(compile(ast.fix_missing_locations(mod), 'security_policy', 'exec'), env)
        self.env = env
        self.get = env['get_security_policy']
        self.update = env['update_security_policy']

    def test_other_worker_update_invalidates_cache(self):
        """核心回归：其他 worker 更新安全策略后，本进程必须回源。"""
        ips, domains = self.get()
        self.assertEqual(domains, ['gov.cn'])

        # 另一个 worker 改了策略并递增版本
        self.coll.docs['security_policy'] = {
            '_id': 'security_policy',
            'black_ips': ['10.0.0.0/8'],
            'forbidden_domains': ['gov.cn', 'edu.cn'],
        }
        self.cfg_mod.bump_system_config_version()

        _, domains2 = self.get()
        self.assertEqual(domains2, ['gov.cn', 'edu.cn'], '版本变化后必须回源')

    def test_version_missing_on_cache_fill_is_still_invalidated(self):
        """seen is None 时也必须失效重取（修复前此处会静默返回旧值）。"""
        self.coll.docs.pop('_config_cache_version', None)
        self.get()
        self.assertIsNone(self.env['_cache'].get('version'))

        self.coll.docs['security_policy'] = {
            '_id': 'security_policy',
            'black_ips': ['10.0.0.0/8'],
            'forbidden_domains': ['edu.cn'],
        }
        self.cfg_mod.bump_system_config_version()

        _, domains = self.get()
        self.assertEqual(domains, ['edu.cn'])

    def test_update_bumps_version(self):
        """更新策略必须递增版本号，否则其他 worker 无法感知。"""
        v0 = self.coll.docs['_config_cache_version']['version']
        self.update(['10.0.0.0/8'], ['gov.cn'])
        v1 = self.coll.docs['_config_cache_version']['version']
        self.assertEqual(v1, v0 + 1)

    def test_version_read_failure_does_not_break_read(self):
        """版本读取异常时必须降级返回缓存值，而不是让策略读取整体失败。"""
        self.get()
        with patch.object(self.cfg_mod, '_read_config_version',
                          side_effect=RuntimeError('db down')):
            ips, domains = self.get()
        self.assertEqual(domains, ['gov.cn'])
