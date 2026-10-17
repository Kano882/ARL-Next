#!/usr/bin/env python3
"""前端内联样式基线扫描（check_inline_style.py）。

背景：frontend/src 存在 1300+ 处静态 style=" 内联声明，与 Ant Design Vue
规范（统一色系/间距/栅格，严禁散落硬编码内联样式）冲突。存量随触随改，
新增代码零内联——本脚本即新增卡点。

Usage:
    python3 tools/check_inline_style.py                  # 全量扫描并公示 Top 文件
    python3 tools/check_inline_style.py --check          # 与基线比对，超基线则 exit 1
    python3 tools/check_inline_style.py --set-baseline   # 将当前计数写为新基线
    python3 tools/check_inline_style.py --diff           # 仅扫描 git 新增行（提交前用）

判定口径：
- 静态 style=" 计入基线（一次性布局声明为主，是收敛目标）。
- Vue 动态 :style= 绑定（多为主题/状态绑定）仅公示计数，不计入基线。
- 基线文件：tools/.inline_style_baseline（纯数字，入库）。

退出码：--check 下静态计数 > 基线时 exit 1；--diff 下新增行含 style=" 时 exit 1。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
BASELINE_FILE = Path(__file__).resolve().parent / ".inline_style_baseline"

STATIC_RE = re.compile(r'(?<!:)style="[^"]*"')
DYNAMIC_RE = re.compile(r':style="[^"]*"|:style=\'')


def count_static(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    return len(STATIC_RE.findall(text))


def scan_all():
    per_file = {}
    for f in sorted(SRC.rglob("*.vue")) + sorted(SRC.rglob("*.js")):
        n = count_static(f)
        if n:
            per_file[str(f.relative_to(ROOT))] = n
    dyn = 0
    for f in list(SRC.rglob("*.vue")) + list(SRC.rglob("*.js")):
        try:
            dyn += len(DYNAMIC_RE.findall(f.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return per_file, dyn


def read_baseline():
    try:
        return int(BASELINE_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def cmd_report(_args):
    per_file, dyn = scan_all()
    total = sum(per_file.values())
    print(f"静态 style=\" 共 {total} 处（{len(per_file)} 个文件），动态 :style= 共 {dyn} 处（仅公示）")
    print("-" * 70)
    for f, n in sorted(per_file.items(), key=lambda x: -x[1])[:20]:
        print(f"  {n:5d}  {f}")
    base = read_baseline()
    print("-" * 70)
    print(f"基线：{base if base is not None else '未设定（用 --set-baseline 写入）'}，当前：{total}")
    return 0


def cmd_check(_args):
    per_file, _ = scan_all()
    total = sum(per_file.values())
    base = read_baseline()
    if base is None:
        print("未设定基线，先执行 --set-baseline")
        return 2
    if total > base:
        print(f"FAIL: 静态内联样式 {total} 处，超出基线 {base}，新增代码请用 scoped CSS / 设计 Token")
        for f, n in sorted(per_file.items(), key=lambda x: -x[1])[:10]:
            print(f"  {n:5d}  {f}")
        return 1
    print(f"OK: 静态内联样式 {total} 处，未超基线 {base}")
    return 0


def cmd_set_baseline(_args):
    per_file, _ = scan_all()
    total = sum(per_file.values())
    BASELINE_FILE.write_text(str(total) + "\n")
    print(f"基线已写入 {total}（{BASELINE_FILE.name}）")
    return 0


def cmd_diff(_args):
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--", "frontend/src"],
            capture_output=True, text=True, cwd=ROOT,
        )
    except OSError as e:
        print(f"git 调用失败: {e}")
        return 2
    hits = [l for l in out.stdout.splitlines()
            if l.startswith("+") and not l.startswith("+++") and 'style="' in l
            and ':style' not in l]
    if hits:
        print(f"FAIL: 暂存区新增 {len(hits)} 行静态内联 style，请改用 scoped CSS / 设计 Token：")
        for l in hits[:20]:
            print(f"  {l.strip()[:160]}")
        return 1
    print("OK: 暂存区无新增静态内联 style")
    return 0


def main():
    ap = argparse.ArgumentParser(description="前端内联样式基线扫描")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="与基线比对")
    g.add_argument("--set-baseline", action="store_true", help="写入当前计数为基线")
    g.add_argument("--diff", action="store_true", help="仅扫描 git 暂存区新增行")
    args = ap.parse_args()
    if args.check:
        return cmd_check(args)
    if args.set_baseline:
        return cmd_set_baseline(args)
    if args.diff:
        return cmd_diff(args)
    return cmd_report(args)


if __name__ == "__main__":
    sys.exit(main())
