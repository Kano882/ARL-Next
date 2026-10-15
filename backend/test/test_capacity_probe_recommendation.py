"""容量探测接口的内存预算与推荐值测试。

核心回归点：推荐值必须扣除**实测可用内存**而非固定预留。
历史上的错误实现按 (总内存 - 1G) / 单进程上限 计算，在本项目典型的小内存
多容器部署（MongoDB ≈1G + Web ≈0.7G + Puppeteer ≈0.26G 等常驻合计 2G+）
上会显著高估，把用户推向 OOM Killer。本测试锁定该回归。
"""
import ast
import copy
import sys
import types
import unittest
from unittest.mock import patch

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 与 start_worker_prod.sh 的 --max-memory-per-child=500000 对齐
PER_WORKER_MB = 500000 // 1024


class CapacityProbeTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'app/routes/system_config.py').read_text())
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == 'CapacityProbe')
        node = copy.deepcopy(next(n for n in cls.body
                                  if isinstance(n, ast.FunctionDef) and n.name == 'get'))
        node.decorator_list = []
        # get() 依赖模块级内存读取函数与并发分配函数，连同其常量一并注入。
        # 分配算法本身的正确性由 test_capacity_peak_model.py 覆盖，
        # 本文件只关注端点契约（字段、降级、边界）。
        helpers = [copy.deepcopy(n) for n in tree.body
                   if isinstance(n, ast.FunctionDef)
                   and n.name in {'_read_memory_report', '_allocate_concurrency'}]
        consts = [copy.deepcopy(n) for n in tree.body
                  if isinstance(n, ast.Assign) and any(
                      getattr(t, 'id', '').startswith('QUEUE_MEMORY')
                      or getattr(t, 'id', '').startswith('_QUEUE_')
                      for t in n.targets)]
        mod = ast.Module(body=consts + helpers + [node], type_ignores=[])
        self.env = {}
        exec(compile(ast.fix_missing_locations(mod), 'CapacityProbe.get', 'exec'), self.env)

    def probe(self, total_mb, available_mb):
        """在受控内存读数下调用 get()。"""
        self.env['_read_memory_report'] = lambda: {
            'total_memory_mb': total_mb,
            'available_memory_mb': available_mb,
        }
        return self.env['get'](types.SimpleNamespace())['data']

    # ---------- 核心回归：实测服务器规格 ----------

    def test_real_small_vps_recommends_one_and_one(self):
        """实测生产机（3.8GB / MemAvailable 1017MB）应推荐 1/1。

        该机经人工验证：1/1 稳定，2/2 触发 OOM。
        旧公式 (3911-1024)/488 = 5 会给出危险建议，此用例锁定修复。
        """
        data = self.probe(total_mb=3911, available_mb=1017)
        self.assertEqual(data['heavy_recommended'], 1)
        self.assertEqual(data['light_recommended'], 1)

    def test_old_formula_would_have_overstated(self):
        """确保实现不再退化为基于总内存的估算。"""
        data = self.probe(total_mb=3911, available_mb=1017)
        old_style = max(1, min(128, (3911 - 1024) // PER_WORKER_MB))
        self.assertEqual(old_style, 5)
        self.assertLess(data['heavy_recommended'], old_style)

    def test_large_available_memory_scales_up(self):
        """可用内存充裕时应给出显著大于 1 的推荐，证明未被压死为常数。"""
        data = self.probe(total_mb=65536, available_mb=63488)
        self.assertGreater(data['heavy_recommended'], 1)
        self.assertGreater(data['light_recommended'], 1)

    def test_headroom_deducts_burst_reserve(self):
        """预算必须小于可用内存，保留突发余量以避免顶满触发 OOM。"""
        data = self.probe(total_mb=3911, available_mb=1017)
        self.assertLess(data['headroom_mb'], data['available_memory_mb'])
        # 余量取 max(256, 15%)；1017 的 15% = 152，故应取 256
        self.assertEqual(data['available_memory_mb'] - data['headroom_mb'], 256)

    def test_burst_reserve_scales_with_large_memory(self):
        """内存很大时余量按 15% 计，而非固定 256MB。"""
        data = self.probe(total_mb=65536, available_mb=63488)
        expected_reserve = int(63488 * 0.15)
        self.assertEqual(data['available_memory_mb'] - data['headroom_mb'], expected_reserve)

    # ---------- 边界 ----------

    def test_zero_available_memory_still_recommends_one(self):
        """可用内存为 0 时不能推荐 0（0 会让页面无法回填，且等于禁用队列）。"""
        data = self.probe(total_mb=2048, available_mb=0)
        self.assertEqual(data['heavy_recommended'], 1)
        self.assertEqual(data['light_recommended'], 1)

    def test_tiny_available_memory_still_recommends_one(self):
        data = self.probe(total_mb=2048, available_mb=100)
        self.assertEqual(data['heavy_recommended'], 1)
        self.assertEqual(data['light_recommended'], 1)

    def test_unreadable_memory_degrades_to_none(self):
        """内存读取失败时推荐值为 None，由前端降级为不展示，而非猜测一个数字。"""
        data = self.probe(total_mb=None, available_mb=None)
        self.assertIsNone(data['heavy_recommended'])
        self.assertIsNone(data['light_recommended'])
        self.assertIsNone(data['headroom_mb'])
        self.assertIn('未能读取', data['basis'])

    def test_recommendations_respect_upper_bounds(self):
        """极端大内存下仍需遵守 :max 上限，避免生成前端无法提交的值。"""
        data = self.probe(total_mb=4194304, available_mb=4194304)
        self.assertLessEqual(data['heavy_recommended'], 128)
        self.assertLessEqual(data['light_recommended'], 256)
        self.assertLessEqual(data['github_recommended'], 64)

    def test_osint_is_always_one(self):
        """OSINT 受外网反爬约束，与内存无关，恒为 1。"""
        for total, avail in ((3911, 1017), (65536, 63488), (2048, 0)):
            with self.subTest(total=total, avail=avail):
                data = self.probe(total_mb=total, available_mb=avail)
                self.assertEqual(data['osint_recommended'], 1)

    # ---------- 守恒性 ----------

    def test_budgets_share_the_same_headroom(self):
        """三队列共享同一份可用预算：最坏峰值合计不应超过 headroom。

        注意须按**各队列各自的上限**核算（heavy 488 / light 292 / github 292），
        不能统一乘一个数——那正是早期实现的错误所在。
        """
        data = self.probe(total_mb=65536, available_mb=63488)
        caps = data['queue_memory_caps_mb']
        peak = (data['heavy_recommended'] * caps['heavy']
                + data['light_recommended'] * caps['light']
                + data['github_recommended'] * caps['github'])
        self.assertLessEqual(peak, data['headroom_mb'])
        self.assertEqual(peak, data['peak_used_mb'])

    def test_basis_mentions_measured_numbers(self):
        """依据文案必须包含可复核的实测数字，便于用户自行验证。"""
        data = self.probe(total_mb=3911, available_mb=1017)
        self.assertIn('1017', data['basis'])
        self.assertIn(str(PER_WORKER_MB), data['basis'])
        # 峰值合计需在依据中可见，便于用户自行核对最坏情形
        self.assertIn(str(data['peak_used_mb']), data['basis'])

    def test_exposes_github_and_peak_fields(self):
        """端点须向新前端暴露 github 推荐值与峰值/可行性指标。"""
        data = self.probe(total_mb=3911, available_mb=1017)
        self.assertIn('github_recommended', data)
        self.assertIn('peak_used_mb', data)
        self.assertIn('steady_ok', data)
        self.assertIn('queue_memory_caps_mb', data)


class MemoryReportTests(unittest.TestCase):
    """_read_memory_report 的解析与降级行为。"""

    def setUp(self):
        tree = ast.parse((ROOT / 'app/routes/system_config.py').read_text())
        node = copy.deepcopy(next(n for n in tree.body
                                  if isinstance(n, ast.FunctionDef)
                                  and n.name == '_read_memory_report'))
        mod = ast.Module(body=[node], type_ignores=[])
        self.env = {}
        exec(compile(ast.fix_missing_locations(mod), 'MemoryReport', 'exec'), self.env)
        self.report = self.env['_read_memory_report']

    def _with_meminfo(self, content, cgroup=None):
        """以受控 /proc/meminfo 与 cgroup 内容执行读取。"""
        def fake_open(path, *a, **k):
            if path == '/proc/meminfo':
                import io
                return io.StringIO(content)
            if 'cgroup' in path:
                if cgroup is None:
                    raise FileNotFoundError(path)
                import io
                return io.StringIO(cgroup)
            raise FileNotFoundError(path)
        import builtins
        real_open = builtins.open
        builtins.open = fake_open
        try:
            return self.report()
        finally:
            builtins.open = real_open

    def test_prefers_memavailable_over_memfree(self):
        """必须用 MemAvailable（含可回收缓存），用 MemFree 会保守到不可用。"""
        out = self._with_meminfo(
            "MemTotal:  4005676 kB\n"
            "MemFree:    306680 kB\n"
            "MemAvailable: 1041972 kB\n")
        self.assertEqual(out['total_memory_mb'], 3911)
        self.assertEqual(out['available_memory_mb'], 1017)

    def test_missing_memavailable_yields_none(self):
        out = self._with_meminfo("MemTotal:  4005676 kB\nMemFree: 306680 kB\n")
        self.assertEqual(out['total_memory_mb'], 3911)
        self.assertIsNone(out['available_memory_mb'])

    def test_cgroup_limit_clamps_total(self):
        """容器设了内存限额时应与宿主机总量取小，避免按整机内存推荐。"""
        out = self._with_meminfo(
            "MemTotal:  4005676 kB\nMemAvailable: 1041972 kB\n",
            cgroup="2147483648\n")  # 2GB
        self.assertEqual(out['total_memory_mb'], 2048)
        # 限额 2048MB 高于实测可用 1017MB，故 available 取 min 后仍为 1017（不被抬高）
        self.assertEqual(out['available_memory_mb'], 1017)

    def test_cgroup_max_sentinel_is_ignored(self):
        """cgroup v2 未设限额时写入 'max'，必须被忽略而非解析失败。"""
        out = self._with_meminfo(
            "MemTotal:  4005676 kB\nMemAvailable: 1041972 kB\n",
            cgroup="max\n")
        self.assertEqual(out['total_memory_mb'], 3911)

    def test_huge_cgroup_sentinel_is_ignored(self):
        """cgroup v1 未设限额时给出极大值，必须视作无效。"""
        out = self._with_meminfo(
            "MemTotal:  4005676 kB\nMemAvailable: 1041972 kB\n",
            cgroup="9223372036854771712\n")
        self.assertEqual(out['total_memory_mb'], 3911)

    def test_unreadable_meminfo_returns_none(self):
        out = self._with_meminfo("")  # 空内容等价于解析不到字段
        self.assertIsNone(out['total_memory_mb'])
        self.assertIsNone(out['available_memory_mb'])


if __name__ == '__main__':
    unittest.main()
