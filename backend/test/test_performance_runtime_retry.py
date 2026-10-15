"""对原配置处理器执行受控 Worker 状态和通信时序测试。"""
import ast
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HEAVY = 'arltask_heavy@fixture'
LIGHT = 'arltask_light@fixture'


class Control:
    """受控 Celery 控制面。

    sizes 是真实运行进程数（pool.processes 的长度）。max-concurrency 固定为 1，
    模拟真实 Celery：它是池构造时的启动值，pool_grow/pool_shrink 不会更新它。
    池伸缩由 Supervisor 线程异步补齐，因此 adjust() 只登记待生效的增量，
    下一次 stats() 才让其可见——post() 必须等待收敛才能判定结果。
    silent_shrink 模拟「命令被接收(ok)但进程数始终不变」：真实环境中进程仍被任务占用时，
    billiard 的缩容不会生效，而回复依然是 ok。
    """
    def __init__(self, sizes):
        self.sizes = dict(sizes)
        self.online = True
        self.calls = []
        self.failure = None
        self.missing_processes = False
        self.silent_shrink = False
        self._pending = {}
    def inspect(self, **kwargs): return self
    def stats(self):
        if not self.online: return None
        if self._pending:
            for name, delta in self._pending.items():
                self.sizes[name] = max(1, self.sizes[name] + delta)
            self._pending.clear()
        out = {}
        for name, size in self.sizes.items():
            pool = {'max-concurrency': 1}
            if not self.missing_processes:
                pool['processes'] = list(range(size))
            out[name] = {'pool': pool}
        return out
    def adjust(self, action, n, destination, **kwargs):
        name = destination[0]
        self.calls.append((action, n, name))
        if self.failure == 'before': raise RuntimeError('fixture connection failure')
        if self.failure == 'busy': return [{name: {'error': 'All processes busy'}}]
        if self.failure == 'no_reply': return []
        if action == 'shrink' and self.silent_shrink:
            # 命令被接收，但进程数始终不变：永不收敛。
            return [{name: {'ok': 'pool will shrink'}}]
        if self.failure == 'after':
            # 调整已生效，但回复丢失。
            self.sizes[name] += n if action == 'grow' else -n
            raise TimeoutError('fixture reply lost after adjustment')
        self._pending[name] = n if action == 'grow' else -n
        return [{name: {'ok': 'pool will ' + action}}]
    def pool_grow(self, **kwargs): return self.adjust('grow', **kwargs)
    def pool_shrink(self, **kwargs): return self.adjust('shrink', **kwargs)


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.saved = {'celery_heavy_concurrency': 1, 'celery_light_concurrency': 1, 'osint_concurrency': 1}
        self.control = Control({HEAVY: 1, LIGHT: 1})
        def save(h, l, o):
            self.saved.update(celery_heavy_concurrency=h, celery_light_concurrency=l, osint_concurrency=o)
        self.env = {'get_performance_config': lambda: dict(self.saved), 'update_performance_config': save,
                    'performance_model': None}
        tree = ast.parse((ROOT / 'app/routes/system_config.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Performance')
        node = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'post'))
        node.decorator_list = []
        # post() 依赖模块级辅助函数与常量，一并注入执行环境。
        helpers = [copy.deepcopy(n) for n in tree.body
                   if (isinstance(n, ast.FunctionDef)
                       and (n.name.startswith('_runtime_') or n.name == '_wait_pool_size'))
                   or (isinstance(n, ast.Assign) and any(
                       getattr(t, 'id', '').startswith('_POOL_SETTLE') for t in n.targets))]
        mod = ast.Module(body=helpers + [node], type_ignores=[])
        exec(compile(ast.fix_missing_locations(mod), 'Performance.post', 'exec'), self.env)

    def submit(self, heavy=4, light=1):
        args = dict(self.saved, celery_heavy_concurrency=heavy, celery_light_concurrency=light)
        instance = types.SimpleNamespace(get_parser=lambda _: types.SimpleNamespace(parse_args=lambda: args))
        module = types.ModuleType('app.celerytask')
        module.celery = types.SimpleNamespace(control=self.control)
        with patch.dict(sys.modules, {'app': types.ModuleType('app'), 'app.celerytask': module}):
            return self.env['post'](instance)

    def test_failed_grow_can_retry_the_same_saved_target(self):
        self.control.failure = 'before'
        self.assertIn('异常', self.submit()['message'])
        self.assertEqual(self.saved['celery_heavy_concurrency'], 4)
        self.assertEqual(self.control.sizes[HEAVY], 1)
        self.control.failure = None
        self.submit()
        self.assertEqual(self.control.sizes[HEAVY], 4)
        self.assertEqual(self.control.calls, [('grow', 3, HEAVY), ('grow', 3, HEAVY)])

    def test_lost_reply_after_grow_does_not_repeat_an_applied_change(self):
        self.control.failure = 'after'
        self.submit()
        self.control.failure = None
        self.submit()
        self.assertEqual(self.control.sizes[HEAVY], 4)
        self.assertEqual(len(self.control.calls), 1)

    def test_returning_worker_reconciles_the_saved_target(self):
        self.control.online = False
        self.assertIn('未响应', self.submit()['message'])
        self.assertEqual(self.saved['celery_heavy_concurrency'], 4)
        self.control.online = True
        self.submit()
        self.assertEqual(self.control.sizes[HEAVY], 4)

    def test_busy_shrink_requires_retry_and_does_not_claim_automatic_completion(self):
        self.control.sizes[HEAVY] = 8
        self.control.failure = 'busy'
        message = self.submit()['message']
        self.assertIn('重试', message)
        self.assertNotIn('自动释放', message)
        self.assertEqual(self.control.sizes[HEAVY], 8)
        self.control.failure = None
        self.submit()
        self.assertEqual(self.control.sizes[HEAVY], 4)
        self.assertEqual(self.control.calls, [('shrink', 4, HEAVY), ('shrink', 4, HEAVY)])

    def test_empty_reply_is_not_confirmation(self):
        self.control.failure = 'no_reply'
        message = self.submit()['message']
        self.assertIn('未收到节点确认', message)
        self.assertNotIn('已确认扩容', message)

    def test_pool_already_at_target_is_not_adjusted(self):
        self.control.sizes[HEAVY] = 4
        self.submit()
        self.assertEqual(self.control.calls, [])

    def test_each_worker_uses_its_own_runtime_size(self):
        second = 'arltask_heavy@second'
        self.control.sizes[second] = 3
        self.submit()
        self.assertEqual(self.control.calls, [('grow', 3, HEAVY), ('grow', 1, second)])

    def test_stale_max_concurrency_does_not_suppress_a_real_gap(self):
        # max-concurrency 恒为启动值 1，而真实运行 2 个进程、目标 4：
        # 必须按真实运行态算差额 -> 扩容 2（若误用 max-concurrency 会算成 3）。
        self.saved['celery_heavy_concurrency'] = 4
        self.control.sizes[HEAVY] = 2
        self.submit()
        self.assertEqual(self.control.calls, [('grow', 2, HEAVY)])

    def test_confirmed_grow_reports_the_observed_size(self):
        self.assertIn('已扩容至 4 个并发进程', self.submit()['message'])

    def test_confirmed_shrink_reports_the_observed_size(self):
        self.control.sizes[HEAVY] = 6
        self.assertIn('已缩容至 4 个并发进程', self.submit()['message'])

    def test_silent_shrink_is_reported_as_not_yet_effective(self):
        # 缩容命令被接收(ok)，但运行进程数始终不变：不得声称已缩容。
        self.control.sizes[HEAVY] = 8
        self.control.silent_shrink = True
        message = self.submit()['message']
        self.assertIn('运行进程数仍为 8', message)
        self.assertNotIn('已缩容至', message)
        self.assertEqual(self.control.sizes[HEAVY], 8)
        # 占用解除后可重试并真正生效
        self.control.silent_shrink = False
        self.submit()
        self.assertEqual(self.control.sizes[HEAVY], 4)
        self.assertEqual(self.control.calls, [('shrink', 4, HEAVY), ('shrink', 4, HEAVY)])

    def test_missing_runtime_processes_does_not_guess_from_startup_config(self):
        self.control.missing_processes = True
        self.assertIn('未返回运行进程数', self.submit()['message'])
        self.assertEqual(self.control.calls, [])


if __name__ == '__main__':
    unittest.main()
