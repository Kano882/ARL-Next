#!/usr/bin/env python3
"""观察 ARL-Next 生产机的内存与 swap 分布，判断 mongod 换出是稳态还是 uptime 累积。

Usage:
    # 单次采样（默认 SSH 直连）
    python3 tools/mem_watch.py

    # 指定主机/端口/密钥
    python3 tools/mem_watch.py --host root@192.0.2.10 --port 2222 --key ~/.ssh/id_ed25519

    # 记录到文件，便于多日对比
    python3 tools/mem_watch.py --append memory_log.txt

    # 离线分析已有采样
    python3 tools/mem_watch.py --analyze memory_log.txt

背景：生产机（2 核 / 3.8G）曾观察到 670MB swap 占用，其中 447MB 属于 mongod。
重启 mongod 后 swap 降至 186MB、mongod VmSwap 归零，说明该占用是 uptime 累积
而非稳态。本工具用于持续验证这一判断，以决定是否需要下调 WiredTiger 缓存。

判据：
  - 若 VmSwap 在数天内重新爬升到 400MB+  → 属稳态，应下调 --wiredTigerCacheSizeGB
  - 若长期维持在低位                  → 属累积，重启（或等待其自然回收）即可
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime

# 需要观察的进程名特征（命令行匹配）
WATCHED_PROCESSES = {
    'mongod': 'mongod --wiredTiger',
    'celery': 'celery',
    'gunicorn': 'gunicorn',
}

REMOTE_SCRIPT = r'''
echo "###UPTIME### $(uptime -p 2>/dev/null | sed 's/up //')"
echo "###MEMINFO###"
grep -E "^(MemTotal|MemAvailable|SwapTotal|SwapFree):" /proc/meminfo
echo "###PROC###"
for p in $(ls /proc 2>/dev/null | grep -E "^[0-9]+$"); do
  [ -r "/proc/$p/cmdline" ] || continue
  cmd=$(tr "\0" " " < "/proc/$p/cmdline" 2>/dev/null)
  [ -z "$cmd" ] && continue
  rss=$(grep -m1 "^VmRSS:" "/proc/$p/status" 2>/dev/null | awk '{print $2}')
  swp=$(grep -m1 "^VmSwap:" "/proc/$p/status" 2>/dev/null | awk '{print $2}')
  echo "PROC|${rss:-0}|${swp:-0}|$cmd"
done
'''


def run_remote(host, port, key, timeout=25):
    """采集远端原始输出。失败返回 None。"""
    ssh_cmd = [
        'ssh', '-i', key, '-p', str(port),
        '-o', 'StrictHostKeyChecking=no',
        '-o', f'ConnectTimeout={timeout}',
        host, 'bash -s',
    ]
    try:
        proc = subprocess.run(
            ssh_cmd, input=REMOTE_SCRIPT, capture_output=True,
            text=True, timeout=timeout + 15,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f'采集失败：{exc}', file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f'SSH 返回非零：{proc.stderr.strip()[:300]}', file=sys.stderr)
        return None
    return proc.stdout


def parse(raw):
    """把远端输出解析为结构化 dict。纯函数，便于单测。"""
    out = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': '',
        'mem': {},
        'procs': [],
    }
    for line in (raw or '').splitlines():
        if line.startswith('###UPTIME###'):
            out['uptime'] = line.replace('###UPTIME###', '').strip()
        elif line.startswith('MemTotal:'):
            out['mem']['total_mb'] = int(line.split()[1]) // 1024
        elif line.startswith('MemAvailable:'):
            out['mem']['available_mb'] = int(line.split()[1]) // 1024
        elif line.startswith('SwapTotal:'):
            out['mem']['swap_total_mb'] = int(line.split()[1]) // 1024
        elif line.startswith('SwapFree:'):
            out['mem']['swap_free_mb'] = int(line.split()[1]) // 1024
        elif line.startswith('PROC|'):
            parts = line.split('|', 3)
            if len(parts) == 4:
                try:
                    out['procs'].append({
                        'rss_mb': int(parts[1]) // 1024,
                        'swap_mb': int(parts[2]) // 1024,
                        'cmd': parts[3][:120],
                    })
                except ValueError:
                    continue
    if 'swap_total_mb' in out['mem'] and 'swap_free_mb' in out['mem']:
        out['mem']['swap_used_mb'] = out['mem']['swap_total_mb'] - out['mem']['swap_free_mb']
    return out


def classify(cmd):
    """把进程命令行归类为受观察的服务名。"""
    for name, needle in WATCHED_PROCESSES.items():
        if needle in cmd:
            return name
    return None


def summarize(sample):
    """按服务聚合 RSS 与 swap。纯函数。"""
    agg = {}
    for proc in sample.get('procs', []):
        name = classify(proc['cmd'])
        if not name:
            continue
        slot = agg.setdefault(name, {'count': 0, 'rss_mb': 0, 'swap_mb': 0})
        slot['count'] += 1
        slot['rss_mb'] += proc['rss_mb']
        slot['swap_mb'] += proc['swap_mb']
    return agg


def render(sample):
    agg = summarize(sample)
    mem = sample['mem']
    lines = [
        f"时间 {sample['timestamp']}   uptime {sample['uptime'] or '未知'}",
        '',
        f"  内存   已用 {mem.get('total_mb', 0) - mem.get('available_mb', 0)} MB"
        f" / 总计 {mem.get('total_mb', 0)} MB"
        f"  （available {mem.get('available_mb', 0)} MB）",
        f"  Swap   已用 {mem.get('swap_used_mb', 0)} MB"
        f" / 总计 {mem.get('swap_total_mb', 0)} MB",
        '',
        f"  {'服务':<10} {'进程数':>6} {'RSS':>10} {'Swap':>10}",
    ]
    for name in sorted(agg):
        slot = agg[name]
        lines.append(
            f"  {name:<10} {slot['count']:>6} {slot['rss_mb']:>8} MB {slot['swap_mb']:>8} MB"
        )

    # 判据提示
    mongod_swap = agg.get('mongod', {}).get('swap_mb', 0)
    if mongod_swap >= 400:
        lines += ['', f"  ⚠️  mongod 换出 {mongod_swap}MB（≥400MB）：倾向稳态，"
                      "建议下调 --wiredTigerCacheSizeGB"]
    elif mongod_swap == 0 and mem.get('swap_used_mb', 0) > 100:
        lines += ['', f"  ℹ️  mongod 无换出，但整机 swap 仍占 {mem['swap_used_mb']}MB："
                      "换出主体可能是其他服务（如 rabbitmq）"]
    else:
        lines += ['', f"  ✅ mongod 换出 {mongod_swap}MB：暂属正常区间，继续观察"]
    return '\n'.join(lines)


def append_log(sample, path):
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(sample, ensure_ascii=False) + '\n')


def analyze(path):
    """对历史采样做趋势分析。"""
    samples = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not samples:
        print('日志为空或格式不符')
        return 1

    print(f"共 {len(samples)} 条采样\n")
    print(f"  {'时间':<20} {'uptime':<18} {'mongod RSS':>11} {'mongod Swap':>12} {'整机 Swap':>10}")
    for s in samples:
        agg = summarize(s)
        m = agg.get('mongod', {})
        print(f"  {s.get('timestamp',''):<20} {s.get('uptime','')[:16]:<18}"
              f" {m.get('rss_mb',0):>8} MB {m.get('swap_mb',0):>9} MB"
              f" {s['mem'].get('swap_used_mb',0):>7} MB")

    swaps = [summarize(s).get('mongod', {}).get('swap_mb', 0) for s in samples]
    print()
    if len(swaps) >= 2 and swaps[-1] > swaps[0] + 100:
        print(f"  趋势：mongod 换出由 {swaps[0]}MB 增至 {swaps[-1]}MB —— 指向稳态，建议下调缓存")
    elif max(swaps) >= 400:
        print(f"  趋势：峰值 {max(swaps)}MB ≥400MB —— 指向稳态，建议下调缓存")
    else:
        print(f"  趋势：峰值 {max(swaps)}MB，未达阈值 —— 保持观察")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description='观察 ARL-Next 生产机内存与 swap 分布（判断 mongod 换出是否为稳态）')
    ap.add_argument('--host', default='root@192.0.2.10', help='SSH 目标（占位符，请替换为实际主机）')
    ap.add_argument('--port', type=int, default=2222, help='SSH 端口')
    ap.add_argument('--key', default='~/.ssh/id_ed25519', help='SSH 私钥路径')
    ap.add_argument('--append', metavar='FILE', help='把本次采样追加到 JSONL 文件')
    ap.add_argument('--analyze', metavar='FILE', help='分析已有采样文件并退出')
    ap.add_argument('--json', action='store_true', help='以 JSON 输出本次采样')
    args = ap.parse_args()

    if args.analyze:
        return analyze(args.analyze)

    import os
    key = os.path.expanduser(args.key)
    raw = run_remote(args.host, args.port, key)
    if raw is None:
        return 1

    sample = parse(raw)
    if not sample['mem']:
        print('未解析到内存信息，请检查主机可达性与权限', file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(sample, ensure_ascii=False, indent=2))
    else:
        print(render(sample))

    if args.append:
        append_log(sample, args.append)
        print(f"\n已追加到 {args.append}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
