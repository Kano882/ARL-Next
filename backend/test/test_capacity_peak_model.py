"""并发推荐值的峰值模型测试。

历史缺陷：早期实现按 (总内存 - 固定预留) ÷ 同一个单进程上限 估算，存在两处错误：
  1. 固定预留（1G）在小内存多容器部署上远小于实际常驻（2G+），导致高估承载力；
  2. 忽略各队列 --max-memory-per-child 不同（488/292/292MB），且未校验峰值叠加。

后果：在 2 核 3.8G 机器上推荐 5/…，而人工验证的稳定配置是 1/1/1，用户照做即 OOM。
本测试锁定峰值模型的核心性质。
"""
import ast
import copy
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_allocator():
    tree = ast.parse((ROOT / 'app/routes/system_config.py').read_text())
    wanted = {'_allocate_concurrency'}
    funcs = [copy.deepcopy(n) for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assigns = [copy.deepcopy(n) for n in tree.body
               if isinstance(n, ast.Assign) and any(
                   getattr(t, 'id', '').isupper() or getattr(t, 'id', '').startswith('_QUEUE')
                   for t in n.targets)]
    mod = ast.Module(body=assigns + funcs, type_ignores=[])
    env = {}
    exec(compile(ast.fix_missing_locations(mod), 'capacity', 'exec'), env)
    return env


class PeakModelTests(unittest.TestCase):
    def setUp(self):
        self.env = _load_allocator()
        self.alloc = self.env['_allocate_concurrency']
        self.caps = self.env['QUEUE_MEMORY_CAPS_MB']

    # ---------- 核心回归 ----------

    def test_real_small_vps_allocates_one_each(self):
        """实测生产机（可用 1430MB → 预算 1174MB）应推荐 1/1/1。

        该机人工验证：1/1 稳定、2/2 触发 OOM。旧公式曾推荐 5。
        """
        avail = 1430
        reserve = max(256, int(avail * 0.15))
        result = self.alloc(avail - reserve)
        self.assertEqual(result['heavy'], 1)
        self.assertEqual(result['light'], 1)
        self.assertEqual(result['github'], 1)
        self.assertTrue(result['steady_ok'])

    def test_old_single_cap_approach_would_overstate(self):
        """确保不再退化为"单一上限 + 忽略峰值叠加"的估算。"""
        avail = 1430
        headroom = avail - max(256, int(avail * 0.15))
        result = self.alloc(headroom)
        # 旧口径：预算 / 单个 488MB 上限（且不看峰值）
        old_style = headroom // 488
        self.assertGreaterEqual(old_style, 2)
        self.assertLess(result['heavy'], old_style + 1)

    def test_light_and_github_use_their_own_lower_caps(self):
        """轻任务与 GitHub 队列的上限较低（292MB），必须按各自上限换算。

        这是旧实现（统一用 heavy 的 488MB 换算全部队列）最直接的错误：
        用 488 去除 292MB 的队列，会把它们能开的进程数算少约 1.67 倍。
        该错误在大内存机器上表现为"轻任务与 github 被系统性压低"，而非安全问题，
        因此不会被"峰值是否超预算"这类断言捕获，需单独锁定。
        """
        headroom = 6000
        result = self.alloc(headroom)
        budget_light = int(headroom * self.env['_QUEUE_WEIGHTS']['light'])
        budget_github = int(headroom * self.env['_QUEUE_WEIGHTS']['github'])
        # 按各自上限应得的数量
        expect_light = budget_light // self.caps['light']
        expect_github = budget_github // self.caps['github']
        # 旧口径（统一用 heavy 上限）会得到的数量，必须与之不同
        old_light = budget_light // self.caps['heavy']
        old_github = budget_github // self.caps['heavy']
        self.assertGreater(expect_light, old_light,
                           '轻任务数量应高于按 heavy 上限换算的结果')
        self.assertGreater(expect_github, old_github,
                           'GitHub 数量应高于按 heavy 上限换算的结果')
        # 关键判据：实际结果必须**严格大于**旧口径的值。
        # 用 >= 会写出空测试——旧模型下峰值收敛恰好把 light 削回 old_light，
        # 断言仍成立，无法区分两种实现。此处锁定为严格不等。
        self.assertGreater(result['light'], old_light,
                           '轻任务数量必须高于"统一按 heavy 上限换算"的结果')
        self.assertGreater(result['github'], old_github,
                           'GitHub 数量必须高于"统一按 heavy 上限换算"的结果')

    # ---------- 最小可用性 ----------

    def test_each_queue_keeps_at_least_one(self):
        """任何预算下每队列都保留 1：自动置 0 等于静默停用能力。"""
        for headroom in (0, 1, 100, 500, 1071):
            with self.subTest(headroom=headroom):
                result = self.alloc(headroom)
                self.assertGreaterEqual(result['heavy'], 1)
                self.assertGreaterEqual(result['light'], 1)
                self.assertGreaterEqual(result['github'], 1)

    def test_reports_infeasible_when_budget_too_small(self):
        """预算低于最小可行峰值时必须如实上报不可行，而非假装安全。"""
        min_peak = (self.caps['heavy'] + self.caps['light'] + self.caps['github'])
        result = self.alloc(min_peak - 1)
        self.assertFalse(result['steady_ok'])
        result_ok = self.alloc(min_peak)
        self.assertTrue(result_ok['steady_ok'])

    # ---------- 优先级 ----------

    def test_heavy_queue_is_sacrificed_last(self):
        """收敛时须优先削减 github / 轻任务，重任务最后被削。"""
        tight = 1072 + 200  # 仅够 1/1/1 加少量余量
        result = self.alloc(tight)
        # 重任务不应低于轻任务与 github
        self.assertGreaterEqual(result['heavy'], result['github'])

    def test_larger_budget_yields_larger_allocation(self):
        """预算越大分配越多，证明未被压死为常数。"""
        small = self.alloc(1200)
        large = self.alloc(20000)
        self.assertGreater(large['heavy'], small['heavy'])
        self.assertGreater(large['light'], small['light'])
        self.assertGreater(large['github'], small['github'])

    # ---------- 上限约束 ----------

    def test_respects_queue_maximums(self):
        """极大预算下仍须遵守各队列的硬上限。"""
        result = self.alloc(10 ** 9)
        maxs = self.env['_QUEUE_MAX']
        self.assertLessEqual(result['heavy'], maxs['heavy'])
        self.assertLessEqual(result['light'], maxs['light'])
        self.assertLessEqual(result['github'], maxs['github'])

    def test_returns_all_required_keys(self):
        result = self.alloc(5000)
        for key in ('heavy', 'light', 'github', 'peak_used_mb', 'steady_ok'):
            self.assertIn(key, result)

    def test_caps_match_start_script(self):
        """队列上限必须与 start_worker_prod.sh 的 --max-memory-per-child 一致。"""
        script = (ROOT / 'start_worker_prod.sh').read_text()
        # 重任务与轻任务/github 的熔断值
        self.assertIn('--max-memory-per-child=500000', script)
        self.assertIn('--max-memory-per-child=300000', script)
        self.assertEqual(self.caps['heavy'], 500000 // 1024)
        self.assertEqual(self.caps['light'], 300000 // 1024)
        self.assertEqual(self.caps['github'], 300000 // 1024)


if __name__ == '__main__':
    unittest.main()
