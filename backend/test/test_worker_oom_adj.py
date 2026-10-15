"""Celery worker 的 OOM 优先级分层测试。

背景：三个队列（heavy / light / github）共用 arl-worker-prod 容器。
compose 的 oom_score_adj 是**每容器**属性，无法区分队列——实测三者
adj 同为 500、oom_score 同为 1010，内存耗尽时内核的取舍取决于 PID 等
无关因素。分层的目的：让长耗时扫描任务（被杀需重跑）比短周期 API 轮询
更晚被牺牲。

关键约束（容器内非特权用户，实测）：
  - 只能**提升** adj，不能低于容器基线（写低值返回 Permission denied）
  - 有效范围 [-1000, 1000]

因此测试锁定三点：范围钳制、失败降级（不得阻断启动）、exec 语义。
"""
import ast
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'run_worker_with_oom_adj.py'


def _load_wrapper():
    tree = ast.parse(WRAPPER.read_text())
    funcs = [copy.deepcopy(n) for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in {'normalize',
                                                              'apply_oom_score_adj'}]
    # 注意：常量既有单名赋值，也有元组解包（OOM_SCORE_ADJ_MIN, MAX = -1000, 1000），
    # 后者的 target 是 ast.Tuple，不能只按 ast.Name 过滤——否则函数内引用会 NameError。
    def _names_of(node):
        out = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                out.append(t.id)
            elif isinstance(t, ast.Tuple):
                out.extend(e.id for e in t.elts if isinstance(e, ast.Name))
        return out

    consts = [copy.deepcopy(n) for n in tree.body
              if isinstance(n, ast.Assign)
              and any(nm.startswith('OOM_SCORE_ADJ') for nm in _names_of(n))]
    mod = ast.Module(body=consts + funcs, type_ignores=[])
    env = {}
    exec(compile(ast.fix_missing_locations(mod), 'wrapper', 'exec'), env)
    return env


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.normalize = _load_wrapper()['normalize']

    def test_accepts_valid_range(self):
        for v, expect in (('0', 0), ('500', 500), ('700', 700),
                          ('1000', 1000), ('-1000', -1000)):
            with self.subTest(v=v):
                self.assertEqual(self.normalize(v), expect)

    def test_clamps_out_of_range(self):
        """超出内核范围时钳制，避免写入被内核拒绝导致整个 worker 起不来。"""
        self.assertEqual(self.normalize('1500'), 1000)
        self.assertEqual(self.normalize('-2000'), -1000)
        self.assertEqual(self.normalize('99999'), 1000)

    def test_rejects_non_integer(self):
        for bad in ('abc', '', None, '7.5', [], '0x10'):
            with self.subTest(bad=bad):
                self.assertIsNone(self.normalize(bad))


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.env = _load_wrapper()
        self.apply = self.env['apply_oom_score_adj']

    def test_writes_value_to_path(self):
        with tempfile.NamedTemporaryFile('w+', delete=False) as fh:
            path = fh.name
        try:
            ok, info = self.apply('700', path=path)
            self.assertTrue(ok)
            self.assertEqual(info, 700)
            self.assertEqual(Path(path).read_text(), '700')
        finally:
            os.unlink(path)

    def test_permission_error_returns_failure_not_raise(self):
        """容器内写低值会 PermissionError，必须降级为返回值而非抛出。"""
        with patch('builtins.open', side_effect=PermissionError('denied')):
            ok, info = self.apply('100')
        self.assertFalse(ok)
        self.assertIn('权限', info)

    def test_oserror_returns_failure(self):
        with patch('builtins.open', side_effect=OSError('no such file')):
            ok, info = self.apply('700')
        self.assertFalse(ok)
        self.assertIn('写入失败', info)

    def test_invalid_input_returns_failure(self):
        ok, info = self.apply('not-a-number')
        self.assertFalse(ok)
        self.assertIn('无法解析', info)

    def test_failure_never_raises(self):
        """任何失败路径都不得抛异常，否则会阻断 worker 启动。"""
        cases = [
            patch('builtins.open', side_effect=PermissionError('x')),
            patch('builtins.open', side_effect=OSError('y')),
            patch('builtins.open', side_effect=ValueError('z')),
        ]
        for patcher in cases:
            with self.subTest(patcher=patcher):
                with patcher:
                    try:
                        self.apply('700')
                    except Exception as exc:  # noqa: BLE001
                        self.fail(f'不应抛出异常，但抛出了 {exc!r}')


class StartupScriptTests(unittest.TestCase):
    """启动脚本与本包装脚本的契约。"""

    def setUp(self):
        self.script = (ROOT / 'start_worker_prod.sh').read_text()

    def test_all_three_queues_go_through_wrapper(self):
        """三个队列都必须经包装脚本启动，否则优先级分层不完整。"""
        for queue in ('arltask_light', 'arltask_heavy', 'arlgithub'):
            with self.subTest(queue=queue):
                # 找到该队列的启动行，确认前缀是包装器
                line = next((l for l in self.script.splitlines()
                             if f'-Q {queue}' in l or f'arltask,{queue}' in l), None)
                self.assertIsNotNone(line, f'未找到 {queue} 的启动行')
                self.assertIn('OOM_ADJ_WRAPPER', line,
                              f'{queue} 未通过 OOM 包装器启动')

    def test_github_adj_is_higher_than_scan(self):
        """github 的 adj 必须**高于**扫描队列，使其先被 OOM 牺牲。

        ⚠️ 方向极易搞反：oom_score_adj 的语义是「被牺牲的优先度」，
        **数值越大越先被杀**。此测试锁定正确方向——
        初版实现曾把扫描队列调到 700、github 留 500，结果扫描任务
        变成最先被杀（score 1144 vs 1010），与意图完全相反。
        """
        import re
        scan = int(re.search(r'OOM_ADJ_SCAN=(-?\d+)', self.script).group(1))
        gh = int(re.search(r'OOM_ADJ_GITHUB=(-?\d+)', self.script).group(1))
        self.assertGreater(gh, scan,
                           'github 的 adj 必须高于扫描队列，才会先被 OOM Killer 选中')

    def test_scan_queues_keep_container_baseline(self):
        """扫描队列保持容器基线，不额外提升（提升意味着更早被杀）。"""
        import re
        scan = int(re.search(r'OOM_ADJ_SCAN=(-?\d+)', self.script).group(1))
        self.assertEqual(scan, 500,
                         '扫描队列应保持容器基线 adj=500，更晚被牺牲')

    def test_adj_values_within_kernel_range(self):
        """脚本中的取值必须在 [-1000, 1000] 内，否则写入会被内核拒绝。"""
        import re
        for name in ('OOM_ADJ_SCAN', 'OOM_ADJ_GITHUB'):
            with self.subTest(name=name):
                val = int(re.search(rf'{name}=(-?\d+)', self.script).group(1))
                self.assertGreaterEqual(val, -1000)
                self.assertLessEqual(val, 1000)

if __name__ == '__main__':
    unittest.main()
