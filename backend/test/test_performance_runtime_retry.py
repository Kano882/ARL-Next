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
    def __init__(self, sizes):
        self.sizes = dict(sizes)
        self.online = True
        self.calls = []
        self.failure = None
        self.missing_processes = False
    def inspect(self, **kwargs): return self
    def stats(self):
        if not self.online: return None
        return {name: {'pool': {'max-concurrency': 99, **(
            {} if self.missing_processes else {'processes': list(range(size))})}}
                for name, size in self.sizes.items()}
    def adjust(self, action, n, destination, **kwargs):
        name = destination[0]
        self.calls.append((action, n, name))
        if self.failure == 'before': raise RuntimeError('fixture connection failure')
        if self.failure == 'busy': return [{name: {'error': 'All processes busy'}}]
        self.sizes[name] += n if action == 'grow' else -n
        if self.failure == 'after': raise TimeoutError('fixture reply lost after adjustment')
        if self.failure == 'no_reply': return []
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
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), 'Performance.post', 'exec'), self.env)

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

    def test_runtime_size_overrides_stale_startup_max_concurrency(self):
        self.saved['celery_heavy_concurrency'] = 4
        self.control.sizes[HEAVY] = 2
        self.submit()
        self.assertEqual(self.control.calls, [('grow', 2, HEAVY)])

    def test_missing_runtime_processes_does_not_guess_from_startup_config(self):
        self.control.missing_processes = True
        self.assertIn('未返回运行进程数', self.submit()['message'])
        self.assertEqual(self.control.calls, [])


if __name__ == '__main__':
    unittest.main()
